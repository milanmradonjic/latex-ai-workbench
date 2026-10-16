"""Tests of what the workbench no longer does: each removal of a release, pinned so that it stays removed.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 6 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_scope_4_0_0.py:
Workbench 4.0.0 keeps the LaTeX build, the bibliography checks, the agent rules and the file checks, and drops the rest
(see docs/maintainers/minimal-scope.md): the research modules, the notes and Markdown modules, and everything that served them.

These tests pin what is gone, so that nothing of it comes back by accident: not as a module, a profile, a command, a Make
target, a generated step, a runtime file or a sentence of the documentation.

test_scope_4_1_0.py:
Workbench 4.1.0 no longer generates CI workflows for the projects it installs (see docs/maintainers/minimal-scope.md).

These tests pin what is gone: the generator, its options and its configuration, and that a project's own workflows are left alone.
This repository's own workflows are plain files now, and test_architecture.py keeps them pinned.

test_scope_4_2_0.py:
Workbench 4.2.0 replaces the long generated handbook by a short manual (see docs/maintainers/minimal-scope.md).

These tests pin what is gone (the generator, the web page, the topics, the packaged copies) and that the manual that replaced it stays short.

test_scope_4_3_0.py:
Workbench 4.3.0 removes the installer's upgrade machinery (see docs/maintainers/minimal-scope.md): the installer creates a
project (`init`), says how a project differs from this release (`diff`) and refreshes its vendored runtime (`runtime`). There is no
audit, upgrade, configure or recovery; a project is updated by an agent following docs/upgrading.md, with a diff and `make check`.

These tests pin what is gone (the modes, the three-way merge, the manifest of every managed file, the disabled-module memory) and what the
three modes promise: `init` never touches an installed project, `diff` never writes, `runtime` never overwrites an edited file unasked.

test_scope_4_4_0.py:
Workbench 4.4.0 removes the adoption of a project's own Makefile (see docs/maintainers/minimal-scope.md): the workbench no longer merges
into, parses or wraps a Makefile it did not write. `init` creates a project and refuses to touch a file of the project's that differs
from what it would write; an existing project is migrated to the workbench's layout by an agent following docs/migrating.md.

These tests pin what is gone (the Make parser, the adapter, the build hooks, the Make version requirement), what `init` now promises
(it writes only files that are absent or already identical, and says what to do about the rest) and what stays (a project's own Make
targets run as an ordinary build command, and `validate` still runs a project's own `check`).

test_scope_4_5_0.py:
Workbench 4.5.0, step 3.4 of docs/maintainers/plan-after-4.4.0.md: one engine (pdflatex), one bibliography program (BibTeX), no installer profiles.

`--engine`, `--backend` and `--profile` are gone from `init`, as are the lualatex, xelatex and biber paths behind them and the `biblatex` export format. A configuration that
says what stays (`engine: pdflatex`, `backend: none` or `bibtex`, export format `bibtex`) works as it did, and anything else is refused by name with a hint that points at
`build_command`. `--modules` chooses what a profile chose: `--modules ""` was `--profile core` and `--modules latex` was `--profile writing`.
"""

import io
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap
import commands
import core
import diagnostics
import guide
import latex
import runtime
import schema
from test_installer import FIXTURES
from test_support import ProjectCase


REMOVED_ACTIONS = ("run", "figure", "freshness", "history", "claims-check", "research-check", "md-check", "md-render")


REMOVED_FILES = ("research.py", "task_graph.py", "markdown.py", "docs/research.md", "docs/research-loop.md", "docs/markdown.md", "examples/decay")


REMOVED_MODULES = ("notes", "markdown", "numerics", "figures", "provenance", "freshness", "claims")


REMOVED_WORDS = re.compile(r"make (?:latex-ai-)?(?:run|figure|freshness|history|claims-check|research-check|research-validate|md-check|md-render)\b"
                           r"|--profile (?:notebook|tex-notebook|numerical|research-paper)|experiments\.json|claims\.json|task manifest")


GONE = ("workflow", "core_workflow", "document_workflow", "pin_actions", "PINNED_ACTIONS", "ci_action", "ci_command", "ci_host_checks")


REMOVED_MODES = ("upgrade", "audit", "configure", "recover", "migrate")


REMOVED_WORDS_4_3_0 = re.compile(r"latex-ai-init (?:upgrade|audit|configure)\b|\bconfigure (?:--enable|--disable)|--enable (?:bibliography|latex)\b"
                           r"|\bdisabled_modules\b|installation\.py|\.latex-ai/installation\.json.{0,40}manifest|three-way")


SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"


REMOVED_ACTIONS_4_4_0 = ("build-prepare", "build-finish", "build-shell")


REMOVED_FILES_4_4_0 = ("make_graph.py", "adapters.py", "recipe-shell.sh")


class Scope(unittest.TestCase):
    """Origin: tests/test_scope_4_0_0.py, workbench 4.0.0."""


    def test_no_removed_action_has_a_command_a_handler_or_a_make_target(self):
        for name in REMOVED_ACTIONS:
            with self.subTest(action=name):
                self.assertNotIn(name, commands.NAMES)
                self.assertFalse(hasattr(runtime, "do_" + name.replace("-", "_")))
        shown = {name for command in commands.COMMANDS for name in (command.short,)}
        self.assertFalse(shown & {"run", "figure", "freshness", "history", "claims-check", "md-check", "md-render",
                                  "research-check", "research-validate", "latex-ai-run", "latex-ai-figure", "latex-ai-freshness"})

    def test_the_distribution_carries_none_of_the_removed_files(self):
        for name in REMOVED_FILES:
            with self.subTest(file=name):
                self.assertFalse((PACKAGE / name).exists())
        for config in ({'schema_version': 4},
                       {'schema_version': 4, 'default_document': 'p', 'documents': {'p': {'root': 'main.tex'}}, 'bibliography': {}}):
            sources = core.runtime_sources(config)
            self.assertFalse({"research.py", "task_graph.py", "markdown.py"} & set(sources))
        self.assertFalse({"research.py", "task_graph.py", "markdown.py"} & set(core.RUNTIME_FILES))

    def test_the_plan_and_the_validation_actions_no_longer_know_research_or_markdown(self):
        self.assertFalse(hasattr(core, "VALIDATION_ACTIONS"))
        plan = runtime.validation_plan(PACKAGE, {'schema_version': 4}, ["notes.md"])
        self.assertFalse({"research", "research_modules", "markdown"} & set(plan))

    def test_no_generated_file_mentions_a_removed_capability(self):
        for label, config in FIXTURES.items():
            texts = {name: text for name, text in __import__("bootstrap").desired_files(config).items()
                     if name in {"Makefile", ".vscode/tasks.json", ".vscode/settings.json"}}
            for name, text in texts.items():
                with self.subTest(fixture=label, file=name):
                    self.assertNotRegex(text, r"(?i)pandoc|research|latex-ai-(?:run|figure|freshness|history|claims|md-)")

    def test_the_policy_and_the_guide_do_not_describe_what_is_gone(self):
        for name in ("templates/AGENTS.md", "README.md", "skills/latex-ai-workbench/SKILL.md"):
            text = (PACKAGE / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertIsNone(REMOVED_WORDS.search(text), REMOVED_WORDS.search(text))
        self.assertFalse(hasattr(core, "MODULES"))

    def test_no_live_document_describes_what_is_gone(self):
        for path in sorted((PACKAGE / "docs").glob("*.md")):
            with self.subTest(file=path.name):
                self.assertIsNone(REMOVED_WORDS.search(path.read_text(encoding="utf-8")))


class NoGeneratedCI(ProjectCase):
    """Origin: tests/test_scope_4_1_0.py, workbench 4.1.0."""

    def test_the_generator_and_its_pins_are_gone(self):
        for name in GONE:
            with self.subTest(name=name):
                self.assertFalse(hasattr(bootstrap, name))
        self.assertEqual(core.integrations({"integrations": {"editor": True}}), {"editor": True})

    def test_the_options_of_the_generator_are_gone(self):
        for option in ("--ci", "--no-ci", "--no-artifact"):
            with self.subTest(option=option):
                done = subprocess.run([sys.executable, "-B", str(PACKAGE / "latex-ai-init"), "init", option, str(self.project)],
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
                self.assertIn("unrecognized arguments", done.stderr)
        done = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), "plan", "--github-output", "x", "--project", str(self.project)],
                              capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)

    def test_a_configuration_that_asks_for_ci_is_refused_with_a_hint(self):
        config = {'schema_version': 4, 'default_document': 'paper', 'documents': {'paper': {'root': 'main.tex'}}, 'integrations': {'editor': False, 'ci': {'enabled': True}}}
        (self.project / 'main.tex').write_text(SOURCE)
        with self.assertRaises(core.WorkbenchError) as raised:
            schema.validate_config(self.project, config)
        self.assertIn("ci", str(raised.exception))
        self.assertIn("editor", raised.exception.hint)
        self.assertIn("supported: editor", raised.exception.hint)

    def test_an_install_writes_no_workflow_and_leaves_an_existing_one_alone(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        workflow = self.project / ".github/workflows/mine.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: mine\non: workflow_dispatch\n")
        self.install('init', lint=False)
        self.assertEqual(sorted(p.name for p in workflow.parent.iterdir()), ["mine.yml"])
        self.assertEqual(workflow.read_text(), "name: mine\non: workflow_dispatch\n")
        self.install("runtime")
        self.assertEqual(workflow.read_text(), "name: mine\non: workflow_dispatch\n")

    def test_the_documents_of_a_project_carry_no_ci_settings(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        config = self.configure()
        schema.validate_config(self.project, config)
        for target in schema.specifications(config):
            self.assertNotIn("ci", target.view)


class NoHandbook(ProjectCase):
    """Origin: tests/test_scope_4_2_0.py, workbench 4.2.0."""

    def test_the_handbook_and_its_copies_are_gone(self):
        for name in ("handbook.py", "docs/handbook.md", "docs/handbook.html"):
            with self.subTest(file=name):
                self.assertFalse((PACKAGE / name).exists())
        self.assertNotIn("handbook.py", core.RUNTIME_FILES)
        self.assertNotIn("handbook.py", core.runtime_sources({'schema_version': 4}))
        self.assertNotIn("handbook", (PACKAGE / "Makefile").read_text(encoding="utf-8"))

    def test_there_is_one_guide_command_and_it_takes_no_topic(self):
        self.assertIn("guide", commands.NAMES)
        self.assertNotIn("guide-html", commands.NAMES)
        self.assertNotIn("topic", commands.RECIPE_ARGUMENTS)
        done = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), "guide", "--topic", "loop", "--project", str(self.project)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("unrecognized arguments", done.stderr)

    def test_no_installed_makefile_exports_a_topic(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.install('init', lint=False)
        self.assertIsNone(re.search(r"TOPIC", (self.project / "Makefile").read_text(encoding="utf-8")))
        self.assertFalse((self.project / ".latex-ai/handbook.py").exists())


class NoUpgradeMachinery(ProjectCase):
    """Origin: tests/test_scope_4_3_0.py, workbench 4.3.0."""

    def test_the_installer_has_three_modes_and_refuses_the_removed_ones_by_name(self):
        for mode in REMOVED_MODES:
            with self.subTest(mode=mode):
                done = self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), mode, str(self.project), expected=2)
                self.assertIn("invalid choice", done.stderr)
                self.assertIn("{init,diff,runtime}", done.stderr)  # the usage line: the error text quotes the names differently by Python version

    def test_the_merge_engine_and_the_manifest_are_gone(self):
        self.assertFalse((PACKAGE / "installation.py").exists())
        self.assertNotIn("installation.py", core.RUNTIME_FILES)
        self.assertFalse(hasattr(bootstrap, "installation"))
        for name in ("three_way", "upgrade", "audit", "do_upgrade", "do_audit", "do_configure", "manifest_text", "migrate"):
            self.assertFalse(hasattr(bootstrap, name), name)
        self.assertFalse(hasattr(diagnostics, "manifest"))
        (self.project / "main.tex").write_text(SOURCE)
        self.install('init', lint=False, editor=False)
        self.assertFalse((self.project / ".latex-ai/installation.py").exists())

    def test_the_installer_stays_small(self):
        lines = (PACKAGE / "bootstrap.py").read_text(encoding="utf-8").count("\n")
        self.assertLess(lines, 640, "the installer is a create script, not an engine")


class NothingDescribesWhatIsGone(unittest.TestCase):
    """Origin: tests/test_scope_4_3_0.py, workbench 4.3.0."""

    def test_no_live_document_or_guide_describes_the_removed_modes(self):
        paths = [PACKAGE / name for name in ("README.md", "templates/AGENTS.md", "skills/latex-ai-workbench/SKILL.md", "guide.py", "runtime.py",
                                             "bootstrap.py", "Makefile")]
        paths += sorted(path for path in (PACKAGE / "docs").glob("*.md") if path.name != "migrating.md")  # the recipe names the settings that are gone, to find them
        for path in paths:
            with self.subTest(file=path.name):
                found = REMOVED_WORDS_4_3_0.search(path.read_text(encoding="utf-8"))
                self.assertIsNone(found, found and found.group(0))

    def test_the_update_recipe_is_written_down_for_an_agent_to_follow(self):
        # 4.9.0 moved the recipe into the skill file; docs/upgrading.md is the short guide that points to it
        text = (PACKAGE / "skills/latex-ai-workbench/references/installation.md").read_text(encoding="utf-8").split("## Update")[1].split("\n## ")[0]
        for step in ("diff", "runtime", "releases.md", "make check", "snapshot"):
            self.assertIn(step, text)
        self.assertLessEqual(len(text.splitlines()), 60, "a recipe an agent follows, not a manual")


class NoAdoption(unittest.TestCase):
    """Origin: tests/test_scope_4_4_0.py, workbench 4.4.0."""

    def test_the_parser_the_adapter_and_the_recipe_shell_are_gone(self):
        for name in REMOVED_FILES_4_4_0:
            with self.subTest(file=name):
                self.assertFalse((PACKAGE / name).exists())
                self.assertNotIn(name, core.RUNTIME_FILES)
                for config in ({'schema_version': 4}, {'schema_version': 4, 'default_document': 'p', 'documents': {'p': {'root': 'main.tex'}}}):
                    self.assertNotIn(name, core.runtime_sources(config))

    def test_removed_build_hooks_are_unknown_actions(self):
        for action in REMOVED_ACTIONS_4_4_0:
            done = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), action], capture_output=True, text=True)
            self.assertEqual(done.returncode, 2)
            self.assertIn("invalid choice", done.stderr)

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


class WhatIsGone(ProjectCase):
    """Origin: tests/test_scope_4_5_0.py, workbench 4.5.0."""

    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE)

    def test_the_options_that_chose_an_engine_a_backend_or_a_profile_are_gone(self):
        for option in (("--engine", "pdflatex"), ("--backend", "bibtex"), ("--profile", "core")):
            with self.subTest(option=option[0]):
                result = self.install("init", "--dry-run", *option, expected=2)
                self.assertIn("unrecognized arguments", result.stderr)
                self.assertIn(option[0], result.stderr)
        self.assertFalse(hasattr(core, "PROFILES"))

    def test_the_diagnostic_report_lists_only_the_tools_that_stay(self):
        self.assertEqual(set(diagnostics.tool_versions()) - {"python", "platform"}, {"make", "git", "latexmk", "pdflatex", "chktex", "bibtex"})

    def test_messages_only_biber_printed_are_not_read_as_errors(self):
        """The log patterns kept are LaTeX's and BibTeX's: a Biber `ERROR -` or `WARN -` line is neither a failure nor a warning."""
        self.configure()
        self.edit_config(lambda data: data["documents"]["paper"].update(backend="bibtex"))
        out = self.project / "outputs"
        out.mkdir()
        (out / "main.pdf").write_bytes(b"%PDF-1.5\n")
        (out / "main.log").write_text("Output written on main.pdf.\n")
        (out / "main.blg").write_text("ERROR - Cannot find 'refs.bib'\nFATAL - Error 1\nWARN - Duplicate entry key 'x'\nPlease (re)run Biber on the file.\n")
        view = schema.document_settings(schema.load_config(self.project))
        printed = io.StringIO()
        with redirect_stdout(printed):
            latex.verify(self.project, view, check_receipt=False)
        self.assertNotIn("WARN", printed.getvalue())
        (out / "main.blg").write_text("I couldn't open database file refs.bib\n")  # BibTeX's own failure still is one
        with self.assertRaisesRegex(core.WorkbenchError, "integrity"):
            latex.verify(self.project, view, check_receipt=False)


if __name__ == "__main__":
    unittest.main()
