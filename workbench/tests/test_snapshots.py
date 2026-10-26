"""Tests of snapshots: the three stores, retention, exact bytes, isolation, the timers.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 3 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_scope_4_7_0.py:
Workbench 4.7.0, step 3.6 of docs/maintainers/plan-after-4.4.0.md: `make snapshot` and `make snapshots`; what they keep, how it is kept, and what they refuse.

A snapshot is a commit of every file of the project in a Git repository of its own, kept outside the project. Release 4.8.0 replaced the two rotating tiers of 4.7.0
by three stores (`manual`, `weekly`, `frequent`) with counted retention, and its tests are in test_snapshots.py; what 4.7.0 established and 4.8.0 kept is here:
the contents of a snapshot, the bytes kept exactly, the isolation from the user's Git, the refusals (the code that deletes is held to a short list, tested one by one),
the hardening an independent review asked for, and the commands. Every test runs with a temporary HOME and its own snapshot folder, so none of them touches the
machine it runs on.

test_scope_4_8_0.py:
Workbench 4.8.0: the snapshots are three stores, each a repository of its own, with counted retention.

4.7.0 kept two tiers that rotated by week and month, so a clock that jumped forward could delete the history. The stores are `manual` (what `make snapshot` takes, all
kept, none ever deleted by the workbench), `weekly` (a timer asks every day, the first snapshot of each calendar week is taken, the newest 6 are kept) and `frequent` (a
timer asks every half hour, a snapshot is taken when files changed, the newest 60 are kept). A snapshot is a commit of its own, named by a number that only grows, so
dropping the oldest is deleting one reference and the files only it held. The clock decides when a snapshot is taken and never what is deleted. The tests of what 4.7.0
established and 4.8.0 kept (contents, exact bytes, isolation, refusals, the commands) are in test_snapshots.py.

test_scope_4_8_1.py:
4.8.1: independent-audit regressions, output safety, source integrity and bounded scans.

Every project is disposable; overwrite probes use only synthetic sentinel files.
"""

import contextlib
import errno
import hashlib
import importlib
import io
import json
import os
import plistlib
import re
import shlex
import shutil
import stat
import subprocess
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap
import commands
import core
import snapshot
import schema
from test_support import ProjectCase, fixture_env


IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"


def at(day=0, hour=12):
    """A moment of the test calendar: Wednesday 2026-10-14 plus days, UTC. Day 5 is the next Monday, and a whole number of weeks is a Wednesday again."""
    return datetime(2026, 10, 14, hour, tzinfo=timezone.utc) + timedelta(days=day)


def git(repository, *args):
    result = subprocess.run(["git", "--git-dir", str(repository), *args], capture_output=True, env=fixture_env(), check=True)
    return result.stdout


def history(store):
    """{store: the labels of its snapshots, newest first} for every snapshot repository of a project's folder."""
    return {repository.name: git(repository, "for-each-ref", "--sort=-refname", "--format=%(subject)", "refs/snapshots/").decode().splitlines()
            for repository in sorted(store.iterdir()) if (repository / "HEAD").is_file()}


def shadow():
    """The module under test, imported when used: a tree without it fails each test, not the whole file."""
    return importlib.import_module("snapshot")


def stores(base):
    """The folders of a snapshot folder that belong to projects: not the lock's, which starts with a dot."""
    return [path for path in sorted(base.iterdir()) if not path.name.startswith(".")]


def numbers(repository):
    """The numbers of a store's snapshots, newest first."""
    return [int(ref.rsplit("/", 1)[1]) for ref in git(repository, "for-each-ref", "--sort=-refname", "--format=%(refname)", "refs/snapshots/").decode().split()]


EXCLUDED = ("main.aux", "main.log", "main.synctex.gz", "outputs/main.pdf", "outputs/main.fls", ".latex-ai/artifacts/locks/build.lock",
            ".latex-ai/backups/20260101T000000Z/old.py", "__pycache__/x.pyc", "docs/__pycache__/y.pyc", "node_modules/p/index.js", ".venv/lib/x.py",
            "env/pyvenv.cfg", "env/lib/x.py", "conda/conda-meta/history", "conda/lib/x.py", "vendor/lib/.git/HEAD", "vendor/lib2/.git", "vendor/lib3/.GIT/config")


FILES = {"main.tex": SOURCE, "refs.bib": "@misc{k}\n", "notes/todo.txt": "z", "figure.pdf": "%PDF-1.5", "main.pdf": "%PDF-1.5 beside its source", ".gitignore": "secret.txt\n", "secret.txt": "kept anyway",
         "a b.tex": "", "é.tex": "", "[x]*.tex": "", "-n.tex": "", ".latex-ai/workbench.py": "# runtime", "crlf.txt": "a\r\nb\r\n", "vendor/lib/x.txt": "a nested repository's file",
         "scripts/train.log": "", "results/solver.out": "", "data/run.toc": "", "refs.bbl": "", "analysis/notes.aux": "",  # a compiler's suffixes, and no .tex of that name beside them
         **({} if os.name == "nt" else {"line\nbreak.tex": ""})}


def newest(repository):
    """The commit of the store's newest snapshot."""
    return git(repository, "for-each-ref", "--sort=-refname", "--count=1", "--format=%(objectname)", "refs/snapshots/").decode().strip()


def names(repository, revision=None):
    return set(git(repository, "ls-tree", "-r", "-z", "--name-only", revision or newest(repository)).decode().split("\0")) - {""}


def digest(folder):
    """Every byte of a folder, in one hash: what 'untouched' means for a project's own .git."""
    total = hashlib.sha256()
    for path in sorted(Path(folder).rglob("*")):
        total.update(os.fsencode(path.relative_to(folder)))
        if path.is_file() and not path.is_symlink():
            total.update(path.read_bytes())
    return total.hexdigest()


def numbers_and_names(repository):
    return sorted(ref.rsplit("/", 1)[1] for ref in git(repository, "for-each-ref", "--format=%(refname)", "refs/snapshots/").decode().split())


SOURCE_4_8_1 = '\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n'


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

    def install(self, *args, **choices):
        result = super().install(*args, **choices)
        if args and args[0] == 'init' and result.returncode == 0:
            self.edit_config(lambda config: config.update(snapshots=True))
        return result

    def take(self, day=0, hour=12, note="", tier="manual", **options):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = shadow().take(self.project, tier=tier, note=note, base=self.base, now=at(day, hour), **options)
        self.output = output.getvalue()
        return result

    def edit(self, text):
        (self.project / "main.tex").write_text(text)

    def store(self):
        (store,) = stores(self.base)
        return store

    def history(self):
        return history(self.store())

    def repository(self, tier="manual"):
        return self.store() / tier

    def own_git(self, *paths):
        for arguments in (["init", "-q"], ["add", *(paths or ["-A"])], ["commit", "-q", "-m", "first"]):
            subprocess.run(["git", *arguments], cwd=self.project, env={**fixture_env(), **IDENTITY}, check=True, capture_output=True)


class Case_4_8_0(Case):
    def setUp(self):
        super().setUp()
        if hasattr(time, "tzset"):  # the calendar week is the user's own: the tests keep it to UTC, whatever machine they run on
            patcher = patch.dict(os.environ, {"TZ": "UTC"})
            patcher.start()
            time.tzset()
            self.addCleanup(time.tzset)
            self.addCleanup(patcher.stop)

    def labels(self, tier):
        return self.history().get(tier, [])


class Basics(Case):
    """Origin: tests/test_scope_4_7_0.py, workbench 4.7.0."""

    def test_nothing_changed_makes_no_snapshot(self):
        first = self.take(note="first")
        again = self.take(0, 13, note="again")
        self.assertEqual((first["changed"], again["changed"]), (True, False))
        self.assertEqual(again["commit"], first["commit"])
        self.assertIn("Nothing changed", self.output)
        self.assertEqual(numbers(self.repository()), [1])

    def test_a_label_is_the_snapshots_subject_and_defaults_to_snapshot(self):
        self.take(note="before the rewrite of section 3")
        self.edit("b")
        self.take(0, 13)
        self.assertEqual(self.history()["manual"], ["snapshot", "before the rewrite of section 3"])

    def test_the_store_is_named_after_the_project_and_its_path(self):
        self.take()
        self.assertRegex(self.store().name, r"^project-[0-9a-f]{8}$")


class Contents(Case):
    """Origin: tests/test_scope_4_7_0.py, workbench 4.7.0."""

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

    def test_the_count_is_of_what_is_kept(self):
        self.assertEqual(self.take()["files"], len(names(self.repository())))

    def test_a_default_output_folder_is_left_out_too(self):
        (self.project / "build").mkdir()
        (self.project / "build/x.txt").write_text("x")
        (self.project / core.CONFIG).write_text(json.dumps({"default_document": "a", "defaults": {"output_dir": "build"}, "documents": {"a": {"root": "main.tex"}}}))
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
        self.assertEqual(git(self.repository(), "show", f"{newest(self.repository())}:crlf.txt"), b"a\r\nb\r\n")

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
        listed = git(self.repository(), "ls-tree", "-r", newest(self.repository())).decode()
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
                (self.project / core.CONFIG).write_text(json.dumps({"default_document": "a", "documents": {"a": {"root": root, "output_dir": output}}}))
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
    """Origin: tests/test_scope_4_7_0.py, workbench 4.7.0."""

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
            self.assertEqual(git(repository, "show", f"{newest(repository)}:{name}"), data, name)
        for name in original:
            (self.project / name).write_bytes(b"changed\n")
        theirs = {key: value for key, value in self.env.items() if key != "GIT_CONFIG_GLOBAL"}  # the user's own settings apply to the restore
        self.run_command("git", "--git-dir", str(repository), "--work-tree", str(self.project), "checkout", newest(repository), "--", ".", env=theirs)
        for name, data in original.items():
            self.assertEqual((self.project / name).read_bytes(), data, name)
        self.assertFalse((self.root / "hook-ran").exists())


class Isolation(Case):
    """Origin: tests/test_scope_4_7_0.py, workbench 4.7.0."""

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
        self.assertEqual(git(self.repository(), "log", "-1", "--format=%an <%ae>", newest(self.repository())).decode().strip(), "snapshot <snapshot@localhost.invalid>")
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
    """What the workbench deletes is snapshots, one reference at a time, inside a repository it made. Each way it could touch something else is refused.

    Origin: tests/test_scope_4_7_0.py, workbench 4.7.0.
    """

    def made(self):
        self.take(0, note="first")
        self.edit("b")
        return self.repository(), self.store()

    def test_a_repository_that_is_a_link_is_never_followed(self):
        repository, store = self.made()
        victim = self.root / "victim"
        repository.rename(victim)
        os.symlink(victim, repository)
        with self.assertRaises(core.WorkbenchError):
            self.take(0, 13, note="second")
        self.assertEqual(numbers(victim), [1])

    def test_a_folder_without_the_marker_is_not_a_repository_of_ours_and_nothing_is_written_into_it(self):
        repository, store = self.made()
        (repository / "SNAPSHOT-REPOSITORY").unlink()
        with self.assertRaises(core.WorkbenchError):
            self.take(0, 13, note="second")
        self.assertEqual(numbers(repository), [1])

    def test_a_store_without_the_marker_is_not_ours_and_nothing_in_it_is_touched(self):
        repository, store = self.made()
        (store / "PROJECT").unlink()
        with self.assertRaises(core.WorkbenchError):
            self.take(0, 13, note="second")
        self.assertEqual(numbers(repository), [1])

    def test_a_store_made_for_another_path_is_not_used(self):
        repository, store = self.made()
        (store / "PROJECT").write_text("/somewhere/else\n")
        with self.assertRaises(core.WorkbenchError):
            self.take(0, 13, note="second")
        self.assertEqual(numbers(repository), [1])

    def test_a_snapshot_folder_inside_the_project_is_refused(self):
        with self.assertRaises(core.WorkbenchError):
            shadow().take(self.project, base=self.project / "snapshots", now=at())
        self.assertFalse((self.project / "snapshots").exists())

    def test_nothing_else_in_the_store_or_beside_it_is_touched(self):
        self.take(0, note="a", tier="frequent")
        store = self.store()
        (store / "keep-me").mkdir()
        (store / "keep-me/x").write_text("x")
        other = self.base / "other-0123abcd"
        other.mkdir()
        (other / "frequent").mkdir()
        (other / "frequent/x").write_text("another project's")
        with patch.dict(shadow().KEEP, {"frequent": 2}):
            for number in range(6):
                self.edit(str(number))
                self.take(0, 13, note=str(number), tier="frequent")
        self.assertEqual(numbers(store / "frequent"), [7, 6])
        self.assertEqual((store / "keep-me/x").read_text(), "x")
        self.assertEqual((other / "frequent/x").read_text(), "another project's")


class Hardening(Case):
    """What an independent review reproduced: simultaneous runs, a run that stops half way, a label of blanks, private files, a name too long to be a folder's.

    Origin: tests/test_scope_4_7_0.py, workbench 4.7.0.
    """

    def test_snapshots_taken_at_the_same_time_each_hold_every_file(self):
        self.configure(snapshots=True)
        for number in range(600):
            (self.project / f"f{number}.txt").write_text(str(number))
        command = [sys.executable, "-B", str(PACKAGE / "runtime.py"), "snapshot", "--project", str(self.project)]
        runs = [subprocess.Popen(command, env={**self.env, "LATEX_AI_SNAPSHOT_DIR": str(self.base)}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for _ in range(6)]
        for run in runs:
            output = run.communicate()[0]
            self.assertEqual(run.returncode, 0, output)
        for repository in (path for path in self.store().iterdir() if (path / "HEAD").is_file()):
            for commit in git(repository, "for-each-ref", "--format=%(objectname)", "refs/snapshots/").decode().split():
                self.assertEqual(len(names(repository, commit)), 602, "a snapshot that is missing files")

    def test_a_second_snapshot_that_cannot_get_the_lock_says_so_and_writes_nothing(self):
        self.take()
        with patch.object(shadow(), "PATIENCE", 0.2), core.operation_lock(self.base, "snapshot-" + shadow().project_key(self.project)), \
                self.assertRaisesRegex(core.WorkbenchError, "Another snapshot of this project"):
            self.edit("b")
            self.take(0, 13)
        self.assertEqual(numbers(self.repository()), [1])

    def test_a_run_that_stops_half_way_through_making_a_repository_leaves_nothing_that_blocks_the_next(self):
        def stopping(path):
            (path / "half").write_text("x")
            raise OSError(errno.ENOSPC, "No space left on device")
        with patch.object(shadow(), "initialize", stopping), self.assertRaises(OSError):
            self.take()
        self.assertTrue(self.take()["changed"])
        self.assertEqual(numbers(self.repository()), [1])

    def test_a_label_of_blanks_is_no_label(self):
        self.take(note="   ")
        shadow().listing(self.project, base=self.base)
        self.assertEqual(self.history()["manual"], ["snapshot"])

    def test_the_folders_are_private_to_the_user(self):
        if os.name == "nt":
            self.skipTest("POSIX permissions")
        self.take()
        for path in (self.base, self.store(), self.repository()):
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


class Commands(Case):
    """`make snapshot` and `make snapshots` on an installed project, with the HOME of the case.

    Origin: tests/test_scope_4_7_0.py, workbench 4.7.0.
    """

    def setUp(self):
        super().setUp()
        self.install('init', editor=False)
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

    def test_both_work_with_opt_in_when_document_configuration_is_broken(self):
        (self.project / core.CONFIG).write_text(json.dumps({'snapshots': True, 'documents': {}}))
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


    def test_the_guide_and_help_name_both_commands(self):
        for text in (self.command("guide").stdout, self.command("help").stdout):
            self.assertRegex(text, r"make snapshot\b")
            self.assertRegex(text, r"make snapshots\b")


class BeforeInstall(Case):
    """The new release snapshots a project that has no workbench yet, which is what the first step of updating and migrating asks of it.

    Origin: tests/test_scope_4_7_0.py, workbench 4.7.0.
    """

    def test_the_distribution_snapshots_a_project_with_no_workbench_and_says_what_to_run_to_list_them(self):
        self.configure(snapshots=True)
        runtime = [sys.executable, "-B", str(PACKAGE / "runtime.py"), "--project", str(self.project)]
        made = self.run_command(*runtime[:3], "snapshot", *runtime[3:], "--note", "before migrating", cwd=self.root).stdout
        self.assertNotIn("make ", made)  # this project has no Makefile target to name
        self.assertIn("before migrating", self.run_command(*runtime[:3], "snapshots", *runtime[3:], cwd=self.root).stdout)
        self.assertEqual(sorted(path.name for path in self.project.iterdir()), [".latex-ai.json", "main.tex"])


class OptionalSnapshots(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE)

    def configure_choice(self, **settings):
        self.configure(**settings)
        self.install('init')

    def test_omitted_or_false_choice_blocks_every_snapshot_tier_without_creating_stores(self):
        self.configure_choice()
        store = Path(self.env['HOME']) / '.snapshots'
        for settings in ({}, {'snapshots': False}):
            self.edit_config(lambda config: (config.pop('snapshots', None), config.update(settings)))
            for tier in ('manual', 'frequent', 'weekly'):
                with self.subTest(settings=settings, tier=tier):
                    result = self.command('snapshot', '--tier', tier, expected=1)
                    self.assertIn('Snapshots are disabled', result.stderr)
                    self.assertFalse(store.exists())
            self.command('snapshots', expected=1)
            self.assertFalse(store.exists())
            self.assertNotIn('make snapshot', self.command('guide').stdout)
            self.assertNotIn('make snapshot', self.command('help').stdout)

    def test_explicit_opt_in_enables_commands_and_disabling_keeps_existing_history(self):
        self.configure_choice(snapshots=True)
        self.command('snapshot')
        self.assertIn('make snapshot', self.command('guide').stdout)
        self.assertIn('make snapshot', self.command('help').stdout)
        store = Path(self.env['HOME']) / '.snapshots'
        before = {str(path.relative_to(store)): path.read_bytes() for path in store.rglob('*') if path.is_file()}
        self.edit_config(lambda config: config.update(snapshots=False))
        self.command('snapshot', expected=1)
        self.command('snapshots', expected=1)
        after = {str(path.relative_to(store)): path.read_bytes() for path in store.rglob('*') if path.is_file()}
        self.assertEqual(before, after)

    def test_opted_in_recovery_does_not_require_valid_document_paths(self):
        self.configure_choice(snapshots=True)
        (self.project / 'main.tex').unlink()
        self.command('snapshot')
        self.command('snapshots')

    def test_missing_or_malformed_configuration_cannot_opt_in(self):
        self.configure_choice()
        config = self.project / core.CONFIG
        for contents in (None, '{broken', '[]', '{"snapshots": "true"}'):
            if contents is None:
                config.unlink(missing_ok=True)
            else:
                config.write_text(contents)
            self.command('snapshot', expected=1)
            self.assertFalse((Path(self.env['HOME']) / '.snapshots').exists())

    def test_snapshot_choice_must_be_boolean_and_git_is_required_only_when_enabled(self):
        for value in ('true', 1, None, {}, []):
            with self.subTest(value=value), self.assertRaisesRegex(core.WorkbenchError, 'snapshots must be true or false'):
                schema.validate_config(self.project, self.configure(snapshots=value))
        for value in (False, True):
            config = schema.validate_config(self.project, self.configure(snapshots=value))
            self.assertEqual('git' in schema.required_tools(config), value)

    def test_setup_reports_the_selected_choice_without_creating_stores(self):
        for value in (False, True):
            self.configure(snapshots=value)
            report = json.loads(self.install('init', '--dry-run', '--json').stdout)
            self.assertIs(report['snapshots'], value)
            self.assertFalse(report['applied'])
            self.assertFalse((Path(self.env['HOME']) / '.snapshots').exists())

    def test_snapshot_choice_does_not_invalidate_document_receipts(self):
        self.builder()
        self.configure_choice(snapshots=False)
        self.command('build')
        self.assertEqual(self.state(), 'current')
        self.edit_config(lambda config: config.update(snapshots=True))
        self.assertEqual(self.state(), 'current')


class Registered(unittest.TestCase):
    """Origin: tests/test_scope_4_7_0.py, workbench 4.7.0."""

    def test_both_actions_are_standalone_and_always_available(self):
        for name in ("snapshot", "snapshots"):
            with self.subTest(action=name):
                action = commands.BY_NAME[name]
                self.assertTrue(action.standalone)
                self.assertFalse(action.document or action.batch or action.view)

    def test_the_generated_makefile_carries_them_even_with_no_module(self):
        text = bootstrap.desired_files({'schema_version': 4, 'integrations': {'editor': False}})["Makefile"]
        self.assertIn("export ISSUE_NOTE ISSUE_COMMAND SNAPSHOT_NOTE DOC\n", text)
        self.assertIn('snapshot:\n\t@$(PYTHON) .latex-ai/workbench.py snapshot --note="$$SNAPSHOT_NOTE"\n', text)
        self.assertIn("snapshots:\n\t@$(PYTHON) .latex-ai/workbench.py snapshots\n", text)


    def test_every_installed_runtime_carries_the_module(self):
        self.assertIn("snapshot.py", core.RUNTIME_FILES)
        for modules in ({}, {"latex": {"default_document": "paper", "documents": {"paper": {"root": "main.tex"}}}}, {"bibliography": {}}):
            with self.subTest(modules=sorted(modules)):
                self.assertEqual(core.runtime_sources({"schema_version": 3, "modules": modules})["snapshot.py"], "snapshot.py")

    def test_the_upgrade_guide_uses_git_and_keeps_snapshots_optional(self):
        for name in ("upgrading.md",):
            with self.subTest(guide=name):
                first = re.search(r"^1\. (.*?)(?=^2\. )", (PACKAGE / "docs" / name).read_text(), re.S | re.M)[1]
                self.assertRegex(first, r"make snapshot|runtime\.py snapshot --project")
                self.assertIn("optional", first.lower())
                self.assertIn("Git", first)
                self.assertNotIn("planned", first)


class Stores(Case_4_8_0):
    """Origin: tests/test_scope_4_8_0.py, workbench 4.8.0."""

    def test_the_stores_and_what_each_keeps(self):
        self.assertEqual(shadow().TIERS, ("manual", "weekly", "frequent"))
        self.assertEqual(shadow().KEEP, {"weekly": 6, "frequent": 60})  # manual is not here: it keeps all

    def test_manual_is_the_default_and_each_store_has_a_repository_of_its_own_numbered_from_one(self):
        self.take(note="mine")
        self.edit("b")
        self.take(0, 13, note="timer", tier="frequent")
        self.edit("c")
        self.take(0, 14, note="week", tier="weekly")
        self.assertEqual(sorted(self.history()), ["frequent", "manual", "weekly"])
        for tier in ("manual", "frequent", "weekly"):
            self.assertEqual(numbers(self.store() / tier), [1], tier)

    def test_a_store_that_is_not_one_is_refused(self):
        with self.assertRaises(core.WorkbenchError):
            self.take(tier="hourly")
        self.assertFalse(self.base.exists())

    def test_the_stores_do_not_touch_each_other(self):
        self.take(note="keep me")
        with patch.dict(shadow().KEEP, {"frequent": 2}):
            for number in range(6):
                self.edit(str(number))
                self.take(0, 13, note=str(number), tier="frequent")
        self.assertEqual(self.labels("manual"), ["keep me"])
        self.assertEqual(self.labels("frequent"), ["5", "4"])


class Frequent(Case_4_8_0):
    """Origin: tests/test_scope_4_8_0.py, workbench 4.8.0."""

    def test_it_keeps_the_newest_few_and_drops_the_oldest_one_at_a_time(self):
        with patch.dict(shadow().KEEP, {"frequent": 3}):
            for number in range(1, 7):
                self.edit(str(number))
                self.take(0, 8 + number, note=str(number), tier="frequent")
                if number == 4:
                    self.assertIn("Dropped snapshot #1", self.output)
                    self.assertEqual(self.labels("frequent"), ["4", "3", "2"])
        self.assertEqual(self.labels("frequent"), ["6", "5", "4"])
        self.assertEqual(numbers(self.store() / "frequent"), [6, 5, 4])

    def test_it_takes_a_snapshot_whenever_files_changed_and_never_otherwise(self):
        self.take(0, 12, tier="frequent")
        self.take(0, 12, tier="frequent")  # nothing changed: the same instant, the same files
        self.assertIn("Nothing changed", self.output)
        self.edit("b")
        self.take(0, 12, tier="frequent")  # changed, in the same minute: taken
        self.assertEqual(numbers(self.store() / "frequent"), [2, 1])

    def test_dropping_removes_the_files_only_the_dropped_snapshots_held_and_keeps_the_rest_whole(self):
        with patch.dict(shadow().KEEP, {"frequent": 2}):
            for number in range(1, 4):
                self.edit(f"content {number}\n")
                self.take(0, 9 + number, note=str(number), tier="frequent")
        repository = self.store() / "frequent"

        def held(text):
            blob = subprocess.run(["git", "hash-object", "--stdin"], input=text.encode(), capture_output=True, env=fixture_env(), check=True).stdout.decode().strip()
            return subprocess.run(["git", "--git-dir", str(repository), "cat-file", "-e", blob], env=fixture_env(), capture_output=True).returncode == 0
        self.assertFalse(held("content 1\n"), "the dropped snapshot's file is still there")
        self.assertTrue(held("content 2\n") and held("content 3\n"))
        subprocess.run(["git", "--git-dir", str(repository), "fsck", "--no-dangling"], env=fixture_env(), check=True, capture_output=True)
        oldest_kept = git(repository, "for-each-ref", "--sort=refname", "--count=1", "--format=%(objectname)", "refs/snapshots/").decode().strip()
        self.assertEqual(git(repository, "show", f"{oldest_kept}:main.tex"), b"content 2\n")

    def test_what_the_user_keeps_by_a_reference_of_their_own_survives_the_dropping(self):
        with patch.dict(shadow().KEEP, {"frequent": 1}):
            self.edit("content 1\n")
            self.take(0, 10, tier="frequent")
            repository = self.store() / "frequent"
            git(repository, "update-ref", "refs/keep/mine", newest(repository))
            self.edit("content 2\n")
            self.take(0, 11, tier="frequent")
        self.assertEqual(numbers(repository), [2])
        self.assertEqual(git(repository, "show", "refs/keep/mine:main.tex"), b"content 1\n")

    def test_a_reference_that_is_not_a_number_is_not_ours_and_is_never_dropped(self):
        self.take(0, 10, tier="frequent")
        repository = self.store() / "frequent"
        git(repository, "update-ref", "refs/snapshots/keep-me", newest(repository))
        with patch.dict(shadow().KEEP, {"frequent": 1}):
            for number in range(3):
                self.edit(str(number))
                self.take(0, 11 + number, tier="frequent")
        self.assertEqual(numbers_and_names(repository), ["00000004", "keep-me"])
        shadow().listing(self.project, base=self.base)


class Weekly(Case_4_8_0):
    """Origin: tests/test_scope_4_8_0.py, workbench 4.8.0."""

    def test_it_takes_the_first_snapshot_of_each_calendar_week_and_no_other(self):
        self.take(0, tier="weekly", note="wednesday")
        self.edit("b")
        for day in (1, 4):  # the Thursday and the Sunday of the same week
            result = self.take(day, tier="weekly", note="again")
            self.assertEqual(result["status"], "week")
            self.assertIn("This week already has a snapshot", self.output)
        self.assertEqual(self.labels("weekly"), ["wednesday"])
        self.assertEqual(self.take(5, tier="weekly", note="monday")["status"], "taken")  # the next Monday is a new week
        self.assertEqual(self.labels("weekly"), ["monday", "wednesday"])

    def test_a_week_in_which_nothing_changed_does_not_use_up_the_next_one(self):
        self.take(0, tier="weekly", note="first")
        self.assertEqual(self.take(7, tier="weekly")["status"], "same")  # a new week, but the files are the same
        self.edit("b")
        self.assertEqual(self.take(8, tier="weekly", note="second")["status"], "taken")  # the first run of that week with something to keep
        self.assertEqual(self.labels("weekly"), ["second", "first"])

    def test_it_keeps_the_newest_six(self):
        for week in range(8):
            self.edit(str(week))
            self.take(7 * week, tier="weekly", note=f"week {week}")
        self.assertEqual(self.labels("weekly"), [f"week {week}" for week in range(7, 1, -1)])
        self.assertEqual(numbers(self.store() / "weekly"), [8, 7, 6, 5, 4, 3])


class TheClockDecidesNothingThatIsDeleted(Case_4_8_0):
    """Origin: tests/test_scope_4_8_0.py, workbench 4.8.0."""

    def test_a_clock_that_jumps_far_forward_and_back_deletes_nothing(self):
        for day, tier in ((0, "weekly"), (7, "weekly"), (14, "weekly")):
            self.edit(str(day))
            self.take(day, tier=tier, note=f"day {day}")
        self.edit("far")
        self.take(2000, tier="weekly", note="2032")  # the clock says a different week, so one is taken; no repository is old enough to matter
        self.edit("back")
        self.take(21, tier="weekly", note="back")
        self.assertEqual(self.labels("weekly"), ["back", "2032", "day 14", "day 7", "day 0"])

    def test_the_numbers_only_grow_whatever_the_dates_say(self):
        with patch.dict(shadow().KEEP, {"frequent": 2}):
            for day in (5, 3, 4, 0):  # dates that go backwards
                self.edit(str(day))
                self.take(day, tier="frequent", note=f"day {day}")
        self.assertEqual(numbers(self.store() / "frequent"), [4, 3])
        self.assertEqual(self.labels("frequent"), ["day 0", "day 4"])  # the newest by number, not by date


class AfterTheReview(Case_4_8_0):
    """What an independent review of 4.8.0 reproduced.

    Origin: tests/test_scope_4_8_0.py, workbench 4.8.0.
    """

    def test_a_lock_left_by_a_killed_run_does_not_block_the_store_for_good(self):
        self.take(tier="frequent")
        (self.store() / "frequent" / "index.lock").write_text("left by Git when the run was killed")  # a timer is stopped at logout; launchd sends SIGTERM
        self.edit("b")
        self.assertTrue(self.take(0, 13, tier="frequent")["changed"])
        self.assertFalse((self.store() / "frequent" / "index.lock").exists())

    def test_a_label_with_characters_that_python_calls_line_ends_is_kept_and_does_not_break_the_list(self):
        labels = ["x\x0cy", "a\u2028b", "c\x85d", "e\rf", "g\x1ch"]
        for number, label in enumerate(labels):
            self.edit(str(number))
            self.take(0, 8 + number, note=label)
        listed = shadow().listing(self.project, base=self.base)["snapshots"]
        self.assertEqual([row["label"] for row in sorted(listed, key=lambda row: row["number"])], labels)
        self.edit("more")
        self.take(0, 14, note="after")  # and the next snapshot still works

    def test_a_reference_that_only_looks_like_a_number_is_not_ours(self):
        self.take(tier="frequent")
        repository = self.store() / "frequent"
        for name in ("1", "\u00b2", "123456789", "0000000x"):
            git(repository, "update-ref", f"refs/snapshots/{name}", newest(repository))
        self.edit("b")
        result = self.take(0, 13, tier="frequent")
        self.assertEqual((result["status"], result["number"]), ("taken", 2))
        shadow().listing(self.project, base=self.base)

    def test_a_project_folder_that_ends_in_a_blank_is_not_refused_the_second_time(self):
        odd = self.root / "proj "
        odd.mkdir()
        (odd / "main.tex").write_text(SOURCE)
        with patch.object(sys, "stdout"):
            shadow().take(odd, base=self.base, now=at())
            (odd / "main.tex").write_text("changed")
            self.assertTrue(shadow().take(odd, base=self.base, now=at(0, 13))["changed"])

    def test_two_projects_do_not_wait_for_each_other_and_one_project_waits_for_itself(self):
        other = self.root / "other"
        other.mkdir()
        (other / "main.tex").write_text(SOURCE)
        with patch.object(shadow(), "PATIENCE", 0.2), core.operation_lock(self.base, "snapshot-" + shadow().project_key(self.project)):
            with patch.object(sys, "stdout"):
                self.assertTrue(shadow().take(other, base=self.base, now=at())["changed"])  # another project's snapshot is not held up by this one's
            with self.assertRaisesRegex(core.WorkbenchError, "Another snapshot of this project"):
                self.take()

    def test_a_lock_can_be_waited_for_as_many_seconds_as_asked(self):
        with core.operation_lock(self.base, "x"):
            started = time.monotonic()
            with self.assertRaises(core.WorkbenchError):
                with core.operation_lock(self.base, "x", wait=0.3):
                    pass
            self.assertTrue(0.3 <= time.monotonic() - started < 3, "it waited for the default few seconds, or not at all")

    def test_a_snapshot_waits_for_the_one_before_it_and_then_takes_its_own(self):
        self.assertEqual(shadow().PATIENCE, 60)  # the timers of one project start together at login
        held, release = threading.Event(), threading.Event()

        def hold():
            with core.operation_lock(self.base, "snapshot-" + shadow().project_key(self.project)):
                held.set()
                release.wait(10)
        thread = threading.Thread(target=hold)
        thread.start()
        held.wait(5)
        threading.Timer(0.5, release.set).start()
        try:
            self.assertTrue(self.take()["changed"])
        finally:
            release.set()
            thread.join()


class Layout(Case_4_8_0):
    """Origin: tests/test_scope_4_8_0.py, workbench 4.8.0."""

    def test_folders_made_by_4_7_0_are_left_alone(self):
        self.take()
        store = self.store()
        for name in ("fine-0", "daily-1"):
            (store / name).mkdir()
            (store / name / "x").write_text("an old repository")
        self.edit("b")
        self.take(0, 13)
        shadow().listing(self.project, base=self.base)
        for name in ("fine-0", "daily-1"):
            self.assertEqual((store / name / "x").read_text(), "an old repository")


class Commands_4_8_0(Case_4_8_0):
    """Origin: tests/test_scope_4_8_0.py, workbench 4.8.0."""

    def setUp(self):
        super().setUp()
        self.install('init', editor=False)
        self.snapshots = self.home / ".snapshots"

    def test_the_tier_option_chooses_the_store_and_make_snapshot_is_the_manual_one(self):
        self.command("snapshot", "--tier", "frequent")
        (store,) = stores(self.snapshots)
        self.assertEqual(sorted(history(store)), ["frequent"])
        self.run_command("make", "snapshot", "SNAPSHOT_NOTE=mine")
        self.assertEqual(sorted(history(store)), ["frequent", "manual"])
        self.assertEqual(history(store)["manual"], ["mine"])

    def test_an_unknown_store_is_refused_by_name(self):
        result = self.command("snapshot", "--tier", "hourly", expected=2)
        self.assertIn("frequent", result.stderr)
        self.assertFalse(self.snapshots.exists())

    def test_the_weekly_store_takes_one_the_first_time(self):
        self.command("snapshot", "--tier", "weekly")
        (store,) = stores(self.snapshots)
        self.assertEqual(numbers(store / "weekly"), [1])

    def test_the_list_names_each_store_with_what_it_keeps_and_the_numbers_newest_first(self):
        self.run_command("make", "snapshot", "SNAPSHOT_NOTE=first")
        (self.project / "main.tex").write_text("b")
        self.run_command("make", "snapshot", "SNAPSHOT_NOTE=second")
        self.command("snapshot", "--tier", "frequent")
        listing = self.run_command("make", "snapshots").stdout
        self.assertRegex(listing, r"manual store \(yours: all kept")
        self.assertRegex(listing, r"frequent store \(for a timer, when files changed: the newest 60 kept\)")
        self.assertRegex(listing, r"#2 +[0-9a-f]{7}  \S+ \S+  second\n  #1 +[0-9a-f]{7}  \S+ \S+  first")
        self.assertNotRegex(listing, r"weekly store")  # no snapshot there yet

    def test_the_restore_command_names_the_repository_of_the_store_that_holds_the_newest(self):
        self.command("snapshot", "--tier", "frequent")
        (self.project / "main.tex").write_text("damaged")
        listing = self.run_command("make", "snapshots").stdout
        line = re.search(r"^\s+one file back:\s+(git --git-dir=\S+/frequent --work-tree=\S+ checkout \w+ -- FILE)$", listing, re.M)
        self.assertIsNotNone(line, listing)
        self.run_command(*line[1].replace("FILE", "main.tex").split())
        self.assertNotEqual((self.project / "main.tex").read_text(), "damaged")

    def test_the_json_form_names_the_store_and_the_number(self):
        result = json.loads(self.command("snapshot", "--tier", "weekly", "--json").stdout)["result"]
        self.assertEqual((result["tier"], result["number"], result["status"]), ("weekly", 1, "taken"))


class Launchd(Case_4_8_0):
    """The two launch agents the docs give are valid property lists, and the command each runs is one the runtime accepts.

    Origin: tests/test_scope_4_8_0.py, workbench 4.8.0.
    """

    def setUp(self):
        super().setUp()
        self.install('init', editor=False)

    def agents(self):
        text = (PACKAGE / "docs/snapshots.md").read_text()
        return {plist["Label"].split(".")[-2]: plist for plist in (plistlib.loads(block.encode()) for block in re.findall(r"```xml\n(.*?)```", text, re.S))}

    def test_the_docs_give_one_agent_for_each_timer(self):
        agents = self.agents()
        self.assertEqual(sorted(agents), ["frequent", "weekly"])
        self.assertEqual(agents["frequent"]["StartInterval"], 1800)
        self.assertTrue(agents["frequent"]["RunAtLoad"])
        self.assertTrue(agents["weekly"]["RunAtLoad"])
        self.assertNotIn("Weekday", agents["weekly"]["StartCalendarInterval"])  # every day: the program decides whether the week has its snapshot

    def test_the_command_each_agent_runs_is_accepted_and_goes_to_its_store(self):
        for tier, plist in self.agents().items():
            with self.subTest(tier=tier):
                argv = [word.replace("/Users/YOU/PATH/TO/PROJECT", str(self.project)) for word in plist["ProgramArguments"]]
                self.assertEqual(argv[1:], [f"{self.project}/.latex-ai/workbench.py", "snapshot", "--tier", tier, "--project", str(self.project)])
                self.assertNotIn("WorkingDirectory", plist)  # a folder launchd cannot enter fails before the program starts, and leaves no log
                self.run_command(sys.executable, "-B", *argv[1:], cwd=self.root, env={**self.env, "LATEX_AI_SNAPSHOT_DIR": str(self.home / "s")})
        (store,) = stores(self.home / "s")
        self.assertEqual(sorted(history(store)), ["frequent", "weekly"])


class Registered_4_8_0(unittest.TestCase):
    """Origin: tests/test_scope_4_8_0.py, workbench 4.8.0."""

    def test_the_runtime_offers_exactly_the_stores(self):
        help_text = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), "--help"], capture_output=True, text=True, check=True).stdout
        self.assertIn("{" + ",".join(shadow().TIERS) + "}", help_text)


class AuditRepairs(ProjectCase):
    """Origin: tests/test_scope_4_8_1.py, workbench 4.8.1."""

    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE_4_8_1)

    def test_o3_snapshot_inventories_files_only_after_taking_its_lock(self):
        @contextlib.contextmanager
        def waited_lock(*args, **kwargs):
            (self.project / 'new.txt').write_text('Created while this run waited')
            yield
        with patch.object(snapshot, 'operation_lock', waited_lock), contextlib.redirect_stdout(io.StringIO()):
            result = snapshot.take(self.project, base=self.root / 'snapshots')
        repository = Path(result['store']) / 'manual'
        self.assertIn('new.txt', snapshot.git(repository, None, 'ls-tree', '-r', '--name-only', result['commit']).splitlines())


if __name__ == "__main__":
    unittest.main()
