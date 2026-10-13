"""Phase 3, F9: each fact the code spelled twice is now spelled once.

What each duplicate was, and what pins it: the Make goals that would make a project's build command call itself (derived from the
command registry), the folders no check treats as project sources (core.GENERATED_TREES), the suffixes the planner routes, the
Make names the template already defines, and the Markdown link check of the file checks.
"""
import ast
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import bootstrap
import commands
import core
import runtime
import schema
from test_support import ProjectCase

OLD_RECURSIVE_GOALS = {"latex-ai-build", "latex-ai-document-check", "latex-ai-validate", "check", "document-check", "validate"}
# How 3.6.0 routed each file name, recorded from its code before this change: M manuscript input or potential figure,
# O ordinary documentation/data/code, U unclassified (conservative manuscript validation).
ROUTING = dict(
    zip(".tex .bib .sty .cls .bst .bbx .cbx .lbx .tikz .png .jpg .jpeg .pdf .svg .eps .ps .webp .tif .tiff .csv .tsv .PNG .CSV".split(), "M" * 24),
    **dict(zip(".md .markdown .txt .rst .adoc .json .yaml .yml .toml .py .MD".split(), "O" * 11)),
    **{".rules": "U", ".xyz": "U", ".log": "U", ".ipynb": "U"})
REASON = {"M": "manuscript input or potential figure", "O": "ordinary documentation/data/code: file checks; use task-specific tests when relevant",
          "U": "unclassified input: conservative manuscript validation"}


def set_literals(path):
    """Every set display in a module, as the set of its string members."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [{node.value for node in display.elts if isinstance(node, ast.Constant) and isinstance(node.value, str)}
            for display in ast.walk(tree) if isinstance(display, ast.Set)]


class RecursionGuard(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")

    def test_the_goals_that_run_the_build_again_come_from_the_registry(self):
        self.assertEqual(set(commands.RECURSIVE_GOALS), OLD_RECURSIVE_GOALS)
        names = {name for command in commands.COMMANDS for name in (command.short, command.reserved)}
        self.assertLessEqual(commands.RECURSIVE_GOALS, names | {"latex-ai-build"})
        self.assertTrue(all(goal.startswith(commands.RESERVED_PREFIX) or goal in {"check", "validate", "document-check"}
                            for goal in commands.RECURSIVE_GOALS))
        self.assertTrue(all(command.reserved.startswith(commands.RESERVED_PREFIX) for command in commands.COMMANDS if command.reserved))

    def test_a_build_command_naming_any_of_them_is_refused(self):
        for goal in sorted(commands.RECURSIVE_GOALS) + ["latex-ai-plan", "latex-ai-anything"]:
            with self.subTest(goal=goal):
                config = self.configure(documents_={"paper": {"root": "main.tex", "build_command": ["make", goal]}})
                with self.assertRaisesRegex(schema.WorkbenchError, "Recursive build_command"):
                    schema.validate_config(self.project, config)

    def test_the_project_s_own_targets_are_not_refused(self):
        for goal in ("build", "lint", "paper", "all"):
            with self.subTest(goal=goal):
                config = self.configure(documents_={"paper": {"root": "main.tex", "build_command": ["make", goal]}})
                schema.validate_config(self.project, config)

    def test_the_closure_check_forbids_the_same_goals(self):
        source = (PACKAGE / "schema.py").read_text(encoding="utf-8")
        self.assertNotIn('"latex-ai-document-check"', source, "the goals are the registry's, not a second list")
        self.assertNotIn('"document-check", "validate"', source)


class GeneratedTrees(unittest.TestCase):
    def test_one_constant_holds_the_folders_no_check_treats_as_sources(self):
        self.assertEqual(core.GENERATED_TREES, {".git", ".latex-ai", ".venv", "__pycache__", "node_modules", "site-packages", "dist-packages"})

    def test_the_installer_adds_only_its_own_folders(self):
        self.assertEqual(bootstrap.EXCLUDED, core.GENERATED_TREES | {"workbench", "build", "out"})

    def test_no_module_but_core_lists_them_again(self):
        for path in sorted(PACKAGE.glob("*.py")):
            if path.name == "core.py":
                continue
            for members in set_literals(path):
                with self.subTest(module=path.name, members=sorted(members)):
                    self.assertFalse({".git", ".venv"} <= members or {".latex-ai", "node_modules"} <= members)

    def test_a_walk_without_git_skips_them(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            for folder in ("notes", *sorted(core.GENERATED_TREES)):
                (project / folder).mkdir()
                (project / folder / "page.md").write_text("# Page\n")
            with patch.object(runtime, "git_names", side_effect=OSError):
                self.assertEqual(runtime.project_files(project), ["notes/page.md"])


class PlannerSuffixes(ProjectCase):
    def test_every_suffix_is_routed_as_it_was(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.configure()
        config = runtime.load_config(self.project)
        for suffix, route in ROUTING.items():
            name = "data/file" + suffix
            with self.subTest(name=name):
                self.assertEqual(runtime.validation_plan(self.project, config, [name])["reasons"][name], REASON[route])
        for name, route in (("data/.gitignore", "O"), ("data/LICENSE", "O"), ("data/noext", "U")):
            with self.subTest(name=name):
                self.assertEqual(runtime.validation_plan(self.project, config, [name])["reasons"][name], REASON[route])

    def test_the_tables_name_each_suffix_once(self):
        self.assertEqual(runtime.DATA_SUFFIXES, {".csv", ".tsv"})
        self.assertTrue(runtime.DATA_SUFFIXES <= runtime.MANUSCRIPT_SUFFIXES)
        self.assertFalse(runtime.DATA_SUFFIXES & runtime.DOCUMENT_SUFFIXES)
        self.assertEqual(runtime.CHECKED_SUFFIXES,
                         {".md", ".markdown", ".txt", ".rst", ".adoc", ".json", ".yaml", ".yml", ".toml", ".py", ".rules", ".tex", ".bib", ".csv", ".tsv"})
        literals = [members for members in set_literals(PACKAGE / "runtime.py") if members & {".csv", ".tsv"}]
        self.assertEqual(literals, [{".csv", ".tsv"}], "a suffix list in runtime.py repeats the data suffixes")


class MarkdownLinks(unittest.TestCase):
    def check(self, files, name, text):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            for file in files:
                (project / file).parent.mkdir(parents=True, exist_ok=True)
                (project / file).write_text("x\n")
            (project / name).parent.mkdir(parents=True, exist_ok=True)
            return runtime.broken_markdown_link(project, project / name, text)

    def test_a_missing_local_target_is_reported_as_written(self):
        self.assertEqual(self.check([], "notes.md", "See [it](gone.md) and ![fig](img/gone.png)."), "gone.md")

    def test_existing_and_non_local_targets_are_fine(self):
        text = ("[a](here.md) [b](here.md#part) [c](here.md?x=1) [d](<here.md>) [e](sub/there%20now.md) [f](https://example.org/x) "
                "[g](mailto:a@b.c) [h](#anchor) [i](/absolute) [j](here.md \"title\") [k](../outside.md)")
        self.assertIsNone(self.check(["here.md", "sub/there now.md"], "notes.md", text))

    def test_code_fences_are_not_links(self):
        self.assertIsNone(self.check([], "notes.md", "```\n[x](gone.md)\n```\n~~~\n[y](gone2.md)\n~~~\n"))

    def test_the_target_is_resolved_beside_the_file(self):
        self.assertIsNone(self.check(["docs/here.md"], "docs/notes.md", "[a](here.md)"))
        self.assertEqual(self.check(["docs/here.md"], "notes.md", "[a](here.md)"), "here.md")


class TemplateTargets(unittest.TestCase):
    def test_the_template_decides_which_short_names_it_already_has(self):
        self.assertNotIn('{"build", "lint", "check"}', (PACKAGE / "bootstrap.py").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "workbench"
            shutil.copytree(PACKAGE, copy, ignore=shutil.ignore_patterns("__pycache__", "tests", "docs"))
            template = copy / "templates" / "Makefile"
            template.write_text(template.read_text(encoding="utf-8") + "\nclean:\n\t@echo the template's own\n", encoding="utf-8")
            config = {"schema_version": 3, "modules": {"latex": {"default_document": "paper", "documents": {"paper": {"root": "main.tex"}}}}}
            with patch.object(bootstrap, "PACKAGE", copy):
                makefile = bootstrap.desired_files(config)["Makefile"]
        self.assertNotIn("\nclean: latex-ai-clean", makefile)
        with patch.object(bootstrap, "PACKAGE", PACKAGE):
            self.assertIn("\nclean: latex-ai-clean", bootstrap.desired_files(config)["Makefile"])


if __name__ == "__main__":
    unittest.main()
