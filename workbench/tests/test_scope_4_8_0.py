"""Workbench 4.8.0: the snapshots are three stores, each a repository of its own, with counted retention.

4.7.0 kept two tiers that rotated by week and month, so a clock that jumped forward could delete the history. The stores are `manual` (what `make snapshot` takes, all
kept, none ever deleted by the workbench), `weekly` (a timer asks every day, the first snapshot of each calendar week is taken, the newest 6 are kept) and `frequent` (a
timer asks every half hour, a snapshot is taken when files changed, the newest 60 are kept). A snapshot is a commit of its own, named by a number that only grows, so
dropping the oldest is deleting one reference and the files only it held. The clock decides when a snapshot is taken and never what is deleted. The tests of what 4.7.0
established and 4.8.0 kept (contents, exact bytes, isolation, refusals, the commands) are in test_scope_4_7_0.py.
"""
import json
import os
import plistlib
import re
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import core
from test_scope_4_7_0 import SOURCE, Case as SnapshotCase, at, git, history, newest, numbers, shadow, stores
from test_support import fixture_env


class Case(SnapshotCase):
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


class Stores(Case):
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


class Frequent(Case):
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


def numbers_and_names(repository):
    return sorted(ref.rsplit("/", 1)[1] for ref in git(repository, "for-each-ref", "--format=%(refname)", "refs/snapshots/").decode().split())


class Weekly(Case):
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


class TheClockDecidesNothingThatIsDeleted(Case):
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


class AfterTheReview(Case):
    """What an independent review of 4.8.0 reproduced."""

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


class Layout(Case):
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


class Commands(Case):
    def setUp(self):
        super().setUp()
        self.install("init", "--skip-editor")
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


class Launchd(Case):
    """The two launch agents the docs give are valid property lists, and the command each runs is one the runtime accepts."""

    def setUp(self):
        super().setUp()
        self.install("init", "--skip-editor")

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


class Registered(unittest.TestCase):
    def test_the_runtime_offers_exactly_the_stores(self):
        help_text = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), "--help"], capture_output=True, text=True, check=True).stdout
        self.assertIn("{" + ",".join(shadow().TIERS) + "}", help_text)


if __name__ == "__main__":
    unittest.main()
