"""Workbench 4.4.0 removes the adoption of a project's own Makefile (see docs/maintainers/minimal-scope.md): the workbench no longer merges
into, parses or wraps a Makefile it did not write. `init` creates a project and refuses to touch a file of the project's that differs
from what it would write; an existing project is migrated to the workbench's layout by an agent following docs/migrating.md.

These tests pin what is gone (the Make parser, the adapter, the build hooks, the Make version requirement), what `init` now promises
(it writes only files that are absent or already identical, and says what to do about the rest) and what stays (a project's own Make
targets run as an ordinary build command, and `validate` still runs a project's own `check`).
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import bootstrap
import commands
import core
import guide
import runtime
from test_generated_files_guard import FIXTURES
from test_support import ProjectCase

REMOVED_FILES = ("make_graph.py", "adapters.py", "recipe-shell.sh")
REMOVED_ACTIONS = ("build-prepare", "build-finish", "build-shell")
REMOVED_WORDS = re.compile(r"(?i)adopted (?:make|single-target|build|command|goal|document)|EXTRA_PREREQS|GNU Make 4\.3|build-shell|build-prepare"
                           r"|kept your Makefile target|explicit (?:project )?adapter|phased (?:Make|build)|shared adopted|Make adoption")
SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"
OWN_FILES = {"AGENTS.md": "Mine.\n", ".gitignore": "*.tmp\n", "Makefile": "pdf:\n\ttrue\n", ".vscode/settings.json": '{"editor.tabSize": 3}\n',
             ".claude/settings.json": '{"permissions": {"allow": ["Bash(ls)"]}}\n'}


class NoAdoption(unittest.TestCase):
    def test_the_parser_the_adapter_and_the_recipe_shell_are_gone(self):
        for name in REMOVED_FILES:
            with self.subTest(file=name):
                self.assertFalse((PACKAGE / name).exists())
                self.assertNotIn(name, core.RUNTIME_FILES)
                for config in ({"schema_version": 3, "modules": {}}, {"schema_version": 3, "modules": {"latex": {"default_document": "p", "documents": {"p": {"root": "main.tex"}}}}}):
                    self.assertNotIn(name, core.runtime_sources(config))

    def test_the_build_hooks_are_not_actions_and_are_refused_by_name_with_a_pointer(self):
        for name in REMOVED_ACTIONS:
            with self.subTest(action=name):
                self.assertNotIn(name, commands.NAMES)
                self.assertFalse(hasattr(runtime, "do_" + name.replace("-", "_")))
                self.assertIn(name, commands.REMOVED_ACTIONS)
                done = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), name], capture_output=True, text=True)
                self.assertEqual(done.returncode, 2)
                self.assertIn("docs/migrating.md", done.stderr)
                self.assertNotIn("invalid choice", done.stderr)

    def test_no_make_version_is_required(self):
        self.assertFalse(hasattr(core, "ADOPTED_MAKE"))
        self.assertFalse(hasattr(core, "make_has_extra_prereqs"))
        self.assertFalse(hasattr(bootstrap, "make_adapter"))
        self.assertFalse(hasattr(bootstrap, "merge_block"))
        self.assertFalse(hasattr(bootstrap, "initial_json_merge"))

    def test_no_generated_makefile_carries_a_hook(self):
        for label, config in FIXTURES.items():
            with self.subTest(fixture=label):
                self.assertNotRegex(bootstrap.desired_files(config)["Makefile"], r"EXTRA_PREREQS|build-prepare|build-shell|RECIPE_SHELL|LATEX AI WORKBENCH")

    def test_the_guard_has_no_fixture_for_a_project_makefile(self):
        self.assertFalse(any(name.startswith("adopted-") for name in FIXTURES))

    def test_the_installer_stays_small(self):
        lines = (PACKAGE / "bootstrap.py").read_text(encoding="utf-8").count("\n")
        self.assertLess(lines, 580, "the installer creates files; it does not read other people's")


class Init(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE)

    def init(self, *extra, expected=0):
        return self.install("init", "--no-lint", *extra, expected=expected)

    def put(self, files):
        for name, text in files.items():
            (self.project / name).parent.mkdir(parents=True, exist_ok=True)
            (self.project / name).write_text(text)

    def test_init_refuses_each_file_of_the_project_that_differs_and_writes_nothing(self):
        for name, text in OWN_FILES.items():
            with self.subTest(file=name):
                self.put({name: text})
                before = self.snapshot()
                done = self.init(expected=2)
                self.assertIn(name, done.stdout)
                self.assertIn("docs/migrating.md", done.stdout + done.stderr)
                self.assertEqual(before, self.snapshot())
                (self.project / name).unlink()

    def test_init_lists_every_collision_at_once(self):
        self.put(OWN_FILES)
        done = self.init(expected=2)
        for name in OWN_FILES:
            self.assertRegex(done.stdout, rf"CONFLICT: {re.escape(name)}")

    def test_init_refuses_the_other_spellings_of_a_makefile(self):
        for name in ("GNUmakefile", "makefile"):
            with self.subTest(file=name):
                self.put({name: "pdf:\n\ttrue\n"})
                before = self.snapshot()
                done = self.init(expected=2)
                self.assertIn(name, done.stdout)
                self.assertEqual(before, self.snapshot())
                (self.project / name).unlink()

    def test_a_file_that_is_already_what_init_writes_is_no_collision(self):
        self.init()
        installed = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file() and ".latex-ai/" not in p.as_posix()}
        (self.project / ".latex-ai/installation.json").unlink()
        self.init()
        self.assertEqual(installed, {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file() and ".latex-ai/" not in p.as_posix()})

    def test_the_other_files_of_a_project_are_never_touched(self):
        own = {"latexmkrc": "$pdf_mode = 1;\n", "scripts/figure.py": "print('x')\n", "README.md": "# Paper\n", "refs.bib": "@misc{k,title={T}}\n"}
        self.put(own)
        self.init()
        for name, text in own.items():
            self.assertEqual((self.project / name).read_text(), text)

    def test_a_project_s_own_make_targets_are_added_after_init_not_merged_by_it(self):
        self.init()
        makefile = self.project / "Makefile"
        text = makefile.read_text()
        makefile.write_text(text + "\n.PHONY: figures\nfigures:\n\t@echo figures\n")
        done = self.run_command("make", "figures")
        self.assertIn("figures", done.stdout)
        self.run_command("make", "latex-ai-help")  # and the workbench's own targets still work beside it


class ProjectMake(ProjectCase):
    def test_a_project_target_runs_as_an_ordinary_build_command_and_stays_incremental(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.configure({"paper": {"root": "main.tex", "lint": {"enabled": False}, "output_dir": "outputs", "build_command": ["make", "outputs/main.pdf"]}})
        self.install("init", "--skip-editor")
        makefile = self.project / "Makefile"
        makefile.write_text(makefile.read_text() + f"\noutputs/main.pdf: main.tex builder.py\n\t@{sys.executable} builder.py\n")
        for _ in range(3):
            self.run_command("make", "check")
        self.assertEqual((self.project / "count").read_text(), "1", "Make compiled once; the receipt vouches for the runs that changed nothing")
        self.assertEqual(self.state(), "current")
        makefile.write_text(makefile.read_text() + "# the project's Make policy changed\n")
        self.assertEqual(self.state(), "stale", "the Makefile is an input of a build that runs through it")

    def test_make_s_dry_run_question_and_touch_modes_run_nothing(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")
        for mode in ("-n", "-q", "-t"):
            with self.subTest(mode=mode):
                self.run_command("make", mode, "check", expected=None)
                self.assertFalse((self.project / "count").exists())
                self.assertFalse((self.project / ".latex-ai/artifacts/documents").exists())

    def test_validate_still_runs_the_project_s_own_check(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.configure()
        self.install("init", "--skip-editor")
        makefile = self.project / "Makefile"
        template = makefile.read_text()
        self.assertFalse(guide.project_check_rule(self.project), "the Makefile as init wrote it has no check of the project's")
        for label, extra in (("a prerequisite", "\ncheck: my-tests\nmy-tests:\n\t@true\n"), ("a second recipe", "\ncheck::\n\t@echo mine\n"),
                             ("an include", "\n-include extra.mk\n")):
            with self.subTest(label):
                makefile.write_text(template + extra)
                self.assertTrue(guide.project_check_rule(self.project))
        makefile.write_text(template + "\n.PHONY: figures\nfigures:\n\t@true\n")
        self.assertFalse(guide.project_check_rule(self.project), "a target that is not check does not make validate conservative")


class AnOlderAdapter(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--no-lint", "--skip-editor")
        makefile = self.project / "Makefile"
        makefile.write_text(makefile.read_text() + "\n.PHONY: latex-ai-build-prepare\nlatex-ai-build-prepare:\n\t+@$(PYTHON) .latex-ai/workbench.py build-prepare --build-owner \"$$PPID\"\n")

    def test_runtime_refuses_to_refresh_a_project_whose_makefile_still_wraps_its_build(self):
        before = self.snapshot()
        done = self.install("runtime", expected=2)
        self.assertIn("docs/migrating.md", done.stdout + done.stderr)
        self.assertEqual(before, self.snapshot())

    def test_status_says_so(self):
        text = self.command("status", expected=None).stdout
        self.assertIn("docs/migrating.md", text)


class Documents(unittest.TestCase):
    def test_no_live_document_or_guide_describes_what_is_gone(self):
        paths = [PACKAGE / name for name in ("README.md", "templates/AGENTS.md", "skills/latex-ai-workbench/SKILL.md", "skills/latex-ai-workbench/references/installation.md",
                                             "runtime.py", "schema.py", "bootstrap.py", "core.py", "latex.py", "Makefile")]
        paths += sorted(path for path in (PACKAGE / "docs").glob("*.md") if path.name != "migrating.md")  # the recipe names the old adapter, to recognize it
        for path in paths:
            with self.subTest(file=path.name):
                found = REMOVED_WORDS.search(path.read_text(encoding="utf-8"))
                self.assertIsNone(found, found and found.group(0))

    def test_the_migration_recipe_is_written_down_for_an_agent_to_follow(self):
        text = (PACKAGE / "docs/migrating.md").read_text(encoding="utf-8")
        for step in ("snapshot", "move", "init", "AGENTS.md", ".gitignore", ".vscode", "build_command", "lint-baseline", "make check", "git diff"):
            self.assertIn(step, text)
        self.assertLessEqual(len(text.splitlines()), 80, "a recipe an agent follows, not a manual")


if __name__ == "__main__":
    unittest.main()
