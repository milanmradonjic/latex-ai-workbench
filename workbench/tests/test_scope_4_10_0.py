"""Workbench 4.10.0, gate G1 of docs/maintainers/plan-after-4.4.0.md: the Git guardrails the agents' rule files carry.

The owner decided that the generated deny set stays, that the prompts are for the Git commands that write history, branches or the working tree (so
`git add` and `git fetch` no longer prompt), that commit and push keep their prompts in the generated files, and that the equivalent spellings of a push to
the default branch are tested. What the rule files say is held here to what the two agents are documented to match:

* Claude Code (https://code.claude.com/docs/en/permissions): a `*` in a Bash rule is any text, anywhere; a trailing ` *` or `:*` also matches the bare command
  when it is the rule's only wildcard; deny, then ask, then allow decide; flags before the subcommand (`git -C . push`) and quoting are not matched.
* Codex: a rule is a prefix of whole words (each may be a list of alternatives); it has no wildcard.
"""
import ast
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from test_support import ProjectCase

TEMPLATES = PACKAGE / "templates"
REPOSITORY = PACKAGE.parent


def claude_rules():
    return json.loads((TEMPLATES / ".claude/settings.json").read_text())["permissions"]


def claude_matches(rule, command):
    """Whether a `Bash(...)` rule matches a command, as Anthropic's permissions page describes it."""
    body = rule[len("Bash("):-1] if rule.startswith("Bash(") else None
    if body is None:
        return False
    if body.endswith(":*"):
        body = body[:-2] + " *"
    if "*" not in body:
        return command == body
    pattern = re.escape(body).replace(r"\*", ".*")
    if body.endswith(" *") and body.count("*") == 1 and command == body[:-2]:
        return True
    return re.fullmatch(pattern, command) is not None


def codex_rules():
    """(decision, [alternatives per word]) for every rule of the Codex file."""
    rules = []
    for call in ast.walk(ast.parse((TEMPLATES / ".codex/rules/git-safety.rules").read_text())):
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "prefix_rule":
            values = {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}
            rules.append((values["decision"], [token if isinstance(token, list) else [token] for token in values["pattern"]]))
    return rules


def codex_decisions(command):
    words = command.split()
    return {decision for decision, pattern in codex_rules() if len(pattern) <= len(words) and all(word in alternatives for word, alternatives in zip(words, pattern))}


def pushes_to_the_default_branch():
    """Equivalent spellings of one act: pushing to main or master."""
    for remote, options, branch, source, trailing in itertools.product(
            ("origin", "upstream", "fork"),
            ("", "-u", "--set-upstream", "-f", "--force", "--force-with-lease", "--no-verify", "-u --force"),
            ("main", "master"),
            ("", "HEAD", "feature", "+feature", "+HEAD", "refs/heads/feature"),
            ("", " --force")):
        for destination in (branch, f"refs/heads/{branch}"):
            refspec = f"{source}:{destination}" if source else destination
            for spelled in {refspec, "+" + refspec} if not source else {refspec}:
                yield " ".join(part for part in ("git push", options, remote, spelled) if part) + trailing


class Pushes(unittest.TestCase):
    def test_the_matcher_agrees_with_the_examples_on_the_permissions_page(self):
        for rule, command, expected in (
                ("Bash(npm run build)", "npm run build", True), ("Bash(npm run build)", "npm run build --watch", False),
                ("Bash(npm run *)", "npm run", True), ("Bash(npm run *)", "npm install", False),
                ("Bash(git log * main)", "git log --oneline main", True), ("Bash(git log * main)", "git log main", False),
                ("Bash(ls *)", "ls", True), ("Bash(ls *)", "lsof", False), ("Bash(ls:*)", "ls -la", True),
                ("Bash(* --help *)", "npm --help", False), ("Bash(* --help *)", "npm --help x", True)):
            with self.subTest(rule=rule, command=command):
                self.assertEqual(claude_matches(rule, command), expected)

    def test_every_spelling_of_a_push_to_the_default_branch_is_refused_by_claude_and_never_silent_in_codex(self):
        deny, ask = claude_rules()["deny"], claude_rules()["ask"]
        count = 0
        for command in pushes_to_the_default_branch():
            count += 1
            with self.subTest(command=command):
                self.assertTrue(any(claude_matches(rule, command) for rule in deny), f"Claude does not refuse: {command}")
                self.assertTrue(codex_decisions(command), f"Codex does not even prompt: {command}")  # forbidden for the plain forms, a prompt for the rest
        self.assertGreater(count, 1000)

    def test_the_wildcards_leave_topic_branches_alone_and_every_push_still_prompts(self):
        deny, ask = claude_rules()["deny"], claude_rules()["ask"]
        for command in ("git push -u origin ccr-932b87a5-oxi7nb", "git push origin feature/main-fix", "git push origin domain", "git push origin maintenance",
                        "git push origin feature:feature", "git push upstream HEAD:feature/main-fix", "git push --force-with-lease origin feature",
                        "git push origin mainline", "git push origin HEAD:refs/heads/mainstream"):
            with self.subTest(command=command):
                self.assertFalse(any(claude_matches(rule, command) for rule in deny), f"a topic branch is refused: {command}")
                self.assertTrue(any(claude_matches(rule, command) for rule in ask), f"Claude does not prompt: {command}")
                self.assertEqual(codex_decisions(command), {"prompt"})

    def test_the_wildcard_denies_are_claudes_alone_and_the_literal_ones_still_agree_with_codex(self):
        deny = claude_rules()["deny"]
        wildcards = [entry for entry in deny if entry.startswith("Bash(") and "*" in entry[len("Bash("):-1].removesuffix(":*")]
        self.assertEqual(len(wildcards), 24)
        self.assertTrue(all(entry.startswith("Bash(git push ") for entry in wildcards))
        forbidden = {tuple(words) for decision, pattern in codex_rules() if decision == "forbidden" for words in itertools.product(*pattern)}
        self.assertTrue(all(command[:2] == ("git", "push") or command == ("gh", "pr", "merge") for command in forbidden))
        self.assertIn("mcp__github__merge_pull_request", deny)
        self.assertIn("mcp__github__enable_pr_auto_merge", deny)
        self.assertIn("Bash(gh pr merge:*)", deny)


class Prompts(unittest.TestCase):
    WRITE = (("commit",), ("push",), ("pull",), ("merge",), ("rebase",), ("reset",), ("restore",), ("clean",), ("stash",), ("checkout",), ("switch",),
             ("cherry-pick",), ("revert",), ("am",), ("rm",), ("mv",), ("tag",), ("update-ref",), ("filter-branch",), ("commit-tree",),
             ("branch", "-d"), ("branch", "-D"), ("branch", "-m"), ("worktree", "add"), ("worktree", "remove"), ("remote", "set-url"), ("reflog", "expire"))

    def commands(self):
        ask = claude_rules()["ask"]
        return {rule[len("Bash(git "):-1].removesuffix(":*").split()[0] for rule in ask if rule.startswith("Bash(git ")}

    def test_what_writes_history_branches_or_the_working_tree_prompts_in_both_agents(self):
        for words in self.WRITE:
            for argument in ("", " some-argument"):  # a rule may cover the bare command and not the one with arguments
                command = "git " + " ".join(words) + argument
                with self.subTest(command=command):
                    self.assertTrue(any(claude_matches(rule, command) for rule in claude_rules()["ask"]), f"Claude: {command}")
                    self.assertIn("prompt", codex_decisions(command), f"Codex: {command}")

    def test_staging_and_fetch_no_longer_prompt_in_either_agent(self):
        for command in ("git add", "git add -A", "git add paper.tex", "git fetch", "git fetch origin", "git fetch --all"):
            with self.subTest(command=command):
                self.assertFalse(any(claude_matches(rule, command) for rule in claude_rules()["ask"] + claude_rules()["deny"]), f"Claude: {command}")
                self.assertEqual(codex_decisions(command), set(), f"Codex: {command}")
        self.assertNotIn("add", self.commands())
        self.assertNotIn("fetch", self.commands())

    def test_init_and_clone_still_prompt_as_the_earlier_audit_repair_has_it(self):
        for command in ("git init", "git clone https://example.invalid/x.git"):
            self.assertTrue(any(claude_matches(rule, command) for rule in claude_rules()["ask"]), command)
            self.assertIn("prompt", codex_decisions(command), command)

    def test_inspection_stays_prompt_free(self):
        for command in ("git status", "git diff", "git log --oneline", "git show HEAD", "git ls-files", "git rev-parse HEAD", "git worktree list", "git remote -v"):
            self.assertFalse(any(claude_matches(rule, command) for rule in claude_rules()["ask"] + claude_rules()["deny"]), command)
            self.assertEqual(codex_decisions(command), set(), command)


class Wording(ProjectCase):
    def test_the_policy_names_what_needs_approval_and_says_staging_and_fetch_do_not(self):
        text = " ".join((TEMPLATES / "AGENTS.md").read_text().split())
        self.assertIn("Git mutations that write history, branches or the working tree require explicit user approval", text)
        self.assertIn("Staging (`git add`) and `git fetch` change none of those and need no approval of their own", text)
        self.assertNotIn("including staging", text)

    def test_an_installed_project_receives_the_rules_and_the_policy(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.install("init", "--skip-editor")
        for name in (".claude/settings.json", ".codex/rules/git-safety.rules", "AGENTS.md"):
            self.assertEqual((self.project / name).read_bytes(), (TEMPLATES / name).read_bytes(), name)
        self.assertIn("Bash(git push *:main)", json.loads((self.project / ".claude/settings.json").read_text())["permissions"]["deny"])

    @unittest.skipUnless((REPOSITORY / ".claude/settings.json").is_file(), "a standalone distribution is not inside the repository")
    def test_this_repositorys_rule_files_are_the_templates(self):
        for name in (".claude/settings.json", ".codex/rules/git-safety.rules"):
            self.assertEqual((REPOSITORY / name).read_bytes(), (TEMPLATES / name).read_bytes(), name)

    def test_the_docs_describe_what_prompts_and_what_is_refused(self):
        text = " ".join((PACKAGE / "docs/agents.md").read_text().split())
        for words in ("Staging (`git add`) and `git fetch` do not prompt", "`git push upstream feature:main` is refused.", "Codex rules match whole words, so there it only prompts",
                      "that is a line of `AGENTS.md`, not a rule in these files"):
            self.assertIn(words, text)


if __name__ == "__main__":
    unittest.main()
