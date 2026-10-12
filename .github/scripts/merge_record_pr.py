#!/usr/bin/env python3
"""Squash-merge a *record* pull request, and nothing else.

The owner delegates one kind of merge to an agent: a pull request whose every changed file is a record, that is
``plan-after-3.0.2.md`` or a ``verification*.md`` under ``workbench/docs/maintainers/``. Anything else (code, policy,
permission rules, workflows, this script) is the owner's to merge. The agent's rule files still deny a raw
``gh pr merge``; this script is the one way in, so the limit lives in code that tests can check.

    python3 .github/scripts/merge_record_pr.py NUMBER [--dry-run]

It refuses unless the pull request is open, not a draft, aimed at ``main``, mergeable with no pending or failing check, and
made only of records. It merges against the exact commit it inspected (a later push cannot slip in) and then deletes the
pull request's branch on GitHub. It never touches the local clone: updating that stays the owner's step.
Exit status: 0 merged (or would merge, with --dry-run), 1 refused, 2 an error.
"""
import json
import re
import subprocess
import sys

BASE = "main"
RECORD = re.compile(r"workbench/docs/maintainers/(plan-after-3\.0\.2|verification(-[0-9][A-Za-z0-9.]*)?)\.md")
FIELDS = "number,title,state,isDraft,baseRefName,headRefName,headRefOid,mergeable,mergeStateStatus,files,statusCheckRollup"
PASSED = {"SUCCESS", "SKIPPED", "NEUTRAL"}
LIMIT = 100  # gh lists at most this many files; more than that cannot be checked


class GhError(Exception):
    pass


def gh(*arguments):
    done = subprocess.run(["gh", *arguments], capture_output=True, text=True)
    if done.returncode:
        raise GhError((done.stderr or done.stdout).strip())
    return done.stdout


def check_name(check):
    return check.get("name") or check.get("context") or "a check"


def check_passed(check):
    if check.get("__typename") == "StatusContext":
        return check.get("state") == "SUCCESS"
    return check.get("status") == "COMPLETED" and check.get("conclusion") in PASSED


def refusals(pr):
    """Why this pull request may not be merged by the agent; empty when it may."""
    reasons = []
    if pr["state"] != "OPEN":
        reasons.append(f"it is {pr['state'].lower()}, not open")
    if pr["isDraft"]:
        reasons.append("it is a draft")
    if pr["baseRefName"] != BASE:
        reasons.append(f"it targets {pr['baseRefName']}, not {BASE}")
    if pr["mergeable"] != "MERGEABLE" or pr["mergeStateStatus"] != "CLEAN":
        reasons.append(f"GitHub does not report it clean and mergeable ({pr['mergeable']}, {pr['mergeStateStatus']})")
    checks = pr["statusCheckRollup"] or []
    if not checks:
        reasons.append("no check has run")
    for check in checks:
        if not check_passed(check):
            reasons.append(f"check {check_name(check)} has not passed")
    paths = [item["path"] for item in pr["files"]]
    if not paths:
        reasons.append("it changes no file")
    elif len(paths) >= LIMIT:
        reasons.append(f"it changes {len(paths)} or more files, too many to check")
    others = [path for path in paths if not RECORD.fullmatch(path)]
    if others:
        reasons.append("it changes files that are not records, which only the owner may merge: " + ", ".join(others[:6])
                       + (f" and {len(others) - 6} more" if len(others) > 6 else ""))
    return reasons


def main(arguments, run=gh):
    dry = "--dry-run" in arguments
    numbers = [argument for argument in arguments if argument != "--dry-run"]
    if len(numbers) != 1 or not numbers[0].isdigit():
        print(__doc__.split("\n\n")[1].strip(), file=sys.stderr)
        return 2
    number = numbers[0]
    try:
        pr = json.loads(run("pr", "view", number, "--json", FIELDS))
        reasons = refusals(pr)
        if reasons:
            print(f"Not merging #{number} ({pr['title']}):", *[f"  - {reason}" for reason in reasons], sep="\n")
            return 1
        sha = pr["headRefOid"]
        print(f"#{number} is a record pull request: {len(pr['files'])} file(s), all checks green, head {sha[:8]}.")
        if dry:
            print("Dry run: it would be squash-merged and its branch deleted.")
            return 0
        run("pr", "merge", number, "--squash", "--match-head-commit", sha)
        print(f"Squash-merged #{number}.")
        branch = pr["headRefName"]
        if branch != BASE:
            repository = json.loads(run("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
            try:
                run("api", "-X", "DELETE", f"repos/{repository}/git/refs/heads/{branch}")
                print(f"Deleted the branch {branch} on GitHub.")
            except GhError:
                print(f"The branch {branch} was already gone on GitHub.")
        print("Waiting for the owner: git switch main, then git pull (and delete the local branch when convenient).")
        return 0
    except GhError as error:
        print(f"gh failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
