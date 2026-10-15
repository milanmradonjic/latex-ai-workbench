"""Tests of what the tool says to a person: the manual, help, status, the reasons and the hints.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 6 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_guide_3_0_1.py:
Orientation: the short manual (`make guide`), the reasons status gives, and the grouped help.

Until 4.2.0 the guide was a long generated handbook (pictures, topics, a web page). These tests keep what replaced it honest: every
command the manual names exists, it is written with the names that work in the project, and the read-only commands stay read-only.

test_modules.py:
(no docstring)

test_repairs_3_0_1.py:
Regressions found by the independent 3.0.0 audit; each one failed before its repair.

The fixtures come from ``test_support.ProjectCase``; the genuine latexmk/GNU Make scenarios are
skipped when those tools are absent.

test_scope_4_2_0.py:
Workbench 4.2.0 replaces the long generated handbook by a short manual (see docs/maintainers/minimal-scope.md).

These tests pin what is gone (the generator, the web page, the topics, the packaged copies) and that the manual that replaced it stays short.

test_scope_4_6_0.py:
Workbench 4.6.0, step 3.5 of docs/maintainers/plan-after-4.4.0.md: `make all`, and `make NAME` for each document of a project that has several.

`make all` builds every document, one after another (one runtime action, `build --all`, because the project's build lock refuses two builds at once and so
`make -j all` must not start them side by side). `make notes` builds that document, as `make build DOC=notes` does. The generated Makefile gains the targets on purpose:
`all` for every project with LaTeX, and a target per document when there are two or more, written only where the name is free. The bare `make` still builds the
default document. `make guide` names the targets, and `diff` shows an existing project the lines it lacks.

test_scope_4_9_1.py:
Workbench 4.9.1: the manual (`make guide`) after two independent readers used it.

Two agents were each given only the manual and a project (a newcomer's, with no Git; an owner's, with two documents under Git) and asked to work. What both
misread, or could not find, is fixed here, and each claim the manual now makes is held to what the tool does:

* a document is named with its file, and one never built is "not built yet" (it read as a missing file);
* where the PDF goes after `make build`, from the same rule the build uses;
* "verified build", read as "the checks passed", is gone from the states;
* `make all` stops at the first failure; an undefined reference or citation is an ERROR; an error does not always have a Hint;
* the snapshot commands need Git installed (the project need not use it) and print FILE for the reader to replace;
* `lint-baseline` is for style warnings, never an ERROR;
* what the agents ask about, in the words of the installed rules; where to read how to update; what `validate` does without Git.
"""

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
import guide
import latex
import runtime as rt
import schema
from test_support import ProjectCase, fixture_env, isolate_environment, own_targets


MAKE = bool(shutil.which("make"))


SOURCE = "\\documentclass{article}\n\\begin{document}Guide fixture.\\end{document}\n"


SOURCE_3_0_1 = "\\documentclass{article}\n\\begin{document}Audit fixture.\\end{document}\n"


MANUAL_LINES = 60  # a manual that cannot be read in a minute is a handbook again


BUILDER = ("import sys\nfrom pathlib import Path\nname = sys.argv[1]\n"
           "if Path('fail-' + name).exists():\n    sys.exit('simulated compiler failure for ' + name)\n"
           "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
           "(out / (name + '.pdf')).write_bytes(b'%PDF-fixture ' + name.encode())\n"
           "(out / (name + '.log')).write_text('Clean log\\n')\n"
           "(out / (name + '.fls')).write_text('PWD ' + str(Path.cwd()) + '\\nINPUT ' + name + '.tex\\n')\n")


SOURCE_4_6_0 = "\\documentclass{article}\\begin{document}x\\end{document}\n"


def document(name, **fields):
    return {"root": f"{name}.tex", "lint": {"enabled": False}, "output_dir": "outputs", "build_command": [sys.executable, "builder.py", name], **fields}


def configuration(*names, default=None, **fields):
    return {"schema_version": 3, "modules": {"latex": {"default_document": default or names[0], "documents": {name: document(name, **fields) for name in names}}},
            "integrations": {"editor": False}}


IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


MANUAL_LINES_4_9_1 = 60


class Orientation(ProjectCase):
    """Origin: tests/test_guide_3_0_1.py, workbench 3.0.1."""

    def paper(self, own=()):
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")
        self.own_targets(*own)

    def test_the_manual_shows_the_project_and_the_everyday_loop(self):
        self.paper()
        text = self.command("guide").stdout
        self.assertIn("manual for", text)
        self.assertRegex(text, r"Documents: paper = main.tex \(default\): not built yet")
        for command in ("make status", "make validation-plan", "make validate", "make check", "make build DOC=NAME", "make lint-baseline DOC=NAME"):
            self.assertIn(command, text)
        for state in ("current", "stale", "failed", "running", "missing"):
            self.assertRegex(text, rf"(?m)^  {state}\s")
        self.assertIn("INTERNAL ERROR", text)
        self.assertIn("AGENTS.md", text)
        self.assertEqual(self.command("guide").stdout, text)  # the same every time

    def test_the_guide_reads_and_writes_nothing(self):
        self.paper()
        before = self.snapshot()
        self.command("guide")
        self.assertEqual(self.snapshot(), before)

    def test_the_guide_works_when_the_configuration_is_broken(self):
        self.paper()
        (self.project / core.CONFIG).write_text("{ not json")
        result = self.command("guide")
        self.assertIn("Configuration problem", result.stdout)
        self.assertIn("make status", result.stdout)

    def test_the_manual_names_the_commands_this_makefile_really_has(self):
        self.paper(own=("build", "guide"))
        text = self.command("guide").stdout
        self.assertIn("make latex-ai-build DOC=NAME", text)
        self.assertNotRegex(text, r"make build\b")
        self.assertRegex(text, r"Names: your Makefile keeps its own target for `(guide`, `build|build`, `guide)`")
        self.assertIn("make latex-ai-guide", self.command("help").stdout)

    def test_every_command_the_manual_names_exists(self):
        self.paper()
        names = {command.short for command in guide.COMMANDS} | {command.reserved for command in guide.COMMANDS if command.reserved}
        for name in re.findall(r"make ([a-z][a-z-]*)", self.command("guide").stdout):
            if name not in {"sure"}:
                self.assertIn(name, names, name)

    def test_a_project_without_latex_gets_a_manual_without_documents(self):
        self.install("init", "--modules", "")
        text = self.command("guide").stdout
        self.assertIn("Modules: none (core only)", text)
        self.assertNotIn("make build", text)
        self.assertNotIn("What a document's state means", text)

    @unittest.skipUnless(MAKE, "GNU Make required")
    def test_make_prints_the_manual(self):
        self.paper()
        self.assertIn("The everyday loop", self.run_command("make", "guide").stdout)
        self.assertIn("The everyday loop", self.run_command("make", "latex-ai-guide").stdout)

    @unittest.skipUnless(MAKE, "GNU Make required")
    def test_a_project_target_named_guide_is_kept(self):
        self.paper(own=("guide",))
        self.assertEqual(self.run_command("make", "guide").stdout.strip(), "mine")
        self.assertIn("The everyday loop", self.run_command("make", "latex-ai-guide").stdout)

    def test_help_has_one_heading_per_group_and_points_to_the_guide(self):
        self.paper()
        text = self.command("help").stdout
        groups = {command.group for command in guide.COMMANDS}
        headings = [line for line in text.splitlines() if line in groups]
        self.assertEqual(headings, list(dict.fromkeys(headings)), headings)
        self.assertRegex(text, r"(?m)^Start here: .*status.*guide")
        self.assertRegex(text, r"(?m)^\s+make guide\s")
        self.assertNotIn("guide-html", text)
        self.assertIn("make guide", text.splitlines()[-1])

    def built(self):
        self.paper()
        self.command("build")
        self.assertEqual(self.state(), "current")

    def reasons(self):
        return json.loads(self.command("status", "--json").stdout)["result"]["documents"][0].get("reasons")

    def test_status_names_the_sources_that_changed(self):
        self.built()
        (self.project / "main.tex").write_text(SOURCE + "% edited\n")
        text = self.command("status").stdout
        self.assertRegex(text, r"paper: stale .*\n\s+changed since the build: main\.tex")
        self.assertEqual(self.reasons(), ["changed since the build: main.tex"])

    def test_status_names_the_settings_that_changed(self):
        self.built()
        config = json.loads((self.project / core.CONFIG).read_text())
        config["modules"]["latex"]["documents"]["paper"]["backend"] = "bibtex"
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.assertEqual(self.reasons(), ["build settings changed: bibliography"])

    def test_status_says_when_the_outputs_no_longer_match(self):
        self.built()
        (self.project / "outputs/main.pdf").write_bytes(b"replaced")
        self.assertEqual(self.reasons(), ["output changed since the build: outputs/main.pdf"])
        (self.project / "outputs/main.pdf").unlink()
        self.assertEqual(self.reasons(), ["output missing: outputs/main.pdf"])

    def test_a_current_document_has_no_reasons(self):
        self.built()
        self.assertIsNone(self.reasons())

    def test_many_changed_sources_are_summarised(self):
        (self.project / "main.tex").write_text(SOURCE)
        names = [f"part{number}.txt" for number in range(7)]
        for name in names:
            (self.project / name).write_text("1\n")
        self.builder(inputs=("main.tex", *names))
        self.configure()
        self.install("init", "--skip-editor")
        self.command("build")
        for name in names:
            (self.project / name).write_text("2\n")
        reasons = self.reasons()
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn("and 3 more", reasons[0])


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
        self.assertEqual(self.cli("init", "--modules", ""), 0)
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
        self.assertEqual(self.cli("init", "--modules", ""), 0)
        own_targets(self.project, "help", recipe="@echo PROJECT_HELP")
        own_targets(self.project, "issue", recipe="@echo PROJECT_ISSUE")
        self.assertEqual(self.make_output("help").strip(), "PROJECT_HELP")  # the project's target is kept
        text = self.make_output("latex-ai-help")
        self.assertIn("make latex-ai-help", text)
        self.assertIn("make latex-ai-issue", text)
        self.assertNotIn("make issue", text)
        self.assertIn("make status", text)  # an alias nothing else uses stays short

    def test_help_survives_a_broken_configuration(self):
        self.assertEqual(self.cli("init", "--modules", ""), 0)
        (self.project / core.CONFIG).write_text("{not json")
        text = self.make_output("help")
        self.assertIn("Configuration problem", text)
        self.assertIn("make check", text)

    def test_every_installed_make_target_is_described_by_help(self):
        for modules in ("", "latex"):
            with self.subTest(modules=modules):
                shutil.rmtree(self.project)
                self.project.mkdir()
                (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n")
                self.assertEqual(self.cli("init", "--modules", modules), 0)
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
        self.assertEqual(self.cli("init", "--modules", ""), 0)
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

    def test_common_errors_say_what_to_do_next(self):
        run = lambda *arguments: self.run_main(*arguments)  # noqa: E731
        empty = Path(tempfile.mkdtemp(prefix="workbench-empty-"))
        self.addCleanup(shutil.rmtree, empty, True)
        with patch.object(sys, "argv", ["workbench", "check", "--project", str(empty)]), contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(rt.main(), 1)
        self.assertIn("no workbench installed", errors.getvalue())
        self.assertIn("latex-ai-init init .", errors.getvalue())
        self.assertEqual(self.cli("init", "--modules", ""), 0)
        status, errors = run("build")
        self.assertEqual(status, 1)
        self.assertIn("Module is disabled: latex", errors)
        self.assertIn('"modules" in .latex-ai.json', errors)
        with patch.object(shutil, "which", return_value=None):
            status, errors = run("doctor")
        self.assertIn("Missing required tools", errors)
        self.assertIn("make doctor", errors)

    def test_status_does_not_count_the_projects_own_files_as_changed_installation_files(self):
        # Editor settings are merged with the project's own: editing them is the intended use, not a change to the installation.
        self.assertEqual(self.cli("init", "--modules", "", "--editor"), 0)
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
        self.assertEqual(self.cli("init", "--modules", ""), 0)
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
        self.assertEqual(self.cli("init", "--modules", "latex"), 0)
        own_targets(self.project, "doctor", "bib-check", "pdf-artifact", "clean", recipe="@echo MINE")
        targets = guide.make_targets((self.project / "Makefile").read_text())
        for name in ("doctor", "bib-check", "pdf-artifact"):
            self.assertIn("latex-ai-" + name, targets)
        self.assertIn("latex-ai-clean", targets)  # the selected document determines whether cleanup is supported
        self.assertEqual(self.make_output("clean").strip(), "MINE")
        self.assertEqual(self.make_output("doctor").strip(), "MINE")  # and the project's recipes are still its own

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_status_only_says_nothing_is_pending_when_that_is_known(self):
        self.assertEqual(self.cli("init", "--modules", ""), 0)
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
        self.assertEqual(self.cli("init", "--modules", ""), 0)
        (self.project / core.CONFIG).unlink()
        for target in ("help", "status"):
            with self.subTest(target=target):
                text = self.make_output(target)
                self.assertIn("no workbench installed", text)
                self.assertNotIn("FileNotFoundError", text)
                self.assertIn("latex-ai-init init .", text)

    def fresh_project(self):
        shutil.rmtree(self.project)
        self.project.mkdir()

    def test_small_print_of_everyday_commands(self):
        self.assertEqual(self.cli("init", "--modules", ""), 0)
        env = {name: value for name, value in os.environ.items() if name not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "TASK", "LATEX_AI_BASE"}}
        shown = subprocess.run(["make", "help"], cwd=self.project, capture_output=True, text=True, env=env)  # no -s: the recipe itself is quiet
        self.assertTrue(shown.stdout.startswith("LaTeX AI Workbench"), shown.stdout[:120])
        with patch.object(shutil, "which", side_effect=lambda name: None if name == "chktex" else "/usr/bin/" + Path(name).name):
            status, errors = self.run_main("doctor")
        self.assertNotIn("TeX distribution", errors)  # a core project does not need one
        self.assertNotIn("citation keys", next(command.description for command in guide.COMMANDS if command.short == "bib-check"))
        self.fresh_project()
        self.assertEqual(self.cli("init", "--modules", ""), 0)
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

    def test_small_print_from_the_blind_trial(self):
        self.assertEqual(self.cli("init", "--modules", ""), 0)
        self.assertIn("All required tools found", self.command("doctor").stdout)
        quickstart = (boot.PACKAGE / "docs/quickstart.md").read_text()
        self.assertNotIn("fullest", quickstart)
        self.assertIn("make latex-ai-lint-baseline", quickstart)
        self.assertNotIn("`workbench/skills/latex-ai-workbench/`", (boot.PACKAGE / "templates/AGENTS.md").read_text())  # no path that an adopted project lacks


class Repairs(ProjectCase):

    # --- build-produced inputs -------------------------------------------------------------------------

    """Origin: tests/test_repairs_3_0_1.py, workbench 3.0.1."""

    @unittest.skipUnless(hasattr(os, "getuid"), "POSIX users")
    def test_stale_state_hints_name_the_document(self):
        self.configure({"paper": {"root": "main.tex", "lint": {"enabled": False}},
                        "note": {"root": "note.tex", "lint": {"enabled": False}}})
        for name in ("main.tex", "note.tex"):
            (self.project / name).write_text(SOURCE_3_0_1)
        self.install("init", "--skip-editor")
        config = schema.load_config(self.project)
        view = schema.document_settings(config, "note")
        for label, call in {"unverified receipt": lambda: latex.verify(self.project, view),
                            "unprepared build": lambda: latex.finish_build(self.project, view, os.getpid())}.items():
            with self.subTest(label), self.assertRaises(core.WorkbenchError) as caught:
                call()
            self.assertIn("DOC=note", str(caught.exception) + (caught.exception.hint or ""))
        with self.subTest("missing log"), self.assertRaises(core.WorkbenchError) as caught:
            latex.verify(self.project, view, check_receipt=False)
        self.assertIn("DOC=note", str(caught.exception) + (caught.exception.hint or ""))

    def test_status_puts_the_running_build_before_anything_that_would_start_another(self):
        self.configure()
        (self.project / "main.tex").write_text(SOURCE_3_0_1)
        self.builder()
        self.install("init", "--skip-editor")
        view = schema.document_settings(schema.load_config(self.project))
        path = self.project / latex.receipt_path(view)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": latex.RECEIPT_SCHEMA, "status": "running", "owner_pid": os.getpid(),
                                    "owner_token": latex.process_token(os.getpid())}))
        text = self.command("status").stdout
        steps = [line.strip() for line in text.split("Next:")[1].splitlines() if line.strip()]
        self.assertTrue(steps[0].startswith("wait for this build"), steps)
        self.assertTrue(all("after" in step for step in steps[1:]), steps)


class NoHandbook(ProjectCase):
    """Origin: tests/test_scope_4_2_0.py, workbench 4.2.0."""

    def test_the_manual_stays_short_whatever_the_project(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.install("init", "--no-lint")
        text = self.command("guide").stdout
        self.assertLessEqual(len(text.splitlines()), MANUAL_LINES, text)
        self.assertTrue(all(len(line) <= 140 for line in text.splitlines()))


class Guide(ProjectCase):
    """Origin: tests/test_scope_4_6_0.py, workbench 4.6.0."""

    def setUp(self):
        super().setUp()
        for name in ("paper", "notes"):
            (self.project / f"{name}.tex").write_text(SOURCE_4_6_0)
        (self.project / "builder.py").write_text(BUILDER)
        (self.project / core.CONFIG).write_text(json.dumps(configuration("paper", "notes")))
        self.install("init", "--skip-editor")

    def test_the_guide_and_help_name_the_targets(self):
        guide = self.command("guide").stdout
        self.assertRegex(guide, r"make notes")
        self.assertRegex(guide, r"make all")
        help_text = self.command("help").stdout
        self.assertRegex(help_text, r"make all\s")
        self.assertIn("make paper, make notes: each builds that document.", help_text)

    def test_a_document_with_no_target_is_built_by_name_the_long_way(self):
        self.add_document("extra", "extra.tex", build_command=[sys.executable, "builder.py", "extra"], lint={"enabled": False}, output_dir="outputs")
        (self.project / "extra.tex").write_text(SOURCE_4_6_0)
        self.assertIn("make build DOC=extra", self.command("guide").stdout)

    def test_diff_shows_a_4_5_project_exactly_the_lines_it_lacks(self):
        path = self.project / "Makefile"
        text = path.read_text()
        old = re.sub(r"\.PHONY: (?:all|notes|paper)\n(?:all|notes|paper):[^\n]*\n(?:\t[^\n]*\n)?", "", text)
        old = re.sub(r"\.PHONY: latex-ai-build-all\nlatex-ai-build-all:\n\t[^\n]*\n", "", old)
        self.assertNotEqual(old, text)
        path.write_text(old)
        diff = self.install("diff", "--diff", expected=None).stdout
        self.assertIn("DIFFERS", diff)
        for line in ("+.PHONY: all", "+.PHONY: notes", "+.PHONY: paper", "+.PHONY: latex-ai-build-all"):
            self.assertIn(line, diff)
        self.assertEqual([l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")], [])


class DocumentTargetSafety(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE)
        (self.project / 'note.tex').write_text(SOURCE)
        self.builder()

    def test_a_document_named_clean_does_not_offer_the_cleanup_command_as_a_build(self):
        self.configure({'paper': {'root': 'main.tex'}, 'clean': {'root': 'note.tex'}})
        self.install('init', '--skip-editor')
        output = self.command('guide').stdout
        self.assertIn('clean has no target of its own: make build DOC=clean', output)
        self.assertNotIn('make clean: each builds that document', output)

    def test_an_unrelated_target_is_not_offered_as_a_document_build(self):
        self.configure({'paper': {'root': 'main.tex'}, 'note': {'root': 'note.tex'}})
        self.install('init', '--skip-editor')
        makefile = self.project / 'Makefile'
        text = makefile.read_text().replace('note:\n\t@$(PYTHON) .latex-ai/workbench.py build --document note',
                                           'note:\n\t@echo unrelated task')
        text = text.replace('build: latex-ai-build', 'build:\n\t@echo unrelated build')
        makefile.write_text(text)
        output = self.command('guide').stdout
        self.assertIn('note has no target of its own: make latex-ai-build DOC=note', output)
        self.assertNotIn('make note: each builds that document', output)


class Manual(ProjectCase):
    """Origin: tests/test_scope_4_9_1.py, workbench 4.9.1."""

    def paper(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")

    def default_paper(self):
        """A project as `init` leaves it, with the documents' default output folders."""
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--skip-editor")

    def guide(self):
        return self.command("guide").stdout

    def test_a_document_is_named_with_its_file_and_a_new_one_is_not_built_yet(self):
        self.paper()
        text = self.guide()
        self.assertIn("Documents: paper = main.tex (default): not built yet", text)
        self.assertNotIn("is missing", text)
        self.command("build")
        self.assertIn("Documents: paper = main.tex (default): current", self.guide())

    def test_each_document_of_several_is_named_with_its_file(self):
        self.paper()
        (self.project / "talk.tex").write_text(SOURCE)
        self.add_document("talk", "talk.tex", output_dir="outputs", build_command=[sys.executable, "builder.py"], lint={"enabled": False})
        self.assertIn("Documents: paper = main.tex (default): not built yet; talk = talk.tex: not built yet", self.guide())

    def test_the_manual_says_where_the_pdf_goes_and_it_goes_there(self):
        self.paper()  # outputs/ is set for this document, so the manual must name it and not the usual folder
        text = self.guide()
        folder = re.search(r"build the PDF \(into (\S+)\)", text)
        self.assertTrue(folder, text)
        self.assertNotIn(".latex-ai/artifacts/documents/NAME/build", text)
        self.command("build")
        self.assertTrue(list((self.project / folder[1]).glob("*.pdf")), f"no PDF in {folder[1]}")

    def test_the_usual_folder_is_named_with_NAME_and_is_the_one_the_build_uses(self):
        self.default_paper()
        text = self.guide()
        self.assertIn("build the PDF (into .latex-ai/artifacts/documents/NAME/build/)", text)
        spec = schema.specifications(core.effective_config(schema.load_config(self.project)))[0]
        self.assertEqual(spec.view["output_dir"], f".latex-ai/artifacts/documents/{spec.name}/build")

    def test_the_states_do_not_say_that_the_checks_passed(self):
        self.paper()
        self.assertNotIn("verified", " ".join(schema.STATES.values()))
        text = self.guide()
        self.assertNotIn("verified", text)
        self.assertRegex(text, r"What a document's state means \(.*not .*checks")
        self.command("build")
        status = self.command("status").stdout
        self.assertNotIn("verified build", status)
        self.assertRegex(status, r"paper: current \(built from [^;]*without a LaTeX error")

    def test_status_does_not_say_verified_build_for_a_document_never_built_or_changed_since(self):
        self.paper()
        for arguments in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "first"]):
            subprocess.run(["git", *arguments], cwd=self.project, env={**fixture_env(), **IDENTITY}, check=True, capture_output=True)
        status = self.command("status").stdout
        self.assertIn("(no build yet: paper)", status)
        self.assertNotIn("verified build", status)
        self.command("build")
        (self.project / "main.tex").write_text(SOURCE + "% changed\n")
        status = self.command("status").stdout
        self.assertIn("changed since the build: main.tex", status)
        self.assertNotIn("verified build", status)

    def test_make_all_is_said_to_stop_at_the_first_failure(self):
        # Behaviour: test_scope_4_6_0 (all does not try the documents after a failure).
        self.paper()
        self.assertRegex(self.guide(), r"build every document, one after another; it stops at the first one that fails")

    def test_an_undefined_reference_is_an_error_as_the_manual_says_and_an_error_may_have_no_hint(self):
        self.paper()
        text = self.guide()
        self.assertRegex(text, r"ERROR: is an ordinary failure \(an undefined reference or citation is one\)")
        self.assertIn("and its Hint, if it has one", text)
        (self.project / "builder.py").write_text(
            "from pathlib import Path\n"
            "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
            "(out / 'main.pdf').write_bytes(b'%PDF-fixture')\n"
            "(out / 'main.log').write_text(\"LaTeX Warning: Reference `fig:one' on page 1 undefined on input line 3.\\nLaTeX Warning: There were undefined references.\\n\")\n"
            "(out / 'main.fls').write_text('PWD ' + str(Path.cwd()) + '\\nINPUT main.tex\\n')\n")
        result = self.command("build", expected=1)
        self.assertIn("undefined", result.stderr)
        self.assertEqual(self.state(), "failed")

    def test_the_snapshot_lines_say_git_is_needed_and_what_to_replace_in_the_command(self):
        self.paper()
        text = self.guide()
        self.assertIn("needs Git installed; the project need not use it", text)
        self.assertIn("write a file's path where it says FILE", text)
        self.command("snapshot")
        self.assertIn("FILE", self.command("snapshots").stdout)  # what the manual tells the reader to replace is really printed

    def test_a_snapshot_keeps_uncommitted_files_as_the_manual_says(self):
        self.paper()
        self.assertIn("keep a copy of every file, uncommitted ones too, outside the project", self.guide())
        for arguments in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "first"]):
            subprocess.run(["git", *arguments], cwd=self.project, env={**fixture_env(), **IDENTITY}, check=True, capture_output=True)
        (self.project / "notes.txt").write_text("never committed\n")
        self.command("snapshot")
        printed = re.search(r"--git-dir=(\S+) --work-tree=\S+ checkout (\w+) -- FILE", self.command("snapshots").stdout)
        self.assertTrue(printed)
        names = subprocess.run(["git", f"--git-dir={printed[1]}", "ls-tree", "-r", "--name-only", printed[2]], env=fixture_env(), check=True,
                               capture_output=True, text=True).stdout.split("\n")
        self.assertIn("notes.txt", names)

    def test_lint_baseline_is_for_style_warnings_and_never_for_an_error(self):
        self.paper()
        text = self.guide()
        self.assertIn("accept today's ChkTeX style warnings so that only new ones fail; your decision, never for an ERROR", text)
        self.assertNotIn("the owner's decision", text)

    def test_the_agent_lines_say_what_they_ask_about_and_the_installed_rules_agree(self):
        self.paper()
        text = self.guide()
        self.assertNotIn("any Git change", text)
        self.assertIn("They ask before committing, pushing or anything that rewrites or discards work", text)
        self.assertIn("never push to the default branch (main or master) or merge a pull request", text)
        rules = json.loads((self.project / ".claude/settings.json").read_text())["permissions"]
        for command in ("git commit", "git push", "git reset", "git clean", "git restore"):
            self.assertIn(f"Bash({command}:*)", rules["ask"], command)
        self.assertIn("Bash(git push origin main)", rules["deny"])
        self.assertIn("Bash(gh pr merge:*)", rules["deny"])

    def test_the_update_pointer_names_a_file_the_package_has(self):
        self.paper()
        text = self.guide()
        self.assertIn("follow docs/upgrading.md in a newer workbench folder", text)
        self.assertNotIn("docs/quickstart.md", text)
        self.assertTrue((PACKAGE / "docs/upgrading.md").is_file())

    def test_validation_plan_is_said_to_select_everything_without_git_and_does(self):
        self.paper()
        self.assertIn("nothing runs; without Git, all of them", self.guide())
        self.assertIn("full validation selected", self.command("plan").stdout)

    def test_the_manual_stays_short_and_narrow_for_the_richest_project(self):
        self.paper()
        for name in ("talk", "poster"):
            (self.project / f"{name}.tex").write_text(SOURCE)
            self.add_document(name, f"{name}.tex", output_dir=f"out-{name}", build_command=[sys.executable, "builder.py"], lint={"enabled": False})
        text = self.guide()
        self.assertLessEqual(len(text.splitlines()), MANUAL_LINES_4_9_1, text)
        self.assertTrue(all(len(line) <= 140 for line in text.splitlines()), [line for line in text.splitlines() if len(line) > 140])
        self.assertIn("build the PDF (into paper: outputs/; poster: out-poster/; talk: out-talk/)", text)  # several, each with its own folder: each named


class FailedDocumentLog(ProjectCase):
    """Workbench 4.10.1, after the readers of the manual used it: `status` says where the log of a failed document is.

    Origin: workbench 4.10.1 (the reader findings recorded in verification-4.9.1.md).
    """

    def fixture(self, log, code=0):
        """A project whose stand-in compiler writes this log and exits with this code."""
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}x\\end{document}\n")
        self.configure()
        self.install("init", "--skip-editor")
        self.compiler(log, code)

    def compiler(self, log, code=0):
        (self.project / "builder.py").write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
            "(out / 'main.pdf').write_bytes(b'%PDF-fixture')\n"
            f"(out / 'main.log').write_text({log!r})\n"
            "(out / 'main.fls').write_text('PWD ' + str(Path.cwd()) + '\\nINPUT main.tex\\n')\n"
            f"sys.exit({code})\n")

    def test_status_names_the_log_of_a_failed_document_and_only_of_a_failed_one(self):
        self.fixture("LaTeX Warning: Reference `fig:one' on page 1 undefined on input line 3.\nLaTeX Warning: There were undefined references.\n")
        self.assertNotIn("read its log", self.command("status").stdout)            # never built
        self.command("build", expected=1)
        self.assertEqual(self.state(), "failed")
        self.assertIn("read its log: outputs/main.log", self.command("status").stdout)
        self.compiler("Clean log\n")
        self.command("build")
        self.assertEqual(self.state(), "current")
        self.assertNotIn("read its log", self.command("status").stdout)

    def test_status_does_not_name_a_log_that_is_not_there(self):
        self.fixture("LaTeX Warning: Reference `fig:one' on page 1 undefined on input line 3.\nLaTeX Warning: There were undefined references.\n")
        self.command("build", expected=1)
        (self.project / "outputs/main.log").unlink()
        self.assertEqual(self.state(), "failed")
        self.assertNotIn("read its log", self.command("status").stdout)


if __name__ == "__main__":
    unittest.main()
