"""Workbench 4.4.1, step 3.1 of docs/maintainers/plan-after-4.4.0.md: refreshing a project's runtime no longer renders its policy, Makefile
and editor files, and `diff` renders what it compares once.

`runtime_files(config)` is the runtime half of `desired_files(config)`, which now builds on it. These tests pin that the two agree (in content and in order,
since `init` and `diff` print in that order), that `runtime` and `diff` keep their behaviour, and that the schema's errors name this workbench.
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import bootstrap
import core
import schema
from test_support import ProjectCase

SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"
CONFIGS = (
    {"schema_version": 3, "modules": {}},
    {"schema_version": 3, "modules": {"latex": {}}},
    {"schema_version": 3, "modules": {"latex": {}, "bibliography": {"files": ["refs.bib"]}}, "integrations": {"editor": False}},
)


class RuntimeApartFromProjectFiles(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE)
        self.configure()
        self.install("init")

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = bootstrap.main([*args, str(self.project)])
        return status, out.getvalue()

    def test_the_runtime_files_are_the_packages_own_files_for_the_modules_in_use(self):
        for config in CONFIGS:
            with self.subTest(modules=sorted(config["modules"])):
                expected = {".latex-ai/" + target: (PACKAGE / source).read_text(encoding="utf-8")
                            for source, target in core.runtime_sources(core.effective_config(config)).items()}
                self.assertTrue(expected)
                self.assertEqual(bootstrap.runtime_files(config), expected)
                self.assertEqual(list(bootstrap.runtime_files(config)), list(expected))  # init and diff print in this order
                self.assertEqual({name: text for name, text in bootstrap.desired_files(config).items() if name.startswith(".latex-ai/")}, expected)

    def test_refreshing_the_runtime_renders_no_project_file(self):
        (self.project / ".latex-ai/guide.py").unlink()
        render = AssertionError("runtime must not render the policy, Makefile and editor files")
        with patch.object(bootstrap, "desired_files", side_effect=render):
            status, text = self.cli("runtime")
        self.assertEqual(status, 0, text)
        self.assertIn("CREATE: .latex-ai/guide.py", text)
        self.assertEqual((self.project / ".latex-ai/guide.py").read_text(), (PACKAGE / "guide.py").read_text())
        self.assertEqual(self.cli("diff")[0], 0)

    def test_diff_renders_once(self):
        with patch.object(bootstrap, "desired_files", wraps=bootstrap.desired_files) as spy:
            status, text = self.cli("diff")
        self.assertEqual(status, 0, text)
        self.assertEqual(spy.call_count, 1)

    def test_diff_still_reports_a_missing_and_a_changed_runtime_file(self):
        (self.project / ".latex-ai/guide.py").unlink()
        changed = self.project / ".latex-ai/core.py"
        changed.write_text(changed.read_text() + "# edited\n")
        status, text = self.cli("diff", "--diff")
        self.assertEqual(status, 1, text)
        lines = text.splitlines()
        self.assertEqual([line for line in lines if line.startswith("RUNTIME")],
                         ["RUNTIME differs: .latex-ai/core.py", "RUNTIME missing: .latex-ai/guide.py"] if lines.index("RUNTIME differs: .latex-ai/core.py") < lines.index("RUNTIME missing: .latex-ai/guide.py")
                         else ["RUNTIME missing: .latex-ai/guide.py", "RUNTIME differs: .latex-ai/core.py"])
        self.assertTrue(lines[-1].endswith("2 runtime file(s) differ."), lines[-1])
        self.assertIn("-# edited", text)

    def test_the_schema_errors_name_the_current_workbench(self):
        with self.assertRaisesRegex(core.WorkbenchError, r"^Workbench 4 supports only project configuration schema 3 \(this file declares 2\)"):
            schema.validate_config(self.project, {"schema_version": 2, "modules": {}})
        with self.assertRaisesRegex(core.WorkbenchError, r"^Workbench 4 supports only project configuration schema 3$"):
            schema.document_settings({"schema_version": 2, "modules": {}})


if __name__ == "__main__":
    unittest.main()
