"""Regressions for the architecture review's installed workflow failures."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from test_support import isolate_environment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap
import core
import schema
import latex
import research
import runtime


class ReviewFixes(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-review-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def install(self, *arguments, env=None):
        return subprocess.run([sys.executable, "-B", str(bootstrap.PACKAGE / "latex-ai-init"),
                               "init", str(self.project), *arguments], env=env, capture_output=True, text=True)

    def task_project(self, tasks, freshness=True):
        config = {'schema_version': 3, 'modules': {'numerics': {}, 'provenance': {}}}
        if freshness:
            config["modules"]["freshness"] = {}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        (self.project / "experiments.json").write_text(json.dumps({"schema_version": 1, "tasks": tasks}))
        return config

    def test_deleted_inferred_dependencies_select_and_fail_validation(self):
        p = self.project
        (p / "input").write_text("one")
        for name in ("runner.py", "check.py", "env.py"):
            (p / name).write_text("from pathlib import Path\nPath('result').write_text('result')\n")
        task = {"command": [sys.executable, "runner.py"], "inputs": ["input"], "outputs": ["result"],
                "checks": [{"command": [sys.executable, "check.py"], "cost": "cheap"}],
                "environment": {"command": [sys.executable, "env.py"]}}
        config = self.task_project({"calculate": task})
        with contextlib.redirect_stdout(io.StringIO()):
            research.execute(p, config, "numerics", "calculate")
        for name in ("runner.py", "check.py", "env.py"):
            with self.subTest(dependency=name):
                original = (p / name).read_bytes()
                (p / name).unlink()
                plan = runtime.validation_plan(p, config, [name])
                self.assertIn("research", plan["actions"])
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(core.WorkbenchError):
                    runtime.validate_changes(p, plan)
                (p / name).write_bytes(original)

    def test_deleted_extensionless_launcher_is_still_affected(self):
        p = self.project
        (p / "input").write_text("input")
        (p / "runner").write_text("#!/usr/bin/env python3\n")
        config = self.task_project({"run": {"command": ["./runner"], "inputs": ["input"], "outputs": ["out"]}})
        (p / "runner").unlink()
        self.assertIn("numerics", research.affected(p, config, ["runner"]))

    def test_deleted_arbitrary_file_argument_is_preserved_from_history(self):
        p = self.project
        (p / "input").write_text("input")
        (p / "settings").write_text("config")
        (p / "runner.py").write_text("from pathlib import Path\nPath('out').write_text('result')\n")
        config = self.task_project({"calculate": {"command": [sys.executable, "runner.py", "settings"],
                                                "inputs": ["input"], "outputs": ["out"]}})
        with contextlib.redirect_stdout(io.StringIO()):
            research.execute(p, config, "numerics", "calculate")
        (p / "settings").unlink()
        self.assertIn("numerics", research.affected(p, config, ["settings"]))
        self.assertEqual(research.freshness(p, config)[0]["status"], "stale")

    def test_script_shaped_option_value_is_not_a_missing_dependency(self):
        p = self.project
        (p / "input").write_text("input")
        (p / "runner.py").write_text("import argparse\nfrom pathlib import Path\np = argparse.ArgumentParser()\np.add_argument('--tag')\np.parse_args()\nPath('out').write_text('result')\n")
        config = self.task_project({"calculate": {"command": [sys.executable, "runner.py", "--tag", "study.py"],
                                                "inputs": ["input"], "outputs": ["out"]}})
        with contextlib.redirect_stdout(io.StringIO()):
            research.execute(p, config, "numerics", "calculate")
        self.assertEqual(research.freshness(p, config)[0]["status"], "current")


    def test_status_guidance_orders_cross_module_producers_first(self):
        p = self.project
        (p / "input").write_text("input")
        config = self.task_project({"consumer": {"command": ["true"], "inputs": ["plot"], "outputs": ["out"]}})
        config["modules"]["figures"] = {}
        (p / core.CONFIG).write_text(json.dumps(config))
        (p / "figures").mkdir()
        (p / "figures/manifest.json").write_text(json.dumps({"schema_version": 1, "tasks": {
            "producer": {"command": ["true"], "inputs": ["input"], "outputs": ["plot"]}}}))
        self.assertEqual(self.install().returncode, 0)
        result = subprocess.run(["make", "status"], cwd=p, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        steps = result.stdout.split("Next:")[1]
        self.assertLess(steps.index("make figure TASK=producer"), steps.index("make run TASK=consumer"))

    def test_invalid_graph_fails_before_execution_with_or_without_freshness(self):
        p = self.project
        (p / "input").write_text("input")
        command = [sys.executable, "-c", "from pathlib import Path; Path('out').write_text('written')"]
        task = {"command": command, "inputs": ["input"], "outputs": ["out"]}
        for freshness in (True, False):
            with self.subTest(freshness=freshness):
                config = self.task_project({"a": task, "b": task}, freshness)
                with self.assertRaisesRegex(core.WorkbenchError, "Multiple producers"):
                    research.execute(p, config, "numerics", "a")
                self.assertFalse((p / "out").exists())
                self.assertFalse((p / "results").exists())

    def test_cycles_fail_before_execution_without_freshness(self):
        p = self.project
        (p / "one").write_text("old"); (p / "two").write_text("old")
        tasks = {"a": {"command": ["true"], "inputs": ["two"], "outputs": ["one"]},
                 "b": {"command": ["true"], "inputs": ["one"], "outputs": ["two"]}}
        config = self.task_project(tasks, False)
        with self.assertRaisesRegex(core.WorkbenchError, "Cyclic"):
            research.execute(p, config, "numerics", "a")

    def test_refresh_guidance_is_topological_across_modules(self):
        p = self.project
        (p / "input").write_text("input")
        tasks = {"consumer": {"command": ["true"], "inputs": ["middle"], "outputs": ["last"]},
                 "producer": {"command": ["true"], "inputs": ["input"], "outputs": ["middle"]}}
        config = self.task_project(tasks)
        (p / "Makefile").write_text("latex-ai-run:\n\t@true\nrun: latex-ai-run\n")
        self.assertEqual(research.refresh_commands(p, research.freshness(p, config)),
                         ["make run TASK=producer", "make run TASK=consumer"])

    def test_installation_and_audit_without_git(self):
        tools = self.project / "tools"; tools.mkdir()
        for name in ("make", "python3"):
            (tools / name).symlink_to(shutil.which(name))
        # Hermetic: CI exports LATEX_AI_BASE, all zeros on a new branch, which would replace the Git diagnosis.
        env = {**{k: v for k, v in os.environ.items() if k != "LATEX_AI_BASE"}, "PATH": str(tools)}
        result = self.install("--profile", "core", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([sys.executable, str(bootstrap.PACKAGE / "latex-ai-init"), "audit", str(self.project)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([sys.executable, str(self.project / ".latex-ai/workbench.py"), "validate", "--project", str(self.project)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Git is not installed", result.stdout)

    def test_json_results_capture_child_output_and_preserve_exit_status(self):
        p = self.project
        self.assertEqual(self.install("--profile", "numerical").returncode, 0)
        (p / "input").write_text("input")
        task = {"command": [sys.executable, "-c", "import sys; from pathlib import Path; sys.stdout.buffer.write(b'child output \\xff\\n'); Path('out').write_text('value')"],
                "inputs": ["input"], "outputs": ["out"]}
        (p / "experiments.json").write_text(json.dumps({"schema_version": 1, "tasks": {"calculate": task}}))
        for action, extra in (("run", ["--task", "calculate"]), ("status", []), ("check", [])):
            result = subprocess.run([sys.executable, str(p / ".latex-ai/workbench.py"), action, "--project", str(p), "--json", *extra],
                                    capture_output=True, text=True)
            data = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, data)
            self.assertEqual(data["exit_status"], 0)
            self.assertIsInstance(data["result"], dict)
            if action == "run":
                self.assertIn("child output", data["stdout"])
                self.assertEqual(data["result"]["status"], "success")
        (p / "input").write_text("changed")
        result = subprocess.run([sys.executable, str(p / ".latex-ai/workbench.py"), "check", "--project", str(p), "--json"],
                                capture_output=True, text=True)
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data["status"], "failed")
        self.assertIn("Stale", data["stderr"])

    def test_portability_preflight_has_a_report_without_a_traceback(self):
        tools = self.project / "tools"; tools.mkdir()
        result = subprocess.run([sys.executable, str(bootstrap.PACKAGE / "tests/portability.py"),
                                 "--output-parent", str(self.project)], env={**os.environ, "PATH": str(tools)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing tools:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(next(self.project.glob("latex-ai-portability-*/report.json")).read_text())
        self.assertEqual(report["status"], "blocked")
        self.assertIn("chktex", report["missing_tools"])

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "needs pdfLaTeX")
    def test_default_build_receipt_rejects_stale_verify_and_export(self):
        p = self.project
        source = p / "main.tex"
        source.write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'lint': {'enabled': False}, 'output_dir': '.'}}}}, 'integrations': {'ci': {'pdf_artifact': True}}}
        with contextlib.redirect_stdout(io.StringIO()):
            latex.build(p, schema.document_settings(config))
            latex.build(p, schema.document_settings(config))
            source.write_text(source.read_text().replace("Fixture", "\\undefinedcommand"))
            for action in (latex.verify, latex.artifact):
                with self.subTest(action=action.__name__), self.assertRaisesRegex(core.WorkbenchError, "freshness|receipt"):
                    action(p, schema.document_settings(config))
            with self.assertRaises(core.WorkbenchError):
                latex.build(p, schema.document_settings(config))
            source.write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
            with self.assertRaises(core.WorkbenchError):
                latex.verify(p, schema.document_settings(config))

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "needs pdfLaTeX")
    def test_existing_make_target_and_custom_build_work_together(self):
        p = self.project
        (p / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        (p / "Makefile").write_text("build: pdf\npdf:\n\t@echo compiler >> calls\n\tlatexmk -pdf -recorder -interaction=nonstopmode -halt-on-error main.tex\nlint:\n\t@true\ncheck: build lint\n")
        result = self.install("--engine", "pdflatex", "--build-command", '["make","pdf"]', "--no-lint", "--no-ci", "--skip-editor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for count in range(1, 3):
            result = subprocess.run(["make", "-j4", "check"], cwd=p, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len((p / "calls").read_text().splitlines()), count)
        self.assertIn("build: pdf", (p / "Makefile").read_text())
        self.assertEqual(latex.read_receipt(p, schema.document_settings(schema.load_config(p)))["status"], "verified")
        # An unchanged raw project build retains its valid receipt. The reserved
        # wrapper is what establishes a new one after inputs or outputs change.
        receipt = (p / latex.receipt_path(schema.document_settings(schema.load_config(p)))).read_bytes()
        result = subprocess.run(["make", "pdf"], cwd=p, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((p / latex.receipt_path(schema.document_settings(schema.load_config(p)))).read_bytes(), receipt)

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "needs pdfLaTeX")
    def test_declared_adopted_default_build_preserves_its_command(self):
        p = self.project
        (p / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        (p / "Makefile").write_text("build:\n\t@echo MY_BUILD\n\tlatexmk -pdf -recorder -interaction=nonstopmode -halt-on-error main.tex\nlint:\n\t@true\n")
        config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'lint': {'enabled': False}, 'output_dir': '.', 'build_command': ['make', 'build']}}}}}
        (p / core.CONFIG).write_text(json.dumps(config))
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run(["make", "check"], cwd=p, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("MY_BUILD"), 1)

    def test_adopted_make_build_claim_blocks_overlapping_builds(self):
        p = self.project
        (p / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        (p / "builder.py").write_text("from pathlib import Path\nimport time\nPath('started').touch()\nwhile not Path('release').exists(): time.sleep(.02)\nPath('main.pdf').write_bytes(b'%PDF-fixture\\n')\nPath('main.log').write_text('Fixture compile complete\\n')\n")
        (p / "Makefile").write_text("build: pdf\npdf:\n\t$(PYTHON) builder.py\nlint:\n\t@true\ncheck: build lint\n")
        result = self.install("--engine", "pdflatex", "--build-command", '["make","pdf"]', "--no-lint", "--no-ci", "--skip-editor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        first = subprocess.Popen(["make", "-j4", "check"], cwd=p, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not (p / "started").exists() and first.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((p / "started").exists())
            second = subprocess.run(["make", "-j4", "check"], cwd=p, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("Another build", second.stderr)
            config = schema.load_config(p)
            with self.assertRaisesRegex(core.WorkbenchError, "Another build"):
                latex.build(p, schema.document_settings(config))
            with self.assertRaisesRegex(core.WorkbenchError, "freshness|receipt|build is active"):
                latex.artifact(p, config)
        finally:
            (p / "release").touch()
            stdout, stderr = first.communicate(timeout=5)
        self.assertEqual(first.returncode, 0, stdout + stderr)
        self.assertEqual(latex.read_receipt(p, schema.document_settings(schema.load_config(p)))["status"], "verified")

    def test_adopted_make_aliases_default_goal_and_direct_runtime_share_receipts(self):
        p = self.project
        (p / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        (p / "builder.py").write_text("from pathlib import Path\nwith Path('calls').open('a') as f: f.write('compiler\\n')\nPath('main.pdf').write_bytes(b'%PDF-fixture\\n')\nPath('main.log').write_text('Fixture compile complete\\n')\n")
        (p / "Makefile").write_text("CHECK_TARGET = check\nall: $(CHECK_TARGET)\npdf:\n\t$(PYTHON) builder.py\nlint:\n\t@true\n")
        result = self.install("--engine", "pdflatex", "--build-command", '["make","pdf"]', "--no-lint", "--no-ci", "--skip-editor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for count, goal in enumerate((None, "build", "latex-ai-integrity", "latex-ai-check-passed", "all"), 1):
            result = subprocess.run(["make", "-j4", *([goal] if goal else [])], cwd=p, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len((p / "calls").read_text().splitlines()), count)
            self.assertEqual(latex.read_receipt(p, schema.document_settings(schema.load_config(p)))["status"], "verified")
        receipt = (p / latex.receipt_path(schema.document_settings(schema.load_config(p)))).read_bytes()
        for goal in ("help", "status", "validation-plan"):
            result = subprocess.run(["make", goal], cwd=p, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((p / latex.receipt_path(schema.document_settings(schema.load_config(p)))).read_bytes(), receipt)
        with contextlib.redirect_stdout(io.StringIO()):
            latex.build(p, schema.document_settings(schema.load_config(p)))
        self.assertEqual(len((p / "calls").read_text().splitlines()), 6)
        self.assertEqual(latex.read_receipt(p, schema.document_settings(schema.load_config(p)))["status"], "verified")

    def test_adopted_make_phases_reject_recursive_wrapper_delegation(self):
        p = self.project
        (p / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        # A fixture cap makes a broken recursion guard fail promptly, not hang.
        (p / "builder.py").write_text("from pathlib import Path\nimport subprocess\np = Path('calls')\nn = int(p.read_text()) + 1 if p.exists() else 1\np.write_text(str(n))\nif n >= 4: raise SystemExit(2)\nraise SystemExit(subprocess.call(['make', 'latex-ai-build']))\n")
        (p / "Makefile").write_text("build: pdf\npdf:\n\t$(PYTHON) builder.py\nlint:\n\t@true\n")
        result = self.install("--engine", "pdflatex", "--build-command", '["make","pdf"]', "--no-lint", "--no-ci", "--skip-editor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([sys.executable, str(p / ".latex-ai/workbench.py"), "build", "--project", str(p)],
                                capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Recursive build_command", result.stderr)
        self.assertEqual((p / "calls").read_text(), "1")
        self.assertNotEqual(latex.read_receipt(p, schema.document_settings(schema.load_config(p)))["status"], "verified")

    def test_adopted_make_file_targets_keep_incremental_behavior(self):
        p = self.project
        source = p / "main.tex"
        source.write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        (p / "builder.py").write_text("from pathlib import Path\nwith Path('calls').open('a') as f: f.write('compiler\\n')\nPath('main.pdf').write_bytes(b'%PDF-fixture\\n')\nPath('main.log').write_text('Fixture compile complete\\n')\n")
        (p / "Makefile").write_text("build: pdf\npdf: main.pdf\nmain.pdf: main.tex builder.py\n\t$(PYTHON) builder.py\nlint:\n\t@true\ncheck: build lint\n")
        result = self.install("--engine", "pdflatex", "--build-command", '["make","pdf"]', "--no-lint", "--no-ci", "--skip-editor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for expected in (1, 1, 2):
            if expected == 2:
                source.write_text(source.read_text().replace("Fixture", "Changed"))
            result = subprocess.run(["make", "-j4", "check"], cwd=p, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len((p / "calls").read_text().splitlines()), expected)
            self.assertEqual(latex.read_receipt(p, schema.document_settings(schema.load_config(p)))["status"], "verified")


if __name__ == "__main__":
    unittest.main()
