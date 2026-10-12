"""The one merge the owner delegates to an agent: a record pull request, through .github/scripts/merge_record_pr.py.

The agent's rule files deny a raw `gh pr merge`; the script is the way in, and it refuses everything that is not a pull request
of records (the plan and the verification records) with green checks. These tests are the limit, so they pin every refusal and
that a refusal never reaches `gh pr merge`.
"""
import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "merge_record_pr.py"
RECORDS = ["workbench/docs/maintainers/plan-after-3.0.2.md", "workbench/docs/maintainers/verification-3.5.0.md"]
GREEN = {"__typename": "CheckRun", "name": "validate", "status": "COMPLETED", "conclusion": "SUCCESS"}


@unittest.skipUnless(SCRIPT.is_file(), "a standalone distribution carries no repository scripts")
class RecordMerge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("merge_record_pr", SCRIPT)
        cls.script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.script)

    def pr(self, **changes):
        base = {"number": 7, "title": "Record something", "state": "OPEN", "isDraft": False, "baseRefName": "main",
                "headRefName": "docs/record", "headRefOid": "a" * 40, "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
                "files": [{"path": path} for path in RECORDS], "statusCheckRollup": [GREEN]}
        return {**base, **changes}

    def test_a_clean_green_pull_request_of_records_may_be_merged(self):
        self.assertEqual(self.script.refusals(self.pr()), [])

    def test_only_the_plan_and_verification_records_are_records(self):
        record = self.script.RECORD.fullmatch
        for path in ("workbench/docs/maintainers/plan-after-3.0.2.md", "workbench/docs/maintainers/verification.md",
                     "workbench/docs/maintainers/verification-3.5.0.md", "workbench/docs/maintainers/verification-2.7.1.md"):
            with self.subTest(record=path):
                self.assertTrue(record(path))
        for path in ("workbench/docs/maintainers/README.md",            # holds the maintainers' rules
                     "workbench/docs/maintainers/releases.md",          # goes with a release
                     "workbench/docs/maintainers/plan-after-3.0.2.md.bak", "workbench/docs/maintainers/verification-3.5.0.md/x",
                     "workbench/docs/maintainers/sub/verification-3.5.0.md", "workbench/docs/maintainers/../../core.py",
                     "AGENTS.md", ".claude/settings.json", ".codex/rules/git-safety.rules", ".github/scripts/merge_record_pr.py",
                     ".github/workflows/latex.yml", "workbench/core.py", "workbench/tests/test_record_merge.py"):
            with self.subTest(not_a_record=path):
                self.assertFalse(record(path))

    def test_every_other_condition_refuses(self):
        for label, changes in (
                ("not open", {"state": "MERGED"}), ("a draft", {"isDraft": True}), ("another base", {"baseRefName": "release"}),
                ("conflicting", {"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"}),
                ("behind or blocked", {"mergeStateStatus": "BLOCKED"}),
                ("unstable", {"mergeStateStatus": "UNSTABLE"}),
                ("no checks", {"statusCheckRollup": []}), ("checks missing", {"statusCheckRollup": None}),
                ("a failing check", {"statusCheckRollup": [GREEN, {**GREEN, "name": "test", "conclusion": "FAILURE"}]}),
                ("a pending check", {"statusCheckRollup": [GREEN, {**GREEN, "name": "test", "status": "IN_PROGRESS", "conclusion": ""}]}),
                ("a failing status", {"statusCheckRollup": [{"__typename": "StatusContext", "context": "ci", "state": "FAILURE"}]}),
                ("no file", {"files": []}),
                ("a file that is not a record", {"files": [{"path": RECORDS[0]}, {"path": "AGENTS.md"}]}),
                ("too many files", {"files": [{"path": RECORDS[0]}] * 100})):
            with self.subTest(refusal=label):
                self.assertTrue(self.script.refusals(self.pr(**changes)), label)

    def test_skipped_and_neutral_checks_count_as_passed(self):
        for conclusion in ("SKIPPED", "NEUTRAL"):
            self.assertEqual(self.script.refusals(self.pr(statusCheckRollup=[GREEN, {**GREEN, "conclusion": conclusion}])), [])

    def run_script(self, pr, *flags):
        calls = []

        def run(*arguments):
            calls.append(arguments)
            if arguments[:2] == ("pr", "view"):
                return json.dumps(pr)
            if arguments[:2] == ("repo", "view"):
                return json.dumps({"nameWithOwner": "owner/repo"})
            return ""
        out = io.StringIO()
        with redirect_stdout(out):
            status = self.script.main(["7", *flags], run=run)
        return status, calls, out.getvalue()

    def test_a_refused_pull_request_never_reaches_merge(self):
        status, calls, _ = self.run_script(self.pr(files=[{"path": "workbench/core.py"}]))
        self.assertEqual(status, 1)
        self.assertFalse([call for call in calls if call[:2] == ("pr", "merge")])

    def test_a_dry_run_merges_nothing(self):
        status, calls, shown = self.run_script(self.pr(), "--dry-run")
        self.assertEqual(status, 0)
        self.assertIn("Dry run", shown)
        self.assertEqual([call[:2] for call in calls], [("pr", "view")])

    def test_a_record_pull_request_is_squash_merged_against_the_inspected_commit_and_its_branch_deleted(self):
        status, calls, _ = self.run_script(self.pr())
        self.assertEqual(status, 0)
        self.assertIn(("pr", "merge", "7", "--squash", "--match-head-commit", "a" * 40), calls)
        self.assertIn(("api", "-X", "DELETE", "repos/owner/repo/git/refs/heads/docs/record"), calls)
        self.assertNotIn("--delete-branch", [word for call in calls for word in call], "gh would switch the owner's local branch")

    def test_the_default_branch_is_never_deleted(self):
        status, calls, _ = self.run_script(self.pr(headRefName="main"))
        self.assertEqual(status, 0)
        self.assertFalse([call for call in calls if call[:2] == ("api", "-X")])

    def test_the_script_asks_for_exactly_one_number(self):
        for arguments in ([], ["x"], ["1", "2"]):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.script.main(arguments, run=lambda *a: ""), 2)


if __name__ == "__main__":
    unittest.main()
