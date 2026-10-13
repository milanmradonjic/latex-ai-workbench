"""Workbench 4.3.0 removes the installer's upgrade machinery (see docs/maintainers/minimal-scope.md): the installer creates a
project (`init`), says how a project differs from this release (`diff`) and refreshes its vendored runtime (`runtime`). There is no
audit, upgrade, configure or recovery; a project is updated by an agent following docs/upgrading.md, with a diff and `make check`.

These tests pin what is gone (the modes, the three-way merge, the manifest of every managed file, the disabled-module memory) and what the
three modes promise: `init` never touches an installed project, `diff` never writes, `runtime` never overwrites an edited file unasked.
"""
import contextlib
import io
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import bootstrap
import core
import diagnostics
import schema
from test_support import ProjectCase

SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"
REMOVED_MODES = ("upgrade", "audit", "configure", "recover", "migrate")
REMOVED_WORDS = re.compile(r"latex-ai-init (?:upgrade|audit|configure)\b|\bconfigure (?:--enable|--disable)|--enable (?:bibliography|latex)\b"
                           r"|\bdisabled_modules\b|installation\.py|\.latex-ai/installation\.json.{0,40}manifest|three-way")


class NoUpgradeMachinery(ProjectCase):
    def test_the_installer_has_three_modes_and_refuses_the_removed_ones_by_name(self):
        for mode in REMOVED_MODES:
            with self.subTest(mode=mode):
                done = self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), mode, str(self.project), expected=2)
                self.assertIn("invalid choice", done.stderr)
                self.assertIn("'init', 'diff', 'runtime'", done.stderr)

    def test_the_merge_engine_and_the_manifest_are_gone(self):
        self.assertFalse((PACKAGE / "installation.py").exists())
        self.assertNotIn("installation.py", core.RUNTIME_FILES)
        self.assertFalse(hasattr(bootstrap, "installation"))
        for name in ("three_way", "upgrade", "audit", "do_upgrade", "do_audit", "do_configure", "manifest_text", "migrate"):
            self.assertFalse(hasattr(bootstrap, name), name)
        self.assertFalse(hasattr(diagnostics, "manifest"))
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--engine", "pdflatex", "--no-lint", "--skip-editor")
        self.assertFalse((self.project / ".latex-ai/installation.py").exists())

    def test_the_installer_stays_small(self):
        lines = (PACKAGE / "bootstrap.py").read_text(encoding="utf-8").count("\n")
        self.assertLess(lines, 640, "the installer is a create script, not an engine")

    def test_a_configuration_that_remembers_disabled_modules_is_refused_by_name(self):
        config = {"schema_version": 3, "modules": {}, "disabled_modules": {"bibliography": {"files": ["refs.bib"]}}}
        with self.assertRaises(core.WorkbenchError) as raised:
            schema.validate_config(self.project, config)
        self.assertIn("disabled_modules", str(raised.exception))
        self.assertIn("modules", raised.exception.hint)

    def test_a_disabled_module_is_one_that_is_absent_and_the_commands_say_how_to_turn_it_on(self):
        self.install("init", "--profile", "core")
        done = self.command("bib-check", expected=None)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('"modules"', done.stderr)
        self.assertNotRegex(done.stderr, REMOVED_WORDS)


class Init(ProjectCase):
    def test_init_creates_a_project_and_records_a_digest_of_each_runtime_file_and_nothing_else(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--engine", "pdflatex", "--no-lint", "--skip-editor")
        record = json.loads((self.project / ".latex-ai/installation.json").read_text(encoding="utf-8"))
        self.assertEqual(set(record), {"schema_version", "version", "files"})
        self.assertEqual(record["version"], core.VERSION)
        self.assertTrue(record["files"] and all(name.startswith(".latex-ai/") for name in record["files"]))
        for name, digest in record["files"].items():
            self.assertEqual(digest, diagnostics.sha256_text((self.project / name).read_text(encoding="utf-8")), name)

    def test_init_refuses_a_project_that_is_installed_and_writes_nothing(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--engine", "pdflatex", "--no-lint", "--skip-editor")
        before = {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        done = self.install("init", expected=2)
        self.assertIn("already has the workbench installed", done.stdout + done.stderr)
        self.assertIn("runtime", done.stdout + done.stderr)  # the hint names what to do instead
        self.assertEqual(before, {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()})

    def test_init_builds_a_project_from_the_configuration_it_already_has_and_does_not_change_it(self):
        (self.project / "main.tex").write_text(SOURCE)
        config = self.configure()
        text = (self.project / core.CONFIG).read_text(encoding="utf-8")
        self.install("init", "--skip-editor")
        self.assertEqual((self.project / core.CONFIG).read_text(encoding="utf-8"), text)
        self.assertEqual(json.loads(text), config)
        self.assertTrue((self.project / ".latex-ai/workbench.py").is_file())

    def test_an_init_that_dies_half_way_is_finished_by_running_it_again_without_the_starting_options(self):
        (self.project / "main.tex").write_text(SOURCE)
        written = []
        real = bootstrap.publish

        def dies_on_the_sixth_file(project, name, text):
            written.append(name)
            if len(written) == 6:
                raise OSError("simulated power cut")
            return real(project, name, text)

        with patch.object(bootstrap, "publish", dies_on_the_sixth_file), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bootstrap.main(["init", "--profile", "writing", "--engine", "pdflatex", str(self.project)]), 2)
        self.assertTrue((self.project / core.CONFIG).is_file())
        self.assertFalse((self.project / ".latex-ai/installation.json").exists(), "the record is written last")
        done = self.install("init", "--profile", "writing", expected=2)
        self.assertIn("run init again without them", done.stdout + done.stderr)
        self.install("init", "--engine", "pdflatex")
        self.assertEqual(self.install("diff").returncode, 0)

    def test_init_does_not_let_an_option_override_the_configuration_it_found(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.configure()
        for option in (("--profile", "core"), ("--modules", "latex"), ("--editor",), ("--engine", "xelatex")):
            with self.subTest(option=option):
                self.install("init", *option, expected=2)


class Diff(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--engine", "pdflatex", "--no-lint", "--skip-editor")

    def snapshot(self):
        return {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()}

    def test_diff_is_silent_about_a_current_project_and_never_writes(self):
        before = self.snapshot()
        done = self.install("diff")
        self.assertIn("runtime files are identical", done.stdout)
        self.assertEqual(before, self.snapshot())

    def test_diff_exits_1_for_an_edited_or_missing_runtime_file_and_still_never_writes(self):
        (self.project / ".latex-ai/core.py").write_text("# local\n")
        (self.project / ".latex-ai/guide.py").unlink()
        before = self.snapshot()
        done = self.install("diff", "--diff", expected=1)
        self.assertIn("RUNTIME differs: .latex-ai/core.py", done.stdout)
        self.assertIn("RUNTIME missing: .latex-ai/guide.py", done.stdout)
        self.assertIn("-# local", done.stdout)
        self.assertEqual(before, self.snapshot())

    def test_diff_names_a_missing_policy_file_and_marks_one_you_extended_as_not_to_be_overwritten(self):
        (self.project / "AGENTS.md").write_text("Mine.\n")
        (self.project / ".gitignore").unlink(missing_ok=True)
        done = self.install("diff")
        self.assertIn("DIFFERS (a file you may have added to; read, do not overwrite): AGENTS.md", done.stdout)

    def test_the_options_only_init_reads_are_refused_not_ignored(self):
        for option in ("--profile=core", "--engine=xelatex", "--json", "--no-lint", "--force"):
            with self.subTest(option=option):
                done = self.install("diff", option, expected=2)
                self.assertIn("does not take", done.stdout + done.stderr)


class Runtime(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--engine", "pdflatex", "--no-lint", "--skip-editor")
        self.core = self.project / ".latex-ai/core.py"
        self.original = self.core.read_text(encoding="utf-8")

    def snapshot(self):
        return {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()}

    def test_runtime_restores_a_missing_runtime_file_and_records_it(self):
        self.core.unlink()
        self.install("runtime")
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)
        self.assertEqual(self.install("diff").returncode, 0)

    def test_runtime_replaces_a_file_the_record_says_the_workbench_wrote_and_backs_up_the_old_one(self):
        # Simulate an older release: its file and the record agree; this release's file differs.
        old = "# an older release\n"
        self.core.write_text(old)
        record = self.project / ".latex-ai/installation.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        data["files"][".latex-ai/core.py"] = diagnostics.sha256_text(old)
        record.write_text(json.dumps(data), encoding="utf-8")
        self.install("runtime")
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)
        backups = list((self.project / ".latex-ai/backups").glob("*/.latex-ai/core.py"))
        self.assertEqual([path.read_text(encoding="utf-8") for path in backups], [old])

    def test_runtime_reads_the_record_an_older_release_wrote(self):
        # 4.2 recorded a digest per file inside an object, with a strategy; a project made by it must not look edited.
        old = "# an older release\n"
        self.core.write_text(old)
        record = self.project / ".latex-ai/installation.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        data["files"] = {name: {"strategy": "full", "installed_sha256": digest} for name, digest in data["files"].items()}
        data["files"][".latex-ai/core.py"]["installed_sha256"] = diagnostics.sha256_text(old)
        record.write_text(json.dumps({**data, "schema_version": 2}), encoding="utf-8")
        self.install("runtime")
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)

    def test_runtime_refuses_to_overwrite_an_edited_file_unless_forced(self):
        self.core.write_text(self.original + "# local edit\n")
        before = self.snapshot()
        done = self.install("runtime", expected=2)
        self.assertIn("modified locally", done.stdout)
        self.assertIn("--force", done.stdout)
        self.assertEqual(before, self.snapshot(), "a refusal changes nothing")
        self.install("runtime", "--force")
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)
        kept = list((self.project / ".latex-ai/backups").glob("*/.latex-ai/core.py"))
        self.assertEqual([path.read_text(encoding="utf-8") for path in kept], [self.original + "# local edit\n"])

    def test_a_runtime_that_dies_half_way_is_finished_by_running_it_again(self):
        # The record is written last, so a refresh that stops after some files leaves the old record, and the files not yet
        # replaced still match it: nothing looks edited, and the second run only does what is left.
        for name in ("core.py", "guide.py", "schema.py"):
            (self.project / ".latex-ai" / name).write_text("# an older release\n")
        record = self.project / ".latex-ai/installation.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        for name in ("core.py", "guide.py", "schema.py"):
            data["files"][".latex-ai/" + name] = diagnostics.sha256_text("# an older release\n")
        record.write_text(json.dumps(data), encoding="utf-8")
        written = []

        def dies_on_the_second_file(project, name, text):
            written.append(name)
            if len(written) == 2:
                raise OSError("simulated power cut")
            return real(project, name, text)

        real = bootstrap.publish
        with patch.object(bootstrap, "publish", dies_on_the_second_file), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bootstrap.main(["runtime", str(self.project)]), 2)
        self.assertEqual(json.loads(record.read_text(encoding="utf-8")), data, "the record is written last")
        self.assertEqual(self.install("diff", expected=1).returncode, 1)
        self.install("runtime")
        self.assertEqual(self.install("diff").returncode, 0)
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)

    def test_runtime_dry_run_writes_nothing(self):
        self.core.unlink()
        before = self.snapshot()
        done = self.install("runtime", "--dry-run")
        self.assertIn("Dry run", done.stdout)
        self.assertEqual(before, self.snapshot())

    def test_runtime_leaves_every_file_that_is_not_runtime_alone(self):
        (self.project / "AGENTS.md").write_text("Mine.\n")
        (self.project / "Makefile").write_text("pdf:\n\ttrue\n")
        (self.project / ".vscode").mkdir(exist_ok=True)
        (self.project / ".vscode/settings.json").write_text('{"editor.tabSize": 3}\n')
        self.core.unlink()
        self.install("runtime")
        self.assertEqual((self.project / "AGENTS.md").read_text(), "Mine.\n")
        self.assertEqual((self.project / "Makefile").read_text(), "pdf:\n\ttrue\n")
        self.assertEqual((self.project / ".vscode/settings.json").read_text(), '{"editor.tabSize": 3}\n')

    def test_runtime_in_a_folder_that_is_not_a_project_is_a_clean_error(self):
        empty = self.root / "empty"
        empty.mkdir()
        done = self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), "runtime", str(empty), expected=2)
        self.assertNotIn("INTERNAL ERROR", done.stdout + done.stderr)
        self.assertEqual(list(empty.iterdir()), [])

    def test_a_status_that_finds_a_changed_runtime_points_to_diff(self):
        self.core.write_text(self.original + "# local edit\n")
        text = self.command("status", expected=None).stdout
        self.assertRegex(text, r"latex-ai-init diff \. --diff")
        self.assertNotRegex(text, REMOVED_WORDS)


class NothingDescribesWhatIsGone(unittest.TestCase):
    def test_no_live_document_or_guide_describes_the_removed_modes(self):
        paths = [PACKAGE / name for name in ("README.md", "templates/AGENTS.md", "skills/latex-ai-workbench/SKILL.md", "guide.py", "runtime.py",
                                             "bootstrap.py", "Makefile")]
        paths += sorted((PACKAGE / "docs").glob("*.md"))
        for path in paths:
            with self.subTest(file=path.name):
                found = REMOVED_WORDS.search(path.read_text(encoding="utf-8"))
                self.assertIsNone(found, found and found.group(0))

    def test_the_update_recipe_is_written_down_for_an_agent_to_follow(self):
        text = (PACKAGE / "docs/upgrading.md").read_text(encoding="utf-8")
        for step in ("diff", "runtime", "releases.md", "make check", "snapshot"):
            self.assertIn(step, text)
        self.assertLessEqual(len(text.splitlines()), 60, "a recipe an agent follows, not a manual")


if __name__ == "__main__":
    unittest.main()
