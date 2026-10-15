"""Workbench 4.9.0, step 3.7 of docs/maintainers/plan-after-4.4.0.md: the doctor's stamp report, and the update recipe in the skill file.

`make doctor` has always checked the tools. It now also reports the project's stamp: what `.latex-ai/installation.json` records, what the vendored runtime is, and which runtime
files were edited or are missing. Given the folder of a release (`LATEX_AI_TEMPLATE=/path/to/workbench`, or `--template`) it adds the template's side by running that
release's own `latex-ai-init diff`, so there is one rule for what differs, and writes nothing. The update recipe an agent follows is in the skill file; `docs/upgrading.md` points to it.
"""
import json
import re
import shutil
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import core
from test_support import ProjectCase

RECORD = ".latex-ai/installation.json"
SKILL = PACKAGE / "skills/latex-ai-workbench/references/installation.md"


class Doctor(ProjectCase):
    def setUp(self):
        super().setUp()
        self.install("init", "--skip-editor", "--modules", "")

    def doctor(self, *args, template=None, expected=0):
        env = {**self.env, **({"LATEX_AI_TEMPLATE": str(template)} if template else {})}
        return self.command("doctor", *args, env=env, expected=expected)

    def edit_record(self, change):
        path = self.project / RECORD
        record = json.loads(path.read_text())
        change(record)
        path.write_text(json.dumps(record))

    def test_the_stamp_of_a_project_that_matches_is_reported(self):
        out = self.doctor().stdout
        self.assertIn(f"stamp: {RECORD} records {core.VERSION}; the vendored runtime is {core.VERSION}\n", out)
        self.assertRegex(out, r"runtime files: all \d+ unmodified")
        self.assertIn("All required tools found", out)

    def test_an_edited_file_a_missing_one_and_a_record_of_another_version_are_named_and_the_doctor_still_passes(self):
        guide = self.project / ".latex-ai/guide.py"
        guide.write_text(guide.read_text() + "\n# edited by someone\n")
        self.edit_record(lambda record: (record["files"].update({".latex-ai/ghost.py": "0" * 64}), record.update(version="4.0.0")))
        out = self.doctor().stdout
        self.assertIn("records 4.0.0; the vendored runtime is " + core.VERSION + " (they differ)", out)
        self.assertIn(".latex-ai/guide.py (modified locally)", out)
        self.assertIn(".latex-ai/ghost.py (missing)", out)

    def test_a_record_that_cannot_be_read_is_named_and_does_not_stop_the_doctor(self):
        (self.project / RECORD).write_text("{not json")
        out = self.doctor().stdout
        self.assertRegex(out, rf"stamp: {re.escape(RECORD)} is unreadable")
        self.assertIn("All required tools found", out)

    def test_without_a_template_it_says_how_to_compare_with_one(self):
        out = self.doctor().stdout
        self.assertIn("template: not given; to compare with a release, make doctor LATEX_AI_TEMPLATE=/path/to/workbench", out)

    def test_nothing_is_written_into_the_project(self):
        before = self.snapshot()
        self.doctor(template=PACKAGE)
        self.assertEqual(self.snapshot(), before)


class MissingTool(ProjectCase):
    def test_the_stamp_is_printed_before_a_missing_tool_stops_the_doctor(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.install("init", "--skip-editor", "--no-lint")
        result = self.command("doctor", env={**self.env, "PATH": str(self.root / "nothing")}, expected=1)  # no latexmk, no make
        self.assertIn("stamp:", result.stdout)
        self.assertIn("latexmk: MISSING", result.stdout)
        self.assertIn("Missing required tools", result.stderr)


class Template(ProjectCase):
    def setUp(self):
        super().setUp()
        self.install("init", "--skip-editor", "--modules", "")

    def doctor(self, *args, template=None, expected=0):
        env = {**self.env, **({"LATEX_AI_TEMPLATE": str(template)} if template else {})}
        return self.command("doctor", *args, env=env, expected=expected)

    def test_it_gives_the_templates_version_and_says_that_nothing_differs(self):
        out = self.doctor(template=PACKAGE).stdout
        self.assertIn(f"template: {PACKAGE}", out)
        self.assertIn(f"Project runtime {core.VERSION}; this release {core.VERSION}; runtime files are identical.", out)

    def test_the_option_and_make_do_what_the_variable_does(self):
        self.assertIn(f"template: {PACKAGE}", self.doctor("--template", str(PACKAGE)).stdout)
        made = self.run_command("make", "doctor", f"LATEX_AI_TEMPLATE={PACKAGE}")
        self.assertIn(f"template: {PACKAGE}", made.stdout)

    def test_it_lists_the_runtime_files_and_the_generated_files_that_differ_and_the_doctor_still_passes(self):
        guide = self.project / ".latex-ai/guide.py"
        guide.write_text(guide.read_text() + "# an older guide\n")  # still runs, and no longer what the release has
        (self.project / "Makefile").write_text((self.project / "Makefile").read_text() + "# the project's own rule\n")
        out = self.doctor(template=PACKAGE).stdout
        self.assertIn("RUNTIME differs: .latex-ai/guide.py", out)
        self.assertIn("DIFFERS (a file you may have added to; read, do not overwrite): Makefile", out)
        self.assertIn("1 runtime file(s) differ.", out)

    def test_an_older_project_is_shown_against_the_template(self):
        record = json.loads((self.project / RECORD).read_text())
        record["version"] = "4.0.0"
        (self.project / RECORD).write_text(json.dumps(record))
        schema = self.project / ".latex-ai/schema.py"
        schema.write_text(schema.read_text() + "# an older schema\n")
        out = self.doctor(template=PACKAGE).stdout
        self.assertIn(f"stamp: {RECORD} records 4.0.0", out)
        self.assertIn(f"Project runtime 4.0.0; this release {core.VERSION}; 1 runtime file(s) differ.", out)

    def test_a_folder_that_is_not_a_workbench_is_refused_with_a_hint(self):
        result = self.doctor(template=self.root, expected=1)
        self.assertIn("is not a workbench folder", result.stderr)
        self.assertIn("latex-ai-init", result.stderr)
        self.assertIn("Hint:", result.stderr)

    def test_an_installer_that_refuses_is_reported_and_not_swallowed(self):
        fake = self.root / "fake"
        fake.mkdir()
        (fake / "core.py").write_text("")
        (fake / "latex-ai-init").write_text("import sys\nprint('boom: this release refuses the project', file=sys.stderr)\nsys.exit(2)\n")
        result = self.doctor(template=fake, expected=1)
        self.assertIn("boom: this release refuses the project", result.stderr)

    def test_the_template_is_only_read(self):
        copy = self.root / "template"
        shutil.copytree(PACKAGE, copy, ignore=shutil.ignore_patterns("__pycache__", "tests", "docs", "examples"))
        before = {path.relative_to(copy).as_posix(): path.read_bytes() for path in copy.rglob("*") if path.is_file()}
        env = {key: value for key, value in self.env.items() if key != "PYTHONDONTWRITEBYTECODE"}  # so that only the doctor's own care keeps bytecode out
        self.command("doctor", "--template", str(copy), env=env)
        after = {path.relative_to(copy).as_posix(): path.read_bytes() for path in copy.rglob("*") if path.is_file()}
        self.assertEqual(after, before, "running the installer left a file in the template (bytecode, for one)")


class Recipe(unittest.TestCase):
    def recipe(self):
        return re.search(r"^## Update\n(.*?)(?=^## |\Z)", SKILL.read_text(encoding="utf-8"), re.S | re.M)[1]

    def test_the_skill_holds_the_whole_recipe_in_order_and_starts_with_a_snapshot(self):
        text = self.recipe()
        steps = dict(re.findall(r"^(\d)\. (.*?)(?=^\d\. |^Never delete|\Z)", text, re.S | re.M))
        self.assertEqual(sorted(steps), list("1234567"))
        for number, words in {"1": ["make snapshot"], "2": ["make doctor", "releases.md"], "3": ["latex-ai-init diff", "LATEX_AI_TEMPLATE"], "4": ["latex-ai-init runtime", "--dry-run"],
                              "5": ["AGENTS.md", "stricter"], "6": [".latex-ai.json"], "7": ["make doctor LATEX_AI_TEMPLATE", "make check", "git diff"]}.items():
            for word in words:
                self.assertIn(word, steps[number], f"step {number} lacks {word}")

    def test_upgrading_md_points_at_the_recipe_and_keeps_to_what_a_person_needs(self):
        text = (PACKAGE / "docs/upgrading.md").read_text(encoding="utf-8")
        self.assertIn("skills/latex-ai-workbench/references/installation.md", text)
        for word in ("diff", "runtime", "releases.md", "make check", "snapshot", "make doctor"):
            self.assertIn(word, text)
        self.assertLessEqual(len(text.splitlines()), 45)


if __name__ == "__main__":
    unittest.main()
