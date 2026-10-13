"""3.5.0, kept in 4.1.0: the GitHub actions this repository's workflows run are pinned to the commit their tag pointed to,
with the tag in a comment.

A tag such as `actions/checkout@v7` is resolved again on every run, so a moved or hijacked tag would change what CI
executes, with the repository's checkout and its token in reach. A commit cannot move. (Until 4.0 the workbench also
generated workflows for the projects it installed, and pinned those; it no longer does.)
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

REPOSITORY = Path(__file__).resolve().parents[2]
USES = re.compile(r"^\s*(?:- )?uses: (?!\./)")
PINNED = re.compile(r"^\s*(?:- )?uses: [A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40} # v\d+(?:\.\d+)*$")


def unpinned(text):
    return [line.strip() for line in text.split("\n") if USES.match(line) and not PINNED.match(line)]


class PinnedActions(unittest.TestCase):

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
