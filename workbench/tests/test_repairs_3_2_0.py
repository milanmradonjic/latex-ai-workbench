"""3.2.0: --document names a LaTeX document, so a project without LaTeX refuses it and says how to turn LaTeX on.

Before, `check --document X` and `bib-check --document X` in a project created without LaTeX stopped with an internal
error (`documents.py` was not installed there). Once the configuration code moved into `schema.py`, which every
project has, they refused, but without the hint `build --document X` gives; where LaTeX had been disabled they
never gave one.
"""
import unittest

from test_support import ProjectCase

TEX = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


class DocumentSelectorWithoutLatex(ProjectCase):
    def refused(self, *args):
        result = self.command(*args, expected=1)
        shown = result.stdout + result.stderr
        self.assertNotIn("INTERNAL ERROR", shown)
        self.assertIn("Module is disabled: latex", result.stderr)
        self.assertIn("--enable latex", result.stderr, "the error must say how to turn LaTeX on")

    def test_a_project_created_without_latex_refuses_the_selector_and_says_how_to_enable_it(self):
        (self.project / "README.md").write_text("notes\n")
        self.install("init", "--profile", "core", "--skip-editor")
        for action in ("check", "bib-check", "build"):  # build always did
            with self.subTest(action=action):
                self.refused(action, "--document", "paper")

    def test_a_project_that_disabled_latex_refuses_it_the_same_way(self):
        (self.project / "main.tex").write_text(TEX)
        self.install("init", "--profile", "writing", "--root", "main.tex", "--engine", "pdflatex", "--no-lint", "--skip-editor")
        self.install("configure", "--disable", "latex")
        for action in ("check", "bib-check", "build"):
            with self.subTest(action=action):
                self.refused(action, "--document", "manuscript")

    def test_with_latex_on_the_selector_still_selects_and_still_rejects_an_unknown_name(self):
        (self.project / "main.tex").write_text(TEX)
        self.install("init", "--profile", "writing", "--root", "main.tex", "--engine", "pdflatex", "--no-lint", "--skip-editor")
        self.command("bib-check", "--document", "manuscript")
        refused = self.command("check", "--document", "nope", expected=1)
        self.assertIn("Unknown document: 'nope'", refused.stderr)
        self.assertNotIn("INTERNAL ERROR", refused.stdout + refused.stderr)


if __name__ == "__main__":
    unittest.main()
