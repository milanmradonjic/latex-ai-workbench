"""Regressions for the architecture review's installed workflow failures."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from test_support import isolate_environment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap
import core
import schema
import latex
import runtime


class ReviewFixes(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-review-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def install(self, *arguments, env=None):
        return subprocess.run([sys.executable, "-B", str(bootstrap.PACKAGE / "latex-ai-init"),
                               "init", str(self.project), *arguments], env=env, capture_output=True, text=True)

    def test_installation_and_diff_without_git(self):
        tools = self.project / "tools"; tools.mkdir()
        for name in ("make", "python3"):
            (tools / name).symlink_to(shutil.which(name))
        # Hermetic: CI exports LATEX_AI_BASE, all zeros on a new branch, which would replace the Git diagnosis.
        env = {**{k: v for k, v in os.environ.items() if k != "LATEX_AI_BASE"}, "PATH": str(tools)}
        result = self.install("--modules", "", env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([sys.executable, str(bootstrap.PACKAGE / "latex-ai-init"), "diff", str(self.project)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([sys.executable, str(self.project / ".latex-ai/workbench.py"), "validate", "--project", str(self.project)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Git is not installed", result.stdout)

    def test_json_results_wrap_the_output_and_preserve_exit_status(self):
        p = self.project
        self.assertEqual(self.install("--modules", "").returncode, 0)
        for action in ("status", "check"):
            result = subprocess.run([sys.executable, str(p / ".latex-ai/workbench.py"), action, "--project", str(p), "--json"],
                                    capture_output=True, text=True)
            data = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, data)
            self.assertEqual(data["exit_status"], 0)
            self.assertEqual(data["status"], "success")
            self.assertIsInstance(data["result"], dict)
        (p / "broken.json").write_text("{invalid}")
        result = subprocess.run([sys.executable, str(p / ".latex-ai/workbench.py"), "check", "--project", str(p), "--json"],
                                capture_output=True, text=True)
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["exit_status"], 1)
        self.assertIn("broken.json", data["stderr"])

    def test_portability_preflight_has_a_report_without_a_traceback(self):
        tools = self.project / "tools"; tools.mkdir()
        result = subprocess.run([sys.executable, str(bootstrap.PACKAGE / "tests/portability.py"),
                                 "--output-parent", str(self.project)], env={**os.environ, "PATH": str(tools)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing tools:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(next(self.project.glob("latex-ai-portability-*/report.json")).read_text())
        self.assertEqual(report["status"], "blocked")
        self.assertIn("chktex", report["missing_tools"])

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "needs pdfLaTeX")
    def test_default_build_receipt_rejects_stale_verify_and_export(self):
        p = self.project
        source = p / "main.tex"
        source.write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'lint': {'enabled': False}, 'output_dir': '.'}}}}, 'integrations': {'ci': {'pdf_artifact': True}}}
        with contextlib.redirect_stdout(io.StringIO()):
            latex.build(p, schema.document_settings(config))
            latex.build(p, schema.document_settings(config))
            source.write_text(source.read_text().replace("Fixture", "\\undefinedcommand"))
            for action in (latex.verify, latex.artifact):
                with self.subTest(action=action.__name__), self.assertRaisesRegex(core.WorkbenchError, "freshness|receipt"):
                    action(p, schema.document_settings(config))
            with self.assertRaises(core.WorkbenchError):
                latex.build(p, schema.document_settings(config))
            source.write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
            with self.assertRaises(core.WorkbenchError):
                latex.verify(p, schema.document_settings(config))

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "needs pdfLaTeX")
    def test_existing_make_target_and_custom_build_work_together(self):
        p = self.project
        (p / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        result = self.install("--build-command", '["make","pdf"]', "--no-lint", "--skip-editor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with (p / "Makefile").open("a") as stream:  # the project's own rule goes after what init wrote
            stream.write("\npdf:\n\t@echo compiler >> calls\n\tlatexmk -pdf -recorder -interaction=nonstopmode -halt-on-error main.tex\n")
        for count in range(1, 3):
            result = subprocess.run(["make", "-j4", "check"], cwd=p, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len((p / "calls").read_text().splitlines()), count)
        self.assertEqual(latex.read_receipt(p, schema.document_settings(schema.load_config(p)))["status"], "verified")
        # An unchanged raw project build retains its valid receipt. The reserved
        # wrapper is what establishes a new one after inputs or outputs change.
        receipt = (p / latex.receipt_path(schema.document_settings(schema.load_config(p)))).read_bytes()
        result = subprocess.run(["make", "pdf"], cwd=p, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((p / latex.receipt_path(schema.document_settings(schema.load_config(p)))).read_bytes(), receipt)


if __name__ == "__main__":
    unittest.main()
