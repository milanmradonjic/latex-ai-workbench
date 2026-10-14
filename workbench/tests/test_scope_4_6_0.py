"""Workbench 4.6.0, step 3.5 of docs/maintainers/plan-after-4.4.0.md: `make all`, and `make NAME` for each document of a project that has several.

`make all` builds every document, one after another (one runtime action, `build --all`, because the project's build lock refuses two builds at once and so
`make -j all` must not start them side by side). `make notes` builds that document, as `make build DOC=notes` does. The generated Makefile gains the targets on purpose:
`all` for every project with LaTeX, and a target per document when there are two or more, written only where the name is free. The bare `make` still builds the
default document. `make guide` names the targets, and `diff` shows an existing project the lines it lacks.
"""
import json
import re
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import bootstrap
import commands
import core
import documents
import schema
from test_support import ProjectCase

SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"
BUILDER = ("import sys\nfrom pathlib import Path\nname = sys.argv[1]\n"
           "if Path('fail-' + name).exists():\n    sys.exit('simulated compiler failure for ' + name)\n"
           "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
           "(out / (name + '.pdf')).write_bytes(b'%PDF-fixture ' + name.encode())\n"
           "(out / (name + '.log')).write_text('Clean log\\n')\n"
           "(out / (name + '.fls')).write_text('PWD ' + str(Path.cwd()) + '\\nINPUT ' + name + '.tex\\n')\n")


def document(name, **fields):
    return {"root": f"{name}.tex", "lint": {"enabled": False}, "output_dir": "outputs", "build_command": [sys.executable, "builder.py", name], **fields}


def configuration(*names, default=None, **fields):
    return {"schema_version": 3, "modules": {"latex": {"default_document": default or names[0], "documents": {name: document(name, **fields) for name in names}}},
            "integrations": {"editor": False}}


def makefile(config):
    return bootstrap.desired_files(config)["Makefile"]


def rules(text):
    """{target: its recipe lines} for the plain rules of a Makefile text."""
    found, current = {}, None
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z][\w-]*):(?!=)\s*(.*)$", line)
        if match:
            current = found.setdefault(match[1], [])
            if match[2]:
                current.append("prerequisites: " + match[2])
        elif line.startswith("\t") and current is not None:
            current.append(line.strip())
        elif line.strip():
            current = None
    return found


class Generated(ProjectCase):
    def test_every_project_with_latex_gets_all_and_one_without_does_not(self):
        text = makefile(configuration("paper"))
        self.assertEqual(rules(text)["latex-ai-build-all"], ["@$(PYTHON) .latex-ai/workbench.py build --all"])
        self.assertEqual(rules(text)["all"], ["prerequisites: latex-ai-build-all"])
        self.assertIn(".PHONY: all", text)
        self.assertNotIn("all", rules(makefile({"schema_version": 3, "modules": {}, "integrations": {"editor": False}})))

    def test_bare_make_still_builds_the_default_document(self):
        self.assertIn(".DEFAULT_GOAL := build", makefile(configuration("paper", "notes", default="notes")))

    def test_a_project_with_several_documents_gets_a_target_for_each(self):
        found = rules(makefile(configuration("paper", "derivation", "notebook")))
        for name in ("paper", "derivation", "notebook"):
            with self.subTest(document=name):
                self.assertEqual(found[name], [f"@$(PYTHON) .latex-ai/workbench.py build --document {name}"])

    def test_a_project_with_one_document_gets_none(self):
        self.assertEqual(set(rules(makefile(configuration("manuscript")))) & {"manuscript"}, set())

    def test_only_a_free_name_gets_a_target(self):
        config = configuration("paper", "check", "help", "all", "status", "latex-ai-x", "notes")
        config["modules"]["latex"]["documents"]["paper"]["build_command"] = ["make", "notes"]  # `notes` is the project's own goal
        found = rules(makefile(config))
        generated = {name for name, recipe in found.items() if recipe == [f"@$(PYTHON) .latex-ai/workbench.py build --document {name}"]}
        self.assertEqual(generated, {"paper"})
        self.assertEqual(found["all"], ["prerequisites: latex-ai-build-all"])  # a document named all does not take the package's target

    def test_the_registry_knows_all(self):
        target = next(t for t in commands.BY_NAME["build"].targets if t.short == "all")
        self.assertEqual(target.reserved, "latex-ai-build-all")
        self.assertNotIn("all", commands.RECURSIVE_GOALS)  # the conventional name of a project's own rule: a build command may name it
        self.assertIn("latex-ai-build-all", commands.RECURSIVE_GOALS)  # the workbench's own name for it may not be named
        (self.project / "paper.tex").write_text(SOURCE)
        for goal, refused in (("all", False), ("latex-ai-build-all", True)):
            with self.subTest(goal=goal):
                config = configuration("paper")
                config["modules"]["latex"]["documents"]["paper"]["build_command"] = ["make", goal]
                if refused:
                    with self.assertRaises(core.WorkbenchError):
                        schema.validate_config(self.project, config)
                else:
                    schema.validate_config(self.project, config)

    def test_all_is_the_projects_own_where_a_document_builds_with_make_all(self):
        config = configuration("paper", "notes")
        config["modules"]["latex"]["documents"]["paper"]["build_command"] = ["make", "all"]
        text = makefile(config)
        self.assertNotIn("all", rules(text))  # no alias for the project's own `all` to fight with
        self.assertIn("latex-ai-build-all", rules(text))  # the workbench's name for it stays


class Running(ProjectCase):
    def setUp(self):
        super().setUp()
        for name in ("paper", "notes"):
            (self.project / f"{name}.tex").write_text(SOURCE)
        (self.project / "builder.py").write_text(BUILDER)
        (self.project / core.CONFIG).write_text(json.dumps(configuration("paper", "notes")))
        self.install("init", "--skip-editor")

    def states(self):
        return {row["id"]: row["state"] for row in documents.report(self.project, schema.load_config(self.project))}

    def test_make_with_a_documents_name_builds_that_document_only(self):
        self.run_command("make", "notes")
        self.assertEqual(self.states(), {"paper": "missing", "notes": "current"})

    def test_bare_make_builds_the_default_document_only(self):
        self.run_command("make")
        self.assertEqual(self.states(), {"paper": "current", "notes": "missing"})

    def test_make_all_builds_every_document_even_when_make_is_asked_for_parallel_jobs(self):
        result = self.run_command("make", "-j4", "all")
        self.assertEqual(self.states(), {"paper": "current", "notes": "current"})
        self.assertNotIn("Cannot lock", result.stdout + result.stderr)

    def test_all_stops_at_the_first_failure_and_names_the_document(self):
        (self.project / "fail-notes").write_text("")
        result = self.run_command("make", "all", expected=2)
        self.assertEqual(self.states()["paper"], "current")
        self.assertIn("notes", result.stdout + result.stderr)

    def test_all_does_not_try_the_documents_after_a_failure(self):
        (self.project / "fail-paper").write_text("")
        self.run_command("make", "all", expected=2)
        self.assertEqual(self.states(), {"paper": "failed", "notes": "missing"})

    def test_all_refuses_a_named_document_and_belongs_to_build_only(self):
        self.command("build", "--all", "--document", "paper", expected=1)
        self.command("lint", "--all", expected=1)


class Guide(ProjectCase):
    def setUp(self):
        super().setUp()
        for name in ("paper", "notes"):
            (self.project / f"{name}.tex").write_text(SOURCE)
        (self.project / "builder.py").write_text(BUILDER)
        (self.project / core.CONFIG).write_text(json.dumps(configuration("paper", "notes")))
        self.install("init", "--skip-editor")

    def test_the_guide_and_help_name_the_targets(self):
        guide = self.command("guide").stdout
        self.assertRegex(guide, r"make notes")
        self.assertRegex(guide, r"make all")
        help_text = self.command("help").stdout
        self.assertRegex(help_text, r"make all\s")
        self.assertIn("make paper, make notes: each builds that document.", help_text)

    def test_a_document_with_no_target_is_built_by_name_the_long_way(self):
        self.add_document("extra", "extra.tex", build_command=[sys.executable, "builder.py", "extra"], lint={"enabled": False}, output_dir="outputs")
        (self.project / "extra.tex").write_text(SOURCE)
        self.assertIn("make build DOC=extra", self.command("guide").stdout)

    def test_diff_shows_a_4_5_project_exactly_the_lines_it_lacks(self):
        path = self.project / "Makefile"
        text = path.read_text()
        old = re.sub(r"\.PHONY: (?:all|notes|paper)\n(?:all|notes|paper):[^\n]*\n(?:\t[^\n]*\n)?", "", text)
        old = re.sub(r"\.PHONY: latex-ai-build-all\nlatex-ai-build-all:\n\t[^\n]*\n", "", old)
        self.assertNotEqual(old, text)
        path.write_text(old)
        diff = self.install("diff", "--diff", expected=None).stdout
        self.assertIn("DIFFERS", diff)
        for line in ("+.PHONY: all", "+.PHONY: notes", "+.PHONY: paper", "+.PHONY: latex-ai-build-all"):
            self.assertIn(line, diff)
        self.assertEqual([l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")], [])


if __name__ == "__main__":
    unittest.main()
