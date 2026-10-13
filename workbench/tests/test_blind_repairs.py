"""Installed-workflow regressions from the ten blind reviewers (current schema only)."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
import schema
import documents
import latex
from test_support import fixture_env, isolate_environment

PACKAGE = Path(__file__).resolve().parents[1]
TEX = shutil.which("latexmk") and shutil.which("pdflatex")
SOURCE = "\\documentclass{article}\n\\begin{document}A note.\\end{document}\n"


class BlindRepairTests(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.directory = tempfile.TemporaryDirectory(prefix="workbench-blind-fix-")
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name).resolve()

    def command(self, *argv, cwd=None, expected=0):
        result = subprocess.run(argv, cwd=cwd or self.project, env=fixture_env(),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def install(self, *args, expected=0):
        return self.command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"),
                            *args, expected=expected)

    def fixture(self, project=None, custom=True, hidden=False):
        project = project or self.project
        (project / "tex/nested").mkdir(parents=True)
        text = SOURCE if not hidden else SOURCE.replace("A note.", "\\def\\partname{hidden}\\input{\\partname}")
        (project / "tex/nested/paper.tex").write_text(text)
        if hidden:
            (project / ("hidden.tex" if custom else "tex/nested/hidden.tex")).write_text("Original source.\n")
        settings = {"root": "tex/nested/paper.tex", "lint": {"enabled": False}, "output_dir": "custom/output with spaces"}
        if custom:
            settings["build_command"] = ["latexmk", "-pdf", "-recorder", "-interaction=nonstopmode",
                                         "-halt-on-error", "-outdir=custom/output with spaces", "tex/nested/paper.tex"]
        config = {"schema_version": 3, "modules": {"latex": {"default_document": "paper", "documents": {"paper": settings}}},
                  "integrations": {"ci": {"enabled": False, "pdf_artifact": True}}}
        (project / core.CONFIG).write_text(json.dumps(config))
        self.install("init", str(project))
        return config

    @unittest.skipUnless(TEX, "real compiler required; fixture lint deliberately disabled")
    def test_first_custom_nested_build_needs_no_retry(self):
        self.fixture()
        self.command("make", "latex-ai-build")
        self.assertEqual(documents.report(self.project, schema.load_config(self.project))[0]["state"], "current")

    @unittest.skipUnless(TEX, "real compiler required; fixture lint deliberately disabled")
    def test_changed_compiler_recorded_input_refuses_verification_and_export(self):
        config = self.fixture(hidden=True)
        # Permit the old first-build retry here so the stale-certification failure
        # is independently demonstrated, rather than hidden by the first-run defect.
        first = subprocess.run(["make", "latex-ai-build"], cwd=self.project,
                               env=fixture_env(), capture_output=True, text=True, timeout=30)
        if first.returncode:
            self.command("make", "latex-ai-build")
        (self.project / "hidden.tex").write_text("Changed source.\n")
        result = self.command(sys.executable, ".latex-ai/workbench.py", "verify", "--json", expected=1)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")
        self.command("make", "latex-ai-pdf-artifact", expected=2)
        self.assertEqual(documents.report(self.project, config)[0]["state"], "stale")

    @unittest.skipUnless(TEX, "real compiler required; fixture lint deliberately disabled")
    def test_recorder_context_matrix_and_durable_dependencies(self):
        for custom in (False, True):
            for spelling in ("plain", "Project With Spaces"):
                with self.subTest(custom=custom, spelling=spelling):
                    project = self.project / str(custom) / spelling
                    config = self.fixture(project, custom, hidden=True)
                    self.command("make", "latex-ai-build", cwd=project)
                    view = schema.document_settings(config)
                    name = "hidden.tex" if custom else "tex/nested/hidden.tex"
                    receipt = latex.read_receipt(project, view)
                    self.assertIsNotNone(receipt["inputs"].get(name), receipt)
                    self.assertNotIn("tex/nested/tex/nested/paper.tex", receipt["inputs"])
                    Path(str(latex.output_paths(project, view)[2]) + ".fls").unlink()
                    self.assertEqual(documents.report(project, config)[0]["state"], "current")
                    self.assertIn(name, documents.dependency_index(project, config)["paper"])
                    (project / name).write_text("Changed hidden source.\n")
                    self.assertEqual(documents.report(project, config)[0]["state"], "stale")
                    self.command("make", "latex-ai-build", cwd=project)
                    self.command("make", "latex-ai-pdf-artifact", cwd=project)

    def test_recorder_pwd_is_authoritative_and_unresolvable_relative_inputs_fail(self):
        nested = self.project / "nested"
        nested.mkdir()
        (self.project / "source with spaces.txt").write_text("source")
        (nested / "alias.txt").symlink_to(self.project / "source with spaces.txt")
        fls = self.project / "paper.fls"
        fls.write_text(f"PWD {self.project}\nINPUT source with spaces.txt\nPWD {nested}\nINPUT alias.txt\nINPUT /outside/system.tex\n")
        self.assertEqual(latex.recorder_inputs(self.project, fls), {"source with spaces.txt"})
        fls.write_text("INPUT relative.txt\n")
        with self.assertRaises(core.WorkbenchError):
            latex.recorder_inputs(self.project, fls)

    @unittest.skipUnless(TEX, "real compiler required; fixture lint deliberately disabled")
    def test_native_discovery_is_protected_before_certification(self):
        for mutate_again in (False, True):
            with self.subTest(mutate_again=mutate_again):
                project = self.project / str(mutate_again)
                config = self.fixture(project, custom=False, hidden=True)
                hidden = project / "tex/nested/hidden.tex"
                actual_run = latex.run_compiler
                calls = []

                def change_after_read(*args, **kwargs):
                    result = actual_run(*args, **kwargs)  # genuine TeX has consumed the source
                    calls.append(1)
                    if len(calls) == 1 or mutate_again:
                        hidden.write_text(f"Changed source {len(calls)}.\n")
                    return result

                with patch.object(latex, "run_compiler", side_effect=change_after_read):
                    if mutate_again:
                        with self.assertRaises(core.WorkbenchError):
                            latex.build(project, schema.document_settings(config))
                    else:
                        latex.build(project, schema.document_settings(config))
                self.assertEqual(len(calls), 2)
                self.assertEqual(documents.report(project, config)[0]["state"], "failed" if mutate_again else "current")
                if not mutate_again and shutil.which("pdftotext"):
                    pdf = Path(str(latex.output_paths(project, schema.document_settings(config))[2]) + ".pdf")
                    text = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True)
                    self.assertIn("Changed source 1.", text)
                    self.assertNotIn("Original source.", text)

    def test_discovery_rebuild_still_rejects_input_changes(self):
        config = self.fixture()
        settings = config["modules"]["latex"]["documents"]["paper"]
        settings["output_dir"] = "outputs"
        settings["build_command"] = [sys.executable, "builder.py"]
        (self.project / "hidden.txt").write_text("original")
        (self.project / "builder.py").write_text(
            "from pathlib import Path\n"
            "count=int(Path('count').read_text())+1 if Path('count').exists() else 1\n"
            "Path('count').write_text(str(count))\n"
            "out=Path('outputs');out.mkdir(exist_ok=True)\n"
            "(out/'paper.pdf').write_bytes(b'%PDF-fixture')\n"
            "(out/'paper.log').write_text('Clean log\\n')\n"
            "(out/'paper.fls').write_text('PWD '+str(Path.cwd())+'\\nINPUT hidden.txt\\nINPUT tex/nested/paper.tex\\n')\n"
            "if count==2: Path('hidden.txt').write_text('changed during protected rebuild')\n")
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("upgrade", str(self.project))
        self.command("make", "latex-ai-build", expected=2)
        self.assertEqual((self.project / "count").read_text(), "2")
        self.assertEqual(documents.report(self.project, config)[0]["state"], "failed")

    def test_receipt_without_protected_discovery_guarantee_cannot_certify(self):
        config = self.fixture(custom=False, hidden=True)
        view = schema.document_settings(config)
        stem = latex.output_paths(self.project, view)[2]
        stem.parent.mkdir(parents=True, exist_ok=True)
        Path(str(stem) + ".pdf").write_bytes(b"%PDF-old")
        Path(str(stem) + ".log").write_text("Clean old log\n")
        # Format 2 allowed newly observed inputs to be hashed after compilation.
        # Its recorder may already be gone; do not reuse its certification or
        # its incomplete stored dependency list under the new guarantee.
        path = self.project / latex.receipt_path(view)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": 2, "status": "verified", "identity": latex.build_identity(self.project, view),
                                    "inputs": latex.build_inputs(self.project, view), "outputs": latex.build_outputs(self.project, view)}))
        self.assertEqual(documents.report(self.project, config)[0]["state"], "stale")
        with self.assertRaises(core.WorkbenchError):
            latex.verify(self.project, view)

    def test_foreign_installed_runtime_reports_project_context_not_internal_fault(self):
        notebook = self.project / "notebook"
        notebook.mkdir()
        self.install("init", str(notebook), "--profile", "core")
        self.fixture()
        script = notebook / ".latex-ai/workbench.py"
        result = self.command(sys.executable, str(script), "status", "--json", expected=1)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "failed")
        self.assertIn("--project", data["stderr"])
        self.command(sys.executable, str(script), "status", "--project", str(notebook))
        (notebook / core.CONFIG).write_text("{broken")
        self.command(sys.executable, str(script), "status", cwd=notebook)

    def test_configure_reports_resolved_policy_and_missing_root_recovery(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", str(self.project), "--no-lint", "--no-ci", "--skip-editor")
        (self.project / "note.tex").write_text(SOURCE)
        result = self.install("configure", str(self.project), "--document", "note", "--root", "note.tex", "--dry-run")
        self.assertIn("lint: enabled", result.stdout)
        self.assertIn("output: .latex-ai/artifacts/documents/note/build", result.stdout)
        self.assertIn("defaults", result.stdout)
        result = self.install("configure", str(self.project), "--document", "note", "--root", "note.tex", "--no-lint", "--dry-run", "--json")
        data = json.loads(result.stdout)
        self.assertFalse(data["document"]["lint"]["enabled"])
        self.assertEqual(data["document"]["name"], "note")
        result = self.install("configure", str(self.project), "--document", "absent", "--root", "missing.tex", expected=2)
        self.assertIn("Hint:", result.stderr)

    def test_bibliography_success_names_actual_documents_and_files(self):
        config = self.fixture()
        (self.project / "note.tex").write_text(SOURCE)
        (self.project / "paper.bib").write_text("@misc{paper, title={Paper}}\n")
        (self.project / "note.bib").write_text("@misc{note, title={Note}}\n")
        config["modules"]["latex"]["documents"]["paper"]["bibliography_files"] = ["paper.bib"]
        config["modules"]["latex"]["documents"]["note"] = {"root": "note.tex", "bibliography_files": ["note.bib"], "lint": {"enabled": False}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("upgrade", str(self.project))
        result = self.command(sys.executable, ".latex-ai/workbench.py", "bib-check", "--document", "note", "--json")
        data = json.loads(result.stdout)
        self.assertEqual(data["result"]["bibliographies"], [{"document": "note", "files": ["note.bib"]}])
        result = self.command("make", "latex-ai-bib-check")
        self.assertIn("paper: paper.bib", result.stdout)
        self.assertIn("note: note.bib", result.stdout)

    def test_live_orphan_compiler_is_visible_in_document_status(self):
        config = self.fixture()
        view = schema.document_settings(config)
        receipt = {"status": "running", "owner_pid": 101, "owner_token": "owner", "compiler_groups": [{"pid": 202, "token": "compiler"}]}
        with patch.object(latex, "read_receipt", return_value=receipt), patch.object(latex, "process_alive", return_value=False), patch.object(latex, "group_alive", return_value=True):
            row = documents.report(self.project, config)[0]
        self.assertEqual(row["state"], "running")
        self.assertEqual(row["ownership"], {"owner_pid": 101, "owner_alive": False, "compiler_groups": [202]})


if __name__ == "__main__":
    unittest.main()
