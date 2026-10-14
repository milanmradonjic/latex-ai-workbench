"""Phase 1 of the plan after 3.0.2: one registry (commands.py) holds what six tables used to say about each action."""
import inspect
import re
import subprocess
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import commands
import core
import guide
import runtime


class CommandRegistry(unittest.TestCase):
    def test_every_action_has_exactly_one_handler_and_no_handler_is_left_over(self):
        names = [action.name for action in commands.ACTIONS]
        self.assertEqual(len(names), len(set(names)))
        defined = {name for name, value in vars(runtime).items() if name.startswith("do_") and callable(value)}
        self.assertEqual({action.handler for action in commands.ACTIONS}, defined)
        self.assertEqual(set(runtime.HANDLERS), set(names))

    def test_dispatch_is_a_lookup_not_a_chain_of_branches(self):
        source = inspect.getsource(runtime.dispatch)
        self.assertNotIn("elif", source)
        self.assertIsNone(re.search(r"args\.action\s*(==|!=|in\b|not in\b)", source))

    def test_the_argument_parser_offers_exactly_the_registered_actions(self):
        help_text = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), "--help"], capture_output=True, text=True, check=True).stdout
        choices = [set(group.split(",")) for group in re.findall(r"\{([^}]*)\}", help_text)]  # the actions are the choices that include `check`; an option may have choices of its own
        self.assertIn(set(commands.NAMES), choices)
        self.assertEqual([group for group in choices if "check" in group], [set(commands.NAMES)] * len([group for group in choices if "check" in group]))
        self.assertEqual(runtime.ACTIONS, commands.NAMES)

    def test_the_names_shown_to_readers_are_derived_not_restated(self):
        self.assertIs(guide.COMMANDS, commands.COMMANDS)
        reserved = [command.reserved for command in commands.COMMANDS if command.reserved]
        self.assertEqual(len(reserved), len(set(reserved)))
        shorts = [command.short for command in commands.COMMANDS]
        self.assertEqual(len(shorts), len(set(shorts)))

    def test_the_flags_of_an_action_agree_with_each_other(self):
        for action in commands.ACTIONS:
            with self.subTest(action=action.name):
                if action.standalone:
                    self.assertIsNone(action.module, "a standalone action reads no configuration, so it cannot require a module")
                if action.view:
                    self.assertEqual(action.module, "latex", "only a LaTeX document has a view of the configuration")
                for target in action.targets:
                    self.assertIn(target.selects, commands.RECIPE_ARGUMENTS)
                    if target.selects == "document":
                        self.assertTrue(action.document, "a recipe cannot pass DOC to an action that refuses --document")
                    if target.usage:
                        self.assertEqual(target.usage.split("=")[0], {"document": "DOC", "task": "TASK"}[target.selects])

    def test_json_output_is_native_only_where_the_commands_always_printed_their_own(self):
        self.assertEqual({action.name for action in commands.ACTIONS if action.native_json}, {"plan", "modules"})

    def test_every_installed_runtime_carries_the_registry(self):
        self.assertIn("commands.py", core.RUNTIME_FILES)
        for modules in ({}, {"latex": {"default_document": "paper", "documents": {"paper": {"root": "main.tex"}}}}, {"bibliography": {}}):
            with self.subTest(modules=sorted(modules)):
                self.assertIn("commands.py", core.runtime_sources({"schema_version": 3, "modules": modules}))


if __name__ == "__main__":
    unittest.main()
