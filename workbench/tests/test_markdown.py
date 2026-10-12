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
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap as boot
import core
import schema
import markdown as md
import runtime as rt


class MarkdownFixture(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-md-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return boot.main([*args, str(self.project)])

    def config(self):
        return schema.load_config(self.project)


class MarkdownInstallTests(MarkdownFixture):
    def test_markdown_is_opt_in_and_installs_without_pandoc_or_tex(self):
        self.assertEqual(self.cli("init", "--profile", "notebook"), 0)
        self.assertFalse((self.project / ".latex-ai/markdown.py").exists())
        self.assertEqual(self.cli("configure", "--enable", "markdown"), 0)
        self.assertTrue((self.project / ".latex-ai/markdown.py").is_file())
        self.assertFalse((self.project / ".latex-ai/latex.py").exists())
        make = (self.project / "Makefile").read_text()
        self.assertIn("md-render: latex-ai-md-render", make)
        with patch.object(md.shutil, "which", return_value=None), self.assertRaisesRegex(core.WorkbenchError, "requires Pandoc"):
            md.check(self.project, self.config())

    def test_upgrade_disable_and_reenable_retain_notes_and_exports(self):
        self.assertEqual(self.cli("init", "--modules", "notes,markdown"), 0)
        note = self.project / "notes/index.md"
        note.write_text("# My own notes\n")
        output = self.project / md.OUTPUT / "notes/index.html"
        output.parent.mkdir(parents=True)
        output.write_text("Prior generated export")
        before = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(self.cli("upgrade"), 0)
        self.assertEqual(before, {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()})
        self.assertEqual(self.cli("configure", "--disable", "markdown"), 0)
        self.assertFalse(core.has_module(self.config(), "markdown"))
        self.assertNotIn("md-render:", (self.project / "Makefile").read_text())
        self.assertEqual(note.read_text(), "# My own notes\n")
        self.assertEqual(output.read_text(), "Prior generated export")
        self.assertEqual(self.cli("upgrade"), 0)
        self.assertEqual(self.cli("configure", "--enable", "markdown"), 0)
        self.assertTrue(core.has_module(self.config(), "markdown"))

    def test_input_configuration_rejects_escape_and_empty_selection(self):
        for files in ([], "notes/*.md", ["../notes.md"], ["/notes.md"], [".latex-ai/**/*.md"], ["notes\n.md"]):
            with self.subTest(files=files), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, {'schema_version': 3, 'modules': {'markdown': {'files': files}}})

    def test_plan_checks_markdown_after_link_target_deletion_without_tex(self):
        self.assertEqual(self.cli("init", "--modules", "notes,markdown"), 0)
        for paths in (["notes/index.md"], ["figures/removed.svg"], ["references.bib"]):
            plan = rt.validation_plan(self.project, self.config(), paths)
            self.assertTrue(plan["markdown"])
            self.assertFalse(plan["manuscript"])
            self.assertEqual(plan["research"], paths == ["notes/index.md"])

    def test_ci_provisions_pandoc_only_for_selected_checks_and_never_renders(self):
        self.assertEqual(self.cli("init", "--modules", "notes,markdown", "--ci"), 0)
        workflow = (self.project / ".github/workflows/latex-ai.yml").read_text()
        self.assertIn("steps.plan.outputs.markdown == 'true'", workflow)
        self.assertIn("run: make latex-ai-md-check", workflow)
        self.assertNotIn("md-render", workflow)
        self.assertNotIn("texlive-action", workflow)

    def test_markdown_consumed_by_tex_still_selects_manuscript_validation(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\n\\input{notes/index.md}\n\\end{document}\n")
        self.assertEqual(self.cli("init", "--modules", "latex,notes,markdown"), 0)
        plan = rt.validation_plan(self.project, self.config(), ["notes/index.md"])
        self.assertTrue(plan["manuscript"])
        self.assertTrue(plan["markdown"])
        self.assertIn("python3 make pandoc", boot.workflow(self.config()))


@unittest.skipUnless(shutil.which("pandoc"), "Optional Markdown integration needs Pandoc 2.17+ on PATH")
class MarkdownIntegrationTests(MarkdownFixture):
    def setUp(self):
        super().setUp()
        shutil.copytree(boot.PACKAGE / "examples/markdown", self.project, dirs_exist_ok=True)
        self.assertEqual(self.cli("init"), 0)

    def command(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), *args],
                                cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_real_check_is_read_only_and_render_preserves_math_citations_assets(self):
        before = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.command("md-check")
        self.assertEqual(before, {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()})
        self.command("md-render")
        output = self.project / md.OUTPUT
        index = (output / "notes/index.html").read_text()
        model = (output / "notes/derivation.html").read_text()
        self.assertIn('href="derivation.html#model"', index)
        self.assertIn('id="ref-synthetic"', index)
        self.assertIn('src="../.resources/figures/diagram.svg"', index)
        self.assertIn('<math', model)
        self.assertNotIn('<script', index + model)
        self.assertEqual((output / ".resources/figures/diagram.svg").read_bytes(), (self.project / "figures/diagram.svg").read_bytes())
        for name, data in before.items():
            self.assertEqual(data, (self.project / name).read_bytes())

    def test_broken_anchor_reference_link_and_unknown_citation_fail_without_writes(self):
        note = self.project / "notes/index.md"
        for text, diagnostic in (("[Missing][target]\n\n[target]: derivation.md#absent\n", "Broken Markdown anchor"),
                                 ("[Missing][target]\n\n[target]: absent.md\n", "Broken local Markdown link"),
                                 ("Unknown [@notInTheBib].\n", "Unknown Markdown citation")):
            with self.subTest(text=text):
                note.write_text("# Notebook\n\n" + text)
                self.assertIn(diagnostic, self.command("md-check", expected=1).stderr)
                self.assertIn(diagnostic, self.command("md-render", expected=1).stderr)
                self.assertFalse((self.project / md.OUTPUT).exists())

    def test_bare_at_names_are_citations_only_when_a_bibliography_is_declared(self):
        note = self.project / "notes/index.md"
        mention = "# Notebook\n\nAsk @alice about the @property decorator.\n"
        note.write_text(mention)
        failure = self.command("md-check", expected=1).stderr  # the example declares a bibliography
        self.assertIn("Unknown Markdown citation", failure)
        self.assertIn("\\@alice", failure)  # the message names the escape
        note.write_text(mention.replace("@", "\\@"))
        self.command("md-check")
        self.assertEqual(self.cli("configure", "--disable", "bibliography"), 0)
        note.write_text(mention)
        self.command("md-check")  # without a bibliography a bare @name is a mention
        for citation in ("See [@alice].", "See [-@alice]."):
            note.write_text("# Notebook\n\n" + citation + "\n")
            self.assertIn("Unknown Markdown citation", self.command("md-check", expected=1).stderr)

    def test_pandoc_heading_ids_encoded_links_and_code_are_checked_correctly(self):
        (self.project / "notes/encoded space.md").write_text("# Séction\n\n# Repeat\n\n# Repeat\n")
        (self.project / "notes/index.md").write_text("# Notebook\n\n[Accent](encoded%20space.md#s%C3%A9ction)\n[Duplicate](encoded%20space.md#repeat-1)\n\n`[Not a link](missing.md)`\n\n```python\nprint('[@notACitation] [link](missing.md)')\n```\n")
        self.command("md-check")
        self.command("md-render")
        output = (self.project / md.OUTPUT / "notes/index.html").read_text()
        self.assertIn('href="encoded%20space.html#s%C3%A9ction"', output)

    def test_explicit_duplicate_ids_and_escaping_links_fail(self):
        note = self.project / "notes/index.md"
        note.write_text("# Notebook\n\n# One {#same}\n\n# Two {#same}\n")
        self.assertIn("Duplicate Markdown identifier", self.command("md-check", expected=1).stderr)
        note.write_text("# Notebook\n\n[Outside](../../outside.md)\n")
        self.assertIn("escapes project", self.command("md-check", expected=1).stderr)

    def test_render_cannot_follow_output_symlink_or_load_remote_images(self):
        note = self.project / "notes/index.md"
        note.write_text("# Notebook\n\n![Remote](https://example.invalid/image.png)\n")
        self.assertIn("requires local images", self.command("md-render", expected=1).stderr)
        note.write_text("# Notebook\n")
        output = self.project / md.OUTPUT
        output.parent.mkdir(parents=True, exist_ok=True)  # the project's lock files may have created it
        protected = self.project / "protected"
        protected.mkdir()
        output.symlink_to(protected, target_is_directory=True)
        self.assertIn("Refusing symlink", self.command("md-render", expected=1).stderr)
        self.assertEqual(list(protected.iterdir()), [])

    def test_notes_validation_does_not_render_or_run_scientific_commands(self):
        self.command("validate", "--files", "notes/index.md")
        self.assertFalse((self.project / md.OUTPUT).exists())
        self.assertFalse((self.project / "results").exists())
        self.assertTrue((self.project / ".latex-ai/latex.py").exists())  # bibliography parser only

    def test_installed_export_survives_project_relocation(self):
        self.command("md-render")
        relocated = self.project / "relocated"
        relocated.mkdir()
        for path in list(self.project.iterdir()):
            if path != relocated:
                shutil.move(str(path), relocated / path.name)
        self.project = relocated
        self.command("md-check")
        self.command("md-render")
        self.assertIn('href="derivation.html#model"', (self.project / md.OUTPUT / "notes/index.html").read_text())

    def test_raw_html_and_renderer_front_matter_cannot_add_scripts(self):
        (self.project / "notes/index.md").write_text('---\ntitle: Plain\nheader-includes: <script>alert(1)</script>\n---\n\n# Notebook\n\n<script>alert(2)</script>\n')
        self.command("md-render")
        output = (self.project / md.OUTPUT / "notes/index.html").read_text()
        self.assertNotIn("<script", output)

    def test_colliding_html_destinations_fail_before_writes(self):
        path = self.project / core.CONFIG
        config = self.config()
        config["modules"]["markdown"]["files"] = ["notes/*.md", "notes/*.markdown"]
        path.write_text(json.dumps(config))
        (self.project / "notes/index.markdown").write_text("# Notebook\n")
        self.assertIn("collide", self.command("md-render", expected=1).stderr)
        self.assertFalse((self.project / md.OUTPUT).exists())
