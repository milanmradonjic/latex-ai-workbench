"""The one supported project model retains receipt and source safety."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
import schema
import bootstrap
import documents
import latex
import runtime
import schema3_workflow
from test_support import isolate_environment


class SimplificationTests(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.directory = tempfile.TemporaryDirectory(prefix="workbench-3-")
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name).resolve()

    def config(self):
        return {"schema_version": 3, "modules": {"latex": {
            "default_document": "paper", "documents": {"paper": {
                "root": "./main.tex", "lint": {"enabled": False}}}}}}

    def test_hosted_multi_document_workflow_matches_generated_adapter(self):
        self.assertEqual(schema3_workflow.DESTINATION.read_text(), schema3_workflow.generated_workflow())

    def test_old_project_schemas_refuse_installation_without_writes(self):
        for version in (1, 2):
            config = {"schema_version": version, "modules": {}}
            (self.project / core.CONFIG).write_text(json.dumps(config))
            before = {p.name: p.read_bytes() for p in self.project.iterdir()}
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(bootstrap.main(["upgrade", str(self.project)]), 2)
            self.assertEqual(before, {p.name: p.read_bytes() for p in self.project.iterdir()})

    def test_project_commands_reject_document_selector_without_skipping_checks(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n")
        (self.project / core.CONFIG).write_text(json.dumps(self.config()))
        for action in ("plan", "validate", "modules", "doctor", "documents"):
            with self.subTest(action=action), patch.object(sys, "argv", ["workbench", action, "--document", "paper", "--project", str(self.project)]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runtime.main(), 1)

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "real TeX compiler required")
    def test_canonical_receipt_inputs_survive_recorder_removal(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\n\\def\\partname{hidden}\n\\input{\\partname}\n\\end{document}\n")
        (self.project / "hidden.tex").write_text("A hidden source.\n")
        config = self.config()
        schema.validate_config(self.project, config)
        with contextlib.redirect_stdout(io.StringIO()):
            latex.build(self.project, schema.document_settings(config))
        self.assertEqual(documents.report(self.project, config)[0]["state"], "current")
        stem = latex.output_paths(self.project, schema.document_settings(config))[2]
        Path(str(stem) + ".fls").unlink()
        self.assertIn("hidden.tex", documents.dependency_index(self.project, config)["paper"])
        self.assertEqual(documents.report(self.project, config)[0]["state"], "current")
        (self.project / "hidden.tex").write_text("Changed hidden source.\n")
        self.assertEqual(documents.report(self.project, config)[0]["state"], "stale")

    def test_malformed_receipt_dependencies_are_stale_without_breaking_inspection(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n")
        config = self.config()
        config["modules"]["latex"]["documents"]["paper"]["root"] = "main.tex"
        path = self.project / latex.receipt_path(schema.document_settings(config))
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": latex.RECEIPT_SCHEMA, "status": "verified",
            "identity": latex.build_identity(self.project, config), "inputs": {"../outside": None}, "outputs": {}}))
        self.assertEqual(documents.report(self.project, config)[0]["state"], "stale")
        documents.dependency_index(self.project, config)
