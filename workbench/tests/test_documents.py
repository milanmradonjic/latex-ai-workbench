"""Installed workflows for named TeX documents and mixed note organization."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_support import isolate_environment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap
import core
import schema
import documents
import latex
import runtime


class DocumentTests(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-documents-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def install(self, *arguments, expected=0):
        result = subprocess.run([sys.executable, "-B", str(bootstrap.PACKAGE / "latex-ai-init"),
                                 *arguments, str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def command(self, *arguments, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"),
                                 *arguments], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def make(self, *arguments, expected=0):
        result = subprocess.run(["make", *arguments], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def snapshot(self):
        """Every project file's bytes, except the empty lock files a refused operation leaves in the ignored artifacts."""
        locks = self.project / core.LOCKS
        return {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*")
                if p.is_file() and not p.is_relative_to(locks)}

    def configuration(self):
        for root in ("main.tex", "notes/main.tex"):
            path = self.project / root
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\\documentclass{article}\n\\begin{document}A note.\\end{document}\n")
        (self.project / "compile.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "root, out = Path(sys.argv[1]), Path(sys.argv[2])\n"
            "if 'BROKEN' in root.read_text(): raise SystemExit(2)\n"
            "out.mkdir(parents=True, exist_ok=True)\n"
            "(out/(root.stem+'.pdf')).write_bytes(b'%PDF-1.4\\n'+root.read_bytes())\n"
            "(out/(root.stem+'.log')).write_text('Clean compiler log\\n')\n")
        config = {"schema_version": 3, "modules": {"latex": {
            "default_document": "paper", "defaults": {"lint": {"enabled": False}}, "documents": {
                "paper": {"root": "main.tex", "build_command": [sys.executable, "compile.py", "main.tex", ".latex-ai/artifacts/documents/paper/build"]},
                "note": {"root": "notes/main.tex", "build_command": [sys.executable, "compile.py", "notes/main.tex", ".latex-ai/artifacts/documents/note/build"]}}}},
            "integrations": {"ci": {"enabled": True, "pdf_artifact": True}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        return config


    def test_per_document_defaults_are_independent(self):
        config = self.configuration()
        config["modules"]["latex"]["defaults"]["lint"]["args"] = ["-n8"]
        config["modules"]["latex"]["documents"]["note"]["lint"] = {"enabled": True}
        config["modules"]["latex"]["documents"]["note"]["engine"] = "lualatex"
        schema.validate_config(self.project, config)
        note = schema.resolve(config, "note").view
        self.assertEqual(note["lint"], {"enabled": True, "args": ["-n8"], "baseline": ".latex-ai/lint-baselines/note.json"})
        changed = note.to_json()  # a view is read-only; a copy is the caller's to change
        changed["lint"]["args"].append("-n9")
        self.assertEqual(note["lint"]["args"], ["-n8"])
        self.assertEqual(schema.resolve(config, "paper").view["lint"]["args"], ["-n8"])
        self.assertIn("lualatex", schema.required_tools(config))

    def test_rejects_duplicate_roots_and_output_stems(self):
        config = self.configuration()
        targets = config["modules"]["latex"]["documents"]
        targets["note"]["root"] = "./main.tex"
        with self.assertRaisesRegex(core.WorkbenchError, "collision"):
            schema.validate_config(self.project, config)
        targets["note"]["root"] = "notes/main.tex"
        for target in targets.values():
            target["output_dir"] = "output"
        with self.assertRaisesRegex(core.WorkbenchError, "collision"):
            schema.validate_config(self.project, config)

    def test_rejects_output_directory_symlink_alias(self):
        config = self.configuration()
        (self.project / "output").mkdir()
        (self.project / "alias").symlink_to(self.project / "output", target_is_directory=True)
        targets = config["modules"]["latex"]["documents"]
        targets["paper"]["output_dir"] = "output"
        targets["note"]["output_dir"] = "alias"
        with self.assertRaisesRegex(core.WorkbenchError, "collision"):
            schema.validate_config(self.project, config)

    def test_build_outputs_cannot_overwrite_another_document_export(self):
        config = self.configuration()
        (self.project / "document.tex").write_text("\\documentclass{article}\n")
        config["modules"]["latex"]["documents"]["note"].update({"root": "document.tex", "output_dir": ".latex-ai/artifacts/documents/paper"})
        with self.assertRaisesRegex(core.WorkbenchError, "exported PDF"):
            schema.validate_config(self.project, config)

    def test_malformed_document_values_are_expected_configuration_errors(self):
        for field, value in (("bibliography_files", [{}]), ("root", []), ("lint", []), ("inputs", [{}])):
            config = self.configuration()
            config["modules"]["latex"]["documents"]["note"][field] = value
            with self.subTest(field=field), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, config)

    def test_invalid_selector_does_not_mutate_project(self):
        self.configuration()
        self.install("init")
        before = self.snapshot()
        result = self.make("latex-ai-build", "DOC=../../paper", expected=2)
        self.assertIn("Unknown document", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_malformed_receipt_does_not_break_read_only_document_planning(self):
        config = self.configuration()
        self.install("init")
        receipt = self.project / latex.receipt_path(schema.resolve(config, "note").view)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({"schema_version": 1, "status": "verified", "configuration": None, "inputs": None}))
        before = self.snapshot()
        self.command("documents", "--json")
        report = json.loads(self.command("plan", "--files", "notes/main.tex", "--json").stdout)
        self.assertEqual(report["documents"], ["note"])
        self.assertEqual(self.snapshot(), before)

    def test_two_same_stem_documents_have_independent_receipts_and_exports(self):
        self.configuration()
        self.install("init")
        for name in ("paper", "note"):
            self.make("latex-ai-build", "DOC=" + name)
            self.make("latex-ai-pdf-artifact", "DOC=" + name)
        directory = self.project / ".latex-ai/artifacts/documents"
        paper = (directory / "paper/build-receipt.json").read_bytes()
        (self.project / "notes/main.tex").write_text("BROKEN\n")
        self.make("latex-ai-build", "DOC=note", expected=2)
        self.assertEqual(paper, (directory / "paper/build-receipt.json").read_bytes())
        self.make("latex-ai-pdf-artifact", "DOC=note", expected=2)
        self.make("latex-ai-pdf-artifact", "DOC=paper")
        self.assertTrue((directory / "paper/document.pdf").read_bytes().startswith(b"%PDF-"))
        self.assertFalse((self.project / ".latex-ai/artifacts/manuscript.pdf").exists())

    def test_receipt_configuration_changes_are_scoped(self):
        config = self.configuration()
        self.install("init")
        self.command("check")
        config["modules"]["latex"]["documents"]["note"]["engine"] = "xelatex"
        (self.project / core.CONFIG).write_text(json.dumps(config))
        states = {row["id"]: row["state"] for row in json.loads(self.command("documents").stdout)}
        self.assertEqual(states, {"paper": "current", "note": "stale"})

    def test_failed_full_check_reports_document_and_checks_remaining_target(self):
        self.configuration()
        self.install("init")
        (self.project / "main.tex").write_text("BROKEN\n")
        result = self.command("check", "--json", expected=1)
        report = json.loads(result.stdout)
        self.assertEqual([row["status"] for row in report["result"]["documents"]], ["failed", "passed"])
        self.assertIn("paper", report["stderr"])

    def test_note_change_selects_only_its_document(self):
        config = self.configuration()
        plan = runtime.validation_plan(self.project, config, ["notes/main.tex"])
        self.assertEqual(plan["documents"], ["note"])
        self.assertTrue(plan["manuscript"])
        self.assertEqual(runtime.validation_plan(self.project, config, ["notes/readme.md"])["documents"], [])

    def test_shared_and_deleted_fragments_select_all_consumers(self):
        config = self.configuration()
        (self.project / "shared.tex").write_text("Shared definitions\n")
        for root, include in (("main.tex", "shared"), ("notes/main.tex", "../shared")):
            path = self.project / root
            path.write_text("\\input{" + include + "}\n" + path.read_text())
        self.assertEqual(runtime.validation_plan(self.project, config, ["shared.tex"])["documents"], ["note", "paper"])
        (self.project / "shared.tex").unlink()
        self.assertEqual(runtime.validation_plan(self.project, config, ["shared.tex"])["documents"], ["note", "paper"])

    def test_hard_link_alias_selects_the_declared_document_input(self):
        config = self.configuration()
        (self.project / "resource.md").write_text("Resource\n")
        os.link(self.project / "resource.md", self.project / "alias.md")
        config["modules"]["latex"]["documents"]["paper"]["inputs"] = ["resource.md"]
        self.assertEqual(runtime.validation_plan(self.project, config, ["alias.md"])["documents"], ["paper"])

    def test_uncertain_tex_and_build_policy_select_all_documents(self):
        config = self.configuration()
        for path in ("unclassified.tex", "Makefile", core.CONFIG):
            with self.subTest(path=path):
                self.assertEqual(runtime.validation_plan(self.project, config, [path])["documents"], ["note", "paper"])

    def test_selected_validation_does_not_build_unrelated_paper(self):
        self.configuration()
        self.install("init")
        (self.project / "main.tex").write_text("BROKEN\n")
        self.command("validate", "--files", "notes/main.tex")
        self.assertFalse((self.project / ".latex-ai/artifacts/documents/paper/build-receipt.json").exists())
        self.assertTrue((self.project / ".latex-ai/artifacts/documents/note/build-receipt.json").exists())

    def test_tex_notebook_dry_run_seeds_no_files(self):
        before = self.snapshot()
        result = self.install("init", "--profile", "tex-notebook", "--dry-run", "--json")
        self.assertEqual(before, self.snapshot())
        self.assertFalse(json.loads(result.stdout)["applied"])
        self.install("init", "--profile", "tex-notebook", "--no-lint")
        self.assertIn("\\documentclass", (self.project / "notes/index.tex").read_text())
        self.assertNotIn("\\documentclass", (self.project / "notes/session-state.tex").read_text())
        self.assertNotIn("pandoc", self.command("doctor", expected=0 if shutil.which("latexmk") else 1).stdout)
        self.command("research-check")

    def test_mixed_note_entry_points_and_source_ownership(self):
        config = self.configuration()
        config["modules"]["notes"] = {"path": "notes", "index": "index.md", "session_state": "state.tex"}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        state = self.project / "notes/state.tex"
        state.write_text("Project-owned session state.\n")
        self.command("research-check")
        self.install("upgrade")
        self.assertEqual(state.read_text(), "Project-owned session state.\n")

    def test_notes_paths_cannot_escape_the_notes_directory(self):
        for name in ("../state.tex", "/tmp/state.tex", "", "../../.latex-ai/state.tex"):
            config = {"schema_version": 3, "modules": {"notes": {"session_state": name}}}
            with self.subTest(name=name), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, config)


    def test_add_document_then_disable_and_restore_retains_definitions(self):
        self.configuration()
        self.install("init")
        self.install("configure", "--document", "extra", "--root", "notes/extra.tex", expected=2)
        (self.project / "notes/extra.tex").write_text("\\documentclass{article}\n")
        self.install("configure", "--document", "extra", "--root", "notes/extra.tex", "--engine", "xelatex")
        config = schema.load_config(self.project)
        self.assertEqual(schema.resolve(config, "extra").view["engine"], "xelatex")
        self.install("configure", "--disable", "latex")
        self.command("check")
        self.install("configure", "--enable", "latex")
        self.assertEqual(schema.resolve(schema.load_config(self.project), "extra").view["engine"], "xelatex")

    def test_inspection_leaves_receipts_and_sources_unchanged(self):
        self.configuration()
        self.install("init")
        self.command("check")
        before = self.snapshot()
        self.command("documents")
        self.command("status", "--json")
        self.command("plan", "--files", "notes/main.tex", "--json")
        self.assertEqual(before, self.snapshot())

    def test_document_ci_and_editor_tasks_use_named_make_commands(self):
        config = self.configuration()
        config["integrations"]["editor"] = True
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        workflow = (self.project / ".github/workflows/latex-ai.yml").read_text()
        for name in ("paper", "note"):
            self.assertIn("make latex-ai-document-check DOC=" + name, workflow)
            self.assertIn("artifacts/documents/" + name + "/document.pdf", workflow)
        tasks = json.loads((self.project / ".vscode/tasks.json").read_text())["tasks"]
        self.assertIn(["latex-ai-build", "DOC=note"], [task["args"] for task in tasks])

    def test_deleted_explicit_input_selects_target_before_first_build(self):
        config = self.configuration()
        config["modules"]["latex"]["documents"]["note"]["inputs"] = ["notes/context.md"]
        self.assertEqual(runtime.validation_plan(self.project, config, ["notes/context.md"])["documents"], ["note"])
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        result = self.command("build", "--document", "note", expected=1)
        self.assertIn("Missing declared document input", result.stderr)

    def test_nested_note_index_links_to_the_actual_session_file(self):
        config = {"schema_version": 3, "modules": {"notes": {"index": "sub/index.md", "session_state": "state.md"}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        self.assertIn("(../state.md)", (self.project / "notes/sub/index.md").read_text())
        self.command("validate", "--files", "notes/sub/index.md")

    def test_fresh_disabled_documents_vendor_their_config_validator(self):
        config = self.configuration()
        saved = config["modules"].pop("latex")
        config["disabled_modules"] = {"latex": saved}
        config["integrations"]["ci"]["pdf_artifact"] = False
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        self.assertTrue((self.project / ".latex-ai/documents.py").is_file())
        self.assertFalse((self.project / ".latex-ai/latex.py").is_file())
        self.command("check")

    def test_schema_three_no_tex_fallback_checks_bibliography(self):
        config = {"schema_version": 3, "modules": {"bibliography": {"files": ["refs.bib"]}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        (self.project / "refs.bib").write_text("@misc{fixture, title={Synthetic fixture}}\n")
        self.install("init")
        (self.project / "refs.bib").write_text("@misc{fixture, title={One}}\n@misc{fixture, title={Two}}\n")
        self.assertIn("Duplicate bibliography key", self.command("validate", expected=1).stderr)

    def test_active_adopted_build_blocks_other_cleanup_and_export(self):
        config = self.configuration()
        config["modules"]["latex"]["documents"]["note"]["build_command"] = None
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        with contextlib.redirect_stdout(io.StringIO()):
            latex.prepare_build(self.project, schema.resolve(config, "paper").view, os.getpid())
        before = self.snapshot()
        for action in ("clean", "artifact"):
            result = self.command(action, "--document", "note", expected=1)
            self.assertIn("Another build is active", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_invalid_defaults_and_recursive_commands_fail_before_installation(self):
        for change in ("default", "recursive", "malformed"):
            config = self.configuration()
            values = config["modules"]["latex"]
            if change == "default":
                values["defaults"]["engine"] = "bogus"
                for fields in values["documents"].values():
                    fields["engine"] = "pdflatex"
            else:
                values["documents"]["note"]["build_command"] = ["make", "check" if change == "recursive" else {}]
            with self.subTest(change=change), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, config)

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "real TeX tools required")
    def test_tex_notebook_does_not_adopt_unrelated_existing_build(self):
        (self.project / "Makefile").write_text(".PHONY: build\nbuild:\n\t@echo unrelated > unrelated-marker\n")
        self.install("init", "--profile", "tex-notebook", "--no-lint")
        self.make("latex-ai-build")
        self.assertFalse((self.project / "unrelated-marker").exists())
        self.assertTrue((self.project / ".latex-ai/artifacts/documents/notebook/build/index.pdf").exists())

    def test_adopted_multi_document_make_compiles_paper_once(self):
        config = self.configuration()
        config["modules"]["latex"]["documents"]["paper"].update({"build_command": ["make", "pdf"], "output_dir": "paper-out"})
        (self.project / core.CONFIG).write_text(json.dumps(config))
        script = self.project / "compile.py"
        script.write_text(script.read_text() + "\nif root == Path('main.tex'):\n p=Path('paper-count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')\n")
        (self.project / "Makefile").write_text("CHECK_TARGET := check\n.PHONY: all pdf check\nall: $(CHECK_TARGET)\npdf: paper-out/main.pdf\npaper-out/main.pdf: main.tex compile.py\n\t$(PYTHON) compile.py main.tex paper-out\ncheck: pdf\n")
        self.install("init")
        self.make("-j4", "check")
        self.assertEqual((self.project / "paper-count").read_text(), "1")
        self.make("-j4", "check")
        self.assertEqual((self.project / "paper-count").read_text(), "1")
        self.make("latex-ai-build", "DOC=note")
        self.assertEqual((self.project / "paper-count").read_text(), "1")

    def test_shared_adopted_make_graph_requires_explicit_adapter(self):
        config = self.configuration()
        (self.project / "Makefile").write_text("paper: shared\nnote: shared\n.PHONY: shared\nshared:\n\t@echo shared\n")
        for name in ("paper", "note"):
            config["modules"]["latex"]["documents"][name]["build_command"] = ["make", name]
        with self.assertRaisesRegex(core.WorkbenchError, "share Make targets"):
            schema.validate_config(self.project, config)
        (self.project / "Makefile").write_text("COMMON := shared\npaper: $(COMMON)\nnote: $(COMMON)\nshared:\n\t@echo shared\n")
        with self.assertRaisesRegex(core.WorkbenchError, "ownership"):
            schema.validate_config(self.project, config)

    def test_separate_adopted_graphs_allow_comments_with_make_symbols(self):
        config = self.configuration()
        (self.project / "Makefile").write_text("paper: main.tex # uses $< and 100%\nnote: notes/main.tex\n")
        for name in ("paper", "note"):
            config["modules"]["latex"]["documents"][name]["build_command"] = ["make", name]
        schema.validate_config(self.project, config)

    def test_existing_check_cannot_run_additional_adopted_documents_outside_their_phase(self):
        config = self.configuration()
        for name in ("paper", "note"):
            config["modules"]["latex"]["documents"][name]["build_command"] = ["make", name]
        for rule in ("check: paper note", "check: note", "check: $(EXTRA_DOCS)",
                     "all: check note\ncheck: paper", "all: $(CHECK_TARGET) note\ncheck: paper"):
            (self.project / "Makefile").write_text(
                "CHECK_TARGET := check\nEXTRA_DOCS := note\npaper: main.tex\nnote: notes/main.tex\n" + rule + "\n")
            before = self.snapshot()
            with self.subTest(rule=rule), self.assertRaisesRegex(core.WorkbenchError, "ownership"):
                schema.validate_config(self.project, config)
            self.assertEqual(self.snapshot(), before)
        (self.project / "Makefile").write_text(".PHONY: all paper note check\nall: check\npaper: main.tex\nnote: notes/main.tex\ncheck: paper\n")
        schema.validate_config(self.project, config)

    def test_disabled_documents_do_not_require_operational_make_ownership(self):
        config = self.configuration()
        saved = config["modules"].pop("latex")
        config["disabled_modules"] = {"latex": saved}
        for name in ("paper", "note"):
            saved["documents"][name]["build_command"] = ["make", name]
        (self.project / "main.tex").unlink()
        (self.project / "notes/main.tex").unlink()
        schema.validate_config(self.project, config)
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        self.command("check")
        self.assertEqual(schema.load_config(self.project)["disabled_modules"]["latex"], saved)

    def test_full_adopted_check_ignores_document_selector_without_duplicate_build(self):
        config = self.configuration()
        config["modules"]["latex"]["documents"]["paper"].update({"build_command": ["make", "pdf"], "output_dir": "paper-out"})
        (self.project / core.CONFIG).write_text(json.dumps(config))
        (self.project / "Makefile").write_text(
            "CHECK_TARGET := check\n.PHONY: all pdf check\nall: $(CHECK_TARGET)\npdf:\n"
            "\t@echo paper >> paper-count\n\t$(PYTHON) compile.py main.tex paper-out\ncheck: pdf\n")
        self.install("init")
        for goal in ("check", "all"):
            self.make("-j4", goal, "DOC=note")
        self.assertEqual((self.project / "paper-count").read_text().splitlines(), ["paper", "paper"])
        states = self.command("documents", "--json").stdout
        self.assertEqual(states.count('"state": "current"'), 2)

    def test_symlink_root_uses_named_output_directory(self):
        (self.project / "src").mkdir()
        (self.project / "alias").mkdir()
        (self.project / "src/main.tex").write_text("\\documentclass{article}\n")
        (self.project / "alias/paper.tex").symlink_to(self.project / "src/main.tex")
        self.install("init", "--root", "alias/paper.tex", "--no-lint", "--no-ci", "--skip-editor")
        original = latex.output_paths(self.project, schema.document_settings(schema.load_config(self.project)))[2]
        self.install("configure")
        self.assertEqual(latex.output_paths(self.project, schema.document_settings(schema.load_config(self.project)))[2], original)
        self.assertIn("/.latex-ai/artifacts/documents/manuscript/build/main.pdf", (self.project / ".gitignore").read_text())

    def test_selected_validation_reports_all_failing_documents(self):
        self.configuration()
        self.install("init")
        for path in ("main.tex", "notes/main.tex"):
            (self.project / path).write_text("BROKEN\n")
        report = json.loads(self.command("validate", "--files", "unknown.tex", "--json", expected=1).stdout)
        self.assertEqual({row["id"] for row in report["result"]["documents"]}, {"paper", "note"})
        self.assertTrue(all(row["status"] == "failed" for row in report["result"]["documents"]))


if __name__ == "__main__":
    unittest.main()
