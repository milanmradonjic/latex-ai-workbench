"""Workbench 4.5.1: `init` stops at a paper that needs a toolchain the workbench does not build, and says what to declare.

4.5.0 stopped reading the source for lualatex, xelatex or biber, so `init` on such a paper succeeded as pdflatex and the first build failed with the compiler's
own message. The guard reads the source for the few signs that it needs another engine or biber, refuses before writing anything, and prints the `--build-command`
to run `init` again with, which is the whole fix. A `--build-command` takes the guard away, since the project then builds itself; a project that has its own
configuration is not second-guessed. The hint is tested by following it with the real tools where they are installed.
"""
import json
import re
import shlex
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import core
from test_support import ProjectCase

DOCUMENT = "\\documentclass{article}\n%s\\begin{document}\n%s\\end{document}\n"
NEEDS = (  # source, what the message must name, latexmk's flag the hint must carry
    ("magic comment, lualatex", "% !TeX program = lualatex\n" + DOCUMENT % ("", "x\n"), "lualatex", "-lualatex"),
    ("magic comment, xelatex", "% !TeX TS-program = xelatex\n" + DOCUMENT % ("", "x\n"), "xelatex", "-xelatex"),
    ("directlua", DOCUMENT % ("", "\\directlua{tex.print('x')}\n"), "lualatex", "-lualatex"),
    ("luacode", DOCUMENT % ("\\usepackage{luacode}\n", "x\n"), "lualatex", "-lualatex"),
    ("xeCJK", DOCUMENT % ("\\usepackage{xeCJK}\n", "x\n"), "xelatex", "-xelatex"),
    ("fontspec", DOCUMENT % ("\\usepackage{fontspec}\n", "x\n"), "fontspec", "-lualatex"),
    ("biblatex", DOCUMENT % ("\\usepackage{biblatex}\n\\addbibresource{refs.bib}\n", "x\\printbibliography\n"), "biblatex", "-pdf"),
    ("biblatex with biber named", DOCUMENT % ("\\usepackage[backend=biber]{biblatex}\n", "x\n"), "biblatex", "-pdf"),
)
FINE = (  # sources that mention them without needing them
    ("a magic comment for pdflatex", "% !TeX program = pdflatex\n" + DOCUMENT % ("", "x\n")),
    ("fontspec in a comment", DOCUMENT % ("% \\usepackage{fontspec}\n", "x\n")),
    ("biblatex processed by BibTeX", DOCUMENT % ("\\usepackage[backend=bibtex]{biblatex}\n\\addbibresource{refs.bib}\n", "x\\printbibliography\n")),
    ("plain BibTeX", DOCUMENT % ("", "x\\bibliographystyle{plain}\\bibliography{refs}\n")),
)
BIB = "@misc{fixture, title={Synthetic fixture}, year={2000}}\n"


class Guard(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "refs.bib").write_text(BIB)

    def source(self, text, name="main.tex"):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_init_stops_at_a_source_that_needs_another_toolchain_and_says_what_to_declare(self):
        for name, text, what, flag in NEEDS:
            with self.subTest(source=name):
                self.source(text)
                before = self.snapshot()
                result = self.install("init", "--skip-editor", expected=2)
                self.assertIn(what, result.stderr.split("Hint:")[0])
                hint = result.stderr.split("Hint:")[1]
                self.assertIn("--build-command", hint)
                self.assertIn(f'"{flag}"', hint)
                self.assertIn("main.tex", hint)
                self.assertEqual(before, self.snapshot(), "a refused init wrote files")

    def test_a_build_command_takes_the_guard_away(self):
        self.source(NEEDS[1][1])
        self.install("init", "--skip-editor", "--build-command", '["make", "pdf"]')
        document = json.loads((self.project / core.CONFIG).read_text())["modules"]["latex"]["documents"]["manuscript"]
        self.assertEqual(document["build_command"], ["make", "pdf"])

    def test_the_guard_also_stops_a_module_selection_that_includes_latex(self):
        self.source(NEEDS[0][1])
        self.install("init", "--modules", "latex", expected=2)

    def test_what_only_mentions_another_toolchain_is_not_refused(self):
        for name, text in FINE:
            with self.subTest(source=name):
                shutil.rmtree(self.project)
                self.project.mkdir()
                (self.project / "refs.bib").write_text(BIB)
                self.source(text)
                self.install("init", "--skip-editor")

    def test_a_project_with_its_own_configuration_is_not_second_guessed(self):
        self.source(NEEDS[1][1])
        self.configure()
        self.install("init", "--skip-editor")

    def hint_command(self, stderr):
        """The --build-command argument the hint prints, as init would receive it."""
        return shlex.split(re.search(r"--build-command ('.*?') \(", stderr)[1])[0]

    def follow_the_hint(self, text, written_by, pattern, root="main.tex"):
        """Run what the hint says, then check: the paper builds, the receipt is current, and the named tool left its mark in a file beside the source."""
        self.source(text, root)
        hint = self.install("init", "--skip-editor", expected=2).stderr
        self.assertIn(f'"{root}"', hint)
        self.install("init", "--skip-editor", "--no-lint", "--build-command", self.hint_command(hint))
        self.command("check")
        self.assertEqual(self.state(), "current")
        beside = (self.project / root).parent
        self.assertTrue((beside / "main.pdf").read_bytes().startswith(b"%PDF-"))
        self.assertRegex((beside / written_by).read_text(errors="replace"), pattern)

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("lualatex"), "lualatex needed")
    def test_following_the_hint_builds_a_lualatex_paper(self):
        self.follow_the_hint("% !TeX program = lualatex\n" + DOCUMENT % ("", "\\directlua{tex.print('Synthetic')}\n"), "main.log", r"Lua(?:HB)?TeX")

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("lualatex"), "lualatex needed")
    def test_following_the_hint_builds_a_paper_in_a_subfolder(self):
        self.follow_the_hint("% !TeX program = lualatex\n" + DOCUMENT % ("", "Synthetic\n"), "main.log", r"Lua(?:HB)?TeX", root="paper/main.tex")

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("xelatex"), "xelatex needed")
    def test_following_the_hint_builds_a_xelatex_paper(self):
        self.follow_the_hint("% !TeX program = xelatex\n" + DOCUMENT % ("", "Synthetic\n"), "main.log", r"XeTeX")

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("biber") and subprocess.run(["kpsewhich", "biblatex.sty"], capture_output=True).stdout.strip(),
                         "biber and biblatex needed")
    def test_following_the_hint_builds_a_biblatex_paper(self):
        self.follow_the_hint(DOCUMENT % ("\\usepackage{biblatex}\n\\addbibresource{refs.bib}\n", "Synthetic~\\cite{fixture}.\\printbibliography\n"), "main.blg", r"Biber")


if __name__ == "__main__":
    unittest.main()
