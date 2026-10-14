"""Workbench 4.1.0 no longer generates CI workflows for the projects it installs (see docs/maintainers/minimal-scope.md).

These tests pin what is gone: the generator, its options and its configuration, and that a project's own workflows are left alone.
This repository's own workflows are plain files now, and test_repairs_3_5_0.py keeps them pinned.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import bootstrap
import core
import schema
from test_support import ProjectCase

GONE = ("workflow", "core_workflow", "document_workflow", "pin_actions", "PINNED_ACTIONS", "ci_action", "ci_command", "ci_host_checks")


class NoGeneratedCI(ProjectCase):
    def test_the_generator_and_its_pins_are_gone(self):
        for name in GONE:
            with self.subTest(name=name):
                self.assertFalse(hasattr(bootstrap, name))
        self.assertEqual(core.integrations({"integrations": {"editor": True}}), {"editor": True})

    def test_the_options_of_the_generator_are_gone(self):
        for option in ("--ci", "--no-ci", "--no-artifact"):
            with self.subTest(option=option):
                done = subprocess.run([sys.executable, "-B", str(PACKAGE / "latex-ai-init"), "init", option, str(self.project)],
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
                self.assertIn("unrecognized arguments", done.stderr)
        done = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), "plan", "--github-output", "x", "--project", str(self.project)],
                              capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)

    def test_a_configuration_that_asks_for_ci_is_refused_with_a_hint(self):
        config = {"schema_version": 3, "modules": {}, "integrations": {"editor": False, "ci": {"enabled": True}}}
        with self.assertRaises(core.WorkbenchError) as raised:
            schema.validate_config(self.project, config)
        self.assertIn("integrations.ci", str(raised.exception))
        self.assertIn("remove", raised.exception.hint)
        self.assertIn(".github/workflows/", raised.exception.hint)

    def test_an_install_writes_no_workflow_and_leaves_an_existing_one_alone(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        workflow = self.project / ".github/workflows/mine.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: mine\non: workflow_dispatch\n")
        self.install("init", "--no-lint")
        self.assertEqual(sorted(p.name for p in workflow.parent.iterdir()), ["mine.yml"])
        self.assertEqual(workflow.read_text(), "name: mine\non: workflow_dispatch\n")
        self.install("runtime")
        self.assertEqual(workflow.read_text(), "name: mine\non: workflow_dispatch\n")

    def test_the_documents_of_a_project_carry_no_ci_settings(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        config = self.configure()
        schema.validate_config(self.project, config)
        for target in schema.specifications(config):
            self.assertNotIn("ci", target.view)


if __name__ == "__main__":
    unittest.main()
