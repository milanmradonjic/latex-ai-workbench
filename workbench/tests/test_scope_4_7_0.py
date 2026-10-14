"""Workbench 4.7.0, step 3.6 of docs/maintainers/plan-after-4.4.0.md: `make snapshot` and `make snapshots`.

A snapshot is a commit of every file of the project in a Git repository of its own, kept outside the project, in two tiers that rotate: the fine tier (every
`make snapshot`, kept one to two weeks) and the daily tier (the first of each day, kept one to two months). Each tier has two repositories used by turns, and a
repository older than the previous period is deleted. The code that deletes is held to a short list of refusals, tested here one by one. Every test runs with a
temporary HOME and its own snapshot folder, so none of them touches the machine it runs on.
"""
import contextlib
import errno
import hashlib
import importlib
import io
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import bootstrap
import commands
import core
from test_support import ProjectCase, fixture_env

SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
FILES = {"main.tex": SOURCE, "refs.bib": "@misc{k}\n", "notes/todo.txt": "z", "figure.pdf": "%PDF-1.5", "main.pdf": "%PDF-1.5 beside its source", ".gitignore": "secret.txt\n", "secret.txt": "kept anyway",
         "a b.tex": "", "é.tex": "", "[x]*.tex": "", "-n.tex": "", ".latex-ai/workbench.py": "# runtime", "crlf.txt": "a\r\nb\r\n", "vendor/lib/x.txt": "a nested repository's file",
         "scripts/train.log": "", "results/solver.out": "", "data/run.toc": "", "refs.bbl": "", "analysis/notes.aux": "",  # a compiler's suffixes, and no .tex of that name beside them
         **({} if os.name == "nt" else {"line\nbreak.tex": ""})}
EXCLUDED = ("main.aux", "main.log", "main.synctex.gz", "outputs/main.pdf", "outputs/main.fls", ".latex-ai/artifacts/locks/build.lock",
            ".latex-ai/backups/20260101T000000Z/old.py", "__pycache__/x.pyc", "docs/__pycache__/y.pyc", "node_modules/p/index.js", ".venv/lib/x.py",
            "env/pyvenv.cfg", "env/lib/x.py", "conda/conda-meta/history", "conda/lib/x.py", "vendor/lib/.git/HEAD", "vendor/lib2/.git", "vendor/lib3/.GIT/config")


def shadow():
    """The module under test, imported when used: a tree without it fails each test, not the whole file."""
    return importlib.import_module("snapshot")


def at(day=0, hour=12):
    """A moment of the test calendar: 2026-10-15 (the first day of a fine-tier week) plus days, UTC."""
    return datetime(2026, 10, 15, hour, tzinfo=timezone.utc) + timedelta(days=day)


def git(repository, *args):
    result = subprocess.run(["git", "--git-dir", str(repository), *args], capture_output=True, env=fixture_env(), check=True)
    return result.stdout


def stores(base):
    """The folders of a snapshot folder that belong to projects: not the lock's, which starts with a dot."""
    return [path for path in sorted(base.iterdir()) if not path.name.startswith(".")]


def history(store):
    """{repository: its commit subjects, newest first} for every snapshot repository of a project's store."""
    return {repository.name: git(repository, "log", "--format=%s").decode().splitlines()
            for repository in sorted(store.iterdir()) if (repository / "HEAD").is_file()}


def names(repository, revision="HEAD"):
    return set(git(repository, "ls-tree", "-r", "-z", "--name-only", revision).decode().split("\0")) - {""}


def digest(folder):
    """Every byte of a folder, in one hash: what 'untouched' means for a project's own .git."""
    total = hashlib.sha256()
    for path in sorted(Path(folder).rglob("*")):
        total.update(os.fsencode(path.relative_to(folder)))
        if path.is_file() and not path.is_symlink():
            total.update(path.read_bytes())
    return total.hexdigest()


class Case(ProjectCase):
    def setUp(self):
        super().setUp()
        self.home = self.root / "home"
        self.home.mkdir()
        self.env["HOME"] = str(self.home)
        patcher = patch.dict(os.environ, {"HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.base = self.root / "snapshots"
        (self.project / "main.tex").write_text(SOURCE)

    def take(self, day=0, hour=12, note="", **options):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = shadow().take(self.project, note=note, base=self.base, now=at(day, hour), **options)
        self.output = output.getvalue()
        return result

    def edit(self, text):
        (self.project / "main.tex").write_text(text)

    def store(self):
        (store,) = stores(self.base)
        return store

    def history(self):
        return history(self.store())

    def repository(self, tier="fine"):
        (name,) = [name for name in self.history() if name.startswith(tier + "-")]
        return self.store() / name

    def own_git(self, *paths):
        for arguments in (["init", "-q"], ["add", *(paths or ["-A"])], ["commit", "-q", "-m", "first"]):
            subprocess.run(["git", *arguments], cwd=self.project, env={**fixture_env(), **IDENTITY}, check=True, capture_output=True)


class Retention(Case):
    def test_the_fine_tier_keeps_this_period_and_the_one_before(self):
        for day, text in ((0, "a"), (7, "b"), (14, "c")):
            self.edit(text)
            self.take(day, note=text)
            fine = {name: subjects for name, subjects in self.history().items() if name.startswith("fine-")}
            self.assertEqual(sorted(fine.values()), {0: [["a"]], 7: [["a"], ["b"]], 14: [["b"], ["c"]]}[day])  # the third week replaces the first, not the second
        self.assertEqual(sorted(fine), ["fine-0", "fine-1"])

    def test_every_snapshot_of_a_period_goes_to_that_periods_repository_newest_first(self):
        for hour, text in ((9, "a"), (11, "b"), (13, "c")):
            self.edit(text)
            self.take(0, hour, note=text)
        self.assertEqual([subjects for name, subjects in self.history().items() if name.startswith("fine-")], [["c", "b", "a"]])

    def test_a_repository_older_than_the_previous_period_goes_even_when_the_other_one_is_in_use(self):
        self.take(0, note="old")
        self.edit("d")
        self.take(21, note="new")  # three weeks on: the other repository is used, and the first is far past its two weeks
        self.assertEqual([subjects for name, subjects in self.history().items() if name.startswith("fine-")], [["new"]])

    def test_the_daily_tier_takes_the_first_snapshot_of_each_day(self):
        for day, hour, text in ((0, 9, "a"), (0, 17, "b"), (1, 9, "c"), (1, 10, "d")):
            self.edit(text)
            self.take(day, hour, note=text)
        history = self.history()
        self.assertEqual([subjects for name, subjects in history.items() if name.startswith("daily-")], [["c", "a"]])
        self.assertEqual([subjects for name, subjects in history.items() if name.startswith("fine-")], [["d", "c", "b", "a"]])

    def test_the_daily_tier_keeps_this_month_and_the_one_before(self):
        for day, text in ((0, "a"), (30, "b"), (60, "c")):  # 15 October, 14 November, 14 December
            self.edit(text)
            self.take(day, note=text)
            daily = sorted(subjects for name, subjects in self.history().items() if name.startswith("daily-"))
            self.assertEqual(daily, {0: [["a"]], 30: [["a"], ["b"]], 60: [["b"], ["c"]]}[day])
        self.assertEqual(sorted(name for name in self.history() if name.startswith("daily-")), ["daily-0", "daily-1"])

    def test_a_daily_repository_older_than_the_previous_month_goes_whichever_one_is_in_use(self):
        self.take(0, note="old")
        self.edit("d")
        self.take(91, note="new")  # 14 January: the other repository is used
        self.assertEqual([subjects for name, subjects in self.history().items() if name.startswith("daily-")], [["new"]])

    def test_nothing_changed_makes_no_snapshot(self):
        first = self.take(note="first")
        again = self.take(0, 13, note="again")
        self.assertEqual((first["changed"], again["changed"]), (True, False))
        self.assertEqual(again["commit"], first["commit"])
        self.assertIn("Nothing changed", self.output)
        self.assertEqual(sum(len(subjects) for subjects in self.history().values()), 2)  # one in each tier

    def test_a_label_is_the_commit_subject_and_defaults_to_snapshot(self):
        self.take(note="before the rewrite of section 3")
        self.edit("b")
        self.take(0, 13)
        self.assertEqual(self.history()[self.repository().name], ["snapshot", "before the rewrite of section 3"])

    def test_the_store_is_named_after_the_project_and_its_path(self):
        self.take()
        self.assertRegex(self.store().name, r"^project-[0-9a-f]{8}$")


class Contents(Case):
    def setUp(self):
        super().setUp()
        self.configure()
        for name, text in {**FILES, **dict.fromkeys(EXCLUDED, "x")}.items():
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode() if isinstance(text, str) else text)

    def test_everything_but_the_excluded_is_included_and_the_projects_own_ignore_rules_are_not_followed(self):
        self.take()
        self.assertEqual(names(self.repository()), set(FILES) | {".latex-ai.json"})
        self.assertEqual(names(self.repository("daily")), names(self.repository()))

    def test_the_count_is_of_what_is_kept(self):
        self.assertEqual(self.take()["files"], len(names(self.repository())))

    def test_a_default_output_folder_is_left_out_too(self):
        (self.project / "build").mkdir()
        (self.project / "build/x.txt").write_text("x")
        (self.project / core.CONFIG).write_text(json.dumps({"modules": {"latex": {"default_document": "a", "defaults": {"output_dir": "build"}, "documents": {"a": {"root": "main.tex"}}}}}))
        self.take()
        self.assertNotIn("build/x.txt", names(self.repository()))

    def test_a_file_that_vanishes_during_the_walk_does_not_stop_the_snapshot(self):
        real = os.walk

        def walking(top, **options):
            for directory, folders, files in real(top, **options):
                yield directory, folders, files + ["ghost.tex"]  # listed, then gone
        with patch.object(os, "walk", walking):
            self.take()
        self.assertIn("main.tex", names(self.repository()))
        self.assertNotIn("ghost.tex", names(self.repository()))

    def test_a_file_is_kept_byte_for_byte(self):
        (self.home / ".gitconfig").write_text("[core]\n\tautocrlf = true\n")  # where the user's own settings live
        self.take()
        self.assertEqual(git(self.repository(), "show", "HEAD:crlf.txt"), b"a\r\nb\r\n")

    def test_a_project_with_its_own_git_has_that_repository_left_out(self):
        self.own_git("main.tex")  # the fixture's own odd files are not for this Git to add
        self.take()
        self.assertFalse([name for name in names(self.repository()) if name.split("/")[0] == ".git"])

    def test_a_link_is_kept_as_a_link_and_never_followed(self):
        outside = self.root / "elsewhere"
        outside.mkdir()
        (outside / "inner.txt").write_text("not the project's")
        os.symlink("main.tex", self.project / "link.tex")
        os.symlink(outside, self.project / "shared")
        self.take()
        listed = git(self.repository(), "ls-tree", "-r", "HEAD").decode()
        self.assertRegex(listed, r"120000 blob \w+\tlink\.tex")
        self.assertRegex(listed, r"120000 blob \w+\tshared")
        self.assertNotIn("inner.txt", listed)

    def test_a_dedicated_output_folder_is_left_out_and_a_folder_with_a_source_in_it_is_not(self):
        cases = (("a build folder of its own", "main.tex", "build", "build/x.txt", False),
                 ("the project folder itself", "main.tex", ".", "outputs/x.txt", True),
                 ("the folder the root is in", "paper/main.tex", "paper", "paper/x.txt", True),
                 ("outside the project", "main.tex", "../elsewhere", "elsewhere/x.txt", True))
        for what, root, output, probe, kept in cases:
            with self.subTest(what):
                shutil.rmtree(self.base, ignore_errors=True)
                for name in (probe, root):
                    (self.project / name).parent.mkdir(parents=True, exist_ok=True)
                    (self.project / name).write_text("x")
                (self.project / core.CONFIG).write_text(json.dumps({"modules": {"latex": {"default_document": "a", "documents": {"a": {"root": root, "output_dir": output}}}}}))
                self.take()
                self.assertEqual(probe in names(self.repository()), kept)

    def test_a_configuration_that_cannot_be_read_does_not_stop_the_snapshot(self):
        for text in ("{not json", "[]", '{"modules": {"latex": {"documents": {"a": "text", "b": {"root": 1, "output_dir": 2}}}}}'):
            with self.subTest(text):
                shutil.rmtree(self.base, ignore_errors=True)
                (self.project / core.CONFIG).write_text(text)
                self.take()
                self.assertIn("main.tex", names(self.repository()))

    def test_a_file_over_the_limit_is_left_out_and_named(self):
        (self.project / "big.dat").write_bytes(b"x" * 2000)
        with patch.object(shadow(), "LIMIT", 1000):
            result = self.take()
        self.assertNotIn("big.dat", names(self.repository()))
        self.assertEqual(result["skipped"], ["big.dat"])
        self.assertIn("big.dat", self.output)

    def test_a_folder_that_cannot_be_walked_stops_the_snapshot_rather_than_leaving_it_out_silently(self):
        def refusing(top, onerror=None, **options):
            onerror(PermissionError(13, "Permission denied", str(top)))  # what os.walk reports for a folder it cannot list
            return iter(())
        with patch.object(shadow().os, "walk", refusing), self.assertRaises(PermissionError):
            self.take()

    def test_an_unreadable_folder_stops_the_snapshot_rather_than_leaving_it_out_silently(self):
        if os.geteuid() == 0:
            self.skipTest("root reads any folder")
        locked = self.project / "locked"
        locked.mkdir()
        (locked / "x.txt").write_text("x")
        locked.chmod(0)
        self.addCleanup(locked.chmod, 0o755)
        with self.assertRaises(OSError):
            self.take()


class Bytes(Case):
    def test_the_bytes_are_kept_whatever_gitattributes_and_the_users_git_say_and_a_restore_runs_no_hook(self):
        (self.project / ".gitattributes").write_text("* text=auto eol=lf\n*.tex ident\n*.u16 working-tree-encoding=UTF-16\nloud.txt filter=shout\n")
        original = {"main.tex": b"\\documentclass{article}\r\n$Id: abc 123 $\r\n", "data.txt": b"a\r\nb\r\n", "note.u16": "h\u00e9llo\n".encode("utf-16"), "loud.txt": b"quiet\n"}
        for name, data in original.items():
            (self.project / name).write_bytes(data)
        hooks = self.root / "hooks"
        hooks.mkdir()
        (hooks / "post-checkout").write_text(f"#!/bin/sh\ntouch {self.root / 'hook-ran'}\n")
        (hooks / "post-checkout").chmod(0o755)
        (self.home / ".gitconfig").write_text(f"[core]\n\tautocrlf = true\n\thooksPath = {hooks}\n[filter \"shout\"]\n\tsmudge = tr a-z A-Z\n\tclean = cat\n")
        self.take()
        repository = self.repository()
        for name, data in original.items():
            self.assertEqual(git(repository, "show", f"HEAD:{name}"), data, name)
        for name in original:
            (self.project / name).write_bytes(b"changed\n")
        theirs = {key: value for key, value in self.env.items() if key != "GIT_CONFIG_GLOBAL"}  # the user's own settings apply to the restore
        self.run_command("git", "--git-dir", str(repository), "--work-tree", str(self.project), "checkout", "HEAD", "--", ".", env=theirs)
        for name, data in original.items():
            self.assertEqual((self.project / name).read_bytes(), data, name)
        self.assertFalse((self.root / "hook-ran").exists())


class Isolation(Case):
    def test_neither_the_users_git_configuration_nor_inherited_git_variables_reach_the_snapshot(self):
        other = self.root / "other"
        subprocess.run(["git", "init", "-q", str(other)], env=fixture_env(), check=True)
        before = digest(other)
        hostile = self.home / ".gitconfig"
        hostile.write_text("[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = /bin/false\n[core]\n\thooksPath = /nonexistent\n[init]\n\ttemplateDir = /nonexistent\n"
                           "[user]\n\tuseConfigOnly = true\n[init]\n\tdefaultBranch = trunk\n")
        inherited = {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other), "GIT_INDEX_FILE": str(other / "index"),
                     "GIT_AUTHOR_NAME": "someone else", "GIT_COMMITTER_EMAIL": "else@example.invalid"}
        with patch.dict(os.environ, inherited):
            self.take(note="isolated")
        self.assertEqual(digest(other), before)
        self.assertEqual(names(self.repository()), {"main.tex"})
        self.assertEqual(git(self.repository(), "log", "-1", "--format=%an <%ae>").decode().strip(), "snapshot <snapshot@localhost.invalid>")
        self.assertNotIn("trunk", (self.repository() / "HEAD").read_text())  # the user's init.defaultBranch is theirs, not the snapshots'

    def test_the_projects_own_repository_is_byte_identical_after_a_snapshot(self):
        self.own_git()
        (self.project / "main.tex").write_text("edited and not committed")
        before = digest(self.project / ".git")
        self.take()
        self.take(1, note="again")
        self.assertEqual(digest(self.project / ".git"), before)

    def test_a_snapshot_writes_nothing_into_the_project(self):
        before = self.snapshot()
        self.take()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(sorted(path.name for path in self.project.iterdir()), ["main.tex"])


class Refusals(Case):
    """The only code of the workbench that deletes outside the project: each way it could delete the wrong thing is refused."""

    def stale(self):
        """A snapshot of a past period, so that the next one deletes its repository."""
        self.take(0, note="old")
        self.edit("d")
        return self.repository(), self.store()

    def refused(self):
        self.take(21, note="new")  # raises; the caller then looks at what is left

    def test_a_repository_that_is_a_link_is_never_followed(self):
        repository, store = self.stale()
        victim = self.root / "victim"
        repository.rename(victim)
        os.symlink(victim, repository)
        with self.assertRaises(core.WorkbenchError):
            self.refused()
        self.assertTrue((victim / "HEAD").is_file())

    def test_a_folder_without_the_marker_is_not_a_repository_of_ours_and_is_never_deleted(self):
        repository, store = self.stale()
        (repository / "SNAPSHOT-REPOSITORY").unlink()
        with self.assertRaises(core.WorkbenchError):
            self.refused()
        self.assertTrue((repository / "HEAD").is_file())

    def test_a_store_without_the_marker_is_not_ours_and_nothing_in_it_is_touched(self):
        repository, store = self.stale()
        (store / "PROJECT").unlink()
        with self.assertRaises(core.WorkbenchError):
            self.refused()
        self.assertTrue((repository / "HEAD").is_file())

    def test_a_period_that_cannot_be_read_is_not_a_reason_to_delete(self):
        repository, store = self.stale()
        (repository / "PERIOD").write_text("garbage")
        with self.assertRaises(core.WorkbenchError):
            self.refused()
        self.assertTrue((repository / "HEAD").is_file())

    def test_a_refusal_in_one_tier_leaves_the_other_without_a_new_snapshot(self):
        self.stale()
        (self.repository("daily") / "SNAPSHOT-REPOSITORY").unlink()
        with self.assertRaises(core.WorkbenchError):
            self.take(1, note="refused")  # the next day: the fine tier would take it, the daily tier refuses
        self.assertEqual([subjects for name, subjects in self.history().items() if name.startswith("fine-")], [["old"]])

    def test_a_snapshot_folder_inside_the_project_is_refused(self):
        with self.assertRaises(core.WorkbenchError):
            shadow().take(self.project, base=self.project / "snapshots", now=at())
        self.assertFalse((self.project / "snapshots").exists())

    def test_nothing_else_in_the_store_or_beside_it_is_touched(self):
        self.take(0, note="a")
        store = self.store()
        (store / "keep-me").mkdir()
        (store / "keep-me/x").write_text("x")
        other = self.base / "other-0123abcd"
        other.mkdir()
        (other / "fine-0").mkdir()
        (other / "fine-0/x").write_text("another project's")
        for day, text in ((7, "b"), (14, "c"), (28, "d")):
            self.edit(text)
            self.take(day, note=text)
        self.assertEqual((store / "keep-me/x").read_text(), "x")
        self.assertEqual((other / "fine-0/x").read_text(), "another project's")

    def test_a_project_whose_clock_went_backwards_loses_nothing(self):
        self.take(14, note="later")
        self.edit("b")
        self.take(0, note="earlier")  # a future repository is never stale
        self.assertEqual(sorted(sum((s for n, s in self.history().items() if n.startswith("fine-")), [])), ["earlier", "later"])


class Hardening(Case):
    """What an independent review reproduced: simultaneous runs, a run that stops half way, a label of blanks, private files, a name too long to be a folder's."""

    def test_snapshots_taken_at_the_same_time_each_hold_every_file(self):
        for number in range(600):
            (self.project / f"f{number}.txt").write_text(str(number))
        command = [sys.executable, "-B", str(PACKAGE / "runtime.py"), "snapshot", "--project", str(self.project)]
        runs = [subprocess.Popen(command, env={**self.env, "LATEX_AI_SNAPSHOT_DIR": str(self.base)}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for _ in range(6)]
        for run in runs:
            output = run.communicate()[0]
            self.assertEqual(run.returncode, 0, output)
        for repository in (path for path in self.store().iterdir() if (path / "HEAD").is_file()):
            for commit in git(repository, "rev-list", "HEAD").decode().split():
                self.assertEqual(len(names(repository, commit)), 601, "a snapshot that is missing files")

    def test_a_second_snapshot_that_cannot_get_the_lock_says_so_and_writes_nothing(self):
        self.take()
        with core.operation_lock(self.base, "snapshot"), self.assertRaisesRegex(core.WorkbenchError, "Another snapshot"):
            self.edit("b")
            self.take(0, 13)
        self.assertEqual(sum(len(subjects) for subjects in self.history().values()), 2)

    def test_a_run_that_stops_half_way_through_making_a_repository_leaves_nothing_that_blocks_the_next(self):
        def stopping(path, period):
            (path / "half").write_text("x")
            raise OSError(errno.ENOSPC, "No space left on device")
        with patch.object(shadow(), "initialize", stopping), self.assertRaises(OSError):
            self.take()
        self.assertTrue(self.take()["changed"])
        self.assertEqual(sum(len(subjects) for subjects in self.history().values()), 2)

    def test_a_label_of_blanks_is_no_label(self):
        self.take(note="   ")
        shadow().listing(self.project, base=self.base)
        self.assertEqual([subjects for name, subjects in self.history().items() if name.startswith("fine-")], [["snapshot"]])

    def test_the_folders_are_private_to_the_user(self):
        if os.name == "nt":
            self.skipTest("POSIX permissions")
        self.take()
        for path in (self.base, self.store(), self.repository(), self.repository("daily")):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700, path)

    def test_a_project_name_too_long_for_a_folder_name_still_has_a_store(self):
        long = self.root / ("n" * 250)
        try:
            long.mkdir()
        except OSError:
            self.skipTest("this file system does not allow it")
        (long / "main.tex").write_text(SOURCE)
        with contextlib.redirect_stdout(io.StringIO()):
            shadow().take(long, base=self.base, now=at())
        self.assertLessEqual(len(self.store().name), 70)

    def test_a_project_path_that_is_not_utf8_has_a_store(self):
        odd = self.root / os.fsdecode(b"odd-\xff-project")
        try:
            odd.mkdir()
        except OSError:
            self.skipTest("this file system does not allow it")
        (odd / "main.tex").write_text(SOURCE)
        with contextlib.redirect_stdout(io.StringIO()):
            shadow().take(odd, base=self.base, now=at())
            shadow().listing(odd, base=self.base)

    def test_where_the_home_folder_is_unknown_the_message_says_what_to_set(self):
        with patch.object(Path, "home", side_effect=RuntimeError("no home")), self.assertRaisesRegex(core.WorkbenchError, "home folder") as raised:
            shadow().location()
        self.assertIn("LATEX_AI_SNAPSHOT_DIR", raised.exception.hint)

    def test_a_store_made_for_another_path_is_not_used(self):
        self.take()
        (self.store() / "PROJECT").write_text("/somewhere/else\n")
        with self.assertRaises(core.WorkbenchError):
            self.take(0, 13, note="refused")

    def test_a_snapshot_that_only_the_daily_tier_takes_says_so(self):
        self.take(16, note="a")  # 31 October
        self.take(17, note="a")  # 1 November: the same files, in the same fine week, but the daily tier starts a new month
        self.assertNotIn("Nothing changed", self.output)
        self.assertIn("daily tier", self.output)
        self.assertEqual([subjects for name, subjects in self.history().items() if name.startswith("fine-")], [["a"]])

    def test_a_repository_deleted_for_its_age_is_named_in_the_output(self):
        self.take(0, note="old")
        self.edit("b")
        self.take(2000, note="far on")
        self.assertRegex(self.output, r"Removed fine-\d: older than the previous week \(its newest snapshot: 2026-10-15\)")
        self.assertRegex(self.output, r"Removed daily-\d: older than the previous month")


class Commands(Case):
    """`make snapshot` and `make snapshots` on an installed project, with the HOME of the case."""

    def setUp(self):
        super().setUp()
        self.install("init", "--skip-editor")
        self.snapshots = self.home / ".snapshots"

    def restore_command(self, output, name):
        line = re.search(r"^\s+one file back:\s+(git --git-dir=.* checkout \w+ -- FILE)$", output, re.M)
        self.assertIsNotNone(line, output)
        return shlex.split(line[1].replace("FILE", shlex.quote(name)))

    def cycle(self):
        """Snapshot, damage a file, list the snapshots, and run the restore command they print."""
        git_before = digest(self.project / ".git") if (self.project / ".git").exists() else None
        self.run_command("make", "snapshot")
        (self.project / "main.tex").write_text("damaged")
        listing = self.run_command("make", "snapshots").stdout
        self.run_command(*self.restore_command(listing, "main.tex"))
        self.assertEqual((self.project / "main.tex").read_text(), SOURCE)
        self.assertEqual(git_before, digest(self.project / ".git") if git_before else None)  # neither the snapshot nor the restore touched the project's own Git
        return listing

    def test_a_snapshot_and_a_restore_on_a_project_without_git(self):
        listing = self.cycle()
        self.assertFalse((self.project / ".git").exists())
        self.assertIn("snapshot", listing)

    def test_a_snapshot_and_a_restore_on_a_project_with_its_own_git(self):
        self.own_git()
        self.cycle()

    def test_the_label_reaches_the_snapshot_as_text_and_never_as_shell(self):
        note = 'before "the rewrite"; touch pwned `touch pwned`'
        self.run_command("make", "snapshot", f"SNAPSHOT_NOTE={note}")
        self.assertFalse((self.project / "pwned").exists())
        (store,) = stores(self.snapshots)
        self.assertIn(note, [subject for subjects in history(store).values() for subject in subjects])
        self.assertIn(note, self.run_command("make", "snapshots").stdout)

    def test_a_label_that_starts_with_a_dash_is_a_label(self):
        self.run_command("make", "snapshot", "SNAPSHOT_NOTE=-wip")
        (store,) = stores(self.snapshots)
        self.assertIn("-wip", [subject for subjects in history(store).values() for subject in subjects])

    def test_a_second_snapshot_of_the_same_files_says_so(self):
        self.run_command("make", "snapshot")
        self.assertIn("Nothing changed", self.run_command("make", "snapshot").stdout)

    def test_a_large_file_is_named_in_the_output_and_left_out(self):
        with (self.project / "big.dat").open("wb") as stream:
            stream.truncate(26 * 1024 * 1024)
        result = self.run_command("make", "snapshot")
        self.assertIn("big.dat", result.stdout)
        (store,) = stores(self.snapshots)
        self.assertTrue(all("big.dat" not in names(store / name) for name in history(store)))

    def test_snapshots_before_any_says_how_to_make_one(self):
        self.assertIn("make snapshot", self.run_command("make", "snapshots").stdout)
        self.assertFalse(self.snapshots.exists())

    def test_both_work_when_the_configuration_is_broken(self):
        (self.project / core.CONFIG).write_text("{broken")
        self.run_command("make", "snapshot")
        self.assertIn("snapshot", self.run_command("make", "snapshots").stdout)

    def test_the_json_form_names_the_snapshot(self):
        result = json.loads(self.command("snapshot", "--json").stdout)
        self.assertEqual(result["exit_status"], 0)
        self.assertRegex(result["result"]["commit"], r"^[0-9a-f]{40}$")

    def test_without_git_the_command_says_what_is_missing(self):
        result = self.run_command(sys.executable, "-B", ".latex-ai/workbench.py", "snapshot", env={**self.env, "PATH": str(self.root / "nothing")}, expected=1)
        self.assertIn("Git", result.stderr)
        self.assertFalse(self.snapshots.exists())

    def test_a_projects_own_snapshot_target_is_not_replaced(self):
        self.own_targets("snapshot")
        self.assertIn("mine", self.run_command("make", "snapshot").stdout)
        self.run_command("make", "latex-ai-snapshot")
        self.assertTrue(self.snapshots.exists())

    def test_diff_shows_a_project_from_4_6_exactly_the_lines_it_lacks_and_runtime_leaves_the_makefile_alone(self):
        path = self.project / "Makefile"
        text = path.read_text()
        old = re.sub(r"\.PHONY: (?:latex-ai-)?snapshots?\n(?:latex-ai-)?snapshots?:[^\n]*\n(?:\t[^\n]*\n)?", "", text.replace("export SNAPSHOT_NOTE\n", ""))
        self.assertEqual(len(text.splitlines()) - len(old.splitlines()), 11)
        path.write_text(old)
        diff = self.install("diff", "--diff", expected=None).stdout
        for line in ("+export SNAPSHOT_NOTE", "+.PHONY: snapshot", "+.PHONY: snapshots", "+.PHONY: latex-ai-snapshot", "+.PHONY: latex-ai-snapshots"):
            self.assertIn(line, diff)
        self.assertEqual([line for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")], [])
        self.install("runtime")
        self.assertEqual(path.read_text(), old)

    def test_the_guide_and_help_name_both_commands(self):
        for text in (self.command("guide").stdout, self.command("help").stdout):
            self.assertRegex(text, r"make snapshot\b")
            self.assertRegex(text, r"make snapshots\b")


class BeforeInstall(Case):
    """The new release snapshots a project that has no workbench yet, which is what the first step of updating and migrating asks of it."""

    def test_the_distribution_snapshots_a_project_with_no_workbench_and_says_what_to_run_to_list_them(self):
        runtime = [sys.executable, "-B", str(PACKAGE / "runtime.py"), "--project", str(self.project)]
        made = self.run_command(*runtime[:3], "snapshot", *runtime[3:], "--note", "before migrating", cwd=self.root).stdout
        self.assertNotIn("make ", made)  # this project has no Makefile target to name
        self.assertIn("before migrating", self.run_command(*runtime[:3], "snapshots", *runtime[3:], cwd=self.root).stdout)
        self.assertEqual(sorted(path.name for path in self.project.iterdir()), ["main.tex"])


class Registered(unittest.TestCase):
    def test_both_actions_are_standalone_and_always_available(self):
        for name in ("snapshot", "snapshots"):
            with self.subTest(action=name):
                action = commands.BY_NAME[name]
                self.assertTrue(action.standalone)
                self.assertIsNone(action.module)
                self.assertIsNone(action.needs)
                self.assertFalse(action.document or action.batch or action.view)

    def test_the_generated_makefile_carries_them_even_with_no_module(self):
        text = bootstrap.desired_files({"schema_version": 3, "modules": {}, "integrations": {"editor": False}})["Makefile"]
        self.assertIn("export SNAPSHOT_NOTE\n", text)
        self.assertIn('latex-ai-snapshot:\n\t@$(PYTHON) .latex-ai/workbench.py snapshot --note="$$SNAPSHOT_NOTE"\n', text)
        self.assertIn("latex-ai-snapshots:\n\t@$(PYTHON) .latex-ai/workbench.py snapshots\n", text)
        self.assertIn("snapshot: latex-ai-snapshot\n", text)
        self.assertIn("snapshots: latex-ai-snapshots\n", text)

    def test_a_name_the_project_has_taken_gets_no_alias(self):
        text = bootstrap.module_make_targets({"schema_version": 3, "modules": {}}, frozenset({"snapshot"}))
        self.assertNotIn("\nsnapshot: latex-ai-snapshot", text)
        self.assertIn("\nlatex-ai-snapshot:", text)

    def test_every_installed_runtime_carries_the_module(self):
        self.assertIn("snapshot.py", core.RUNTIME_FILES)
        for modules in ({}, {"latex": {"default_document": "paper", "documents": {"paper": {"root": "main.tex"}}}}, {"bibliography": {}}):
            with self.subTest(modules=sorted(modules)):
                self.assertEqual(core.runtime_sources({"schema_version": 3, "modules": modules})["snapshot.py"], "snapshot.py")

    def test_the_upgrade_and_migration_guides_start_with_a_snapshot(self):
        for name in ("upgrading.md", "migrating.md"):
            with self.subTest(guide=name):
                first = re.search(r"^1\. (.*?)(?=^2\. )", (PACKAGE / "docs" / name).read_text(), re.S | re.M)[1]
                self.assertRegex(first, r"make snapshot|runtime\.py snapshot --project")
                self.assertNotIn("planned", first)


if __name__ == "__main__":
    unittest.main()
