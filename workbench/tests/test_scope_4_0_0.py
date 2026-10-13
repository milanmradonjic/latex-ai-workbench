"""Workbench 4.0.0 keeps the LaTeX build, the bibliography checks, the agent rules and the file checks, and drops the rest
(see docs/maintainers/minimal-scope.md): the research modules, the notes and Markdown modules, and everything that served them.

These tests pin what is gone, so that nothing of it comes back by accident: not as a module, a profile, a command, a Make
target, a generated step, a runtime file or a sentence of the documentation.
"""
import re
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import adapters
import commands
import core
import guide
import runtime
import schema
from test_generated_files_guard import FIXTURES

REMOVED_MODULES = ("notes", "markdown", "numerics", "figures", "provenance", "freshness", "claims")
REMOVED_ACTIONS = ("run", "figure", "freshness", "history", "claims-check", "research-check", "md-check", "md-render")
REMOVED_FILES = ("research.py", "task_graph.py", "markdown.py", "docs/research.md", "docs/research-loop.md", "docs/markdown.md", "examples/decay")
REMOVED_WORDS = re.compile(r"make (?:latex-ai-)?(?:run|figure|freshness|history|claims-check|research-check|research-validate|md-check|md-render)\b"
                           r"|--profile (?:notebook|tex-notebook|numerical|research-paper)|experiments\.json|claims\.json|task manifest")


class Scope(unittest.TestCase):
    def test_two_modules_and_two_profiles_remain(self):
        self.assertEqual(set(core.MODULES), {"latex", "bibliography"})
        self.assertEqual(set(core.PROFILES), {"core", "writing"})

    def test_a_configuration_naming_a_removed_module_is_refused_by_name(self):
        for name in REMOVED_MODULES:
            with self.subTest(module=name), self.assertRaises(core.WorkbenchError) as raised:
                schema.validate_config(PACKAGE, {"schema_version": 3, "modules": {name: {}}})
            self.assertIn(name, str(raised.exception))
            self.assertIn("modules", raised.exception.hint)  # the hint says what to edit

    def test_no_removed_action_has_a_command_a_handler_or_a_make_target(self):
        for name in REMOVED_ACTIONS:
            with self.subTest(action=name):
                self.assertNotIn(name, commands.NAMES)
                self.assertFalse(hasattr(runtime, "do_" + name.replace("-", "_")))
        shown = {name for command in commands.COMMANDS for name in (command.short, command.reserved) if name}
        self.assertFalse(shown & {"run", "figure", "freshness", "history", "claims-check", "md-check", "md-render",
                                  "research-check", "research-validate", "latex-ai-run", "latex-ai-figure", "latex-ai-freshness"})

    def test_the_distribution_carries_none_of_the_removed_files(self):
        for name in REMOVED_FILES:
            with self.subTest(file=name):
                self.assertFalse((PACKAGE / name).exists())
        for config in ({"schema_version": 3, "modules": {}},
                       {"schema_version": 3, "modules": {"latex": {"default_document": "p", "documents": {"p": {"root": "main.tex"}}},
                                                         "bibliography": {}}}):
            sources = core.runtime_sources(config)
            self.assertFalse({"research.py", "task_graph.py", "markdown.py"} & set(sources))
        self.assertFalse({"research.py", "task_graph.py", "markdown.py"} & set(core.RUNTIME_FILES))

    def test_the_plan_and_the_validation_actions_no_longer_know_research_or_markdown(self):
        self.assertEqual(set(core.VALIDATION_ACTIONS), {"unit", "bibliography", "portability", "full"})
        plan = runtime.validation_plan(PACKAGE, {"schema_version": 3, "modules": {}}, ["notes.md"])
        self.assertFalse({"research", "research_modules", "markdown"} & set(plan))

    def test_no_generated_file_mentions_a_removed_capability(self):
        for label, (config, makefile) in FIXTURES.items():
            texts = {**{name: text for name, text in __import__("bootstrap").desired_files(config).items()
                        if name in {"Makefile", ".vscode/tasks.json", ".vscode/settings.json"}},
                     "workflow": adapters.workflow(config)}
            for name, text in texts.items():
                with self.subTest(fixture=label, file=name):
                    self.assertNotRegex(text, r"(?i)pandoc|research|latex-ai-(?:run|figure|freshness|history|claims|md-)")

    def test_the_policy_and_the_guide_do_not_describe_what_is_gone(self):
        for name in ("templates/AGENTS.md", "docs/handbook.md", "README.md", "skills/latex-ai-workbench/SKILL.md"):
            text = (PACKAGE / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertIsNone(REMOVED_WORDS.search(text), REMOVED_WORDS.search(text))
        self.assertFalse({"research", "numerics", "provenance", "freshness", "claims"} & set(guide.PURPOSE))

    def test_no_live_document_describes_what_is_gone(self):
        for path in sorted((PACKAGE / "docs").glob("*.md")):
            if path.name == "handbook.md":
                continue
            with self.subTest(file=path.name):
                self.assertIsNone(REMOVED_WORDS.search(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
