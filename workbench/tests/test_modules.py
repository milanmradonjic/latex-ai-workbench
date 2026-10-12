import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from test_support import isolate_environment
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap as boot
import core
import schema
import diagnostics
import guide
import research
import runtime as rt


class ModuleTests(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-modules-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return boot.main([*args, str(self.project)])

    def snapshot(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}

    def command(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), *args],
                                cwd=self.project, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def example(self):
        shutil.copytree(boot.PACKAGE / "examples/decay", self.project, dirs_exist_ok=True)
        self.assertEqual(self.cli("init"), 0)
        return schema.load_config(self.project)


    def records(self):
        return sorted((self.project / "results/runs").glob("*/record.json"))

    def test_core_install_without_tex_editor_or_research(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        self.assertFalse((self.project / ".latex-ai/latex.py").exists())
        self.assertFalse((self.project / ".latex-ai/research.py").exists())
        self.assertFalse((self.project / ".vscode").exists())
        self.assertFalse((self.project / ".github").exists())
        self.command("check")
        doctor = self.command("doctor").stdout
        self.assertNotIn("latexmk", doctor)
        self.assertEqual(schema.load_config(self.project)["modules"], {})
        before = self.snapshot()
        self.assertEqual(self.cli("upgrade"), 0)
        self.assertEqual(self.cli("audit"), 0)
        self.assertEqual(before, self.snapshot())

    def test_cli_options_before_and_after_project_are_equivalent(self):
        before = self.snapshot()
        reports = []
        for argv in (["init", "--profile", "notebook", str(self.project), "--dry-run", "--json"],
                     ["init", str(self.project), "--profile", "notebook", "--dry-run", "--json"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(boot.main(argv), 0)
            reports.append(json.loads(output.getvalue()))
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(before, self.snapshot())

    def test_disabled_latex_command_fails_before_tool_execution(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        self.assertIn("Module is disabled: latex", self.command("build", expected=1).stderr)
        self.assertIn("Module is disabled: numerics", self.command("run", "--task", "any", expected=1).stderr)

    def test_notebook_save_validation_has_no_compiler(self):
        self.assertEqual(self.cli("init", "--profile", "notebook"), 0)
        notes = self.project / "notes/session-state.md"
        notes.write_text(notes.read_text() + "\nA question about physics.\n")
        self.command("validate", "--files", "notes/session-state.md")
        before = self.snapshot()
        self.assertEqual(self.cli("upgrade"), 0)
        self.assertEqual(self.cli("audit"), 0)
        self.assertEqual(before, self.snapshot())

    def test_missing_history_never_introduces_disabled_modules(self):
        self.assertEqual(self.cli("init", "--profile", "notebook"), 0)
        plan = json.loads(self.command("plan", "--json").stdout)
        self.assertTrue(plan["fallback"])
        self.assertFalse(plan["manuscript"])
        self.assertFalse(plan["portability"])
        self.command("validate")

    def test_core_adapts_existing_make_without_build_target(self):
        make = "local:\n\t@echo local\n"
        (self.project / "GNUmakefile").write_text(make)
        self.assertEqual(self.cli("init", "--profile", "notebook"), 0)
        self.assertTrue((self.project / "GNUmakefile").read_text().startswith(make))
        self.assertFalse((self.project / "Makefile").exists())
        result = subprocess.run(["make", "check"], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_profile_does_not_override_installed_choices(self):
        self.assertEqual(self.cli("init", "--profile", "notebook"), 0)
        before = self.snapshot()
        self.assertEqual(self.cli("upgrade", "--profile", "numerical"), 2)
        self.assertEqual(before, self.snapshot())

    def test_explicit_disable_preserves_research_and_does_not_reenable(self):
        self.example()
        self.command("run", "--task", "decay")
        self.command("figure", "--task", "decay")
        before = {p: data for p, data in self.snapshot().items() if p.startswith(("results/", "figures/", "notes/"))}
        self.assertEqual(self.cli("configure", "--disable", "numerics", "--disable", "figures", "--disable", "freshness"), 0)
        self.assertEqual(before, {p: data for p, data in self.snapshot().items() if p in before})
        self.assertEqual(self.cli("upgrade"), 0)
        self.assertFalse(core.has_module(schema.load_config(self.project), "numerics"))
        self.assertIn("Module is disabled", self.command("run", "--task", "decay", expected=1).stderr)
        self.command("check")
        self.assertEqual(self.cli("configure", "--enable", "numerics"), 0)
        self.assertIn("decay", research.tasks(self.project, schema.load_config(self.project), "numerics"))

    def test_module_dependency_error_never_writes(self):
        self.assertEqual(self.cli("init", "--profile", "numerical"), 0)
        before = self.snapshot()
        self.assertEqual(self.cli("configure", "--disable", "provenance"), 2)
        self.assertEqual(before, self.snapshot())

    def test_notes_paths_are_configurable_and_existing_notes_preserved(self):
        config = {'schema_version': 3, 'modules': {'notes': {'path': 'research/journal'}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        path = self.project / "research/journal/index.md"
        path.parent.mkdir(parents=True)
        path.write_text("My own notes.\n")
        self.assertEqual(self.cli("init"), 0)
        self.assertEqual(path.read_text(), "My own notes.\n")
        self.command("check")
        self.assertEqual(self.cli("configure", "--disable", "notes"), 0)
        self.assertEqual(self.cli("configure", "--enable", "notes"), 0)
        self.assertEqual(core.module_config(schema.load_config(self.project), "notes")["path"], "research/journal")
        self.assertFalse((self.project / "notes").exists())

    def test_unknown_module_and_reserved_paths_are_rejected(self):
        for modules in ({"magic": {}}, {"numerics": {"manifest": "AGENTS.md"}}, {"notes": {"path": ".git"}}, {"notes": {"path": "../outside"}}, {"numerics": {"manifest": "tasks.json"}, "figures": {"manifest": "tasks.json"}}):
            with self.subTest(modules=modules), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, {'schema_version': 3, 'modules': modules})

    def test_independent_bibliography_without_tex(self):
        (self.project / "refs.bib").write_text("@misc{synthetic,title={Synthetic test fixture}}\n")
        config = {'schema_version': 3, 'modules': {'bibliography': {'files': ['refs.bib']}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.assertEqual(self.cli("init"), 0)
        self.command("bib-check")
        self.command("check")
        plan = json.loads(self.command("plan", "--files", "refs.bib", "--json").stdout)
        self.assertTrue(plan["bibliography"])
        self.assertFalse(plan["manuscript"])

    def test_no_tex_ci_has_no_container_or_pdf_upload(self):
        self.assertEqual(self.cli("init", "--profile", "notebook", "--ci", "--editor"), 0)
        workflow = (self.project / ".github/workflows/latex-ai.yml").read_text()
        self.assertNotIn("texlive-action", workflow)
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("latex-workshop", (self.project / ".vscode/tasks.json").read_text())


    def test_disable_latex_stops_managed_editor_autobuild_and_ci_tex(self):
        (self.project / "paper.tex").write_text("\\documentclass{article}\n\\begin{document}Test.\\end{document}\n")
        self.assertEqual(self.cli("init"), 0)
        self.assertEqual(self.cli("configure", "--disable", "latex"), 0)
        self.assertEqual(json.loads((self.project / ".vscode/settings.json").read_text())["latex-workshop.latex.autoBuild.run"], "never")
        self.assertNotIn("texlive-action", (self.project / ".github/workflows/latex-ai.yml").read_text())
        self.command("check")
        self.assertTrue((self.project / "paper.tex").exists())
        self.assertIn("*.aux", (self.project / ".gitignore").read_text())
        self.assertEqual(self.cli("configure", "--enable", "latex"), 0)
        restored = schema.load_config(self.project)
        self.assertTrue(core.integrations(restored)["ci"]["pdf_artifact"])
        self.assertEqual(schema.document_settings(restored)["root"], "paper.tex")

    def test_explicit_pipeline_records_recoverable_inputs_outputs_and_environment(self):
        self.example()
        self.command("run", "--task", "decay")
        self.command("figure", "--task", "decay")
        self.command("check")
        self.command("freshness")
        records = self.records()
        self.assertEqual(len(records), 2)
        for path in records:
            record = json.loads(path.read_text())
            self.assertEqual(record["status"], "success")
            self.assertEqual(record["environment"]["exit_status"], 0)
            for name, digest in record["inputs"].items():
                self.assertEqual(research.sha((path.parent / "inputs" / name).read_bytes()), digest)
            for name, digest in record["outputs"].items():
                self.assertEqual(research.sha((path.parent / "outputs" / name).read_bytes()), digest)

    def test_unicode_task_metadata_is_recorded_as_utf8(self):
        self.example()
        path = self.project / "experiments.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"]["description"] = "Synthetic γ decay"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.command("run", "--task", "decay")
        record = self.records()[0]
        self.assertIn("γ".encode("utf-8"), record.read_bytes())
        self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["definition"]["description"], "Synthetic γ decay")

    def test_input_change_marks_experiment_and_downstream_figure_stale_without_writes(self):
        self.example()
        self.command("run", "--task", "decay")
        self.command("figure", "--task", "decay")
        path = self.project / "parameters.json"
        config = json.loads(path.read_text())
        config["gamma"] = 2.0
        path.write_text(json.dumps(config))
        before = self.snapshot()
        report = json.loads(self.command("freshness", expected=1).stdout)
        self.assertTrue(all(item["status"] == "stale" for item in report))
        self.assertIn("upstream task is stale", " ".join(report[1]["reasons"]))
        self.assertEqual(before, self.snapshot())
        self.command("validate", "--files", "parameters.json", expected=1)
        self.assertEqual(len(self.records()), 2)
        self.command("run", "--task", "decay")
        self.command("figure", "--task", "decay")
        self.command("freshness")

    def test_output_tampering_is_stale(self):
        self.example()
        self.command("run", "--task", "decay")
        (self.project / "results/decay.json").write_text("{}\n")
        report = json.loads(self.command("freshness", expected=1).stdout)
        self.assertIn("output content changed or is missing", report[0]["reasons"])

    def test_expensive_check_is_skipped_until_explicit_request(self):
        config = self.example()
        path = self.project / "experiments.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"]["checks"].append({"cost": "expensive", "command": [sys.executable, "-c", "raise RuntimeError('expensive fixture')"]})
        path.write_text(json.dumps(data))
        self.command("run", "--task", "decay")
        record = json.loads(self.records()[0].read_text())
        self.assertEqual(record["checks"][-1]["status"], "skipped")
        self.command("run", "--task", "decay", "--expensive-checks", expected=1)
        report = research.freshness(self.project, config)
        self.assertIn("latest run did not succeed", report[0]["reasons"])

    def test_failed_command_records_failure_and_retains_prior_outputs(self):
        self.example()
        self.command("run", "--task", "decay")
        before = (self.project / "results/decay.json").read_bytes()
        path = self.project / "scripts/decay.py"
        path.write_text("raise RuntimeError('failure fixture')\n")
        self.command("run", "--task", "decay", expected=1)
        self.assertEqual(before, (self.project / "results/decay.json").read_bytes())
        latest = max((json.loads(p.read_text()) for p in self.records()), key=lambda r: r["started"])
        self.assertEqual(latest["status"], "failed")
        self.assertIn("Command failed", latest["error"])

    def test_exit_zero_without_rewriting_an_existing_output_fails_visibly(self):
        config = self.example()
        self.command("run", "--task", "decay")
        output = self.project / "results/decay.json"
        before = output.read_bytes()
        parameters = self.project / "parameters.json"
        data = json.loads(parameters.read_text())
        data["gamma"] = 2.0
        parameters.write_text(json.dumps(data))
        script = self.project / "scripts/decay.py"
        script.write_text(script.read_text().replace('Path("results/decay.json")', 'Path("results/elsewhere.json")'))
        result = self.command("run", "--task", "decay", expected=1)
        self.assertIn("without rewriting declared outputs: results/decay.json", result.stderr)
        self.assertEqual(before, output.read_bytes())
        latest = max((json.loads(p.read_text()) for p in self.records()), key=lambda r: r["started"])
        self.assertEqual(latest["status"], "failed")
        self.assertIn("without rewriting", latest["error"])
        self.assertIn("latest run did not succeed", research.freshness(self.project, config)[0]["reasons"])
        self.command("check", expected=1)

    def test_rerun_rewriting_identical_bytes_is_still_a_regeneration(self):
        self.example()
        self.command("run", "--task", "decay")
        output = self.project / "results/decay.json"
        first = output.read_bytes()
        self.command("run", "--task", "decay")
        self.assertEqual(first, output.read_bytes())
        self.assertEqual([json.loads(p.read_text())["status"] for p in self.records()], ["success", "success"])

    def test_skipping_tool_is_accepted_only_while_the_last_record_vouches_for_its_output(self):
        config = self.example()
        (self.project / "scripts/lazy.py").write_text(
            "from pathlib import Path\nout = Path('results/lazy.json')\nout.parent.mkdir(exist_ok=True)\n"
            "if not out.exists():  # a build tool that skips existing targets\n    out.write_text(Path('parameters.json').read_text())\n")
        path = self.project / "experiments.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"].update(command=[sys.executable, "scripts/lazy.py"], inputs=["parameters.json"], outputs=["results/lazy.json"], checks=[])
        path.write_text(json.dumps(data))
        output = self.project / "results/lazy.json"
        self.command("run", "--task", "decay")
        self.command("run", "--task", "decay")  # nothing changed: skipping is correct
        def newest():
            return max((json.loads(p.read_text()) for p in self.records()), key=lambda r: r["started"])
        self.assertEqual((newest()["status"], newest()["unchanged_outputs"]), ("success", ["results/lazy.json"]))
        self.assertEqual(research.freshness(self.project, config)[0]["status"], "current")
        output.write_text("tampered\n")  # the recorded result no longer matches
        self.assertIn("without rewriting declared outputs", self.command("run", "--task", "decay", expected=1).stderr)
        output.unlink()
        self.command("run", "--task", "decay")
        parameters = self.project / "parameters.json"
        parameters.write_text(parameters.read_text().replace("1.5", "2.5"))  # input changed: skipping is now stale
        self.assertIn("without rewriting declared outputs", self.command("run", "--task", "decay", expected=1).stderr)
        self.assertEqual(newest()["status"], "failed")

    def test_directly_executed_project_script_is_an_input_but_interpreters_are_not(self):
        self.example()
        script = self.project / "scripts/run.sh"
        script.write_text("#!/bin/sh\npython3 scripts/decay.py\n")
        script.chmod(0o755)
        (self.project / "tools").mkdir()
        (self.project / "tools/binary").write_bytes(b"\x7fELF not a script")
        (self.project / "tools/link").symlink_to(sys.executable)
        base = json.loads((self.project / "experiments.json").read_text())["tasks"]["decay"]
        for command, expected in ((["scripts/run.sh"], True), (["./scripts/run.sh"], True), (["tools/binary"], False), (["tools/link"], False), (["python3", "scripts/decay.py"], False)):
            with self.subTest(command=command):
                inputs = research.task_inputs(self.project, {**base, "command": command})
                self.assertEqual("scripts/run.sh" in inputs, expected)
                self.assertNotIn("tools/binary", inputs)
                self.assertNotIn("tools/link", inputs)
        path = self.project / "experiments.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"]["command"] = ["scripts/run.sh"]
        path.write_text(json.dumps(data))
        self.command("run", "--task", "decay")
        script.write_text("#!/bin/sh\n# launcher behaviour changed\npython3 scripts/decay.py\n")
        reasons = json.loads(self.command("freshness", expected=1).stdout)[0]["reasons"]
        self.assertIn("declared input content changed or is missing", reasons)

    def test_deleted_claim_evidence_selects_the_claims_check(self):
        self.example()
        (self.project / "analysis").mkdir()
        (self.project / "analysis/evidence.md").write_text("Evidence.\n")
        (self.project / "claims.json").write_text(json.dumps({"schema_version": 1, "claims": [
            {"id": "c1", "text": "Synthetic statement", "status": "supported", "evidence": ["analysis/evidence.md"]}]}))
        self.command("claims-check")
        (self.project / "analysis/evidence.md").unlink()
        plan = json.loads(self.command("plan", "--files", "analysis/evidence.md", "--json").stdout)
        self.assertIn("claims", plan["research_modules"])
        self.assertIn("Missing claim evidence", self.command("validate", "--files", "analysis/evidence.md", expected=1).stderr)
        unrelated = json.loads(self.command("plan", "--files", "analysis/other.md", "--json").stdout)
        self.assertNotIn("claims", unrelated["research_modules"])

    def emit_task(self, script, extra=None):
        """Replace the example's numerics task by one that writes results/emit.txt from in.txt."""
        (self.project / "in.txt").write_text("one\n")
        (self.project / "scripts/emit.py").write_text(script)
        path = self.project / "experiments.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"].update(command=[sys.executable, "scripts/emit.py"], inputs=["in.txt"], outputs=["results/emit.txt"], checks=[], **(extra or {}))
        path.write_text(json.dumps(data))

    def newest(self):
        return max((json.loads(p.read_text()) for p in self.records()), key=lambda r: r["started"])

    def test_touch_only_command_cannot_pass_the_examples_attribution_check(self):
        config = self.example()
        self.command("run", "--task", "decay")
        parameters = self.project / "parameters.json"
        data = json.loads(parameters.read_text())
        data["gamma"] = 2.0
        parameters.write_text(json.dumps(data))
        path = self.project / "experiments.json"
        manifest = json.loads(path.read_text())
        manifest["tasks"]["decay"]["command"] = [sys.executable, "-c", "from pathlib import Path; Path('results/decay.json').touch()"]
        path.write_text(json.dumps(manifest))
        failure = self.command("run", "--task", "decay", expected=1)  # exit 0 and a fresh mtime, but the content is the old result
        self.assertIn("was not produced from the current parameters", failure.stdout + failure.stderr)
        self.assertEqual(self.newest()["status"], "failed")
        self.assertIn("latest run did not succeed", research.freshness(self.project, config)[0]["reasons"])

    def test_same_bytes_after_an_input_change_are_flagged_not_failed(self):
        self.example()
        self.emit_task("from pathlib import Path\nPath('results').mkdir(exist_ok=True)\nPath('results/emit.txt').write_text('fixed\\n')\n")
        first = self.command("run", "--task", "decay")
        self.assertNotIn("WARNING", first.stdout)
        self.assertEqual(self.newest()["warnings"], [])
        self.command("run", "--task", "decay")  # nothing changed and identical bytes are rewritten: no warning
        self.assertEqual(self.newest()["warnings"], [])
        (self.project / "in.txt").write_text("two\n")
        changed = self.command("run", "--task", "decay")  # input changed, output has the previous bytes
        self.assertIn("WARNING: results/emit.txt has the same bytes as the previous successful run", changed.stdout)
        self.assertEqual((self.newest()["status"], len(self.newest()["warnings"])), ("success", 1))
        (self.project / "scripts/emit.py").write_text("from pathlib import Path\nPath('results/emit.txt').write_text(Path('in.txt').read_text())\n")
        derived = self.command("run", "--task", "decay")  # bytes now follow the input: nothing to flag
        self.assertNotIn("WARNING", derived.stdout)
        self.assertEqual(self.newest()["warnings"], [])

    def test_a_touch_without_a_content_check_is_accepted_but_visibly_flagged(self):
        # The documented limit: file identity cannot show attribution, so a project without an
        # output-versus-input check gets a success record, a warning and a current report.
        config = self.example()
        self.emit_task("from pathlib import Path\nPath('results').mkdir(exist_ok=True)\nPath('results/emit.txt').write_text(Path('in.txt').read_text())\n")
        self.command("run", "--task", "decay")
        (self.project / "in.txt").write_text("two\n")
        (self.project / "scripts/emit.py").write_text("from pathlib import Path\nPath('results/emit.txt').touch()\n")
        touched = self.command("run", "--task", "decay")
        self.assertEqual((self.project / "results/emit.txt").read_text(), "one\n")
        self.assertIn("WARNING: results/emit.txt has the same bytes", touched.stdout)
        self.assertEqual(self.newest()["status"], "success")
        self.assertEqual(research.freshness(self.project, config)[0]["status"], "current")

    def test_concurrent_runs_of_one_task_are_refused_instead_of_misjudged(self):
        config = self.example()
        self.emit_task("import time\nfrom pathlib import Path\nPath('started').touch()\ntime.sleep(2)\nPath('results').mkdir(exist_ok=True)\n"
                       "out = Path('results/emit.txt')\nif not out.exists():\n    out.write_text(Path('in.txt').read_text())\n")
        self.command("run", "--task", "decay")
        marker = self.project / "started"
        marker.unlink()

        def start():
            return subprocess.Popen([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), "run", "--task", "decay"], cwd=self.project,
                                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        first = start()
        deadline = time.monotonic() + 30
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(marker.exists(), "first run never started")
        second = start()  # the first still holds the task for about two seconds
        refused = second.communicate(timeout=30)
        accepted = first.communicate(timeout=30)
        self.assertEqual((first.returncode, second.returncode), (0, 1), accepted + refused)
        self.assertIn("Another run of numerics/decay is in progress", refused[1])
        self.assertEqual(research.freshness(self.project, config)[0]["status"], "current")  # the refusal left no half-written record
        marker.unlink()
        self.command("run", "--task", "decay")  # the lock is released when the first run ends

    def test_interrupted_run_is_recorded_as_interrupted_and_stays_stale(self):
        config = self.example()
        path = self.project / "experiments.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"].update(command=[sys.executable, "-c", "import time; open('started', 'w').close(); time.sleep(60)"],
                                      inputs=["parameters.json"], outputs=["results/never.json"], checks=[])
        path.write_text(json.dumps(data))
        marker = self.project / "started"
        for name in ("SIGINT", "SIGTERM"):
            with self.subTest(signal=name):
                marker.unlink(missing_ok=True)
                process = subprocess.Popen([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), "run", "--task", "decay"],
                                           cwd=self.project, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    deadline = time.monotonic() + 30
                    while not marker.exists() and time.monotonic() < deadline:
                        time.sleep(0.05)
                    self.assertTrue(marker.exists(), "task command never started")
                    process.send_signal(getattr(signal, name))
                    process.communicate(timeout=30)
                finally:
                    process.kill()
                self.assertNotEqual(process.returncode, 0)
                latest = max((json.loads(p.read_text()) for p in self.records()), key=lambda r: r["started"])
                self.assertEqual(latest["status"], "interrupted")
                self.assertIn("finished", latest)
                self.assertIn("Interrupted", latest["error"])
                self.assertIn("latest run did not succeed", research.freshness(self.project, config)[0]["reasons"])
        self.assertEqual(len(self.records()), 2)

    def run_main(self, *arguments):
        errors = io.StringIO()
        with patch.object(sys, "argv", ["workbench", *arguments, "--project", str(self.project)]), contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            return rt.main(), errors.getvalue()

    def test_internal_faults_are_labelled_apart_from_ordinary_errors_and_never_written_into_the_project(self):
        self.assertEqual(self.cli("init", "--profile", "notebook"), 0)
        self.addCleanup(shutil.rmtree, diagnostics.fault_dir(self.project), True)
        before = self.snapshot()
        with patch.object(rt, "full_check", side_effect=AttributeError("boom")):
            status, errors = self.run_main("check")
        self.assertEqual(status, 70)
        self.assertIn("INTERNAL ERROR: AttributeError: boom", errors)
        self.assertIn("make latex-ai-issue", errors)
        self.assertEqual(before, self.snapshot())  # the traceback lives in the OS temp directory
        self.assertEqual(diagnostics.recent_faults(self.project)[-1]["error_type"], "AttributeError")
        for expected in (rt.WorkbenchError("bad input"), OSError("disk"), ValueError("json"), SyntaxError("python")):
            with self.subTest(expected=type(expected).__name__), patch.object(rt, "full_check", side_effect=expected):
                status, errors = self.run_main("check")
                self.assertEqual(status, 1)
                self.assertTrue(errors.startswith("ERROR: "), errors)
                self.assertNotIn("INTERNAL", errors)
        for unexpected in (KeyError("k"), TypeError("t"), IndexError("i"), RecursionError("r")):
            with self.subTest(unexpected=type(unexpected).__name__), patch.object(rt, "full_check", side_effect=unexpected):
                self.assertEqual(self.run_main("check")[0], 70)

    def test_malformed_project_data_is_reported_never_crashes(self):
        # Hand-edited manifests, claims and run records must produce a diagnostic, not an exception
        # that would be labelled a workbench defect. A sweep over every key with seven bad values.
        config = self.example()
        self.command("run", "--task", "decay")
        record = next(iter(self.records()))
        documents = {path: path.read_text() for path in (self.project / "experiments.json", self.project / "claims.json", record)}
        (self.project / "claims.json").write_text(json.dumps({"schema_version": 1, "claims": [{"id": "c", "text": "t", "status": "proposed", "evidence": ["parameters.json"], "notes": "n"}]}))
        documents[self.project / "claims.json"] = (self.project / "claims.json").read_text()
        replacements = (None, 0, "x", [], {}, True, "DELETE")

        def keys(node, prefix=()):
            yield prefix
            if isinstance(node, dict):
                for key, value in node.items():
                    yield from keys(value, prefix + (key,))
            elif isinstance(node, list):
                for index, value in enumerate(node[:2]):
                    yield from keys(value, prefix + (index,))
        problems = []
        for path, original in documents.items():
            document = json.loads(original)
            for key_path in keys(document):
                for replacement in replacements:
                    mutated = json.loads(original)
                    if not key_path:
                        mutated = None if replacement == "DELETE" else replacement
                    else:
                        parent = mutated
                        for step in key_path[:-1]:
                            parent = parent[step]
                        if replacement == "DELETE":
                            parent.pop(key_path[-1])
                        else:
                            parent[key_path[-1]] = replacement
                    path.write_text(json.dumps(mutated))
                    try:
                        for module in ("numerics", "figures"):
                            research.tasks(self.project, config, module)
                        with contextlib.redirect_stdout(io.StringIO()):
                            research.check_claims(self.project, config)
                        research.freshness(self.project, config)
                    except (core.WorkbenchError, OSError, ValueError, SyntaxError):
                        pass  # a diagnostic: exactly the classes the runtime reports as ERROR
                    except Exception as error:
                        problems.append((path.name, key_path, replacement, f"{type(error).__name__}: {error}"))
            path.write_text(original)
        self.assertEqual(problems, [])
        self.assertEqual(rt.EXPECTED, (core.WorkbenchError, OSError, ValueError, SyntaxError))  # and the runtime agrees

    def test_issue_report_collects_local_evidence_and_nothing_else(self):
        self.example()
        self.command("run", "--task", "decay")
        before = set(self.snapshot())
        hidden = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "LATEX_AI_CANARY": "secret-value-should-not-appear"}
        done = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), "issue", "--note", "observed X; expected Y", "--command", "make check"],
                              cwd=self.project, env=hidden, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        added = set(self.snapshot()) - before
        self.assertEqual(len(added), 1)  # exactly one new file, in the ignored artifacts directory
        name = next(iter(added))
        self.assertTrue(name.startswith(".latex-ai/artifacts/issues/report-"), name)
        text = (self.project / name).read_text()
        self.assertNotIn("secret-value-should-not-appear", text)  # no environment variables
        report = json.loads(text)
        self.assertEqual((report["observed_and_expected"], report["command"]), ("observed X; expected Y", "make check"))
        self.assertEqual(report["workbench_version"], core.VERSION)
        self.assertTrue(report["installation"]["version_matches"])
        self.assertTrue(all(status in ("unmodified", "managed block", "project-owned") for status in report["installation"]["files"].values()), report["installation"]["files"])
        self.assertEqual(report["installation"]["differing"], [])
        self.assertEqual(report["runs"]["numerics/decay"]["status"], "success")
        self.assertIn("python", report["tools"])
        self.assertEqual(report["configuration"]["schema_version"], 3)
        # A locally edited managed file is exactly what explains an upgrade conflict, so the report names it.
        with (self.project / ".latex-ai/research.py").open("a") as stream:
            stream.write("\n# local tweak\n")
        self.command("issue")
        newest = json.loads(max((self.project / ".latex-ai/artifacts/issues").glob("report-*.json")).read_text())
        self.assertEqual(newest["installation"]["files"][".latex-ai/research.py"], "modified locally")
        self.assertEqual(newest["installation"]["differing"], [".latex-ai/research.py"])
        # It must work precisely when the configuration is broken.
        (self.project / core.CONFIG).write_text("{not json")
        self.command("issue")
        broken = json.loads(max((self.project / ".latex-ai/artifacts/issues").glob("report-*.json")).read_text())
        self.assertIsNone(broken["configuration"])
        self.assertIn(".latex-ai.json is not valid JSON", broken["configuration_error"])

    def latest_report(self):
        return json.loads(max((self.project / ".latex-ai/artifacts/issues").glob("report-*.json")).read_text())

    def test_issue_still_reports_when_the_defect_is_in_shared_code(self):
        # A defect that makes the plan uncomputable must not stop the report that is meant to capture it.
        self.example()
        with (self.project / ".latex-ai/task_graph.py").open("a") as stream:
            stream.write("\ndef task_inputs(project, task, **kwargs):\n    raise KeyError('checks')\n")
        crash = self.command("freshness", expected=rt.INTERNAL_FAULT)
        self.assertIn("INTERNAL ERROR: KeyError: 'checks'", crash.stderr)
        done = self.command("issue", "--files", "parameters.json", "--note", "freshness crashed")
        self.assertIn("Issue report written", done.stdout)
        report = self.latest_report()
        self.assertIn("KeyError", report["plan"]["unavailable"])
        self.assertEqual(report["observed_and_expected"], "freshness crashed")
        self.assertEqual(report["configuration"]["schema_version"], 3)  # the rest of the evidence is intact
        self.assertEqual(len(report["recent_internal_faults"]), 1)  # and names the fault just seen

    def test_issue_report_survives_any_one_section_failing(self):
        self.example()
        sections = {"installation": "installation", "tool_versions": "tools", "git_state": "git",
                    "recent_faults": "recent_internal_faults", "runs": "runs"}
        args = argparse.Namespace(files=None, base=None, note="", failed_command="")
        for function, key in sections.items():
            with self.subTest(section=function), patch.object(diagnostics, function, side_effect=RuntimeError("boom")), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(rt.issue(self.project, args), 0)
            self.assertIn("RuntimeError: boom", json.dumps(self.latest_report()[key]))
            self.assertEqual(self.latest_report()["configuration"]["schema_version"], 3)
        with self.subTest(section="configuration"), patch.object(rt, "load_config", side_effect=TypeError("odd")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rt.issue(self.project, args), 0)
        self.assertEqual(self.latest_report()["configuration_error"], "TypeError: odd")

    def test_issue_make_target_takes_free_text_through_the_environment(self):
        self.assertEqual(self.cli("init", "--profile", "notebook"), 0)
        hostile = 'observed "quoted"; touch INJECTED; echo "'
        done = subprocess.run(["make", "issue", f"ISSUE_NOTE={hostile}", "ISSUE_COMMAND=make check"], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse((self.project / "INJECTED").exists())
        report = json.loads(next((self.project / ".latex-ai/artifacts/issues").glob("report-*.json")).read_text())
        self.assertEqual((report["observed_and_expected"], report["command"]), (hostile, "make check"))

    def test_advertised_report_command_works_where_the_project_has_its_own_issue_target(self):
        # The installer keeps a project's own `issue` recipe and installs only `latex-ai-issue`, so
        # whatever the guidance tells an agent to run must be the name that always reaches the report.
        (self.project / "Makefile").write_text("PYTHON ?= python3\nissue:\n\t@touch PROJECT_ISSUE_RAN\n")
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        template = (boot.PACKAGE / "templates/AGENTS.md").read_text()
        advertised = re.search(r"`make ([\w-]+) ISSUE_NOTE=", template).group(1)
        done = subprocess.run(["make", advertised, "ISSUE_NOTE=observed X; expected Y"], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse((self.project / "PROJECT_ISSUE_RAN").exists(), "the advertised command ran the project's own recipe")
        reports = list((self.project / ".latex-ai/artifacts/issues").glob("report-*.json"))
        self.assertEqual(len(reports), 1)
        self.assertEqual(json.loads(reports[0].read_text())["observed_and_expected"], "observed X; expected Y")
        subprocess.run(["make", "issue"], cwd=self.project, capture_output=True, text=True, check=True)
        self.assertTrue((self.project / "PROJECT_ISSUE_RAN").exists())  # and the project's target is still its own
        # Every place that tells a reader what to run names that same command, never the bare short alias.
        self.addCleanup(shutil.rmtree, diagnostics.fault_dir(self.project), True)
        with patch.object(rt, "full_check", side_effect=AttributeError("boom")):
            status, errors = self.run_main("check")
        self.assertEqual(status, 70)
        guidance = {"runtime message": errors, "full policy": template, "short policy": boot.integration_text("AGENTS.md", ""),
                    "skill": (boot.PACKAGE / "skills/latex-ai-workbench/SKILL.md").read_text()}
        for name, text in guidance.items():
            with self.subTest(guidance=name):
                self.assertIn(f"make {advertised}", text)
                self.assertNotRegex(text, r"make issue\b")
        self.assertIn(f"make {advertised}", (boot.PACKAGE / "docs/agents.md").read_text())

    def make_result(self, *arguments):
        # Run as the user would in a fresh shell: not as a child of the package's own `make test` (which sets
        # MAKEFLAGS and makes Make announce directories), and without the caller's TASK or the comparison
        # revision hosted CI exports for the outer repository (LATEX_AI_BASE names a commit these fixtures lack).
        env = {name: value for name, value in os.environ.items() if name not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "TASK", "LATEX_AI_BASE"}}
        return subprocess.run(["make", "-s", "--no-print-directory", *arguments], cwd=self.project, capture_output=True, text=True, env=env)

    def make_output(self, *arguments, expected=0):
        done = self.make_result(*arguments)
        self.assertEqual(done.returncode, expected, done.stdout + done.stderr)
        return done.stdout

    def test_help_lists_what_this_project_has_and_only_that(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        core_help = self.make_output("help")
        for line in ("make check", "make validate", "make status", "make doctor", "make help", "make issue"):
            self.assertIn(line, core_help)
        for absent in ("make run", "make figure", "make freshness", "make md-check", "make build"):
            self.assertNotIn(absent, core_help)
        self.assertIn("Not enabled here", core_help)
        self.assertIn("latex-ai-init configure . --enable", core_help)
        shutil.rmtree(self.project)
        self.project.mkdir()
        self.example()
        help_text = self.make_output("help")
        for line in ("make run TASK=", "make figure TASK=", "make freshness", "declared: decay"):
            self.assertIn(line, help_text)

    def test_help_names_the_command_that_reaches_the_workbench_when_the_project_has_its_own(self):
        (self.project / "Makefile").write_text("PYTHON ?= python3\nhelp:\n\t@echo PROJECT_HELP\nissue:\n\t@echo PROJECT_ISSUE\n")
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        self.assertEqual(self.make_output("help").strip(), "PROJECT_HELP")  # the project's target is kept
        text = self.make_output("latex-ai-help")
        self.assertIn("make latex-ai-help", text)
        self.assertIn("make latex-ai-issue", text)
        self.assertNotIn("make issue", text)
        self.assertIn("make status", text)  # an alias nothing else uses stays short

    def test_help_survives_a_broken_configuration(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        (self.project / core.CONFIG).write_text("{not json")
        text = self.make_output("help")
        self.assertIn("Configuration problem", text)
        self.assertIn("make check", text)

    def test_every_installed_make_target_is_described_by_help(self):
        for profile in ("core", "notebook", "numerical", "research-paper", "writing"):
            with self.subTest(profile=profile):
                shutil.rmtree(self.project)
                self.project.mkdir()
                (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n")
                self.assertEqual(self.cli("init", "--profile", profile), 0)
                text = (self.project / "Makefile").read_text()
                targets = set(re.findall(r"^([A-Za-z][\w-]*)\s*:(?!=)", text, re.M))
                described = {name for command in guide.COMMANDS for name in (command.short, command.reserved) if name}
                self.assertEqual(sorted(targets - described - guide.UNLISTED), [])

    def test_status_reports_where_the_project_stands_and_what_to_do_next(self):
        self.example()
        before = self.snapshot()
        text = self.make_output("status")
        self.assertEqual(before, self.snapshot())  # read-only
        self.assertIn(f"{core.VERSION} installed, matches its manifest", text)
        self.assertIn("numerics", text)
        self.assertIn("stale", text)  # nothing has been run yet
        self.assertIn("make run TASK=decay", text)
        self.command("run", "--task", "decay")
        self.command("figure", "--task", "decay")
        text = self.make_output("status")
        self.assertIn("2 task(s): 2 current", text)
        self.assertNotIn("make run TASK=decay", text)
        parameters = self.project / "parameters.json"
        parameters.write_text(parameters.read_text().replace("1.5", "2.5"))
        text = self.make_output("status")
        self.assertIn("make run TASK=decay", text)
        self.assertIn("make figure TASK=decay", text)

    def commit_everything(self, message="base"):
        if not (self.project / ".git").exists():
            subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
            subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=self.project, check=True)  # any Git version
        subprocess.run(["git", "add", "-A"], cwd=self.project, check=True)
        subprocess.run(["git", "-c", "user.email=t@example.org", "-c", "user.name=t", "commit", "-q", "-m", message], cwd=self.project, check=True)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_status_says_what_git_and_the_installed_files_look_like(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        text = self.make_output("status")
        self.assertIn("not a Git repository", text)
        self.commit_everything()
        (self.project / "notes.txt").write_text("changed\n")
        with (self.project / ".latex-ai/core.py").open("a") as stream:
            stream.write("\n# local tweak\n")
        text = self.make_output("status")
        self.assertIn("branch main", text)
        self.assertIn("2 uncommitted file(s)", text)
        self.assertIn("1 managed file(s) changed locally", text)
        self.assertIn("make validate", text)
        (self.project / core.CONFIG).write_text("{not json")
        text = self.make_output("status")
        self.assertIn("Configuration problem", text)
        self.assertIn("Git", text)

    def cli_result(self, *args):
        out, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errors):
            status = boot.main([*args, str(self.project)])
        return status, out.getvalue(), errors.getvalue()

    def cli_output(self, *args):
        return self.cli_result(*args)[:2]

    def test_common_errors_say_what_to_do_next(self):
        run = lambda *arguments: self.run_main(*arguments)  # noqa: E731
        empty = Path(tempfile.mkdtemp(prefix="workbench-empty-"))
        self.addCleanup(shutil.rmtree, empty, True)
        with patch.object(sys, "argv", ["workbench", "check", "--project", str(empty)]), contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(rt.main(), 1)
        self.assertIn("no workbench installed", errors.getvalue())
        self.assertIn("latex-ai-init init .", errors.getvalue())
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        status, errors = run("run", "--task", "decay")
        self.assertEqual(status, 1)
        self.assertIn("Module is disabled: numerics", errors)
        self.assertIn("latex-ai-init configure . --enable numerics", errors)
        shutil.rmtree(self.project)
        self.project.mkdir()
        self.example()
        status, errors = run("run")
        self.assertEqual(status, 1)
        self.assertIn("Declared numerics tasks: decay", errors)
        status, errors = run("figure", "--task", "nope")
        self.assertEqual((status, "Unknown figures task: nope" in errors, "Declared figures tasks: decay" in errors), (1, True, True))
        status, errors = run("research-check")  # nothing has been run yet
        self.assertEqual(status, 1)
        self.assertIn("Stale research outputs", errors)
        self.assertIn("make run TASK=decay", errors)
        self.assertIn("make figure TASK=decay", errors)
        with patch.object(shutil, "which", return_value=None):
            status, errors = run("doctor")
        self.assertIn("Missing required tools", errors)
        self.assertIn("make doctor", errors)
        # Through Make the same message is reached: no second, poorer one in the Makefile hides it.
        for target, module in (("run", "numerics"), ("figure", "figures")):
            blank = self.make_result(target)
            self.assertNotEqual(blank.returncode, 0)
            self.assertIn("Set TASK", blank.stderr)
            self.assertIn(f"Declared {module} tasks: decay", blank.stderr)
            self.assertIn(f"make {target} TASK=decay", blank.stderr)

    def test_installer_summarises_in_plain_words_and_says_what_comes_next(self):
        shutil.copytree(boot.PACKAGE / "examples/decay", self.project, dirs_exist_ok=True)
        status, text = self.cli_output("audit")
        self.assertIn("Audit only: nothing was changed", text)
        self.assertIn("latex-ai-init init", text)
        status, text = self.cli_output("init", "--dry-run")
        self.assertIn("Dry run: nothing was changed", text)
        self.assertFalse((self.project / ".latex-ai/workbench.py").exists())
        status, text = self.cli_output("init")
        self.assertEqual(status, 0)
        self.assertRegex(text, r"Done: \d+ file\(s\) added")
        for command in ("make doctor", "make help", "make check"):
            self.assertIn(command, text)
        status, text = self.cli_output("upgrade")
        self.assertIn("Already current", text)
        self.assertNotIn("Next:", text)  # nothing was done, so nothing is suggested

    def test_installer_says_when_it_kept_a_project_target_the_workbench_would_have_used(self):
        (self.project / "Makefile").write_text("PYTHON ?= python3\nhelp:\n\t@echo MINE\nissue:\n\t@echo MINE\n")
        status, text = self.cli_output("init", "--profile", "core")
        self.assertEqual(status, 0)
        self.assertIn("kept your Makefile target `help`; the workbench command is `make latex-ai-help`", text)
        self.assertIn("kept your Makefile target `issue`; the workbench command is `make latex-ai-issue`", text)
        self.assertNotIn("kept your Makefile target `status`", text)
        self.assertIn("make latex-ai-help", text.split("Next:")[1])  # the follow-up names the command that works

    # --- Release 2.3.2: findings of the review of 2.2.2-2.3.1 ---

    def test_help_and_status_read_the_makefile_that_make_itself_uses(self):
        # GNU Make prefers GNUmakefile, and a wrapper that includes the project's Makefile is a common layout.
        (self.project / "GNUmakefile").write_text("PYTHON ?= python3\ninclude Makefile\n")
        (self.project / "Makefile").write_text("all:\n\t@echo ALL\n")
        self.assertEqual(self.cli("init", "--profile", "numerical"), 0)
        self.assertIn("latex-ai-help", (self.project / "GNUmakefile").read_text())
        self.assertEqual(guide.active_makefile(self.project), "GNUmakefile")
        text = self.make_output("help")
        for line in ("make check", "make status", "make run TASK=NAME", "make freshness"):
            self.assertIn(line, text)
        self.assertIn("make check", self.make_output("status"))

    def test_installer_summary_follows_the_active_makefile_name(self):
        (self.project / "GNUmakefile").write_text("PYTHON ?= python3\nhelp:\n\t@echo MINE\n")
        status, text = self.cli_output("init", "--profile", "core")
        self.assertEqual(status, 0)
        self.assertIn("kept your Makefile target `help`; the workbench command is `make latex-ai-help`", text)
        following = text.split("Next:")[1]
        for command in ("make doctor", "make latex-ai-help", "make check"):
            self.assertIn(command, following)

    def test_policy_names_orientation_commands_that_reach_the_workbench(self):
        # The rule that made the report command `latex-ai-issue`: a project's own target of the short name is
        # kept, so guidance an agent follows blindly must name the command that always reaches the workbench.
        (self.project / "Makefile").write_text("PYTHON ?= python3\nhelp:\n\t@touch PROJECT_HELP_RAN\nstatus:\n\t@touch PROJECT_STATUS_RAN\n")
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        policies = {"full policy": (boot.PACKAGE / "templates/AGENTS.md").read_text(), "short policy": boot.integration_text("AGENTS.md", ""),
                    "installed policy": (self.project / "AGENTS.md").read_text()}
        for name, text in policies.items():
            with self.subTest(policy=name):
                self.assertNotRegex(text, r"make (?:help|status)\b")
                for advertised in ("make latex-ai-help", "make latex-ai-status"):
                    self.assertIn(advertised, text)
        self.assertIn("LaTeX AI Workbench", self.make_output("latex-ai-status"))
        self.assertIn("make latex-ai-status", self.make_output("latex-ai-help"))
        self.assertFalse(any((self.project / name).exists() for name in ("PROJECT_HELP_RAN", "PROJECT_STATUS_RAN")))

    def test_status_does_not_count_the_projects_own_files_as_changed_installation_files(self):
        # Seeded manifests and notes belong to the project once created, and editor settings are merged with the
        # project's own: editing them is the intended use, not a change to the installation.
        self.assertEqual(self.cli("init", "--modules", "notes,numerics,provenance,freshness", "--editor"), 0)
        (self.project / "in.txt").write_text("1\n")
        (self.project / "experiments.json").write_text(json.dumps({"schema_version": 1, "tasks": {
            "copy": {"command": ["cp", "in.txt", "out.txt"], "inputs": ["in.txt"], "outputs": ["out.txt"]}}}))
        with (self.project / "notes/session-state.md").open("a") as stream:
            stream.write("\nA decision.\n")
        tasks = json.loads((self.project / ".vscode/tasks.json").read_text())
        tasks["tasks"].append({"label": "Mine", "type": "process", "command": "true"})
        (self.project / ".vscode/tasks.json").write_text(json.dumps(tasks))
        (self.project / "notes/index.md").unlink()  # the installer accepts this too: never recreated
        text = self.make_output("status")
        self.assertIn("0 managed file(s) changed locally", text)
        for name in ("experiments.json", "session-state.md", "tasks.json", "index.md"):
            self.assertNotIn(name, text)
        self.assertIn("files differing from the manifest: none", self.command("issue").stdout)
        with (self.project / ".latex-ai/core.py").open("a") as stream:
            stream.write("\n# local tweak\n")
        text = self.make_output("status")
        self.assertIn("1 managed file(s) changed locally", text)
        self.assertIn(".latex-ai/core.py: modified locally", text)
        self.assertIn("files differing from the manifest: .latex-ai/core.py", self.command("issue").stdout)

    def test_a_projects_own_target_is_never_presented_as_the_workbench_command(self):
        (self.project / "Makefile").write_text("PYTHON ?= python3\ndoctor:\n\t@touch PROJECT_DOCTOR_RAN\nclean:\n\t@touch PROJECT_CLEAN_RAN\n"
                                               "build:\n\t@echo software build\nlint:\n\t@echo software lint\n")
        status, text = self.cli_output("init", "--profile", "core")
        self.assertEqual(status, 0)
        self.assertIn("kept your Makefile target `doctor`; the workbench command is `make latex-ai-doctor`", text)
        following = text.split("Next:")[1]
        self.assertIn("make latex-ai-doctor", following)
        self.assertNotRegex(following, r"make doctor\b")
        listed = self.make_output("help")
        self.assertIn("make latex-ai-doctor", listed)
        for wrong in ("make doctor", "make clean", "make build", "make lint", "Manuscript"):
            self.assertNotIn(wrong, listed)  # no manuscript here: these are the project's own recipes
        self.assertIn("python:", self.make_output("latex-ai-doctor"))
        self.assertFalse((self.project / "PROJECT_DOCTOR_RAN").exists())
        with patch.object(shutil, "which", return_value=None):
            status, errors = self.run_main("doctor")
        self.assertIn("make latex-ai-doctor", errors)  # the advice to run it again names the command that works

    def test_every_workbench_command_but_the_shared_two_has_a_reserved_name(self):
        shared = {command.short for command in guide.COMMANDS if command.reserved is None}
        self.assertEqual(shared, {"check", "lint"})  # build has a receipt-producing reserved target
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n")
        (self.project / "Makefile").write_text("PYTHON ?= python3\nbuild:\n\t@echo build\n" + "".join(
            f"{name}:\n\t@echo MINE\n" for name in ("doctor", "bib-check", "pdf-artifact", "clean", "md-check", "research-validate")))
        self.assertEqual(self.cli("init", "--modules", "latex,notes,markdown,numerics,provenance,freshness", "--ci", "--engine", "pdflatex"), 0)
        targets = guide.make_targets((self.project / "Makefile").read_text())
        for name in ("doctor", "bib-check", "pdf-artifact", "md-check", "research-validate"):
            self.assertIn("latex-ai-" + name, targets)
        self.assertIn("latex-ai-clean", targets)  # the selected document determines whether cleanup is supported
        self.assertEqual(self.make_output("clean").strip(), "MINE")
        self.assertEqual(self.make_output("doctor").strip(), "MINE")  # and the project's recipes are still its own

    def test_generated_ci_only_calls_make_names_the_installer_always_provides(self):
        # CI must run the workbench's checks even where the project keeps a target of the short name.
        cases = (("adopted paper", "latex,notes,markdown,numerics,provenance,freshness", True),
                 ("fresh paper", "latex,bibliography,notes,markdown,numerics,provenance,figures,freshness,claims", False),
                 ("no manuscript", "bibliography,notes,markdown,numerics,provenance,freshness", False))
        for label, modules, adopted in cases:
            with self.subTest(case=label):
                shutil.rmtree(self.project)
                self.project.mkdir()
                (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n")
                if adopted:
                    (self.project / "Makefile").write_text("PYTHON ?= python3\nbuild:\n\t@echo build\n" + "".join(
                        f"{name}:\n\t@echo MINE\n" for name in ("bib-check", "pdf-artifact", "md-check", "research-validate")))
                self.assertEqual(self.cli("init", "--modules", modules, "--ci", *(["--engine", "pdflatex"] if adopted else [])), 0)  # an existing build needs the engine named
                workflow = (self.project / ".github/workflows/latex-ai.yml").read_text()
                called = re.findall(r"(?m)^\s*(?:run: )?make (?!-C)([\w-]+)", workflow)
                self.assertTrue(called, workflow)
                targets = guide.make_targets((self.project / "Makefile").read_text())
                for name in called:
                    self.assertTrue(name == "check" or name.startswith("latex-ai-"), f"{label}: CI calls `make {name}`")
                    self.assertIn(name, targets)

    def test_enable_hint_is_a_command_that_works_for_this_configuration(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n")
        self.assertEqual(self.cli("init"), 0)
        hint = re.search(r"Turn one on with: (.+)", self.make_output("help")).group(1)
        words = shlex.split(hint.replace("NAME", "notes"))
        position = next(index for index, word in enumerate(words) if word.endswith("latex-ai-init"))
        self.assertEqual(words[position + 1:position + 3], ["configure", "."])
        self.assertEqual(self.cli(words[position + 1], *words[position + 3:], "--dry-run"), 0, hint)
        status, errors = self.run_main("md-check")
        self.assertIn("--enable markdown", errors)
        shutil.rmtree(self.project)
        self.project.mkdir()
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        hint = re.search(r"Turn one on with: (.+)", self.make_output("help")).group(1)
        self.assertNotIn("--migrate-config", hint)  # current projects have explicit modules
        words = shlex.split(hint.replace("NAME", "notes"))
        position = next(index for index, word in enumerate(words) if word.endswith("latex-ai-init"))
        self.assertEqual(self.cli(words[position + 1], *words[position + 3:], "--dry-run"), 0, hint)

    def test_audit_names_the_command_that_applies_what_it_previewed(self):
        status, text = self.cli_output("audit", "--profile", "numerical", "--ci")
        self.assertEqual(status, 1)
        command = shlex.split(re.search(r"apply with: (.+)", text).group(1))
        self.assertEqual(command[:3], ["python3", str(boot.PACKAGE / "latex-ai-init"), "init"])
        self.assertEqual(Path(command[3]), self.project)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(boot.main(command[2:]), 0)  # exactly what was printed, and it applies
        config = schema.load_config(self.project)
        self.assertEqual(sorted(config["modules"]), ["freshness", "numerics", "provenance"])
        self.assertTrue(config["integrations"]["ci"]["enabled"])
        status, text = self.cli_output("audit")
        self.assertEqual(status, 0)
        self.assertIn("the installation is current", text)

    def test_summary_is_honest_when_only_the_installation_record_would_change(self):
        (self.project / "Makefile").write_text("PYTHON ?= python3\nmine:\n\t@echo MINE\n")
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        with (self.project / "Makefile").open("a") as stream:
            stream.write("\nextra:\n\t@echo extra\n")  # outside the managed block: an ordinary, allowed edit
        status, text = self.cli_output("audit")
        self.assertEqual(status, 1)
        self.assertNotIn("installation is current", text)
        self.assertIn("installation record", text)
        self.assertIn("latex-ai-init upgrade", text)
        status, text = self.cli_output("upgrade")
        self.assertEqual(status, 0)
        self.assertIn("installation record", text)
        self.assertNotIn("0 file(s) added", text)
        self.assertNotIn("Next:", text)
        status, text = self.cli_output("audit")
        self.assertEqual(status, 0)
        self.assertIn("the installation is current", text)

    def test_installer_errors_say_what_to_do_next(self):
        status, _, errors = self.cli_result("init")  # the quickstart's first command, on an empty folder
        self.assertEqual(status, 2)
        self.assertIn("Hint:", errors)
        self.assertIn("--profile", errors)
        for name in ("paper.tex", "thesis.tex"):
            (self.project / name).write_text("\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n")
        status, _, errors = self.cli_result("init")
        self.assertEqual(status, 2)
        self.assertRegex(errors, r"Hint: .*--root")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(boot.main(["init", str(self.project), "--json"]), 2)
        self.assertIn("--root", json.loads(out.getvalue())["hint"])
        quickstart = (boot.PACKAGE / "docs/quickstart.md").read_text()
        self.assertRegex(quickstart, r"latex-ai-init init /path/to/project --profile \w+")  # a command for the empty folder

    def test_a_damaged_installation_record_gets_a_diagnosis_not_the_defect_label(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        self.addCleanup(shutil.rmtree, diagnostics.fault_dir(self.project), True)
        for damaged in ("[]", '{"schema_version": 1, "version": "2.0.0", "files": []}',
                        '{"schema_version": 1, "version": 2, "files": {}}', '{"schema_version": 1, "version": "2.0.0", "files": {"Makefile": 5}}'):
            with self.subTest(record=damaged):
                (self.project / boot.STATE).write_text(damaged)
                done = self.make_result("status")
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertNotIn("INTERNAL ERROR", done.stdout + done.stderr)
                self.assertIn("installation.json", done.stdout)
                self.assertNotIn("Nothing pending", done.stdout)
                self.command("issue")  # and the report can still be written
                status, _, errors = self.cli_result("audit")
                self.assertEqual(status, 2, errors)
                self.assertNotIn("INTERNAL ERROR", errors)
                self.assertIn("installation", errors)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_status_only_says_nothing_is_pending_when_that_is_known(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        text = self.make_output("status")  # no Git: what changed cannot be known
        self.assertNotIn("Nothing pending", text)
        self.assertIn("make check", text.split("Next:")[1])
        self.commit_everything()
        self.assertIn("Nothing pending", self.make_output("status"))
        with (self.project / ".latex-ai/core.py").open("a") as stream:
            stream.write("\n# local tweak\n")
        self.commit_everything("tweak")
        text = self.make_output("status")  # a clean tree, but the installed runtime is not what was installed
        self.assertIn("1 managed file(s) changed locally", text)
        self.assertNotIn("Nothing pending", text)
        self.assertIn("latex-ai-init audit .", text.split("Next:")[1])

    def test_missing_task_example_names_the_command_that_works_here(self):
        (self.project / "Makefile").write_text("PYTHON ?= python3\nrun:\n\t@echo MINE\n")
        self.assertEqual(self.cli("init", "--profile", "numerical"), 0)
        blank = self.make_result("latex-ai-run")
        self.assertNotEqual(blank.returncode, 0)
        self.assertIn("no numerics tasks are declared yet", blank.stderr)
        (self.project / "in.txt").write_text("1\n")
        (self.project / "experiments.json").write_text(json.dumps({"schema_version": 1, "tasks": {
            "copy": {"command": ["cp", "in.txt", "out.txt"], "inputs": ["in.txt"], "outputs": ["out.txt"]}}}))
        blank = self.make_result("latex-ai-run")
        self.assertIn("make latex-ai-run TASK=copy", blank.stderr)
        (self.project / "experiments.json").write_text("{not json")
        blank = self.make_result("latex-ai-run")  # a broken manifest is reported as such, not as "no tasks"
        self.assertNotIn("no numerics tasks are declared yet", blank.stderr)
        self.assertIn("ERROR:", blank.stderr)

    def test_help_and_status_explain_a_missing_configuration_in_plain_words(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        (self.project / core.CONFIG).unlink()
        for target in ("help", "status"):
            with self.subTest(target=target):
                text = self.make_output(target)
                self.assertIn("no workbench installed", text)
                self.assertNotIn("FileNotFoundError", text)
                self.assertIn("latex-ai-init init .", text)

    # --- Release 2.3.3: findings of the user trial of 2.3.2 ---

    PAPER = "\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n"

    def combined(self, *args):
        """Runtime output as an agent captures it: both streams through one pipe."""
        return subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), *args], cwd=self.project,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def fresh_project(self):
        shutil.rmtree(self.project)
        self.project.mkdir()

    def test_full_check_builds_before_linting_and_a_lint_failure_says_what_can_be_done(self):
        import latex
        (self.project / "main.tex").write_text(self.PAPER)
        self.assertEqual(self.cli("init", "--profile", "writing"), 0)
        config = schema.load_config(self.project)
        order = []
        with patch.object(rt, "build", side_effect=lambda *a: order.append("build")), patch.object(rt, "verify", side_effect=lambda *a: order.append("verify")), \
                patch.object(rt, "lint", side_effect=lambda *a: order.append("lint")), contextlib.redirect_stdout(io.StringIO()):
            rt.full_check(self.project, config)
        self.assertEqual(order, ["build", "verify", "lint"])  # a TeX error is reported even when the style checker also objects
        with patch.object(latex, "chktex_warnings", return_value=[dict(self.ROWS[0])]), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(core.WorkbenchError) as raised:
                latex.lint(self.project, schema.document_settings(config))
        for phrase in ("lint", "args", ".chktexrc", "enabled", "baseline"):
            self.assertIn(phrase, raised.exception.hint)
        self.fresh_project()  # the same order where an existing Makefile is adapted
        (self.project / "main.tex").write_text(self.PAPER)
        (self.project / "Makefile").write_text("build:\n\t@echo build\n")
        self.assertEqual(self.cli("init", "--engine", "pdflatex"), 0)
        self.assertRegex((self.project / "Makefile").read_text(), r"(?m)^latex-ai-check-passed: latex-ai-integrity lint$")

    def test_a_broken_json_file_is_named_in_the_error(self):
        self.example()
        self.command("run", "--task", "decay")
        self.command("figure", "--task", "decay")
        for name in ("experiments.json", "figures/manifest.json", "claims.json", core.CONFIG):
            path = self.project / name
            original = path.read_text()
            path.write_text('{"schema_version": 1,,}')
            status, errors = self.run_main("check")
            path.write_text(original)
            with self.subTest(file=name):
                self.assertEqual(status, 1)
                self.assertIn(f"ERROR: {name} is not valid JSON", errors)
                self.assertIn("Hint:", errors)
        (self.project / "data.json").write_text("{broken")  # an ordinary project file, found by the file checks
        status, errors = self.run_main("check")
        self.assertEqual(status, 1)
        self.assertIn("data.json", errors)

    def newer_package(self):
        """Stand-in for a later release: the same package with its project-facing files changed."""
        real = boot.desired_files

        def desired(config, project=None):
            files = real(config, project)
            for name, line in (("Makefile", "# a later release\n"), ("AGENTS.md", "\nA later policy line.\n"), (".gitignore", "later-ignore/\n")):
                files[name] += line
            return files
        return patch.object(boot, "desired_files", desired)

    def test_additions_around_the_installed_text_survive_an_upgrade(self):
        # A fresh project's Makefile, policy and ignore file are installed whole. Adding a target, a rule or an
        # ignore line is ordinary use and must not block every later upgrade.
        (self.project / "main.tex").write_text(self.PAPER)
        self.assertEqual(self.cli("init", "--profile", "writing"), 0)
        additions = {"Makefile": "\nwordcount:\n\ttexcount main.tex\n", "AGENTS.md": "\n# Project rules\n\nUse SI units.\n", ".gitignore": "scratch/\n"}
        for name, text in additions.items():
            with (self.project / name).open("a") as stream:
                stream.write(text)
        makefile = self.project / "Makefile"
        makefile.write_text("# my header\n" + makefile.read_text())  # above the installed text as well as below it
        self.assertIn("0 managed file(s) changed locally", self.make_output("status"))
        with self.newer_package():
            status, text = self.cli_output("upgrade")
            self.assertEqual(status, 0, text)
            for name, line in (("Makefile", "# a later release"), ("AGENTS.md", "A later policy line."), (".gitignore", "later-ignore/")):
                content = (self.project / name).read_text()
                self.assertIn(line, content)
                self.assertIn(additions[name], content)
            self.assertTrue(makefile.read_text().startswith("# my header\n"))
            status, text = self.cli_output("upgrade")
            self.assertEqual(status, 0)
            self.assertIn("Already current", text)
            # A change inside the installed text is still a conflict, now with what to do and the change itself.
            makefile.write_text(makefile.read_text().replace(".DEFAULT_GOAL := build", ".DEFAULT_GOAL := check"))
            status, text, errors = self.cli_result("upgrade", "--diff")
            self.assertEqual(status, 2)
            self.assertIn("CONFLICT: Makefile: ", text)
            self.assertIn("inside the text the workbench installed", text)
            self.assertIn("-.DEFAULT_GOAL := build", text)
            self.assertIn("+.DEFAULT_GOAL := check", text)
            makefile.write_text(makefile.read_text().replace(".DEFAULT_GOAL := check", ".DEFAULT_GOAL := build"))
            # Runtime files stay strict: nothing may be added to them.
            with (self.project / ".latex-ai/core.py").open("a") as stream:
                stream.write("\n# local tweak\n")
            status, text = self.cli_output("upgrade")
            self.assertEqual(status, 2)
            self.assertIn("CONFLICT: .latex-ai/core.py", text)

    def test_the_look_first_output_is_short_and_ends_with_the_summary(self):
        (self.project / "main.tex").write_text(self.PAPER)
        status, text = self.cli_output("init", "--dry-run", "--diff")
        lines = text.rstrip().splitlines()
        self.assertEqual(status, 0)
        self.assertLess(len(lines), 700, "the first command a newcomer runs must stay readable")
        self.assertIn("Dry run: nothing was changed", "\n".join(lines[-3:]))
        self.assertRegex(text, r"(?m)^new file: \.latex-ai/workbench\.py \(\d+ lines")
        self.assertNotIn("+def main():", text)
        self.assertIn("+.DEFAULT_GOAL := build", text)  # files the project will own or read are still shown in full

    def test_validation_without_git_history_says_so_in_plain_words(self):
        self.assertEqual(self.cli("init", "--profile", "notebook"), 0)
        text = self.make_output("validation-plan")
        self.assertIn("full validation selected", text)
        self.assertIn("not a Git repository", text)
        self.assertNotIn("fatal:", text)
        self.assertRegex((boot.PACKAGE / "docs/quickstart.md").read_text(), r"Git repository")
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
            text = self.make_output("validation-plan")
            self.assertIn("no commit", text)
            self.assertNotIn("fatal:", text)

    def test_errors_follow_the_output_that_explains_them_when_both_streams_share_a_pipe(self):
        self.example()
        done = self.combined("research-check")
        self.assertEqual(done.returncode, 1)
        self.assertLess(done.stdout.index("numerics/decay: stale"), done.stdout.index("ERROR:"), done.stdout)

    def test_a_failing_task_check_names_the_task_and_what_to_run(self):
        self.example()
        self.command("run", "--task", "decay")
        self.command("figure", "--task", "decay")
        parameters = self.project / "parameters.json"
        parameters.write_text(parameters.read_text().replace("1.5", "2.5"))
        out = self.combined("research-check")
        self.assertEqual(out.returncode, 1)
        self.assertLess(out.stdout.index("numerics/decay: stale"), out.stdout.index("Traceback"), out.stdout)  # the report comes first
        error = out.stdout.split("ERROR:")[1]
        self.assertIn("Check of numerics/decay failed", error)
        self.assertIn("scripts/check_decay.py", error)  # the whole command, not only its first word
        self.assertRegex(error, r"Hint: .*make run TASK=decay")
        built = self.combined("figure", "--task", "decay")  # runs by design, but says what it is built from
        self.assertEqual(built.returncode, 0, built.stdout)
        self.assertRegex(built.stdout, r"WARNING: .*numerics/decay is stale")
        figures = [record for record in map(json.loads, (path.read_text() for path in self.records())) if record["module"] == "figures"]
        self.assertEqual(max(figures, key=lambda record: record["started"])["stale_upstream"], ["numerics/decay"])

    def test_task_manifest_errors_name_the_file_the_task_and_the_expected_form(self):
        self.assertEqual(self.cli("init", "--profile", "numerical"), 0)
        status, errors = self.run_main("run")
        self.assertIn("experiments.json", errors)
        self.assertIn("docs/research.md", errors)
        self.assertIn("experiments.json", self.make_output("status"))  # with no task yet, status says where one is declared
        (self.project / "experiments.json").write_text(json.dumps({"schema_version": 1, "tasks": {"sim": {"command": "python3 sim.py", "inputs": ["sim.py"]}}}))
        status, errors = self.run_main("run", "--task", "sim")
        self.assertEqual(status, 1)
        for phrase in ("experiments.json", "sim", '["python3", "analysis/run.py"]', "docs/research.md"):
            self.assertIn(phrase, errors)
        self.assertIn("experiments.json", self.make_output("status"))

    def test_targets_in_an_included_makefile_are_the_projects_own(self):
        (self.project / "GNUmakefile").write_text("include Makefile\n")
        (self.project / "Makefile").write_text("PYTHON ?= python3\nall:\n\t@echo ALL\nhelp:\n\t@echo MY-HELP\n")
        status, text = self.cli_output("init", "--profile", "notebook")
        self.assertEqual(status, 0)
        self.assertIn("kept your Makefile target `help`; the workbench command is `make latex-ai-help`", text)
        self.assertEqual(self.make_output("help").strip(), "MY-HELP")
        self.assertIn("make latex-ai-help", self.make_output("latex-ai-help"))

    def test_policy_never_names_a_short_form_the_project_may_own(self):
        policies = {"full policy": (boot.PACKAGE / "templates/AGENTS.md").read_text(), "short policy": boot.integration_text("AGENTS.md", "")}
        for command in guide.COMMANDS:
            for name, text in policies.items():
                if command.reserved:
                    with self.subTest(policy=name, command=command.short):
                        self.assertNotRegex(text, rf"\bmake {re.escape(command.short)}\b")
        self.assertIn("`latex-ai-` form", (boot.PACKAGE / "skills/latex-ai-workbench/SKILL.md").read_text())

    def test_default_paper_install_says_what_it_adds_and_points_to_status(self):
        (self.project / "main.tex").write_text(self.PAPER)
        status, text = self.cli_output("init", "--dry-run")
        self.assertRegex(text, r"NOTE: .*\.vscode.*--skip-editor")
        self.assertRegex(text, r"NOTE: .*workflow.*--no-ci")
        quickstart = (boot.PACKAGE / "docs/quickstart.md").read_text()
        for flag in ("--no-ci", "--skip-editor"):
            self.assertIn(flag, quickstart)
        status, text = self.cli_output("init", "--no-ci", "--skip-editor")
        self.assertEqual(status, 0)
        self.assertNotIn("NOTE: ", text)
        self.assertFalse((self.project / ".vscode").exists() or (self.project / ".github").exists())
        self.assertIn("make status", text.split("Next:")[1])

    def test_more_installer_errors_carry_a_hint(self):
        def attempt(*argv):
            out, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errors):
                return boot.main(list(argv)), errors.getvalue()
        status, errors = attempt("init", str(self.project / "nowhere"))
        self.assertEqual(status, 2)
        self.assertRegex(errors, r"Hint: .*mkdir")
        (self.project / "main.tex").write_text(self.PAPER)
        status, errors = attempt("init", str(self.project / "main.tex"))
        self.assertRegex(errors, r"Hint: .*folder")
        (self.project / "Makefile").write_text("pdf:\n\t./build.sh\n")  # a build that does not name its engine
        status, errors = attempt("init", str(self.project))
        self.assertEqual(status, 2)
        hint = errors.split("Hint:")[1]
        for phrase in ("pdflatex", "lualatex", "xelatex", "--build-command"):
            self.assertIn(phrase, hint)
        (self.project / "Makefile").unlink()
        self.assertEqual(attempt("init", str(self.project))[0], 0)
        status, errors = attempt("init", str(self.project), "--profile", "writing")
        self.assertEqual(status, 2)
        hint = errors.split("Hint:")[1]
        self.assertIn("upgrade", hint)
        self.assertIn("configure", hint)

    def test_small_print_of_everyday_commands(self):
        self.assertEqual(self.cli("init", "--modules", "notes,markdown"), 0)
        env = {name: value for name, value in os.environ.items() if name not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "TASK", "LATEX_AI_BASE"}}
        shown = subprocess.run(["make", "help"], cwd=self.project, capture_output=True, text=True, env=env)  # no -s: the recipe itself is quiet
        self.assertTrue(shown.stdout.startswith("LaTeX AI Workbench"), shown.stdout[:120])
        with patch.object(shutil, "which", side_effect=lambda name: None if name == "pandoc" else "/usr/bin/" + Path(name).name):
            status, errors = self.run_main("doctor")
        self.assertEqual(status, 1)
        self.assertIn("Pandoc", errors.split("Hint:")[1])
        self.assertNotIn("TeX distribution", errors)
        self.assertNotIn("citation keys", next(command.description for command in guide.COMMANDS if command.short == "bib-check"))
        self.fresh_project()
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        checked = subprocess.run(["make", "check"], cwd=self.project, capture_output=True, text=True, env=env)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("passed", checked.stdout.rstrip().splitlines()[-1])
        self.assertNotIn("Changed-file", checked.stdout)
        self.assertNotIn("in the diff", checked.stdout)
        if shutil.which("git"):
            self.commit_everything()
            (self.project / "drafts").mkdir()
            for name in ("a.txt", "b.txt"):
                (self.project / "drafts" / name).write_text("x\n")
            text = self.make_output("status")
            self.assertIn("2 uncommitted file(s)", text)  # counted as files, like the changes below it
            self.assertIn("2 file(s)", text)

    # --- Release 2.4.0: simplifications, and the findings of the blind trial of 2.3.3 ---

    def test_a_plain_install_writes_the_same_configuration_format_as_a_profile(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nSee~\\cite{k}.\n\\bibliographystyle{plain}\n\\bibliography{refs}\n\\end{document}\n")
        (self.project / "refs.bib").write_text("@misc{k, title = {Synthetic fixture}, year = {2000}}\n")
        self.assertEqual(self.cli("init"), 0)
        config = schema.load_config(self.project)
        self.assertEqual(config["schema_version"], 3)
        self.assertEqual(sorted(config["modules"]), ["bibliography", "latex"])
        self.assertEqual(config["modules"]["latex"]["documents"]["manuscript"]["backend"], "bibtex")
        self.assertTrue(config["integrations"]["editor"] and config["integrations"]["ci"]["enabled"])  # the defaults are unchanged
        self.assertTrue((self.project / ".vscode/settings.json").is_file() and (self.project / ".github/workflows/latex-ai.yml").is_file())
        hint = re.search(r"Turn one on with: (.+)", self.make_output("help")).group(1)
        self.assertNotIn("--migrate-config", hint)
        self.assertEqual(self.cli("configure", "--enable", "notes", "--dry-run"), 0)  # no migration step for a new project
        before = self.snapshot()
        self.assertEqual(self.cli("upgrade"), 0)
        self.assertEqual(self.cli("audit"), 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.cli("audit"), 0)
        self.assertEqual(schema.load_config(self.project)["schema_version"], 3)

    def test_one_command_table_drives_targets_actions_and_every_name_shown_to_readers(self):
        reserved = {command.reserved for command in guide.COMMANDS if command.reserved}
        self.assertEqual({command.action.split()[0] for command in guide.COMMANDS if command.action} - set(rt.ACTIONS), set())
        self.assertEqual(len(reserved), sum(1 for command in guide.COMMANDS if command.reserved))  # no reserved name twice
        # Internal targets of adapted Makefiles are the only latex-ai- names outside the table.
        internal = {"latex-ai-integrity", "latex-ai-core-check", "latex-ai-check-passed"}
        texts = {"full policy": (boot.PACKAGE / "templates/AGENTS.md").read_text(), "short policy": boot.integration_text("AGENTS.md", ""),
                 "skill": (boot.PACKAGE / "skills/latex-ai-workbench/SKILL.md").read_text()}
        texts.update({"docs/" + path.name: path.read_text() for path in sorted((boot.PACKAGE / "docs").glob("*.md"))})
        texts["README"] = (boot.PACKAGE / "README.md").read_text()
        for name, text in texts.items():
            with self.subTest(text=name):
                self.assertEqual(set(re.findall(r"\bmake (latex-ai-[a-z-]+)", text)) - reserved - internal, set())
        # The Makefile of every profile holds exactly the reserved targets its modules enable.
        for profile in ("core", "notebook", "numerical", "writing", "research-paper"):
            with self.subTest(profile=profile):
                self.fresh_project()
                (self.project / "main.tex").write_text(self.PAPER)
                self.assertEqual(self.cli("init", "--profile", profile, "--ci"), 0)
                config = schema.load_config(self.project)
                targets = guide.make_targets((self.project / "Makefile").read_text())
                expected = {command.reserved for command in guide.COMMANDS if command.reserved and guide.enabled(command, config)}
                self.assertEqual({name for name in targets if name.startswith("latex-ai-")} - internal, expected)
                self.assertEqual({command.short for command in guide.COMMANDS if command.reserved and guide.enabled(command, config)} - targets, set())  # and every alias
                workflow = (self.project / ".github/workflows/latex-ai.yml").read_text()
                self.assertEqual(set(re.findall(r"make (latex-ai-[a-z-]+)", workflow)) - expected, set())

    ROWS = [{"file": "main.tex", "line": 3, "warning": 2, "message": "Non-breaking space (`~') should have been used.", "text": "See Fig. \\ref{f}."},
            {"file": "main.tex", "line": 3, "warning": 12, "message": "Interword spacing (`\\ ') should perhaps be used.", "text": "See Fig. \\ref{f}."},
            {"file": "sections/a.tex", "line": 9, "warning": 8, "message": "Wrong length of dash may have been used.", "text": "Runge--Kutta"}]

    def test_lint_baseline_accepts_recorded_warnings_and_fails_only_on_new_ones(self):
        import latex
        (self.project / "main.tex").write_text(self.PAPER)
        self.assertEqual(self.cli("init", "--profile", "writing"), 0)
        config = schema.load_config(self.project)
        baseline = self.project / latex.baseline_path(schema.document_settings(config))

        def lint(rows):
            out = io.StringIO()
            with patch.object(latex, "chktex_warnings", return_value=[dict(row) for row in rows]), contextlib.redirect_stdout(out):
                try:
                    latex.lint(self.project, schema.document_settings(config))
                    return None, out.getvalue()
                except core.WorkbenchError as error:
                    return error, out.getvalue()

        error, _ = lint(self.ROWS)  # no baseline yet: every warning fails, and the hint names the way out
        self.assertIsNotNone(error)
        self.assertIn("lint-baseline", error.hint)
        with patch.object(latex, "chktex_warnings", return_value=[dict(row) for row in self.ROWS]):
            status, errors = self.run_main("lint-baseline")
        self.assertEqual(status, 0, errors)
        data = json.loads(baseline.read_text())
        self.assertEqual(sum(entry["count"] for entry in data["accepted"]), 3)
        error, text = lint(self.ROWS)
        self.assertIsNone(error)
        self.assertIn("3 warning(s) accepted", text)
        moved = [dict(row, line=row["line"] + 40) for row in self.ROWS]  # the same lines further down the file are still the same warnings
        self.assertIsNone(lint(moved)[0])
        added = self.ROWS + [{"file": "main.tex", "line": 7, "warning": 18, "message": "Use either `` or '' as an alternative to `\"'.", "text": 'A "new" sentence.'}]
        error, text = lint(added)
        self.assertIn("1 new warning", str(error))
        self.assertIn("main.tex:7", text)
        self.assertNotIn("Runge--Kutta", text)  # accepted warnings are not listed again
        edited = [dict(self.ROWS[0], text="See also Fig. \\ref{f}.")] + self.ROWS[1:]  # touching an accepted line means cleaning it
        self.assertIn("1 new warning", str(lint(edited)[0]))
        error, text = lint(self.ROWS[:1])  # fixed warnings never fail; the leftover entries are reported
        self.assertIsNone(error)
        self.assertIn("2 accepted warning(s) no longer occur", text)
        self.assertIsNone(lint([])[0])
        plan = rt.validation_plan(self.project, config, paths=[".chktex-baseline.json"])
        self.assertTrue(plan["manuscript"])  # changing the baseline is a change to what is checked
        for policy in ((boot.PACKAGE / "templates/AGENTS.md").read_text(), boot.integration_text("AGENTS.md", "")):
            self.assertIn("make latex-ai-lint-baseline", policy)
            self.assertRegex(policy, r"(?s)baseline.*owner")

    def test_lint_output_that_cannot_be_read_fails_instead_of_passing(self):
        import latex
        (self.project / "main.tex").write_text(self.PAPER)
        self.assertEqual(self.cli("init", "--profile", "writing"), 0)
        config = schema.load_config(self.project)
        for returncode, stdout in ((2, "something this version prints differently\n"), (1, "")):
            done = argparse.Namespace(returncode=returncode, stdout=stdout, stderr="chktex: complaint\n")
            with self.subTest(returncode=returncode), patch.object(latex.shutil, "which", return_value="/usr/bin/chktex"), \
                    patch.object(latex.subprocess, "run", return_value=done), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(core.WorkbenchError):
                    latex.chktex_warnings(self.project, schema.document_settings(config))
        fmt = "\x1f".join(("main.tex", "3", "2", "Non-breaking space", "See Fig. \\ref{f}.  ")) + "\n"
        with patch.object(latex.shutil, "which", return_value="/usr/bin/chktex"), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(latex.subprocess, "run", return_value=argparse.Namespace(returncode=2, stdout=fmt, stderr="")):
            rows = latex.chktex_warnings(self.project, schema.document_settings(config))
        self.assertEqual(rows, [{"file": "main.tex", "line": 3, "warning": 2, "message": "Non-breaking space", "text": "See Fig. \\ref{f}."}])

    def test_engine_is_read_from_the_projects_own_build_line(self):
        (self.project / "main.tex").write_text(self.PAPER)
        (self.project / "Makefile").write_text("LATEXMK = latexmk -pdf -interaction=nonstopmode\npdf:\n\t$(LATEXMK) main.tex\n")
        status, text = self.cli_output("init", "--build-command", '["make", "pdf"]', "--dry-run")
        self.assertEqual(status, 0, text)
        self.assertIn("engine: pdflatex", text)
        self.assertRegex(text, r"NOTE: engine pdflatex read from Makefile.*--engine")
        for line, engine in (("latexmk -lualatex main.tex", "lualatex"), ("latexmk -pdfxe main.tex", "xelatex"), ("xelatex main.tex", "xelatex")):
            (self.project / "Makefile").write_text(f"pdf:\n\t{line}\n")
            with self.subTest(line=line):
                self.assertIn(f"engine: {engine}", self.cli_output("init", "--build-command", '["make", "pdf"]', "--dry-run")[1])
        (self.project / "Makefile").write_text("pdf:\n\tpdflatex main.tex\nalt:\n\txelatex main.tex\n")  # two engines: not guessed
        status, _, errors = self.cli_result("init", "--build-command", '["make", "pdf"]', "--dry-run")
        self.assertEqual(status, 2)
        self.assertIn("--engine", errors)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_status_lists_what_to_do_in_the_order_it_has_to_be_done(self):
        self.assertEqual(self.cli("init", "--profile", "numerical"), 0)
        text = self.make_output("status")
        self.assertRegex(text.split("Next:")[1], r"declare .*experiments\.json")  # nothing to run or validate before a task exists
        self.fresh_project()
        self.example()
        self.commit_everything()
        (self.project / "parameters.json").write_text((self.project / "parameters.json").read_text().replace("1.5", "2.5"))
        following = self.make_output("status").split("Next:")[1]
        self.assertLess(following.index("make run TASK=decay"), following.index("make validate"))  # validating stale results can only fail
        self.command("run", "--task", "decay")
        self.command("figure", "--task", "decay")
        plan = self.make_output("validation-plan")
        self.assertEqual(len([line for line in plan.splitlines() if "results/runs/" in line]), 1, plan)  # run records are one line, not dozens
        self.assertRegex(plan, r"results/runs/: \d+ run-record file")

    def test_small_print_from_the_blind_trial(self):
        self.assertEqual(self.cli("init", "--profile", "numerical"), 0)
        self.assertIn("All required tools found", self.command("doctor").stdout)
        manifest = json.loads((self.project / "experiments.json").read_text())
        self.assertEqual(manifest["tasks"], {})
        self.assertEqual(research.tasks(self.project, schema.load_config(self.project), "numerics"), {})  # the example is not a task
        manifest["tasks"]["mine"] = manifest["example"]["task"]  # and it is a valid one once copied under a name
        (self.project / "experiments.json").write_text(json.dumps(manifest))
        self.assertEqual(list(research.tasks(self.project, schema.load_config(self.project), "numerics")), ["mine"])
        self.assertIn("declared: mine", self.make_output("help"))
        self.fresh_project()
        (self.project / "main.tex").write_text(self.PAPER)
        (self.project / "Makefile").write_text("build:\n\t@echo build\n")
        self.assertEqual(self.cli("init", "--engine", "pdflatex"), 0)
        makefile = (self.project / "Makefile").read_text()
        self.assertRegex(makefile, r"(?m)^check: latex-ai-check-passed$")
        self.assertRegex(makefile, r"(?m)^\t@echo \"Workbench checks passed")
        quickstart = (boot.PACKAGE / "docs/quickstart.md").read_text()
        self.assertNotIn("fullest", quickstart)
        self.assertIn("make latex-ai-lint-baseline", quickstart)
        self.assertNotIn("`workbench/skills/latex-ai-workbench/`", (boot.PACKAGE / "templates/AGENTS.md").read_text())  # no path that an adopted project lacks

    def test_doctor_reports_the_interpreter_that_runs_it(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        report = self.command("doctor").stdout
        self.assertIn(f"python: {sys.executable}", report)
        self.assertNotIn("python3:", report)  # the PATH lookup could name a different interpreter

    def test_deleted_seed_files_are_project_decisions_not_upgrade_conflicts(self):
        self.assertEqual(self.cli("init", "--profile", "notebook"), 0)
        (self.project / "notes/session-state.md").unlink()
        self.assertEqual(self.cli("upgrade"), 0)
        self.assertEqual(self.cli("audit"), 0)
        self.assertEqual(self.cli("configure", "--enable", "markdown", "--dry-run"), 0)
        self.assertFalse((self.project / "notes/session-state.md").exists())  # never recreated
        failure = self.command("check", expected=1).stderr
        self.assertIn("Missing notes file", failure)
        self.assertIn("configure --disable notes", failure)
        self.assertEqual(self.cli("configure", "--disable", "notes"), 0)
        self.assertIn("Broken local Markdown link", self.command("check", expected=1).stderr)  # index.md still links to it
        (self.project / "notes/index.md").write_text("# Notes\n")
        self.command("check")

    def test_deleted_manifest_seed_does_not_block_upgrade(self):
        self.assertEqual(self.cli("init", "--profile", "numerical"), 0)
        (self.project / "experiments.json").unlink()
        before = self.snapshot()
        self.assertEqual(self.cli("upgrade"), 0)
        self.assertEqual(before, self.snapshot())

    def test_task_name_is_never_interpreted_as_shell_syntax_by_make(self):
        self.example()
        self.assertIn("export TASK", (self.project / "Makefile").read_text())
        hostile = 'decay"; touch INJECTED; echo "'
        result = subprocess.run(["make", "run", f"TASK={hostile}"], cwd=self.project, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown numerics task", result.stderr)
        self.assertFalse((self.project / "INJECTED").exists())
        for target in ("run", "figure"):
            blank = subprocess.run(["make", target], cwd=self.project, capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "TASK"})
            self.assertNotEqual(blank.returncode, 0)
            self.assertIn("Set TASK", blank.stdout + blank.stderr)
        ok = subprocess.run(["make", "run", "TASK=decay"], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)

    def test_copy_preserving_timestamps_counts_as_rewriting_an_output(self):
        self.example()
        path = self.project / "experiments.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"].update(command=[sys.executable, "-c", "import shutil; shutil.copy2('parameters.json', 'results/copy.json')"],
                                      inputs=["parameters.json"], outputs=["results/copy.json"], checks=[])
        path.write_text(json.dumps(data))
        (self.project / "results").mkdir(exist_ok=True)
        self.command("run", "--task", "decay")
        self.command("run", "--task", "decay")
        self.assertEqual(len(self.records()), 2)

    def test_validation_never_runs_scientific_or_plot_commands(self):
        config = self.example()
        with patch.object(research, "run", side_effect=AssertionError("Any command invoked")):
            report = research.freshness(self.project, config)
            self.assertTrue(report)
        self.command("check", expected=1)
        self.assertFalse((self.project / "results/decay.json").exists())
        self.assertEqual(self.records(), [])

    def test_missing_and_escaping_inputs_prevent_execution(self):
        self.example()
        (self.project / "parameters.json").unlink()
        self.assertIn("Missing declared inputs", self.command("run", "--task", "decay", expected=1).stderr)
        path = self.project / "experiments.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"]["inputs"] = ["../outside.json"]
        path.write_text(json.dumps(data))
        self.command("run", "--task", "decay", expected=1)
        self.assertEqual(self.records(), [])

    def test_claims_need_real_links_and_review_status_is_not_inferred(self):
        self.example()
        path = self.project / "claims.json"
        data = {"schema_version": 1, "claims": [{"id": "c1", "text": "Synthetic statement", "status": "supported", "evidence": ["missing.json"]}]}
        path.write_text(json.dumps(data))
        self.command("claims-check", expected=1)
        data["claims"][0].update(status="proposed", evidence=[])
        path.write_text(json.dumps(data))
        self.command("claims-check")
        self.assertEqual(json.loads(path.read_text())["claims"][0]["status"], "proposed")

    def test_installed_pipeline_survives_relocation_without_distribution(self):
        self.example()
        with tempfile.TemporaryDirectory(prefix="workbench-relocated-") as directory:
            relocated = Path(directory) / "project with spaces"
            shutil.copytree(self.project, relocated)
            result = subprocess.run([sys.executable, "-B", str(relocated / ".latex-ai/workbench.py"), "run", "--project", str(relocated), "--task", "decay"], cwd=directory,
                                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((relocated / "results/decay.json").exists())

    def test_figures_can_consume_external_results_without_numerics(self):
        self.example()
        self.command("run", "--task", "decay")
        self.assertEqual(self.cli("configure", "--disable", "numerics"), 0)
        self.command("figure", "--task", "decay")
        report = json.loads(self.command("freshness").stdout)
        self.assertEqual([(r["module"], r["status"]) for r in report], [("figures", "current")])

    def test_cyclic_and_ambiguous_producers_fail_freshness(self):
        config = self.example()
        path = self.project / "figures/manifest.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"]["outputs"] = ["results/decay.json"]
        data["tasks"]["decay"]["inputs"] = ["parameters.json"]
        path.write_text(json.dumps(data))
        self.assertIn("Multiple producers", self.command("freshness", expected=1).stderr)
        data["tasks"]["decay"]["outputs"] = ["figures/decay.svg"]
        path.write_text(json.dumps(data))
        experiment = self.project / "experiments.json"
        numeric = json.loads(experiment.read_text())
        numeric["tasks"]["decay"]["inputs"].append("figures/decay.svg")
        experiment.write_text(json.dumps(numeric))
        data["tasks"]["decay"]["inputs"] = ["results/decay.json"]
        path.write_text(json.dumps(data))
        self.assertIn("Cyclic research", self.command("freshness", expected=1).stderr)

    def test_declared_relative_executable_works_from_another_cwd(self):
        self.example()
        wrapper = self.project / "tools/python"
        wrapper.parent.mkdir()
        wrapper.symlink_to(sys.executable)
        path = self.project / "experiments.json"
        data = json.loads(path.read_text())
        data["tasks"]["decay"]["command"][0] = "tools/python"
        path.write_text(json.dumps(data))
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), "run", "--project", str(self.project), "--task", "decay"], cwd=self.project.parent,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_provenance_symlink_escape_cannot_write_outside_project(self):
        self.example()
        (self.project / "results").mkdir()
        with tempfile.TemporaryDirectory(prefix="workbench-external-") as directory:
            (self.project / "results/runs").symlink_to(directory)
            self.command("run", "--task", "decay", expected=1)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_configure_and_profile_dry_runs_never_write(self):
        before = self.snapshot()
        self.assertEqual(self.cli("init", "--profile", "numerical", "--dry-run"), 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.cli("init", "--profile", "numerical"), 0)
        before = self.snapshot()
        self.assertEqual(self.cli("configure", "--disable", "numerics", "--dry-run"), 0)
        self.assertEqual(before, self.snapshot())

    def test_notes_only_edits_do_not_run_numerical_checks_or_require_fresh_results(self):
        self.example()
        path = self.project / "notes/session-state.md"
        path.write_text(path.read_text() + "\nA new question.\n")
        plan = json.loads(self.command("plan", "--files", "notes/session-state.md", "--json").stdout)
        self.assertEqual(plan["research_modules"], ["notes"])
        result = self.command("validate", "--files", "notes/session-state.md")
        self.assertNotIn("check_decay.py", result.stdout)
        self.assertEqual(self.records(), [])


if __name__ == "__main__":
    unittest.main()
