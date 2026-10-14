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


REFUSED = (  # what 4.4.2 accepted and 4.5.0 refuses: the word the message must name, and the word the hint must hold
    ("a document's engine, lualatex", configuration({"engine": "lualatex"}), "lualatex", "build_command"),
    ("a document's engine, xelatex", configuration({"engine": "xelatex"}), "xelatex", "build_command"),
    ("the default engine", configuration(defaults={"engine": "xelatex"}), "xelatex", "build_command"),
    ("a document's backend", configuration({"backend": "biber"}), "biber", "build_command"),
    ("the default backend", configuration(defaults={"backend": "biber"}), "biber", "build_command"),
    ("a default engine every document overrides", configuration({"engine": "pdflatex"}, defaults={"engine": "xelatex"}), "xelatex", "build_command"),
    ("a default backend every document overrides", configuration({"backend": "none"}, defaults={"backend": "biber"}), "biber", "build_command"),
    ("the export format", configuration(export={"path": "refs.bib", "format": "biblatex"}), "biblatex", "Better BibTeX"),
    ("an export without a format", configuration(export={"path": "refs.bib"}), "is missing", "Better BibTeX"),
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
        self.assertEqual(set(diagnostics.tool_versions()) - {"python", "platform"}, {"make", "git", "latexmk", "pdflatex", "chktex", "bibtex"})

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


BUILDER_FIXTURE = (  # the stand-in compiler that produced FROZEN_RECEIPT under 4.4.2, byte for byte
    "from pathlib import Path\n"
    "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
    "(out/'main.pdf').write_bytes(b'%PDF-fixture\\n'); (out/'main.log').write_text('Clean log\\n'); (out/'main.fls').write_text('PWD /fixture\\nINPUT main.tex\\n')\n")
FROZEN_RECEIPT = {  # a verified receipt exactly as 4.4.2 wrote it for a document with a build_command; 4.5.0 must judge it current
    "schema_version": 3, "status": "verified",
    "identity": {"root": "main.tex", "engine": "pdflatex", "output": "outputs/main", "build_command": ["python3", "builder.py"],
                 "bibliography": {"files": [], "backend": "none", "export": None}},
    "inputs": {"builder.py": "f12bee0fb7d77e4876bed8b7be1d18697a6491d4f3ebe34b299d28e217a9af11",
               "main.tex": "4bce36483fade5d4eb65a363da4155cb74744440dc9b9cc5e3f4f151659b6005"},
    "input_roles": {"builder.py": "source", "main.tex": "source"},
    "outputs": {".pdf": "6c8d22e47796a2cf56b46bf9aa0dba0f8c666f324080ad8fcdea4b1b3c5b65c2",
                ".log": "da1292e4af11a88d7215a8741c91830d33817b6ecc033653f243844a7cc33623"},
}
BIBTEX_IDENTITY = {  # what 4.4.2 recorded for a default-layout document with BibTeX and a Zotero export
    "root": "main.tex", "engine": "pdflatex", "output": ".latex-ai/artifacts/documents/paper/build/main", "build_command": None,
    "bibliography": {"files": ["refs.bib"], "backend": "bibtex", "export": {"path": "refs.bib", "required": True, "format": "bibtex"}}}


class Receipts(ProjectCase):
    """The plan's criterion for this step: the receipts of projects that use only what stays do not change."""

    def test_a_receipt_written_by_4_4_2_is_still_current(self):
        (self.project / "main.tex").write_text(SOURCE)
        (self.project / "builder.py").write_text(BUILDER_FIXTURE)
        (self.project / "outputs").mkdir()
        (self.project / "outputs/main.pdf").write_bytes(b"%PDF-fixture\n")
        (self.project / "outputs/main.log").write_text("Clean log\n")
        (self.project / core.CONFIG).write_text(json.dumps({"schema_version": 3, "modules": {"latex": {"default_document": "paper", "documents": {
            "paper": {"root": "main.tex", "lint": {"enabled": False}, "output_dir": "outputs", "build_command": ["python3", "builder.py"]}}}}}))
        receipt = self.project / ".latex-ai/artifacts/documents/paper/build-receipt.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps(FROZEN_RECEIPT, indent=2) + "\n")
        self.assertEqual(self.state(), "current")

    def test_the_build_identity_keeps_the_shape_and_values_4_4_2_recorded(self):
        (self.project / "main.tex").write_text(SOURCE)
        config = configuration({"backend": "bibtex"}, files=["refs.bib"], export={"path": "refs.bib", "required": True, "format": "bibtex"})
        view = schema.document_settings(core.effective_config(config))
        self.assertEqual(latex.build_identity(self.project, view), BIBTEX_IDENTITY)


class WhatStays(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE)

    def test_only_pdflatex_and_bibtex_are_accepted_and_the_refusal_says_where_to_go(self):
        for name, config, word, in_hint in REFUSED:
            with self.subTest(refused=name):
                with self.assertRaises(core.WorkbenchError) as raised:
                    schema.validate_config(self.project, config)
                self.assertIn(word, str(raised.exception))
                self.assertIn(in_hint, raised.exception.hint or "")
        for config in ACCEPTED:
            with self.subTest(accepted=json.dumps(config["modules"]["latex"])):
                schema.validate_config(self.project, config)

    def test_the_installed_runtime_refuses_such_a_configuration_by_name(self):
        self.install("init", "--skip-editor")
        self.edit_config(lambda data: data["modules"]["latex"]["documents"]["manuscript"].update(engine="xelatex"))
        result = self.command("check", expected=1)
        self.assertIn("xelatex", result.stderr)
        self.assertIn("build_command", result.stderr)

    def test_status_and_help_say_what_to_edit_when_the_configuration_is_refused(self):
        """After an upgrade the first command is `make status`; it must carry the hint, not point at a last good copy that is the same configuration."""
        self.install("init", "--skip-editor")
        self.edit_config(lambda data: data["modules"]["latex"]["documents"]["manuscript"].update(engine="xelatex"))
        for action in ("status", "help", "guide"):
            with self.subTest(action=action):
                text = self.command(action).stdout
                self.assertIn("engine 'xelatex' is not supported", text)
                self.assertIn("edit .latex-ai.json: remove the engine setting", text)
        (self.project / core.CONFIG).write_text("{")  # a problem that carries no hint of its own keeps the old advice
        self.assertIn("version control has the last good copy", self.command("status").stdout)

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
