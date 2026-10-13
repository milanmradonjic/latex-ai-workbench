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
from test_support import isolate_environment, own_targets
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap as boot
import core
import schema
import diagnostics
import guide
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
        """A small LaTeX project with the workbench installed."""
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nExample.\n\\end{document}\n")
        self.assertEqual(self.cli("init", "--engine", "pdflatex", "--no-lint", "--skip-editor"), 0)
        return schema.load_config(self.project)


    def test_core_install_without_tex_or_editor(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        self.assertFalse((self.project / ".latex-ai/latex.py").exists())
        self.assertFalse((self.project / ".vscode").exists())
        self.assertFalse((self.project / ".github").exists())
        self.command("check")
        doctor = self.command("doctor").stdout
        self.assertNotIn("latexmk", doctor)
        self.assertEqual(schema.load_config(self.project)["modules"], {})
        before = self.snapshot()
        self.assertEqual(self.cli("diff"), 0)  # read-only, and the runtime is this release's
        self.assertEqual(before, self.snapshot())

    def test_cli_options_before_and_after_project_are_equivalent(self):
        before = self.snapshot()
        reports = []
        for argv in (["init", "--profile", "core", str(self.project), "--dry-run", "--json"],
                     ["init", str(self.project), "--profile", "core", "--dry-run", "--json"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(boot.main(argv), 0)
            reports.append(json.loads(output.getvalue()))
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(before, self.snapshot())

    def test_disabled_latex_command_fails_before_tool_execution(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        self.assertIn("Module is disabled: latex", self.command("build", expected=1).stderr)

    def test_saving_a_text_file_validates_without_a_compiler(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        notes = self.project / "notes/session.md"
        notes.parent.mkdir()
        notes.write_text("A question about physics.\n")
        self.command("validate", "--files", "notes/session.md")
        before = self.snapshot()
        self.assertEqual(self.cli("diff"), 0)  # read-only, and the runtime is this release's
        self.assertEqual(before, self.snapshot())

    def test_missing_history_never_introduces_disabled_modules(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        plan = json.loads(self.command("plan", "--json").stdout)
        self.assertTrue(plan["fallback"])
        self.assertFalse(plan["manuscript"])
        self.assertFalse(plan["portability"])
        self.command("validate")

    def test_profile_does_not_override_installed_choices(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        before = self.snapshot()
        self.assertEqual(self.cli("init", "--profile", "core"), 2)  # a project that has the workbench is not created again
        self.assertEqual(before, self.snapshot())

    def test_unknown_modules_and_settings_are_rejected(self):
        for modules in ({"magic": {}}, {"notes": {}}, {"numerics": {}}, {"bibliography": {"unknown_key": 1}}):
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

    def run_main(self, *arguments):
        errors = io.StringIO()
        with patch.object(sys, "argv", ["workbench", *arguments, "--project", str(self.project)]), contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            return rt.main(), errors.getvalue()

    def test_internal_faults_are_labelled_apart_from_ordinary_errors_and_never_written_into_the_project(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
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
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        hostile = 'observed "quoted"; touch INJECTED; echo "'
        done = subprocess.run(["make", "issue", f"ISSUE_NOTE={hostile}", "ISSUE_COMMAND=make check"], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse((self.project / "INJECTED").exists())
        report = json.loads(next((self.project / ".latex-ai/artifacts/issues").glob("report-*.json")).read_text())
        self.assertEqual((report["observed_and_expected"], report["command"]), (hostile, "make check"))

    def test_advertised_report_command_works_where_the_project_has_its_own_issue_target(self):
        # A project may take over the short `issue` and keep only `latex-ai-issue` for the workbench, so
        # whatever the guidance tells an agent to run must be the name that always reaches the report.
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
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

    def make_output(self, *arguments, expected=0):
        done = self.make_result(*arguments)
        self.assertEqual(done.returncode, expected, done.stdout + done.stderr)
        return done.stdout

    def test_help_lists_what_this_project_has_and_only_that(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        core_help = self.make_output("help")
        for line in ("make check", "make validate", "make status", "make doctor", "make help", "make issue"):
            self.assertIn(line, core_help)
        for absent in ("make build", "make pdf-artifact", "make document-check"):
            self.assertNotIn(absent, core_help)
        self.assertIn("Not enabled here", core_help)
        self.assertIn('"modules" in .latex-ai.json', core_help)
        shutil.rmtree(self.project)
        self.project.mkdir()
        self.example()
        help_text = self.make_output("help")
        for line in ("make build", "make document-check", "Documents: manuscript (default)"):
            self.assertIn(line, help_text)

    def test_help_names_the_command_that_reaches_the_workbench_when_the_project_has_its_own(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        own_targets(self.project, "help", recipe="@echo PROJECT_HELP")
        own_targets(self.project, "issue", recipe="@echo PROJECT_ISSUE")
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
        for profile in ("core", "writing"):
            with self.subTest(profile=profile):
                shutil.rmtree(self.project)
                self.project.mkdir()
                (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n")
                self.assertEqual(self.cli("init", "--profile", profile), 0)
                text = (self.project / "Makefile").read_text()
                targets = set(re.findall(r"^([A-Za-z][\w-]*)\s*:(?!=)", text, re.M))
                described = {name for command in guide.COMMANDS for name in (command.short, command.reserved) if name}
                self.assertEqual(sorted(targets - described), [])

    def test_status_reports_where_the_project_stands_and_what_to_do_next(self):
        self.example()
        before = self.snapshot()
        text = self.make_output("status")
        self.assertEqual(before, self.snapshot())  # read-only
        self.assertIn(f"{core.VERSION} installed, matches its record", text)
        self.assertIn("manuscript: missing", text)  # nothing has been built yet
        self.assertIn("make check", text.split("Next:")[1])

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
        status, errors = run("build")
        self.assertEqual(status, 1)
        self.assertIn("Module is disabled: latex", errors)
        self.assertIn('"modules" in .latex-ai.json', errors)
        with patch.object(shutil, "which", return_value=None):
            status, errors = run("doctor")
        self.assertIn("Missing required tools", errors)
        self.assertIn("make doctor", errors)

    def test_installer_summarises_in_plain_words_and_says_what_comes_next(self):
        (self.project / "main.tex").write_text(self.PAPER)
        status, text = self.cli_output("init", "--engine", "pdflatex", "--dry-run")
        self.assertIn("Dry run: nothing was changed", text)
        self.assertFalse((self.project / ".latex-ai/workbench.py").exists())
        status, text = self.cli_output("init", "--engine", "pdflatex")
        self.assertEqual(status, 0)
        self.assertRegex(text, r"Done: \d+ file\(s\) added")
        for command in ("make doctor", "make help", "make check"):
            self.assertIn(command, text)
        status, _, errors = self.cli_result("init", "--engine", "pdflatex")
        self.assertEqual(status, 2)
        self.assertIn("already has the workbench installed", errors)
        self.assertRegex(errors, r"Hint: .*runtime.*diff")

    # --- Release 2.3.2: findings of the review of 2.2.2-2.3.1 ---

    def test_policy_names_orientation_commands_that_reach_the_workbench(self):
        # The rule that made the report command `latex-ai-issue`: a project's own target of the short name is
        # kept, so guidance an agent follows blindly must name the command that always reaches the workbench.
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        own_targets(self.project, "help", recipe="@touch PROJECT_HELP_RAN")
        own_targets(self.project, "status", recipe="@touch PROJECT_STATUS_RAN")
        policies = {"full policy": (boot.PACKAGE / "templates/AGENTS.md").read_text(), "installed policy": (self.project / "AGENTS.md").read_text()}
        for name, text in policies.items():
            with self.subTest(policy=name):
                self.assertNotRegex(text, r"make (?:help|status)\b")
                for advertised in ("make latex-ai-help", "make latex-ai-status"):
                    self.assertIn(advertised, text)
        self.assertIn("LaTeX AI Workbench", self.make_output("latex-ai-status"))
        self.assertIn("make latex-ai-status", self.make_output("latex-ai-help"))
        self.assertFalse(any((self.project / name).exists() for name in ("PROJECT_HELP_RAN", "PROJECT_STATUS_RAN")))

    def test_status_does_not_count_the_projects_own_files_as_changed_installation_files(self):
        # Editor settings are merged with the project's own: editing them is the intended use, not a change to the installation.
        self.assertEqual(self.cli("init", "--profile", "core", "--editor"), 0)
        tasks = json.loads((self.project / ".vscode/tasks.json").read_text())
        tasks["tasks"].append({"label": "Mine", "type": "process", "command": "true"})
        (self.project / ".vscode/tasks.json").write_text(json.dumps(tasks))
        text = self.make_output("status")
        self.assertIn("0 managed file(s) changed locally", text)
        self.assertNotIn("tasks.json", text)
        self.assertIn("files differing from the record: none", self.command("issue").stdout)
        with (self.project / ".latex-ai/core.py").open("a") as stream:
            stream.write("\n# local tweak\n")
        text = self.make_output("status")
        self.assertIn("1 managed file(s) changed locally", text)
        self.assertIn(".latex-ai/core.py: modified locally", text)
        self.assertIn("files differing from the record: .latex-ai/core.py", self.command("issue").stdout)

    def test_a_projects_own_target_is_never_presented_as_the_workbench_command(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        own_targets(self.project, "doctor", recipe="@touch PROJECT_DOCTOR_RAN")
        listed = self.make_output("help")
        self.assertIn("make latex-ai-doctor", listed)
        for wrong in ("make doctor", "make clean", "make build", "make lint", "Manuscript"):
            self.assertNotIn(wrong, listed)  # no manuscript here, and `doctor` is now the project's own recipe
        self.assertIn("python:", self.make_output("latex-ai-doctor"))
        self.assertFalse((self.project / "PROJECT_DOCTOR_RAN").exists())
        with patch.object(shutil, "which", return_value=None):
            status, errors = self.run_main("doctor")
        self.assertIn("make latex-ai-doctor", errors)  # the advice to run it again names the command that works

    def test_every_workbench_command_but_the_shared_two_has_a_reserved_name(self):
        shared = {command.short for command in guide.COMMANDS if command.reserved is None}
        self.assertEqual(shared, {"check", "lint"})  # build has a receipt-producing reserved target
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n")
        self.assertEqual(self.cli("init", "--modules", "latex", "--engine", "pdflatex"), 0)
        own_targets(self.project, "doctor", "bib-check", "pdf-artifact", "clean", recipe="@echo MINE")
        targets = guide.make_targets((self.project / "Makefile").read_text())
        for name in ("doctor", "bib-check", "pdf-artifact"):
            self.assertIn("latex-ai-" + name, targets)
        self.assertIn("latex-ai-clean", targets)  # the selected document determines whether cleanup is supported
        self.assertEqual(self.make_output("clean").strip(), "MINE")
        self.assertEqual(self.make_output("doctor").strip(), "MINE")  # and the project's recipes are still its own

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
                status, _, errors = self.cli_result("runtime")  # writes the record again
                self.assertEqual(status, 0, errors)
                self.assertNotIn("INTERNAL ERROR", errors)
                self.assertEqual(json.loads((self.project / boot.STATE).read_text())["version"], core.VERSION)

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
        self.assertIn("latex-ai-init diff .", text.split("Next:")[1])

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

    def test_a_broken_json_file_is_named_in_the_error(self):
        self.example()
        path = self.project / core.CONFIG
        original = path.read_text()
        path.write_text('{"schema_version": 1,,}')
        status, errors = self.run_main("check")
        path.write_text(original)
        self.assertEqual(status, 1)
        self.assertIn(f"ERROR: {core.CONFIG} is not valid JSON", errors)
        self.assertIn("Hint:", errors)
        (self.project / "data.json").write_text("{broken")  # an ordinary project file, found by the file checks
        status, errors = self.run_main("validate", "--files", "data.json")
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
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
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

    def test_policy_never_names_a_short_form_the_project_may_own(self):
        policies = {"full policy": (boot.PACKAGE / "templates/AGENTS.md").read_text()}
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
        quickstart = (boot.PACKAGE / "docs/quickstart.md").read_text()
        for flag in ("--skip-editor"):
            self.assertIn(flag, quickstart)
        status, text = self.cli_output("init", "--skip-editor")
        self.assertEqual(status, 0)
        self.assertNotIn("NOTE: ", text)
        self.assertFalse((self.project / ".vscode").exists())
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
        (self.project / "main.tex").write_text(self.PAPER.replace("\\begin{document}", "\\usepackage{fontspec}\n\\begin{document}"))  # an engine the source does not name
        status, errors = attempt("init", str(self.project))
        self.assertEqual(status, 2)
        hint = errors.split("Hint:")[1]
        for phrase in ("pdflatex", "lualatex", "xelatex", "--engine"):
            self.assertIn(phrase, hint)
        (self.project / "main.tex").write_text(self.PAPER)
        self.assertEqual(attempt("init", str(self.project))[0], 0)
        status, errors = attempt("init", str(self.project), "--profile", "writing")
        self.assertEqual(status, 2)
        hint = errors.split("Hint:")[1]
        self.assertIn("runtime", hint)
        self.assertIn("diff", hint)

    def test_small_print_of_everyday_commands(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        env = {name: value for name, value in os.environ.items() if name not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "TASK", "LATEX_AI_BASE"}}
        shown = subprocess.run(["make", "help"], cwd=self.project, capture_output=True, text=True, env=env)  # no -s: the recipe itself is quiet
        self.assertTrue(shown.stdout.startswith("LaTeX AI Workbench"), shown.stdout[:120])
        with patch.object(shutil, "which", side_effect=lambda name: None if name == "chktex" else "/usr/bin/" + Path(name).name):
            status, errors = self.run_main("doctor")
        self.assertNotIn("TeX distribution", errors)  # a core project does not need one
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
        self.assertTrue(config["integrations"]["editor"])  # the default is unchanged
        self.assertTrue((self.project / ".vscode/settings.json").is_file())
        before = self.snapshot()
        self.assertEqual(self.cli("diff"), 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(schema.load_config(self.project)["schema_version"], 3)

    def test_one_command_table_drives_targets_actions_and_every_name_shown_to_readers(self):
        reserved = {command.reserved for command in guide.COMMANDS if command.reserved}
        self.assertEqual({command.action.split()[0] for command in guide.COMMANDS if command.action} - set(rt.ACTIONS), set())
        self.assertEqual(len(reserved), sum(1 for command in guide.COMMANDS if command.reserved))  # no reserved name twice
        # Internal targets of adapted Makefiles are the only latex-ai- names outside the table.
        internal = {"latex-ai-integrity", "latex-ai-core-check", "latex-ai-check-passed"}
        texts = {"full policy": (boot.PACKAGE / "templates/AGENTS.md").read_text(),
                 "skill": (boot.PACKAGE / "skills/latex-ai-workbench/SKILL.md").read_text()}
        texts.update({"docs/" + path.name: path.read_text() for path in sorted((boot.PACKAGE / "docs").glob("*.md"))})
        texts["README"] = (boot.PACKAGE / "README.md").read_text()
        for name, text in texts.items():
            with self.subTest(text=name):
                self.assertEqual(set(re.findall(r"\bmake (latex-ai-[a-z-]+)", text)) - reserved - internal, set())
        # The Makefile of every profile holds exactly the reserved targets its modules enable.
        for profile in ("core", "writing"):
            with self.subTest(profile=profile):
                self.fresh_project()
                (self.project / "main.tex").write_text(self.PAPER)
                self.assertEqual(self.cli("init", "--profile", profile), 0)
                config = schema.load_config(self.project)
                targets = guide.make_targets((self.project / "Makefile").read_text())
                expected = {command.reserved for command in guide.COMMANDS if command.reserved and guide.enabled(command, config)}
                self.assertEqual({name for name in targets if name.startswith("latex-ai-")} - internal, expected)
                self.assertEqual({command.short for command in guide.COMMANDS if command.reserved and guide.enabled(command, config)} - targets, set())  # and every alias

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
        policy = (boot.PACKAGE / "templates/AGENTS.md").read_text()
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

    def test_small_print_from_the_blind_trial(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        self.assertIn("All required tools found", self.command("doctor").stdout)
        quickstart = (boot.PACKAGE / "docs/quickstart.md").read_text()
        self.assertNotIn("fullest", quickstart)
        self.assertIn("make latex-ai-lint-baseline", quickstart)
        self.assertNotIn("`workbench/skills/latex-ai-workbench/`", (boot.PACKAGE / "templates/AGENTS.md").read_text())  # no path that an adopted project lacks

    def test_doctor_reports_the_interpreter_that_runs_it(self):
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        report = self.command("doctor").stdout
        self.assertIn(f"python: {sys.executable}", report)
        self.assertNotIn("python3:", report)  # the PATH lookup could name a different interpreter

    def test_dry_runs_and_diff_never_write(self):
        before = self.snapshot()
        self.assertEqual(self.cli("init", "--profile", "core", "--dry-run"), 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.cli("init", "--profile", "core"), 0)
        before = self.snapshot()
        self.assertEqual(self.cli("diff"), 0)
        self.assertEqual(self.cli("runtime", "--dry-run"), 0)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
