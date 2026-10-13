"""Workbench 4.2.0 replaces the long generated handbook by a short manual (see docs/maintainers/minimal-scope.md).

These tests pin what is gone (the generator, the web page, the topics, the packaged copies) and that the manual that replaced it stays short.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import commands
import core
from test_support import ProjectCase

MANUAL_LINES = 60  # a manual that cannot be read in a minute is a handbook again


class NoHandbook(ProjectCase):
    def test_the_handbook_and_its_copies_are_gone(self):
        for name in ("handbook.py", "docs/handbook.md", "docs/handbook.html"):
            with self.subTest(file=name):
                self.assertFalse((PACKAGE / name).exists())
        self.assertNotIn("handbook.py", core.RUNTIME_FILES)
        self.assertNotIn("handbook.py", core.runtime_sources({"schema_version": 3, "modules": {}}))
        self.assertNotIn("handbook", (PACKAGE / "Makefile").read_text(encoding="utf-8"))

    def test_there_is_one_guide_command_and_it_takes_no_topic(self):
        self.assertIn("guide", commands.NAMES)
        self.assertNotIn("guide-html", commands.NAMES)
        self.assertNotIn("topic", commands.RECIPE_ARGUMENTS)
        done = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), "guide", "--topic", "loop", "--project", str(self.project)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("unrecognized arguments", done.stderr)

    def test_the_manual_stays_short_whatever_the_project(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.install("init", "--engine", "pdflatex", "--no-lint")
        text = self.command("guide").stdout
        self.assertLessEqual(len(text.splitlines()), MANUAL_LINES, text)
        self.assertTrue(all(len(line) <= 140 for line in text.splitlines()))

    def test_no_installed_makefile_exports_a_topic(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.install("init", "--engine", "pdflatex", "--no-lint")
        self.assertIsNone(re.search(r"TOPIC", (self.project / "Makefile").read_text(encoding="utf-8")))
        self.assertFalse((self.project / ".latex-ai/handbook.py").exists())


if __name__ == "__main__":
    unittest.main()
