"""3.0.4: changes reach the default branch only through pull requests.

On a private repository of GitHub's free plan, branch protection is not enforced, so the policy and the
agents' own rules carry it. Each test failed before the change.
"""
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_support import ProjectCase

PACKAGE = Path(__file__).resolve().parents[1]
TEMPLATES = PACKAGE / "templates"
RULE = "only through a pull request"
OWNER_MERGES = "only the owner merges"
SOURCE = "\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n"


def codex_rules(decision):
    rules = set()
    for call in ast.walk(ast.parse((TEMPLATES / ".codex/rules/git-safety.rules").read_text())):
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "prefix_rule":
            values = {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}
            if values["decision"] == decision:
                patterns = [[]]
                for token in values["pattern"]:
                    patterns = [prefix + [choice] for prefix in patterns for choice in (token if isinstance(token, list) else [token])]
                rules.update(tuple(pattern) for pattern in patterns)
    return rules


class PullRequestPolicy(ProjectCase):

    def test_policy_states_the_rule(self):
        text = (TEMPLATES / "AGENTS.md").read_text()
        self.assertIn(RULE, text)
        self.assertIn(OWNER_MERGES, " ".join(text.split()))

    def test_installed_projects_receive_the_rule(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--skip-editor")
        self.assertIn(RULE, (self.project / "AGENTS.md").read_text())

    def test_agents_refuse_pushes_to_the_default_branch_and_still_ask_for_other_pushes(self):
        permissions = json.loads((TEMPLATES / ".claude/settings.json").read_text())["permissions"]
        for command in ("git push origin main", "git push origin HEAD:main", "git push -u origin main", "git push --force origin master"):
            with self.subTest(command=command):
                self.assertIn(f"Bash({command})", permissions["deny"])
                self.assertIn(f"Bash({command}:*)", permissions["deny"])
                self.assertIn(tuple(command.split()), codex_rules("forbidden"))
        self.assertIn("Bash(git push:*)", permissions["ask"])  # nothing weakened
        self.assertIn(("git", "push"), codex_rules("prompt"))
        self.assertNotIn(("git", "push", "origin", "main-fix"), codex_rules("forbidden"))

    def test_agents_cannot_merge_pull_requests_themselves(self):
        """A pull request an agent merges itself has had no review: merging is the owner's."""
        deny = json.loads((TEMPLATES / ".claude/settings.json").read_text())["permissions"]["deny"]
        for rule in ("Bash(gh pr merge)", "Bash(gh pr merge:*)", "mcp__github__merge_pull_request", "mcp__github__enable_pr_auto_merge"):
            with self.subTest(rule=rule):
                self.assertIn(rule, deny)
        self.assertIn(("gh", "pr", "merge"), codex_rules("forbidden"))
