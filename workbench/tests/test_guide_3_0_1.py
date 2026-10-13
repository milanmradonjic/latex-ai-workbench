"""Orientation: the short manual (`make guide`), the reasons status gives, and the grouped help.

Until 4.2.0 the guide was a long generated handbook (pictures, topics, a web page). These tests keep what replaced it honest: every
command the manual names exists, it is written with the names that work in the project, and the read-only commands stay read-only.
"""
import json
from pathlib import Path
import re
import shutil
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
import guide
from test_support import ProjectCase, fixture_env

PACKAGE = Path(__file__).resolve().parents[1]
MAKE = bool(shutil.which("make"))
SOURCE = "\\documentclass{article}\n\\begin{document}Guide fixture.\\end{document}\n"






class Orientation(ProjectCase):
    def paper(self, own=()):
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")
        self.own_targets(*own)

    # --- make guide ----------------------------------------------------------------------------------------

    def test_the_manual_shows_the_project_and_the_everyday_loop(self):
        self.paper()
        text = self.command("guide").stdout
        self.assertIn("manual for", text)
        self.assertRegex(text, r"Documents: paper \(default\) is missing")
        for command in ("make status", "make validation-plan", "make validate", "make check", "make build DOC=NAME", "make lint-baseline DOC=NAME"):
            self.assertIn(command, text)
        for state in ("current", "stale", "failed", "running", "missing"):
            self.assertRegex(text, rf"(?m)^  {state}\s")
        self.assertIn("INTERNAL ERROR", text)
        self.assertIn("AGENTS.md", text)
        self.assertEqual(self.command("guide").stdout, text)  # the same every time

    def test_the_guide_reads_and_writes_nothing(self):
        self.paper()
        before = self.snapshot()
        self.command("guide")
        self.assertEqual(self.snapshot(), before)

    def test_the_guide_works_when_the_configuration_is_broken(self):
        self.paper()
        (self.project / core.CONFIG).write_text("{ not json")
        result = self.command("guide")
        self.assertIn("Configuration problem", result.stdout)
        self.assertIn("make status", result.stdout)

    def test_the_manual_names_the_commands_this_makefile_really_has(self):
        self.paper(own=("build", "guide"))
        text = self.command("guide").stdout
        self.assertIn("make latex-ai-build DOC=NAME", text)
        self.assertNotRegex(text, r"make build\b")
        self.assertRegex(text, r"Names: your Makefile keeps its own target for `(guide`, `build|build`, `guide)`")
        self.assertIn("make latex-ai-guide", self.command("help").stdout)

    def test_every_command_the_manual_names_exists(self):
        self.paper()
        names = {command.short for command in guide.COMMANDS} | {command.reserved for command in guide.COMMANDS if command.reserved}
        for name in re.findall(r"make ([a-z][a-z-]*)", self.command("guide").stdout):
            if name not in {"sure"}:
                self.assertIn(name, names, name)

    def test_a_project_without_latex_gets_a_manual_without_documents(self):
        self.install("init", "--profile", "core")
        text = self.command("guide").stdout
        self.assertIn("Modules: none (core only)", text)
        self.assertNotIn("make build", text)
        self.assertNotIn("What a document's state means", text)

    # --- through Make --------------------------------------------------------------------------------------

    @unittest.skipUnless(MAKE, "GNU Make required")
    def test_make_prints_the_manual(self):
        self.paper()
        self.assertIn("The everyday loop", self.run_command("make", "guide").stdout)
        self.assertIn("The everyday loop", self.run_command("make", "latex-ai-guide").stdout)

    @unittest.skipUnless(MAKE, "GNU Make required")
    def test_a_project_target_named_guide_is_kept(self):
        self.paper(own=("guide",))
        self.assertEqual(self.run_command("make", "guide").stdout.strip(), "mine")
        self.assertIn("The everyday loop", self.run_command("make", "latex-ai-guide").stdout)

    # --- help ----------------------------------------------------------------------------------------------

    def test_help_has_one_heading_per_group_and_points_to_the_guide(self):
        self.paper()
        text = self.command("help").stdout
        groups = {command.group for command in guide.COMMANDS}
        headings = [line for line in text.splitlines() if line in groups]
        self.assertEqual(headings, list(dict.fromkeys(headings)), headings)
        self.assertRegex(text, r"(?m)^Start here: .*status.*guide")
        self.assertRegex(text, r"(?m)^\s+make guide\s")
        self.assertNotIn("guide-html", text)
        self.assertIn("make guide", text.splitlines()[-1])

    # --- status gives reasons ------------------------------------------------------------------------------

    def built(self):
        self.paper()
        self.command("build")
        self.assertEqual(self.state(), "current")

    def reasons(self):
        return json.loads(self.command("status", "--json").stdout)["result"]["documents"][0].get("reasons")

    def test_status_names_the_sources_that_changed(self):
        self.built()
        (self.project / "main.tex").write_text(SOURCE + "% edited\n")
        text = self.command("status").stdout
        self.assertRegex(text, r"paper: stale .*\n\s+changed since the verified build: main\.tex")
        self.assertEqual(self.reasons(), ["changed since the verified build: main.tex"])

    def test_status_names_the_settings_that_changed(self):
        self.built()
        config = json.loads((self.project / core.CONFIG).read_text())
        config["modules"]["latex"]["documents"]["paper"]["engine"] = "lualatex"
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.assertEqual(self.reasons(), ["build settings changed: engine"])

    def test_status_says_when_the_outputs_no_longer_match(self):
        self.built()
        (self.project / "outputs/main.pdf").write_bytes(b"replaced")
        self.assertEqual(self.reasons(), ["output changed since the build: outputs/main.pdf"])
        (self.project / "outputs/main.pdf").unlink()
        self.assertEqual(self.reasons(), ["output missing: outputs/main.pdf"])

    def test_a_current_document_has_no_reasons(self):
        self.built()
        self.assertIsNone(self.reasons())

    def test_many_changed_sources_are_summarised(self):
        (self.project / "main.tex").write_text(SOURCE)
        names = [f"part{number}.txt" for number in range(7)]
        for name in names:
            (self.project / name).write_text("1\n")
        self.builder(inputs=("main.tex", *names))
        self.configure()
        self.install("init", "--skip-editor")
        self.command("build")
        for name in names:
            (self.project / name).write_text("2\n")
        reasons = self.reasons()
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn("and 3 more", reasons[0])


if __name__ == "__main__":
    unittest.main()
