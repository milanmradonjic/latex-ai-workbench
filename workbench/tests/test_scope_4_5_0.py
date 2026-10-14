"""Workbench 4.5.0, step 3.4 of docs/maintainers/plan-after-4.4.0.md: one engine (pdflatex), one bibliography program (BibTeX), no installer profiles.

`--engine`, `--backend` and `--profile` are gone from `init`, as are the lualatex, xelatex and biber paths behind them and the `biblatex` export format. A configuration that
says what stays (`engine: pdflatex`, `backend: none` or `bibtex`, export format `bibtex`) works as it did, and anything else is refused by name with a hint that points at
`build_command`. `--modules` chooses what a profile chose: `--modules ""` was `--profile core` and `--modules latex` was `--profile writing`.
"""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import core
import diagnostics
import latex
import schema
from test_support import ProjectCase

SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"


def latex_module(document=None, defaults=None):
    values = {"default_document": "paper", "documents": {"paper": {"root": "main.tex", **(document or {})}}}
    if defaults:
        values["defaults"] = defaults
    return values


def configuration(document=None, defaults=None, **bibliography):
    modules = {"latex": latex_module(document, defaults)}
    if bibliography:
        modules["bibliography"] = {"files": [], **bibliography}
    return {"schema_version": 3, "modules": modules}


REFUSED = (  # what 4.4.2 accepted and 4.5.0 refuses, and the word the message must name
    ("a document's engine, lualatex", configuration({"engine": "lualatex"}), "lualatex"),
    ("a document's engine, xelatex", configuration({"engine": "xelatex"}), "xelatex"),
    ("the default engine", configuration(defaults={"engine": "xelatex"}), "xelatex"),
    ("a document's backend", configuration({"backend": "biber"}), "biber"),
    ("the default backend", configuration(defaults={"backend": "biber"}), "biber"),
    ("a default engine every document overrides", configuration({"engine": "pdflatex"}, defaults={"engine": "xelatex"}), "xelatex"),
    ("a default backend every document overrides", configuration({"backend": "none"}, defaults={"backend": "biber"}), "biber"),
    ("the export format", configuration(export={"path": "refs.bib", "format": "biblatex"}), "biblatex"),
)
ACCEPTED = (  # what stays, and worked before
    configuration({"engine": "pdflatex", "backend": "none"}),
    configuration({"engine": "pdflatex", "backend": "bibtex"}),
    configuration(defaults={"engine": "pdflatex", "backend": "bibtex"}),
    configuration({"backend": "bibtex"}, files=["refs.bib"], export={"path": "refs.bib", "format": "bibtex"}),
)


class WhatIsGone(ProjectCase):
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
        self.assertEqual(diagnostics.TOOLS, ("make", "git", "latexmk", "pdflatex", "chktex", "bibtex"))

    def test_messages_only_biber_printed_are_not_read_as_errors(self):
        """The log patterns kept are LaTeX's and BibTeX's: a Biber `ERROR -` or `WARN -` line is neither a failure nor a warning."""
        self.configure()
        self.edit_config(lambda data: data["modules"]["latex"]["documents"]["paper"].update(backend="bibtex"))
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


class WhatStays(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE)

    def test_only_pdflatex_and_bibtex_are_accepted_and_the_refusal_says_where_to_go(self):
        for name, config, word in REFUSED:
            with self.subTest(refused=name):
                with self.assertRaises(core.WorkbenchError) as raised:
                    schema.validate_config(self.project, config)
                self.assertIn(word, str(raised.exception))
                self.assertIn("build_command", raised.exception.hint or "")
        for config in ACCEPTED:
            with self.subTest(accepted=json.dumps(config["modules"]["latex"])):
                schema.validate_config(self.project, config)

    def test_the_installed_runtime_refuses_such_a_configuration_by_name(self):
        self.install("init", "--skip-editor")
        self.edit_config(lambda data: data["modules"]["latex"]["documents"]["manuscript"].update(engine="xelatex"))
        result = self.command("check", expected=1)
        self.assertIn("xelatex", result.stderr)
        self.assertIn("build_command", result.stderr)

    def init_project(self, name, source, *options):
        """`init` in a fresh folder holding one manuscript; returns the folder's configuration."""
        folder = self.root / name
        folder.mkdir()
        (folder / "main.tex").write_text(source)
        (folder / "refs.bib").write_text("@misc{fixture, title={Synthetic fixture}}\n")
        self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), "init", *options, str(folder))
        return json.loads((folder / core.CONFIG).read_text())

    def test_modules_choose_what_the_profiles_chose(self):
        self.assertEqual(self.init_project("core", SOURCE, "--modules", "")["modules"], {})
        document = {"root": "main.tex", "engine": "pdflatex", "backend": "none", "lint": {"enabled": True, "args": []},
                    "build_command": None, "output_dir": None}
        self.assertEqual(self.init_project("writing", SOURCE, "--modules", "latex")["modules"],
                         {"latex": {"default_document": "manuscript", "documents": {"manuscript": document}}})

    def test_init_reads_a_bibtex_bibliography_and_nothing_else_about_how_to_build(self):
        modules = self.init_project("bibtex", SOURCE.replace("x\\end", "\\bibliographystyle{plain}\\bibliography{refs}\\end"), "--skip-editor")["modules"]
        document = modules["latex"]["documents"]["manuscript"]
        self.assertEqual((document["engine"], document["backend"]), ("pdflatex", "bibtex"))
        self.assertEqual(modules["bibliography"]["files"], ["refs.bib"])

    def test_init_no_longer_guesses_another_engine_or_biber_from_the_source(self):
        sources = ("% !TeX program = xelatex\n" + SOURCE,
                   SOURCE.replace("\\begin", "\\usepackage{fontspec}\\begin"),
                   SOURCE.replace("\\begin", "\\usepackage{luacode}\\begin"),
                   SOURCE.replace("\\begin", "\\usepackage[backend=biber]{biblatex}\\addbibresource{refs.bib}\\begin"))
        for number, source in enumerate(sources):
            with self.subTest(source=source.splitlines()[0][:40]):
                modules = self.init_project(f"guess{number}", source, "--skip-editor")["modules"]
                document = modules["latex"]["documents"]["manuscript"]
                self.assertEqual((document["engine"], document["backend"]), ("pdflatex", "none"))
                self.assertNotIn("bibliography", modules)

    def test_the_default_build_asks_latexmk_for_pdf_output(self):
        self.install("init", "--skip-editor")
        view = schema.document_settings(schema.load_config(self.project))
        commands = []
        with patch.object(latex, "run_compiler", lambda project, config, command, **kw: commands.append(command)):
            latex.compile_document(self.project, view)
        self.assertEqual(commands[0][:2], ["latexmk", "-pdf"])


if __name__ == "__main__":
    unittest.main()
