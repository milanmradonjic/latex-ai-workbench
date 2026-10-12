"""3.5.0: the GitHub actions a workflow runs are pinned to the commit their tag pointed to, with the tag in a comment.

A tag such as `actions/checkout@v7` is resolved again on every run, so a moved or hijacked tag would change what CI
executes, with the project's checkout and its token in reach. A commit cannot move. The workbench pins every action of the
workflows it generates, refuses an action it has no pin for, and keeps this repository's own workflows pinned too.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import adapters
from test_generated_files_guard import FIXTURES

REPOSITORY = Path(__file__).resolve().parents[2]
USES = re.compile(r"^\s*(?:- )?uses: (?!\./)")
PINNED = re.compile(r"^\s*(?:- )?uses: [A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40} # v\d+(?:\.\d+)*$")


def unpinned(text):
    return [line.strip() for line in text.split("\n") if USES.match(line) and not PINNED.match(line)]


class PinnedActions(unittest.TestCase):
    def test_every_workflow_the_workbench_generates_pins_every_action(self):
        for name, (config, _) in FIXTURES.items():
            with self.subTest(configuration=name):
                self.assertEqual(unpinned(adapters.workflow(config)), [])

    def test_a_pin_is_the_commit_of_the_tag_and_keeps_the_tag_for_a_reader(self):
        text = adapters.workflow(FIXTURES["profile-research-paper"][0])
        for action, tag in (("actions/checkout", "v7"), ("actions/upload-artifact", "v7"), ("xu-cheng/texlive-action", "v3")):
            with self.subTest(action=action):
                self.assertRegex(text, rf"uses: {re.escape(action)}@[0-9a-f]{{40}} # {tag}\n")

    def test_the_workbench_refuses_an_action_it_has_no_pin_for(self):
        with self.assertRaises(adapters.WorkbenchError) as raised:
            adapters.pin_actions("      - uses: someone/else@v1\n")
        self.assertIn("someone/else@v1", str(raised.exception))

    def test_the_workflows_of_this_repository_are_pinned_too(self):
        folder = REPOSITORY / ".github" / "workflows"
        if not folder.is_dir():
            self.skipTest("a standalone distribution carries no workflows of its own")
        files = sorted(folder.glob("*.yml"))
        self.assertTrue(files)
        for path in files:
            with self.subTest(workflow=path.name):
                self.assertEqual(unpinned(path.read_text(encoding="utf-8")), [])

    def test_dependabot_keeps_the_pins_of_this_repository_current(self):
        path = REPOSITORY / ".github" / "dependabot.yml"
        if not path.parent.is_dir():
            self.skipTest("a standalone distribution carries no workflows of its own")
        text = path.read_text(encoding="utf-8")
        self.assertRegex(text, r"package-ecosystem: [\"']?github-actions[\"']?")
        self.assertRegex(text, r"directory: [\"']?/[\"']?")


if __name__ == "__main__":
    unittest.main()
