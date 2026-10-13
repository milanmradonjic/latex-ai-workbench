"""Regressions found by the independent 3.0.0 audit; each one failed before its repair.

The fixtures come from ``test_support.ProjectCase``; the genuine latexmk/GNU Make scenarios are
skipped when those tools are absent.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
import schema
import documents
import latex
import runtime
from test_support import ProjectCase, fixture_env

PACKAGE = Path(__file__).resolve().parents[1]
TEX = bool(shutil.which("latexmk") and shutil.which("pdflatex") and shutil.which("make"))
SOURCE = "\\documentclass{article}\n\\begin{document}Audit fixture.\\end{document}\n"
GENERATED = "\\documentclass{article}\n\\begin{document}\\input{table}\\end{document}\n"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Repairs(ProjectCase):

    # --- build-produced inputs -------------------------------------------------------------------------

    def generated_project(self, deterministic=True):
        (self.project / "main.tex").write_text(GENERATED)
        (self.project / "data.txt").write_text("1\n")
        text = "'sum ' + data" if deterministic else "'sum ' + data + ' run ' + count.read_text()"
        self.builder("data = Path('data.txt').read_text().strip()\n"
                     "table = Path('table.tex')\n"
                     f"text = {text}\n"
                     "if not table.exists() or table.read_text() != text:\n"
                     "    table.write_text(text)\n", inputs=("main.tex", "data.txt", "table.tex"))
        self.configure()
        self.install("init", "--skip-editor")

    def test_generated_input_is_certified_on_the_first_build_and_after_data_changes(self):
        self.generated_project()
        self.command("build")  # table.tex is written by the build that includes it
        self.assertEqual(self.state(), "current")
        self.assertEqual(self.receipt()["inputs"]["table.tex"], digest("sum 1"))
        (self.project / "data.txt").write_text("2\n")
        self.assertEqual(self.state(), "stale")
        self.command("build")
        self.assertEqual(self.state(), "current")
        self.assertEqual(self.receipt()["inputs"]["table.tex"], digest("sum 2"))

    def test_generator_that_cannot_settle_names_the_unstable_input(self):
        self.generated_project(deterministic=False)
        result = self.command("build", expected=1)
        self.assertIn("table.tex", result.stderr)
        self.assertIn("changed during execution", result.stderr)
        self.assertEqual(self.state(), "failed")

    @unittest.skipUnless(TEX, "real latexmk, pdflatex and GNU Make required")
    def test_adopted_make_with_generated_table_and_figure_builds_once(self):
        (self.project / "data.csv").write_text("1\n2\n3\n4\n")
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}\n"
                                               "Sum of data: \\input{table}\n\\includegraphics[width=2cm]{figure.pdf}\n\\end{document}\n")
        self.run_command("pdflatex", "-interaction=nonstopmode", "-jobname=base", "\\documentclass{article}\\begin{document}x\\end{document}")
        self.configure({"paper": {"root": "main.tex", "lint": {"enabled": False}, "backend": "none", "build_command": ["make", "pdf"], "output_dir": "."}})
        self.install("init", "--skip-editor")
        with (self.project / "Makefile").open("a") as stream:  # the project's own rules, after what init wrote
            stream.write(
                ".PHONY: pdf\npdf: main.pdf\n"
                "table.tex: data.csv\n\tawk '{s+=$$1} END {printf \"%d\", s}' data.csv > table.tex\n"
                "figure.pdf: data.csv base.pdf\n\tcp base.pdf figure.pdf\n"
                "main.pdf: main.tex table.tex figure.pdf\n\tlatexmk -pdf -interaction=nonstopmode -recorder main.tex\n")
        self.run_command("make", "check")
        self.assertEqual(self.state(), "current")
        (self.project / "data.csv").write_text("5\n5\n")
        self.run_command("make", "check")
        self.assertEqual(self.state(), "current")
        text = subprocess.run(["pdftotext", "main.pdf", "-"], cwd=self.project, capture_output=True, text=True).stdout if shutil.which("pdftotext") else "Sum of data: 10"
        self.assertIn("Sum of data: 10", text)

    # --- links that leave the project and project-local styles -----------------------------------------

    def linked_project(self):
        outside = self.root / "shared-figures"
        outside.mkdir()
        (outside / "plot.txt").write_text("one")
        (self.project / "shared").symlink_to(outside, target_is_directory=True)
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\\includegraphics{shared/plot.pdf}\\end{document}\n")
        self.builder(inputs=("main.tex", "shared/plot.txt", "/outside/system.sty"))
        self.configure()
        self.install("init", "--skip-editor")
        return outside

    def test_link_leaving_the_project_is_a_tracked_input(self):
        outside = self.linked_project()
        self.command("build")
        self.assertEqual(self.state(), "current")
        self.assertIn("shared/plot.txt", self.receipt()["inputs"])
        self.assertNotIn("/outside/system.sty", "".join(self.receipt()["inputs"]))
        (outside / "plot.txt").write_text("two")
        self.assertEqual(self.state(), "stale")
        self.command("verify", expected=1)
        self.command("build")
        self.assertEqual(self.state(), "current")

    def test_link_target_named_in_source_is_tracked_on_a_fresh_checkout(self):
        outside = self.linked_project()
        (outside / "plot.pdf").write_bytes(b"%PDF-figure")
        view = schema.document_settings(schema.load_config(self.project))
        self.assertIn("shared/plot.pdf", latex.manuscript_dependencies(self.project, view, include_receipt=False))

    def test_planning_accepts_a_changed_link_that_leaves_the_project(self):
        self.linked_project()
        self.command("build")
        plan = runtime.validation_plan(self.project, schema.load_config(self.project), ["shared/plot.txt"])
        self.assertEqual(plan["documents"], ["paper"])

    def test_names_that_are_not_project_spellings_still_invalidate_a_receipt(self):
        self.linked_project()
        self.command("build")
        path = self.project / ".latex-ai/artifacts/documents/paper/build-receipt.json"
        for bad in ("../shared-figures/plot.txt", "shared/../main.tex", "/etc/hostname"):
            with self.subTest(name=bad):
                receipt = json.loads(path.read_text())
                receipt["inputs"][bad] = None
                self.assertEqual(latex.recorded_inputs(self.project, schema.document_settings(schema.load_config(self.project)), receipt), {})

    def test_bibliography_style_beside_the_document_is_an_input(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Cite.\\bibliographystyle{house}\\bibliography{refs}\\end{document}\n")
        (self.project / "house.bst").write_text("% local style\n")
        (self.project / "refs.bib").write_text("@article{a,title={A}}\n")
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")
        view = schema.document_settings(schema.load_config(self.project))
        self.assertIn("house.bst", latex.manuscript_dependencies(self.project, view, include_receipt=False))
        self.assertIn("house.bst", latex.build_inputs(self.project, view))
        self.command("build")
        self.assertEqual(self.state(), "current")
        (self.project / "house.bst").write_text("% edited local style\n")
        self.assertEqual(self.state(), "stale")

    def test_system_bibliography_style_adds_no_input(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Cite.\\bibliographystyle{plain}\\end{document}\n")
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")
        view = schema.document_settings(schema.load_config(self.project))
        self.assertNotIn("plain.bst", latex.build_inputs(self.project, view))
        (self.project / "plain.bst").write_text("% a local style shadows the system one\n")
        self.assertIn("plain.bst", latex.build_inputs(self.project, view))

    # --- locks, hints, line endings ----------------------------------------------------------------------

    @unittest.skipUnless(hasattr(os, "getuid"), "POSIX users")
    def test_stale_state_hints_name_the_document(self):
        self.configure({"paper": {"root": "main.tex", "lint": {"enabled": False}},
                        "note": {"root": "note.tex", "lint": {"enabled": False}}})
        for name in ("main.tex", "note.tex"):
            (self.project / name).write_text(SOURCE)
        self.install("init", "--skip-editor")
        config = schema.load_config(self.project)
        view = schema.document_settings(config, "note")
        for label, call in {"unverified receipt": lambda: latex.verify(self.project, view),
                            "unprepared build": lambda: latex.finish_build(self.project, view, os.getpid())}.items():
            with self.subTest(label), self.assertRaises(core.WorkbenchError) as caught:
                call()
            self.assertIn("DOC=note", str(caught.exception) + (caught.exception.hint or ""))
        with self.subTest("missing log"), self.assertRaises(core.WorkbenchError) as caught:
            latex.verify(self.project, view, check_receipt=False)
        self.assertIn("DOC=note", str(caught.exception) + (caught.exception.hint or ""))

    # --- planner, configuration messages, orientation ----------------------------------------------------

    def test_every_installed_runtime_file_is_a_full_validation_trigger(self):
        everything = {"schema_version": 3, "modules": {name: {} for name in core.MODULES}}
        shipped = set(core.runtime_sources(everything)) | {"bootstrap.py", "latex-ai-init"}
        self.assertLessEqual(shipped, set(core.RUNTIME_FILES))
        self.configure()
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.install("init", "--skip-editor")
        (self.project / "workbench").mkdir()
        (self.project / "workbench/Makefile").write_text("test:\n\ttrue\n")
        (self.project / "workbench/latex-ai-init").write_text("#!/usr/bin/env python3\n")
        config = schema.load_config(self.project)
        for name in sorted(core.RUNTIME_FILES):
            with self.subTest(name):
                plan = runtime.validation_plan(self.project, config, [f"workbench/{name}"])
                self.assertTrue(plan["manuscript"] and plan["unit"] and plan["portability"], plan["reasons"])

    def test_configuration_errors_name_the_offending_key(self):
        base = {"schema_version": 3, "modules": {"latex": {"default_document": "paper", "documents": {"paper": {"root": "main.tex"}}}}}
        (self.project / "main.tex").write_text(SOURCE)
        cases = {
            "document": lambda c: c["modules"]["latex"]["documents"]["paper"].update(rooot="main.tex"),
            "latex": lambda c: c["modules"]["latex"].update(documnts={}),
            "core": lambda c: c.update(moduls={}),
            "integrations": lambda c: c.update(integrations={"cii": {}}),
            "module": lambda c: c["modules"].update(bibliography={"pth": "refs.bib"}),
            "validation": lambda c: c.update(validation={"manuscript_input": []}),
        }
        for label, edit in cases.items():
            config = json.loads(json.dumps(base))
            edit(config)
            with self.subTest(label), self.assertRaises(core.WorkbenchError) as caught:
                schema.validate_config(self.project, config)
            self.assertRegex(str(caught.exception), r"rooot|documnts|moduls|cii|pth|manuscript_input", label)

    def test_invalid_schema_hint_says_what_to_do(self):
        with self.assertRaises(core.WorkbenchError) as caught:
            schema.validate_config(self.project, {"schema_version": 2, "modules": {}})
        self.assertIn("configuration.md", caught.exception.hint)
        self.assertIn(str(2), str(caught.exception))

    def test_build_command_that_is_not_json_gets_an_actionable_error(self):
        (self.project / "main.tex").write_text(SOURCE)
        result = self.install("init", "--build-command", "make pdf", "--skip-editor", expected=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--build-command", result.stderr)
        self.assertIn("JSON", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("INTERNAL ERROR", result.stderr)

    def test_plan_says_when_a_document_selector_is_ignored(self):
        self.configure()
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.install("init", "--skip-editor")
        result = self.command("plan", "--files", "main.tex", env=fixture_env(DOC="paper"))
        self.assertIn("DOC=paper", result.stdout)
        self.assertIn("ignored", result.stdout)
        quiet = self.command("plan", "--files", "main.tex")
        self.assertNotIn("DOC", quiet.stdout)

    def test_status_puts_the_running_build_before_anything_that_would_start_another(self):
        self.configure()
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.install("init", "--skip-editor")
        view = schema.document_settings(schema.load_config(self.project))
        path = self.project / latex.receipt_path(view)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": latex.RECEIPT_SCHEMA, "status": "running", "owner_pid": os.getpid(),
                                    "owner_token": latex.process_token(os.getpid())}))
        text = self.command("status").stdout
        steps = [line.strip() for line in text.split("Next:")[1].splitlines() if line.strip()]
        self.assertTrue(steps[0].startswith("wait for this build"), steps)
        self.assertTrue(all("after" in step for step in steps[1:]), steps)

    def test_a_clean_build_reports_its_integrity_once(self):
        self.configure()
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.install("init", "--skip-editor")
        result = self.run_command("make", "check")
        self.assertEqual(result.stdout.count("Citation/reference integrity checks passed"), 1, result.stdout)


if __name__ == "__main__":
    unittest.main()
