"""Orientation added in 3.0.1: the guide (text and HTML), the reasons status gives, and the regrouped help.

The guide is generated from one source (handbook.py). These tests keep it honest: every command it names must
exist, the packaged copies must equal what the code renders, and the read-only commands must stay read-only.
"""
from html.parser import HTMLParser
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
BOX = re.compile("[\u2500-\u257f\u25b2-\u25bc]")


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.external = set(), [], []

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if values.get("id"):
            self.ids.add(values["id"])
        for key in ("href", "src"):
            value = values.get(key) or ""
            if key == "href" and value.startswith("#"):
                self.links.append(value[1:])
            elif value and not value.startswith("#"):
                self.external.append(value)
        if tag in {"script", "link", "img", "iframe"}:
            self.external.append(f"<{tag}>")


class Handbook(unittest.TestCase):
    def setUp(self):
        import handbook
        self.handbook = handbook

    def test_topics_are_complete_and_addressable(self):
        ids = [topic.id for topic in self.handbook.TOPICS]
        self.assertEqual(len(ids), len(set(ids)), "duplicate topic id")
        for topic in self.handbook.TOPICS:
            with self.subTest(topic.id):
                self.assertTrue(topic.title and topic.summary and topic.blocks)
                self.assertRegex(topic.id, r"^[a-z][a-z0-9-]*$")
        for needed in ("overview", "map", "loop", "checks", "states", "names", "glossary", "trouble"):
            self.assertIn(needed, ids)
        howtos = [topic for topic in self.handbook.TOPICS if topic.kind == "howto"]
        self.assertGreaterEqual(len(howtos), 8)
        for topic in howtos:
            self.assertTrue(topic.title.startswith("I "), topic.title)  # each is a want or a situation of the reader's
            self.assertTrue(any(block[0] == "steps" for block in topic.blocks), topic.id)

    def test_every_command_the_guide_names_exists(self):
        known = {name for command in guide.COMMANDS for name in (command.short, command.reserved) if name}
        text = self.handbook.render_markdown()
        named = re.findall(r"\bmake ([a-z][\w-]*)", text)
        self.assertGreater(len(named), 40)
        self.assertEqual(sorted(set(named) - known), [])
        for argument in re.findall(r"\bmake [a-z][\w-]*((?: [A-Z]+=\S+)*)", text):
            self.assertLessEqual({item.split("=")[0] for item in argument.split()}, {"DOC", "TASK", "TOPIC", "ISSUE_NOTE", "ISSUE_COMMAND"})

    def test_every_installer_command_it_shows_is_one_the_installer_has(self):
        text = self.handbook.render_markdown()
        verbs = set(re.findall(r"latex-ai-init ([a-z]+)", text))
        self.assertTrue(verbs and verbs <= {"init", "configure", "upgrade", "audit", "recover"}, verbs)

    def test_text_form_fits_a_terminal_and_has_an_ascii_fallback(self):
        text = self.handbook.render_text("all")
        self.assertTrue(BOX.search(text), "the diagrams should use box drawing where the terminal can show it")
        for line in text.splitlines():
            self.assertLessEqual(len(line), 78, line)
        fallback = self.handbook.render_text("all", ascii_only=True)
        self.assertTrue(fallback.isascii(), sorted({char for char in fallback if not char.isascii()}))
        self.assertEqual([len(line) for line in fallback.splitlines()], [len(line) for line in text.splitlines()],
                         "the fallback must keep the layout")

    def test_one_topic_renders_alone_and_unknown_ones_are_refused(self):
        loop = self.handbook.render_text("loop")
        self.assertIn("make status", loop)
        self.assertNotIn("Glossary", loop)
        with self.assertRaises(core.WorkbenchError) as caught:
            self.handbook.render_text("nonsense")
        self.assertIn("nonsense", str(caught.exception))
        for known in ("loop", "glossary", "stale"):
            self.assertIn(known, caught.exception.hint)

    def test_commands_are_written_with_the_names_that_work_in_the_project(self):
        names = {"build": "latex-ai-build", "check": "check", "lint": None, "doctor": "latex-ai-doctor"}
        before = "`make build DOC=a`, `make check`, `make lint`, `make doctor` and `make unknown`"
        self.assertEqual(self.handbook.localize(before, names),
                         "`make latex-ai-build DOC=a`, `make check`, `make lint`, `make latex-ai-doctor` and `make unknown`")
        self.assertEqual(self.handbook.localize(before, {}), before)

    def test_html_is_one_self_contained_page_whose_links_resolve(self):
        page = self.handbook.render_html()
        parser = Anchors()
        parser.feed(page)
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertEqual(parser.external, [], "the page must not depend on anything outside itself")
        self.assertEqual(sorted(set(parser.links) - parser.ids), [])
        self.assertLessEqual({topic.id for topic in self.handbook.TOPICS}, parser.ids)
        self.assertIn("prefers-color-scheme: dark", page)
        self.assertIn("@media print", page)
        self.assertIn('<meta name="viewport"', page)

    def test_html_escapes_what_comes_from_the_project(self):
        context = {"name": "<b>x</b> & y", "modules": ["<i>latex</i>"], "names": {}, "problem": ["<bad> & worse", "fix <it>"],
                   "documents": [{"id": "a<b", "state": "stale", "default": True, "root": "m.tex", "engine": "pdflatex",
                                  "reasons": ["changed: <script>alert(1)</script>"]}]}
        page = self.handbook.render_html(context)
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("<b>x</b>", page)
        self.assertIn("&lt;b&gt;x&lt;/b&gt; &amp; y", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_the_packaged_copies_equal_what_the_code_renders(self):
        for name, render in (("handbook.md", self.handbook.render_markdown), ("handbook.html", self.handbook.render_html)):
            with self.subTest(name):
                shipped = (PACKAGE / "docs" / name).read_text(encoding="utf-8")
                self.assertEqual(shipped, render(), f"regenerate with: make -C workbench handbook ({name} is generated, do not edit it)")

    def test_handbook_is_a_runtime_file(self):
        self.assertIn("handbook.py", core.RUNTIME_FILES)
        self.assertIn("handbook.py", core.runtime_sources({"schema_version": 3, "modules": {}}))


class Orientation(ProjectCase):
    def paper(self, makefile=None):
        (self.project / "main.tex").write_text(SOURCE)
        if makefile:
            (self.project / "Makefile").write_text(makefile)
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")

    # --- make guide ----------------------------------------------------------------------------------------

    def test_the_front_page_shows_the_project_and_the_way_to_every_topic(self):
        self.paper()
        text = self.command("guide").stdout
        self.assertIn("Your project", text)
        self.assertRegex(text, r"paper \(default\).*missing")
        for topic in ("loop", "states", "stale", "glossary", "trouble"):
            self.assertIn(f"TOPIC={topic}", text)
        self.assertIn("make guide-html", text)

    def test_a_topic_prints_alone_and_all_prints_everything(self):
        self.paper()
        loop = self.command("guide", "--topic", "loop").stdout
        self.assertIn("make status", loop)
        self.assertNotIn("Glossary", loop)
        everything = self.command("guide", "--topic", "all").stdout
        for title in ("Glossary", "What lives where", "The everyday loop"):
            self.assertIn(title, everything)

    def test_an_unknown_topic_says_which_exist(self):
        self.paper()
        result = self.command("guide", "--topic", "nonsense", expected=1)
        self.assertIn("ERROR:", result.stderr)
        self.assertRegex(result.stderr, r"Hint:.*loop")

    def test_the_guide_reads_and_writes_nothing(self):
        self.paper()
        before = self.snapshot()
        self.command("guide")
        self.command("guide", "--topic", "all")
        self.assertEqual(self.snapshot(), before)

    def test_the_guide_works_when_the_configuration_is_broken(self):
        self.paper()
        (self.project / core.CONFIG).write_text("{ not json")
        result = self.command("guide")
        self.assertIn("Configuration problem", result.stdout)
        self.assertIn("make status", result.stdout)

    def test_a_terminal_that_cannot_show_box_drawing_gets_plain_characters(self):
        self.paper()
        result = self.command("guide", "--topic", "map", env=fixture_env(PYTHONIOENCODING="ascii"))
        self.assertTrue(result.stdout.isascii())
        self.assertIn("+--", result.stdout)
        self.assertEqual(self.command("guide", "--topic", "map").stdout.count("\n"), result.stdout.count("\n"))

    def test_how_tos_name_the_commands_this_makefile_really_has(self):
        self.paper("build:\n\t@echo mine\n\nguide:\n\t@echo mine\n")
        text = self.command("guide", "--topic", "pdf").stdout
        self.assertIn("make latex-ai-build", text)
        self.assertNotRegex(text, r"make build\b")
        self.assertIn("make latex-ai-guide", self.command("help").stdout)

    # --- make guide-html -----------------------------------------------------------------------------------

    def test_the_html_guide_is_one_ignored_file_that_knows_the_project(self):
        self.paper()
        before = self.snapshot()
        result = self.command("guide-html")
        after = self.snapshot()
        self.assertEqual(sorted(set(after) - set(before)), [".latex-ai/artifacts/guide.html"])
        self.assertEqual({name for name in before if before[name] != after.get(name)}, set())
        self.assertIn(".latex-ai/artifacts/guide.html", result.stdout)
        page = (self.project / ".latex-ai/artifacts/guide.html").read_text(encoding="utf-8")
        parser = Anchors()
        parser.feed(page)
        self.assertEqual((parser.external, sorted(set(parser.links) - parser.ids)), ([], []))
        self.assertIn("paper", page)
        self.assertIn("missing", page)
        ignored = (self.project / ".gitignore").read_text()
        self.assertIn(".latex-ai/artifacts/", ignored)

    # --- through Make --------------------------------------------------------------------------------------

    @unittest.skipUnless(MAKE, "GNU Make required")
    def test_make_passes_the_topic_and_writes_the_page(self):
        self.paper()
        self.assertIn("The everyday loop", self.run_command("make", "guide", "TOPIC=loop").stdout)
        self.run_command("make", "guide-html")
        self.assertTrue((self.project / ".latex-ai/artifacts/guide.html").is_file())
        self.assertIn("The everyday loop", self.run_command("make", "latex-ai-guide", "TOPIC=loop").stdout)
        self.assertIn("The everyday loop", self.run_command("make", "guide", env=fixture_env(TOPIC="loop")).stdout)  # as DOC and TASK

    @unittest.skipUnless(MAKE, "GNU Make required")
    def test_a_project_target_named_guide_is_kept(self):
        self.paper("guide:\n\t@echo mine\n")
        self.assertEqual(self.run_command("make", "guide").stdout.strip(), "mine")
        self.assertIn("The everyday loop", self.run_command("make", "latex-ai-guide", "TOPIC=loop").stdout)

    # --- help ----------------------------------------------------------------------------------------------

    def test_help_has_one_heading_per_group_and_points_to_the_guide(self):
        self.paper()
        text = self.command("help").stdout
        groups = {command.group for command in guide.COMMANDS}
        headings = [line for line in text.splitlines() if line in groups]
        self.assertEqual(headings, list(dict.fromkeys(headings)), headings)
        self.assertRegex(text, r"(?m)^Start here: .*status.*guide")
        self.assertRegex(text, r"(?m)^\s+make guide\s")
        self.assertRegex(text, r"(?m)^\s+make guide-html\s")
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
