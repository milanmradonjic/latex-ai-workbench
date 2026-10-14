"""Workbench 4.4.2, step 3.2 of docs/maintainers/plan-after-4.4.0.md: a module declares what something reads, and no more.

The module table had a `tools` list, a `requires` list and a `check_group` that nothing used: both lists were empty for both modules, and no caller passed a group
to `module_names`. These tests pin that they are gone, and that what they stood for did not change: the order of the modules, the tools a project needs, what the schema
says about a module or a field it does not know, and what `modules` reports (minus the `requires` that was always empty).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import core
import schema
from test_support import ProjectCase

SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"


def paper(**fields):
    return {"root": "main.tex", "engine": "pdflatex", **fields}


MODULE_ORDER = (
    ({"schema_version": 3, "modules": {}}, ()),
    ({"schema_version": 3, "modules": {"latex": {}}}, ("latex",)),
    ({"schema_version": 3, "modules": {"latex": {}, "bibliography": {"files": ["refs.bib"]}}}, ("latex", "bibliography")),
    ({"schema_version": 3, "modules": {"bibliography": {"files": ["refs.bib"]}}}, ("bibliography",)),
)
TOOLS = (  # what required_tools answered in 4.4.1
    ({"schema_version": 3, "modules": {}}, ["make"]),
    ({"schema_version": 3, "modules": {"latex": {"default_document": "paper", "documents": {"paper": paper(backend="bibtex")}}}},
     ["make", "latexmk", "pdflatex", "chktex", "bibtex"]),
    ({"schema_version": 3, "modules": {"latex": {"default_document": "paper", "documents": {"paper": paper(lint={"enabled": False})}}}},
     ["make", "latexmk", "pdflatex"]),
    ({"schema_version": 3, "modules": {"latex": {"default_document": "a", "documents": {"a": paper(), "b": paper(root="b.tex")}},
                                       "bibliography": {"files": ["refs.bib"]}}},
     ["make", "latexmk", "pdflatex", "chktex"]),
)


class ModuleTable(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE)
        self.configure()
        self.install("init")

    def test_a_module_declares_only_what_something_reads(self):
        for name, spec in core.MODULES.items():
            with self.subTest(module=name):
                self.assertEqual(set(spec), {"runtime", "defaults"})

    def test_module_names_follow_the_table_and_take_no_group(self):
        for config, expected in MODULE_ORDER:
            with self.subTest(modules=expected):
                self.assertEqual(core.module_names(config), expected)
        with self.assertRaises(TypeError):
            core.module_names({"schema_version": 3, "modules": {}}, "latex")

    def test_the_tools_a_project_needs_are_unchanged(self):
        for config, expected in TOOLS:
            with self.subTest(modules=sorted(config["modules"])):
                self.assertEqual(schema.required_tools(core.effective_config(config)), expected)

    def test_the_schema_still_refuses_what_it_does_not_know(self):
        with tempfile.TemporaryDirectory() as temp:
            for config, message in (({"schema_version": 3, "modules": {"bibliography": {"files": [], "bogus": 1}}}, "Unknown bibliography module field: bogus"),
                                    ({"schema_version": 3, "modules": {"magic": {}}}, "Unknown module: magic")):
                with self.subTest(message=message), self.assertRaises(core.WorkbenchError) as raised:
                    schema.validate_config(Path(temp), config)
                self.assertEqual(str(raised.exception), message)

    def test_the_modules_report_has_no_requires(self):
        report = json.loads(self.command("modules").stdout)
        self.assertEqual(sorted(report), ["bibliography", "latex"])
        for name, entry in report.items():
            with self.subTest(module=name):
                self.assertEqual(set(entry), {"enabled", "configuration"})
        self.assertTrue(report["latex"]["enabled"])
        self.assertFalse(report["bibliography"]["enabled"])
        self.assertIsNone(report["bibliography"]["configuration"])


if __name__ == "__main__":
    unittest.main()
