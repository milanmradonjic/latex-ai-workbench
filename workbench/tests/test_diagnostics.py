"""Tests of the doctor, the issue report and the labelling of internal faults.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 5 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_blind_repairs.py:
Installed-workflow regressions from the ten blind reviewers (current schema only).

test_modules.py:
(no docstring)

test_repairs_3_0_2.py:
Regressions from the architecture audit of 3.0.1 (docs/maintainers/architecture-audit-3.0.1.md).

Each test failed before its repair. Findings are named by their audit number (F1, F2, ...).

test_scope_4_9_0.py:
Workbench 4.9.0, step 3.7 of docs/maintainers/plan-after-4.4.0.md: the doctor's stamp report, and the update recipe in the skill file.

`make doctor` has always checked the tools. It now also reports the project's stamp: what `.latex-ai/installation.json` records, what the vendored runtime is, and which runtime
files were edited or are missing. Given the folder of a release (`LATEX_AI_TEMPLATE=/path/to/workbench`, or `--template`) it adds the template's side by running that
release's own `latex-ai-init diff`, so there is one rule for what differs, and writes nothing. The update recipe an agent follows is in the skill file; `docs/upgrading.md` points to it.

test_workbench.py:
(no docstring)
"""

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap as boot
import core
import diagnostics
import runtime as rt
import schema
from test_support import ProjectCase, fixture_env, isolate_environment, own_targets


SOURCE = "\\documentclass{article}\n\\begin{document}A note.\\end{document}\n"


RECORD = ".latex-ai/installation.json"


TEX = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


class BlindRepairTests(unittest.TestCase):
    """Origin: tests/test_blind_repairs.py."""

    def setUp(self):
        isolate_environment(self)
        self.directory = tempfile.TemporaryDirectory(prefix="workbench-blind-fix-")
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name).resolve()

    def command(self, *argv, cwd=None, expected=0):
        result = subprocess.run(argv, cwd=cwd or self.project, env=fixture_env(),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def install(self, *args, expected=0):
        return self.command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"),
                            *args, expected=expected)

    def fixture(self, project=None, custom=True, hidden=False):
        project = project or self.project
        (project / "tex/nested").mkdir(parents=True)
        text = SOURCE if not hidden else SOURCE.replace("A note.", "\\def\\partname{hidden}\\input{\\partname}")
        (project / "tex/nested/paper.tex").write_text(text)
        if hidden:
            (project / ("hidden.tex" if custom else "tex/nested/hidden.tex")).write_text("Original source.\n")
        settings = {"root": "tex/nested/paper.tex", "lint": {"enabled": False}, "output_dir": "custom/output with spaces"}
        if custom:
            settings["build_command"] = ["latexmk", "-pdf", "-recorder", "-interaction=nonstopmode",
                                         "-halt-on-error", "-outdir=custom/output with spaces", "tex/nested/paper.tex"]
        config = {"schema_version": 3, "modules": {"latex": {"default_document": "paper", "documents": {"paper": settings}}}}
        (project / core.CONFIG).write_text(json.dumps(config))
        self.install("init", str(project))
        return config

    def test_foreign_installed_runtime_reports_project_context_not_internal_fault(self):
        notebook = self.project / "notebook"
        notebook.mkdir()
        self.install("init", str(notebook), "--modules", "")
        self.fixture()
        script = notebook / ".latex-ai/workbench.py"
        result = self.command(sys.executable, str(script), "status", "--json", expected=1)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "failed")
        self.assertIn("--project", data["stderr"])
        self.command(sys.executable, str(script), "status", "--project", str(notebook))
        (notebook / core.CONFIG).write_text("{broken")
        self.command(sys.executable, str(script), "status", cwd=notebook)


class ModuleTests(unittest.TestCase):
    """Origin: tests/test_modules.py."""

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
        """A small LaTeX project with the workbench installed."""
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nExample.\n\\end{document}\n")
        self.assertEqual(self.cli("init", "--no-lint", "--skip-editor"), 0)
        return schema.load_config(self.project)

    def run_main(self, *arguments):
        errors = io.StringIO()
        with patch.object(sys, "argv", ["workbench", *arguments, "--project", str(self.project)]), contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            return rt.main(), errors.getvalue()

    def test_internal_faults_are_labelled_apart_from_ordinary_errors_and_never_written_into_the_project(self):
        self.assertEqual(self.cli("init", "--modules", ""), 0)
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

    def test_issue_report_collects_local_evidence_and_nothing_else(self):
        self.example()
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
        self.assertIn("python", report["tools"])
        self.assertEqual(report["configuration"]["schema_version"], 3)
        # A locally edited managed file is exactly what explains an upgrade conflict, so the report names it.
        with (self.project / ".latex-ai/guide.py").open("a") as stream:
            stream.write("\n# local tweak\n")
        self.command("issue")
        newest = json.loads(max((self.project / ".latex-ai/artifacts/issues").glob("report-*.json")).read_text())
        self.assertEqual(newest["installation"]["files"][".latex-ai/guide.py"], "modified locally")
        self.assertEqual(newest["installation"]["differing"], [".latex-ai/guide.py"])
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
        with (self.project / ".latex-ai/documents.py").open("a") as stream:
            stream.write("\ndef dependency_index(project, config, paths=None):\n    raise KeyError('checks')\n")
        crash = self.command("plan", "--files", "main.tex", expected=rt.INTERNAL_FAULT)
        self.assertIn("INTERNAL ERROR: KeyError: 'checks'", crash.stderr)
        done = self.command("issue", "--files", "main.tex", "--note", "plan crashed")
        self.assertIn("Issue report written", done.stdout)
        report = self.latest_report()
        self.assertIn("KeyError", report["plan"]["unavailable"])
        self.assertEqual(report["observed_and_expected"], "plan crashed")
        self.assertEqual(report["configuration"]["schema_version"], 3)  # the rest of the evidence is intact
        self.assertEqual(len(report["recent_internal_faults"]), 1)  # and names the fault just seen

    def test_issue_report_survives_any_one_section_failing(self):
        self.example()
        sections = {"installation": "installation", "tool_versions": "tools", "git_state": "git",
                    "recent_faults": "recent_internal_faults"}
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
        self.assertEqual(self.cli("init", "--modules", ""), 0)
        hostile = 'observed "quoted"; touch INJECTED; echo "'
        done = subprocess.run(["make", "issue", f"ISSUE_NOTE={hostile}", "ISSUE_COMMAND=make check"], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse((self.project / "INJECTED").exists())
        report = json.loads(next((self.project / ".latex-ai/artifacts/issues").glob("report-*.json")).read_text())
        self.assertEqual((report["observed_and_expected"], report["command"]), (hostile, "make check"))

    def test_advertised_report_command_works_where_the_project_has_its_own_issue_target(self):
        # A project may take over the short `issue` and keep only `latex-ai-issue` for the workbench, so
        # whatever the guidance tells an agent to run must be the name that always reaches the report.
        self.assertEqual(self.cli("init", "--modules", ""), 0)
        own_targets(self.project, "issue", recipe="@touch PROJECT_ISSUE_RAN")
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
        guidance = {"runtime message": errors, "full policy": template,
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

    def cli_result(self, *args):
        out, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errors):
            status = boot.main([*args, str(self.project)])
        return status, out.getvalue(), errors.getvalue()

    def test_a_damaged_installation_record_gets_a_diagnosis_not_the_defect_label(self):
        self.assertEqual(self.cli("init", "--modules", ""), 0)
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
                status, _, errors = self.cli_result("runtime")  # writes the record again
                self.assertEqual(status, 0, errors)
                self.assertNotIn("INTERNAL ERROR", errors)
                self.assertEqual(json.loads((self.project / boot.STATE).read_text())["version"], core.VERSION)

    def test_doctor_reports_the_interpreter_that_runs_it(self):
        self.assertEqual(self.cli("init", "--modules", ""), 0)
        report = self.command("doctor").stdout
        self.assertIn(f"python: {sys.executable}", report)
        self.assertNotIn("python3:", report)  # the PATH lookup could name a different interpreter


class Repairs(ProjectCase):

    # --- F1: one lock per project, shared by everyone who works in it ----------------------------------

    """Origin: tests/test_repairs_3_0_2.py, workbench 3.0.2."""

    def test_fault_records_are_kept_per_user(self):
        if hasattr(os, "getuid"):
            self.assertIn(str(os.getuid()), str(diagnostics.fault_dir(self.project)))


class ConfigurationAudit(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE)
        self.configure()
        self.builder()
        self.install('init', '--skip-editor')

    def test_malformed_bibliography_is_an_input_error_in_either_module_order(self):
        config = json.loads((self.project / core.CONFIG).read_text())
        for value in (None, False, 0, '', [], [{}]):
            for first in ('latex', 'bibliography'):
                with self.subTest(value=value, first=first):
                    modules = {'latex': config['modules']['latex'], 'bibliography': value}
                    candidate = {**config, 'modules': {first: modules[first], **modules}}
                    (self.project / core.CONFIG).write_text(json.dumps(candidate))
                    result = self.command('check', expected=1)
                    self.assertIn('bibliography module configuration must be an object', result.stderr)
                    self.assertNotIn('INTERNAL ERROR', result.stderr)

    def test_doctor_names_a_missing_custom_builder(self):
        self.edit_config(lambda config: config['modules']['latex']['documents']['paper'].update(build_command=['./missing-builder']))
        result = self.command('doctor', expected=1)
        self.assertIn('./missing-builder: MISSING', result.stdout)
        self.assertIn('Missing required tools: ./missing-builder', result.stderr)

    def test_doctor_does_not_require_the_native_toolchain_for_a_custom_builder(self):
        tools = self.root / 'tools'
        tools.mkdir()
        make = tools / 'make'
        make.symlink_to(shutil.which('make'))
        result = self.command('doctor', env={**self.env, 'PATH': str(tools)})
        self.assertIn('All required tools found', result.stdout)
        self.assertNotIn('latexmk:', result.stdout)
        self.assertNotIn('pdflatex:', result.stdout)


class Doctor(ProjectCase):
    """Origin: tests/test_scope_4_9_0.py, workbench 4.9.0."""

    def setUp(self):
        super().setUp()
        self.install("init", "--skip-editor", "--modules", "")

    def doctor(self, *args, template=None, expected=0):
        env = {**self.env, **({"LATEX_AI_TEMPLATE": str(template)} if template else {})}
        return self.command("doctor", *args, env=env, expected=expected)

    def edit_record(self, change):
        path = self.project / RECORD
        record = json.loads(path.read_text())
        change(record)
        path.write_text(json.dumps(record))

    def test_the_stamp_of_a_project_that_matches_is_reported(self):
        out = self.doctor().stdout
        self.assertIn(f"stamp: {RECORD} records {core.VERSION}; the vendored runtime is {core.VERSION}\n", out)
        self.assertRegex(out, r"runtime files: all \d+ unmodified")
        self.assertIn("All required tools found", out)

    def test_an_edited_file_a_missing_one_and_a_record_of_another_version_are_named_and_the_doctor_still_passes(self):
        guide = self.project / ".latex-ai/guide.py"
        guide.write_text(guide.read_text() + "\n# edited by someone\n")
        self.edit_record(lambda record: (record["files"].update({".latex-ai/ghost.py": "0" * 64}), record.update(version="4.0.0")))
        out = self.doctor().stdout
        self.assertIn("records 4.0.0; the vendored runtime is " + core.VERSION + " (they differ)", out)
        self.assertIn(".latex-ai/guide.py (modified locally)", out)
        self.assertIn(".latex-ai/ghost.py (missing)", out)

    def test_a_record_that_cannot_be_read_is_named_and_does_not_stop_the_doctor(self):
        (self.project / RECORD).write_text("{not json")
        out = self.doctor().stdout
        self.assertRegex(out, rf"stamp: {re.escape(RECORD)} is unreadable")
        self.assertIn("All required tools found", out)

    def test_without_a_template_it_says_how_to_compare_with_one(self):
        out = self.doctor().stdout
        self.assertIn("template: not given; to compare with a release, make doctor LATEX_AI_TEMPLATE=/path/to/workbench", out)

    def test_nothing_is_written_into_the_project(self):
        before = self.snapshot()
        self.doctor(template=PACKAGE)
        self.assertEqual(self.snapshot(), before)


class MissingTool(ProjectCase):
    """Origin: tests/test_scope_4_9_0.py, workbench 4.9.0."""

    def test_the_stamp_is_printed_before_a_missing_tool_stops_the_doctor(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.install("init", "--skip-editor", "--no-lint")
        result = self.command("doctor", env={**self.env, "PATH": str(self.root / "nothing")}, expected=1)  # no latexmk, no make
        self.assertIn("stamp:", result.stdout)
        self.assertIn("latexmk: MISSING", result.stdout)
        self.assertIn("Missing required tools", result.stderr)


class Template(ProjectCase):
    """Origin: tests/test_scope_4_9_0.py, workbench 4.9.0."""

    def setUp(self):
        super().setUp()
        self.install("init", "--skip-editor", "--modules", "")

    def doctor(self, *args, template=None, expected=0):
        env = {**self.env, **({"LATEX_AI_TEMPLATE": str(template)} if template else {})}
        return self.command("doctor", *args, env=env, expected=expected)

    def test_it_gives_the_templates_version_and_says_that_nothing_differs(self):
        out = self.doctor(template=PACKAGE).stdout
        self.assertIn(f"template: {PACKAGE}", out)
        self.assertIn(f"Project runtime {core.VERSION}; this release {core.VERSION}; runtime files are identical.", out)

    def test_the_option_and_make_do_what_the_variable_does(self):
        self.assertIn(f"template: {PACKAGE}", self.doctor("--template", str(PACKAGE)).stdout)
        made = self.run_command("make", "doctor", f"LATEX_AI_TEMPLATE={PACKAGE}")
        self.assertIn(f"template: {PACKAGE}", made.stdout)

    def test_it_lists_the_runtime_files_and_the_generated_files_that_differ_and_the_doctor_still_passes(self):
        guide = self.project / ".latex-ai/guide.py"
        guide.write_text(guide.read_text() + "# an older guide\n")  # still runs, and no longer what the release has
        (self.project / "Makefile").write_text((self.project / "Makefile").read_text() + "# the project's own rule\n")
        out = self.doctor(template=PACKAGE).stdout
        self.assertIn("RUNTIME differs: .latex-ai/guide.py", out)
        self.assertIn("DIFFERS (a file you may have added to; read, do not overwrite): Makefile", out)
        self.assertIn("1 runtime file(s) differ.", out)

    def test_an_older_project_is_shown_against_the_template(self):
        record = json.loads((self.project / RECORD).read_text())
        record["version"] = "4.0.0"
        (self.project / RECORD).write_text(json.dumps(record))
        schema = self.project / ".latex-ai/schema.py"
        schema.write_text(schema.read_text() + "# an older schema\n")
        out = self.doctor(template=PACKAGE).stdout
        self.assertIn(f"stamp: {RECORD} records 4.0.0", out)
        self.assertIn(f"Project runtime 4.0.0; this release {core.VERSION}; 1 runtime file(s) differ.", out)

    def test_a_folder_that_is_not_a_workbench_is_refused_with_a_hint(self):
        result = self.doctor(template=self.root, expected=1)
        self.assertIn("is not a workbench folder", result.stderr)
        self.assertIn("latex-ai-init", result.stderr)
        self.assertIn("Hint:", result.stderr)

    def test_an_installer_that_refuses_is_reported_and_not_swallowed(self):
        fake = self.root / "fake"
        fake.mkdir()
        (fake / "core.py").write_text("")
        (fake / "latex-ai-init").write_text("import sys\nprint('boom: this release refuses the project', file=sys.stderr)\nsys.exit(2)\n")
        result = self.doctor(template=fake, expected=1)
        self.assertIn("boom: this release refuses the project", result.stderr)

    def test_the_template_is_only_read(self):
        copy = self.root / "template"
        shutil.copytree(PACKAGE, copy, ignore=shutil.ignore_patterns("__pycache__", "tests", "docs", "examples"))
        before = {path.relative_to(copy).as_posix(): path.read_bytes() for path in copy.rglob("*") if path.is_file()}
        env = {key: value for key, value in self.env.items() if key != "PYTHONDONTWRITEBYTECODE"}  # so that only the doctor's own care keeps bytecode out
        self.command("doctor", "--template", str(copy), env=env)
        after = {path.relative_to(copy).as_posix(): path.read_bytes() for path in copy.rglob("*") if path.is_file()}
        self.assertEqual(after, before, "running the installer left a file in the template (bytecode, for one)")


class WorkbenchTests(unittest.TestCase):
    """Origin: tests/test_workbench.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="latex-ai-unit-")
        self.project = Path(self.temp.name).resolve()
        (self.project / "paper.tex").write_text(TEX)

    def tearDown(self):
        self.temp.cleanup()

    def test_installer_separates_internal_defects_from_ordinary_errors(self):
        errors = io.StringIO()
        with patch.object(boot, "detect_config", side_effect=KeyError("missing")), contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            status = boot.main(["init", str(self.project)])
        self.assertEqual(status, 70)
        self.assertIn("INTERNAL ERROR: KeyError", errors.getvalue())
        for ordinary in (rt.WorkbenchError("conflict"), OSError("disk"), ValueError("json")):
            with self.subTest(ordinary=type(ordinary).__name__), patch.object(boot, "detect_config", side_effect=ordinary), \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(boot.main(["init", str(self.project)]), 2)


if __name__ == "__main__":
    unittest.main()
