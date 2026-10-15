"""Workbench 4.9.1: the manual (`make guide`) after two independent readers used it.

Two agents were each given only the manual and a project (a newcomer's, with no Git; an owner's, with two documents under Git) and asked to work. What both
misread, or could not find, is fixed here, and each claim the manual now makes is held to what the tool does:

* a document is named with its file, and one never built is "not built yet" (it read as a missing file);
* where the PDF goes after `make build`, from the same rule the build uses;
* "verified build", read as "the checks passed", is gone from the states;
* `make all` stops at the first failure; an undefined reference or citation is an ERROR; an error does not always have a Hint;
* the snapshot commands need Git installed (the project need not use it) and print FILE for the reader to replace;
* `lint-baseline` is for style warnings, never an ERROR;
* what the agents ask about, in the words of the installed rules; where to read how to update; what `validate` does without Git.
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import core
import schema
from test_support import ProjectCase, fixture_env

SOURCE = "\\documentclass{article}\n\\begin{document}Guide fixture.\\end{document}\n"
MANUAL_LINES = 60
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


class Manual(ProjectCase):
    def paper(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")

    def default_paper(self):
        """A project as `init` leaves it, with the documents' default output folders."""
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--skip-editor")

    def guide(self):
        return self.command("guide").stdout

    def test_a_document_is_named_with_its_file_and_a_new_one_is_not_built_yet(self):
        self.paper()
        text = self.guide()
        self.assertIn("Documents: paper = main.tex (default): not built yet", text)
        self.assertNotIn("is missing", text)
        self.command("build")
        self.assertIn("Documents: paper = main.tex (default): current", self.guide())

    def test_each_document_of_several_is_named_with_its_file(self):
        self.paper()
        (self.project / "talk.tex").write_text(SOURCE)
        self.add_document("talk", "talk.tex", output_dir="outputs", build_command=[sys.executable, "builder.py"], lint={"enabled": False})
        self.assertIn("Documents: paper = main.tex (default): not built yet; talk = talk.tex: not built yet", self.guide())

    def test_the_manual_says_where_the_pdf_goes_and_it_goes_there(self):
        self.paper()  # outputs/ is set for this document, so the manual must name it and not the usual folder
        text = self.guide()
        folder = re.search(r"build the PDF \(into (\S+)\)", text)
        self.assertTrue(folder, text)
        self.assertNotIn(".latex-ai/artifacts/documents/NAME/build", text)
        self.command("build")
        self.assertTrue(list((self.project / folder[1]).glob("*.pdf")), f"no PDF in {folder[1]}")

    def test_the_usual_folder_is_named_with_NAME_and_is_the_one_the_build_uses(self):
        self.default_paper()
        text = self.guide()
        self.assertIn("build the PDF (into .latex-ai/artifacts/documents/NAME/build/)", text)
        spec = schema.specifications(core.effective_config(schema.load_config(self.project)))[0]
        self.assertEqual(spec.view["output_dir"], f".latex-ai/artifacts/documents/{spec.name}/build")

    def test_the_states_do_not_say_that_the_checks_passed(self):
        self.paper()
        self.assertNotIn("verified", " ".join(schema.STATES.values()))
        text = self.guide()
        self.assertNotIn("verified", text)
        self.assertRegex(text, r"What a document's state means \(.*not .*checks")
        self.command("build")
        status = self.command("status").stdout
        self.assertNotIn("verified build", status)
        self.assertRegex(status, r"paper: current \(built from [^;]*without a LaTeX error")

    def test_status_does_not_say_verified_build_for_a_document_never_built_or_changed_since(self):
        self.paper()
        for arguments in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "first"]):
            subprocess.run(["git", *arguments], cwd=self.project, env={**fixture_env(), **IDENTITY}, check=True, capture_output=True)
        status = self.command("status").stdout
        self.assertIn("(no build yet: paper)", status)
        self.assertNotIn("verified build", status)
        self.command("build")
        (self.project / "main.tex").write_text(SOURCE + "% changed\n")
        status = self.command("status").stdout
        self.assertIn("changed since the build: main.tex", status)
        self.assertNotIn("verified build", status)

    def test_make_all_is_said_to_stop_at_the_first_failure(self):
        # Behaviour: test_scope_4_6_0 (all does not try the documents after a failure).
        self.paper()
        self.assertRegex(self.guide(), r"build every document, one after another; it stops at the first one that fails")

    def test_an_undefined_reference_is_an_error_as_the_manual_says_and_an_error_may_have_no_hint(self):
        self.paper()
        text = self.guide()
        self.assertRegex(text, r"ERROR: is an ordinary failure \(an undefined reference or citation is one\)")
        self.assertIn("and its Hint, if it has one", text)
        (self.project / "builder.py").write_text(
            "from pathlib import Path\n"
            "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
            "(out / 'main.pdf').write_bytes(b'%PDF-fixture')\n"
            "(out / 'main.log').write_text(\"LaTeX Warning: Reference `fig:one' on page 1 undefined on input line 3.\\nLaTeX Warning: There were undefined references.\\n\")\n"
            "(out / 'main.fls').write_text('PWD ' + str(Path.cwd()) + '\\nINPUT main.tex\\n')\n")
        result = self.command("build", expected=1)
        self.assertIn("undefined", result.stderr)
        self.assertEqual(self.state(), "failed")

    def test_the_snapshot_lines_say_git_is_needed_and_what_to_replace_in_the_command(self):
        self.paper()
        text = self.guide()
        self.assertIn("needs Git installed; the project need not use it", text)
        self.assertIn("write a file's path where it says FILE", text)
        self.command("snapshot")
        self.assertIn("FILE", self.command("snapshots").stdout)  # what the manual tells the reader to replace is really printed

    def test_a_snapshot_keeps_uncommitted_files_as_the_manual_says(self):
        self.paper()
        self.assertIn("keep a copy of every file, uncommitted ones too, outside the project", self.guide())
        for arguments in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "first"]):
            subprocess.run(["git", *arguments], cwd=self.project, env={**fixture_env(), **IDENTITY}, check=True, capture_output=True)
        (self.project / "notes.txt").write_text("never committed\n")
        self.command("snapshot")
        printed = re.search(r"--git-dir=(\S+) --work-tree=\S+ checkout (\w+) -- FILE", self.command("snapshots").stdout)
        self.assertTrue(printed)
        names = subprocess.run(["git", f"--git-dir={printed[1]}", "ls-tree", "-r", "--name-only", printed[2]], env=fixture_env(), check=True,
                               capture_output=True, text=True).stdout.split("\n")
        self.assertIn("notes.txt", names)

    def test_lint_baseline_is_for_style_warnings_and_never_for_an_error(self):
        self.paper()
        text = self.guide()
        self.assertIn("accept today's ChkTeX style warnings so that only new ones fail; your decision, never for an ERROR", text)
        self.assertNotIn("the owner's decision", text)

    def test_the_agent_lines_say_what_they_ask_about_and_the_installed_rules_agree(self):
        self.paper()
        text = self.guide()
        self.assertNotIn("any Git change", text)
        self.assertIn("They ask before committing, pushing or anything that rewrites or discards work", text)
        self.assertIn("never push to the default branch (main or master) or merge a pull request", text)
        rules = json.loads((self.project / ".claude/settings.json").read_text())["permissions"]
        for command in ("git commit", "git push", "git reset", "git clean", "git restore"):
            self.assertIn(f"Bash({command}:*)", rules["ask"], command)
        self.assertIn("Bash(git push origin main)", rules["deny"])
        self.assertIn("Bash(gh pr merge:*)", rules["deny"])

    def test_the_update_pointer_names_a_file_the_package_has(self):
        self.paper()
        text = self.guide()
        self.assertIn("follow docs/upgrading.md in a newer workbench folder", text)
        self.assertNotIn("docs/quickstart.md", text)
        self.assertTrue((PACKAGE / "docs/upgrading.md").is_file())

    def test_validation_plan_is_said_to_select_everything_without_git_and_does(self):
        self.paper()
        self.assertIn("nothing runs; without Git, all of them", self.guide())
        self.assertIn("full validation selected", self.command("plan").stdout)

    def test_the_manual_stays_short_and_narrow_for_the_richest_project(self):
        self.paper()
        for name in ("talk", "poster"):
            (self.project / f"{name}.tex").write_text(SOURCE)
            self.add_document(name, f"{name}.tex", output_dir=f"out-{name}", build_command=[sys.executable, "builder.py"], lint={"enabled": False})
        text = self.guide()
        self.assertLessEqual(len(text.splitlines()), MANUAL_LINES, text)
        self.assertTrue(all(len(line) <= 140 for line in text.splitlines()), [line for line in text.splitlines() if len(line) > 140])
        self.assertIn("build the PDF (into paper: outputs/; poster: out-poster/; talk: out-talk/)", text)  # several, each with its own folder: each named


if __name__ == "__main__":
    unittest.main()
