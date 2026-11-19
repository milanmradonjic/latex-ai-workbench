"""Tests of the agents' rule files and policy: what prompts, what is refused, the pull-request rule.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 5 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_audit3_repairs.py:
Independent audit 3 failures, exercised through installed workflows.

Compiler fixtures disable lint explicitly. Process/move tests isolate infrastructure;
the source-content and stdin tests use genuine TeX tools.

test_modules.py:
(no docstring)

test_repairs_3_0_4.py:
3.0.4: changes reach the default branch only through pull requests.

On a private repository of GitHub's free plan, branch protection is not enforced, so the policy and the
agents' own rules carry it. Each test failed before the change.

test_scope_4_10_0.py:
Workbench 4.10.0, gate G1 of docs/maintainers/plan-after-4.4.0.md: the Git guardrails the agents' rule files carry.

The owner decided that the generated deny set stays, that the prompts are for the Git commands that write history, branches or the working tree (so
`git add` and `git fetch` no longer prompt), that commit and push keep their prompts in the generated files, and that the equivalent spellings of a push to
the default branch are tested. What the rule files say is held here to what the two agents are documented to match:

* Claude Code (https://code.claude.com/docs/en/permissions): a `*` in a Bash rule is any text, anywhere; a trailing ` *` or `:*` also matches the bare command
  when it is the rule's only wildcard; deny, then ask, then allow decide; flags before the subcommand (`git -C . push`) and quoting are not matched.
* Codex: a rule is a prefix of whole words (each may be a list of alternatives); it has no wildcard.

test_workbench.py:
(no docstring)
"""

import ast
import contextlib
import io
import itertools
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap
import bootstrap as boot
from _workbench_vendor import tomli
import guide
from test_support import ProjectCase, fixture_env, isolate_environment, own_targets, prepare_config


OWNER_MERGES = "only the owner merges"


RULE = "only through a pull request"


SOURCE = "\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n"


TEMPLATES = PACKAGE / "templates"


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


def claude_rules():
    return json.loads((TEMPLATES / ".claude/settings.json").read_text())["permissions"]


def codex_rules_4_10_0():
    """(decision, [alternatives per word]) for every rule of the Codex file."""
    rules = []
    for call in ast.walk(ast.parse((TEMPLATES / ".codex/rules/git-safety.rules").read_text())):
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "prefix_rule":
            values = {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}
            rules.append((values["decision"], [token if isinstance(token, list) else [token] for token in values["pattern"]]))
    return rules


def codex_decisions(command):
    words = command.split()
    return {decision for decision, pattern in codex_rules_4_10_0() if len(pattern) <= len(words) and all(word in alternatives for word, alternatives in zip(words, pattern))}


try:
    import tomllib
except ImportError:  # Python 3.10 lacks tomllib
    tomllib = None


def gemini_rules():
    text = (TEMPLATES / ".gemini/policies/git-safety.toml").read_text(encoding="utf-8")
    return (tomllib or tomli).loads(text)["rule"]


def gemini_shell_decision(command):
    """Highest-priority decision for a `run_shell_command` invocation under Gemini CLI's Policy Engine."""
    payload = json.dumps({"command": command}, separators=(",", ":"))
    matched = []
    for rule in gemini_rules():
        tools = rule.get("toolName")
        names = [tools] if isinstance(tools, str) else list(tools or ())
        if rule.get("mcpName") or "run_shell_command" not in names:
            continue
        hit = False
        if "commandPrefix" in rule:
            prefixes = [rule["commandPrefix"]] if isinstance(rule["commandPrefix"], str) else rule["commandPrefix"]
            hit = any(command == prefix or command.startswith(prefix + " ") for prefix in prefixes)
        elif "commandRegex" in rule:
            hit = re.search('"command":"' + rule["commandRegex"], payload) is not None
        if hit:
            matched.append((rule.get("priority", 0), rule["decision"]))
    if not matched:
        return None
    top = max(priority for priority, _ in matched)
    decisions = {decision for priority, decision in matched if priority == top}
    assert len(decisions) == 1, f"ambiguous Gemini policy tie at priority {top} for {command!r}: {decisions}"
    return next(iter(decisions))


def gemini_mcp_decision(mcp_name, tool_name):
    matched = []
    for rule in gemini_rules():
        if rule.get("mcpName") != mcp_name:
            continue
        tools = rule.get("toolName")
        names = [tools] if isinstance(tools, str) else list(tools or ())
        if tool_name in names:
            matched.append((rule.get("priority", 0), rule["decision"]))
    if not matched:
        return None
    top = max(priority for priority, _ in matched)
    return next(decision for priority, decision in matched if priority == top)


class GeminiUpstreamCompatibility(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("WORKBENCH_GEMINI_UTILS"), "needs the pinned upstream Gemini policy helper")
    def test_upstream_policy_validator_accepts_every_shipped_pattern(self):
        script = """
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const { buildArgsPatterns, isSafeRegExp } = await import(pathToFileURL(process.argv[1]));
const rules = JSON.parse(readFileSync(0, 'utf8'));
for (const [index, rule] of rules.entries()) {
    const patterns = buildArgsPatterns(rule.argsPattern, rule.commandPrefix, rule.commandRegex);
    if (patterns.some(pattern => pattern && !isSafeRegExp(pattern))) {
        console.error(`Gemini rejected rule ${index + 1} (${rule.decision})`);
        process.exitCode = 1;
    }
}
"""
        result = subprocess.run(["node", "--input-type=module", "-e", script, os.environ["WORKBENCH_GEMINI_UTILS"]],
                                input=json.dumps(gemini_rules()), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


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


REPOSITORY = PACKAGE.parent


TEX = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


class Audit3Repairs(unittest.TestCase):
    """Origin: tests/test_audit3_repairs.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix='workbench-audit3-')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve() / 'project'
        self.project.mkdir()
        self.env = fixture_env()
        self.children = []
        self.addCleanup(self.stop_children)

    def stop_children(self):
        for pid in self.children:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                pass

    def test_git_initialization_and_cloning_have_matching_approval_rules(self):
        templates=bootstrap.PACKAGE/'templates'
        rules=set()
        for node in ast.walk(ast.parse((templates/'.codex/rules/git-safety.rules').read_text())):
            if isinstance(node,ast.Call) and getattr(node.func,'id','')=='prefix_rule':
                values={k.arg:ast.literal_eval(k.value) for k in node.keywords}
                if len(values['pattern'])==2:rules.add(tuple(values['pattern']))
        claude=json.loads((templates/'.claude/settings.json').read_text())['permissions']['ask']
        for action in ('init','clone'):
            self.assertIn(('git',action),rules)
            self.assertIn('Bash(git '+action+')',claude)
            self.assertIn('Bash(git '+action+':*)',claude)
            self.assertEqual(gemini_shell_decision('git '+action),'ask_user')
            self.assertEqual(gemini_shell_decision('git '+action+' arg'),'ask_user')


class ModuleTests(unittest.TestCase):
    """Origin: tests/test_modules.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-modules-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, **choices):
        prepare_config(self.project, **choices)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return boot.main([*args, str(self.project)])

    def command(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), *args],
                                cwd=self.project, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def make_result(self, *arguments):
        # Run as the user would in a fresh shell: not as a child of the package's own `make test` (which sets
        # MAKEFLAGS and makes Make announce directories), and without the caller's TASK or the comparison
        # revision hosted CI exports for the outer repository (LATEX_AI_BASE names a commit these fixtures lack).
        env = {name: value for name, value in os.environ.items() if name not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "TASK", "LATEX_AI_BASE"}}
        return subprocess.run(["make", "-s", "--no-print-directory", *arguments], cwd=self.project, capture_output=True, text=True, env=env)

    def make_output(self, *arguments, expected=0):
        done = self.make_result(*arguments)
        self.assertEqual(done.returncode, expected, done.stdout + done.stderr)
        return done.stdout


class PullRequestPolicy(ProjectCase):

    """Origin: tests/test_repairs_3_0_4.py, workbench 3.0.4."""

    def test_policy_states_the_rule(self):
        text = (TEMPLATES / "AGENTS.md").read_text()
        self.assertIn(RULE, text)
        self.assertIn(OWNER_MERGES, " ".join(text.split()))

    def test_installed_projects_receive_the_rule(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install('init', editor=False)
        self.assertIn(RULE, (self.project / "AGENTS.md").read_text())
        self.assertIn("AGENTS.md", (self.project / "GEMINI.md").read_text())

    def test_agents_refuse_pushes_to_the_default_branch_and_still_ask_for_other_pushes(self):
        permissions = json.loads((TEMPLATES / ".claude/settings.json").read_text())["permissions"]
        for command in ("git push origin main", "git push origin HEAD:main", "git push -u origin main", "git push --force origin master"):
            with self.subTest(command=command):
                self.assertIn(f"Bash({command})", permissions["deny"])
                self.assertIn(f"Bash({command}:*)", permissions["deny"])
                self.assertIn(tuple(command.split()), codex_rules("forbidden"))
                self.assertEqual(gemini_shell_decision(command), "deny")
        self.assertIn("Bash(git push:*)", permissions["ask"])  # nothing weakened
        self.assertIn(("git", "push"), codex_rules("prompt"))
        self.assertNotIn(("git", "push", "origin", "main-fix"), codex_rules("forbidden"))
        self.assertEqual(gemini_shell_decision("git push"), "ask_user")
        self.assertEqual(gemini_shell_decision("git push origin main-fix"), "ask_user")

    def test_agents_cannot_merge_pull_requests_themselves(self):
        """A pull request an agent merges itself has had no review: merging is the owner's."""
        deny = json.loads((TEMPLATES / ".claude/settings.json").read_text())["permissions"]["deny"]
        for rule in ("Bash(gh pr merge)", "Bash(gh pr merge:*)", "mcp__github__merge_pull_request", "mcp__github__enable_pr_auto_merge"):
            with self.subTest(rule=rule):
                self.assertIn(rule, deny)
        self.assertIn(("gh", "pr", "merge"), codex_rules("forbidden"))
        self.assertEqual(gemini_shell_decision("gh pr merge"), "deny")
        self.assertEqual(gemini_shell_decision("gh pr merge 42 --auto"), "deny")
        self.assertEqual(gemini_mcp_decision("github", "merge_pull_request"), "deny")
        self.assertEqual(gemini_mcp_decision("github", "enable_pr_auto_merge"), "deny")


class Pushes(unittest.TestCase):
    """Origin: tests/test_scope_4_10_0.py, workbench 4.10.0."""

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
                self.assertEqual(gemini_shell_decision(command), "deny", f"Gemini does not refuse: {command}")
        self.assertGreater(count, 1000)
        for deletion in ("git push origin :main", "git push origin :master", "git push upstream :refs/heads/main"):
            with self.subTest(command=deletion):
                self.assertEqual(gemini_shell_decision(deletion), "deny")

    def test_the_wildcards_leave_topic_branches_alone_and_every_push_still_prompts(self):
        deny, ask = claude_rules()["deny"], claude_rules()["ask"]
        for command in ("git push -u origin ccr-932b87a5-oxi7nb", "git push origin feature/main-fix", "git push origin domain", "git push origin maintenance",
                        "git push origin feature:feature", "git push upstream HEAD:feature/main-fix", "git push --force-with-lease origin feature",
                        "git push origin mainline", "git push origin HEAD:refs/heads/mainstream"):
            with self.subTest(command=command):
                self.assertFalse(any(claude_matches(rule, command) for rule in deny), f"a topic branch is refused: {command}")
                self.assertTrue(any(claude_matches(rule, command) for rule in ask), f"Claude does not prompt: {command}")
                self.assertEqual(codex_decisions(command), {"prompt"})
                self.assertEqual(gemini_shell_decision(command), "ask_user", f"Gemini: {command}")
        for extra in ("git push origin feature/main", "git push origin main:feature"):
            with self.subTest(command=extra):
                self.assertEqual(gemini_shell_decision(extra), "ask_user")

    def test_the_wildcard_denies_are_claudes_alone_and_the_literal_ones_still_agree_with_codex(self):
        deny = claude_rules()["deny"]
        wildcards = [entry for entry in deny if entry.startswith("Bash(") and "*" in entry[len("Bash("):-1].removesuffix(":*")]
        self.assertEqual(len(wildcards), 24)
        self.assertTrue(all(entry.startswith("Bash(git push ") for entry in wildcards))
        forbidden = {tuple(words) for decision, pattern in codex_rules_4_10_0() if decision == "forbidden" for words in itertools.product(*pattern)}
        self.assertTrue(all(command[:2] == ("git", "push") or command == ("gh", "pr", "merge") for command in forbidden))
        self.assertIn("mcp__github__merge_pull_request", deny)
        self.assertIn("mcp__github__enable_pr_auto_merge", deny)
        self.assertIn("Bash(gh pr merge:*)", deny)


class Prompts(unittest.TestCase):
    """Origin: tests/test_scope_4_10_0.py, workbench 4.10.0."""

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
                    self.assertEqual(gemini_shell_decision(command), "ask_user", f"Gemini: {command}")

    def test_staging_and_fetch_no_longer_prompt_in_either_agent(self):
        for command in ("git add", "git add -A", "git add paper.tex", "git fetch", "git fetch origin", "git fetch --all"):
            with self.subTest(command=command):
                self.assertFalse(any(claude_matches(rule, command) for rule in claude_rules()["ask"] + claude_rules()["deny"]), f"Claude: {command}")
                self.assertEqual(codex_decisions(command), set(), f"Codex: {command}")
                self.assertIsNone(gemini_shell_decision(command), f"Gemini: {command}")
        self.assertNotIn("add", self.commands())
        self.assertNotIn("fetch", self.commands())

    def test_init_and_clone_still_prompt_as_the_earlier_audit_repair_has_it(self):
        for command in ("git init", "git clone https://example.invalid/x.git"):
            self.assertTrue(any(claude_matches(rule, command) for rule in claude_rules()["ask"]), command)
            self.assertIn("prompt", codex_decisions(command), command)
            self.assertEqual(gemini_shell_decision(command), "ask_user", command)

    def test_inspection_stays_prompt_free(self):
        for command in ("git status", "git diff", "git log --oneline", "git show HEAD", "git ls-files", "git rev-parse HEAD", "git worktree list", "git remote -v"):
            self.assertFalse(any(claude_matches(rule, command) for rule in claude_rules()["ask"] + claude_rules()["deny"]), command)
            self.assertEqual(codex_decisions(command), set(), command)
            self.assertIsNone(gemini_shell_decision(command), command)


class Wording(ProjectCase):
    """Origin: tests/test_scope_4_10_0.py, workbench 4.10.0."""

    def test_the_policy_names_what_needs_approval_and_says_staging_and_fetch_do_not(self):
        text = " ".join((TEMPLATES / "AGENTS.md").read_text().split())
        self.assertIn("Git mutations that write history, branches or the working tree require explicit user approval", text)
        self.assertIn("Staging (`git add`) and `git fetch` change none of those and need no approval of their own", text)
        self.assertNotIn("including staging", text)

    def test_an_installed_project_receives_the_rules_and_the_policy(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.install('init', editor=False)
        for name in (".claude/settings.json", ".codex/rules/git-safety.rules", ".gemini/settings.json",
                     ".gemini/policies/git-safety.toml", "AGENTS.md", "GEMINI.md"):
            self.assertEqual((self.project / name).read_bytes(), (TEMPLATES / name).read_bytes(), name)
        self.assertIn("Bash(git push *:main)", json.loads((self.project / ".claude/settings.json").read_text())["permissions"]["deny"])

    @unittest.skipUnless((REPOSITORY / ".claude/settings.json").is_file(), "a standalone distribution is not inside the repository")
    def test_this_repositorys_rule_files_are_the_templates(self):
        for name in (".claude/settings.json", ".codex/rules/git-safety.rules", ".gemini/settings.json", ".gemini/policies/git-safety.toml"):
            self.assertEqual((REPOSITORY / name).read_bytes(), (TEMPLATES / name).read_bytes(), name)

    def test_the_docs_describe_what_prompts_and_what_is_refused(self):
        text = " ".join((PACKAGE / "docs/agents.md").read_text().split())
        for words in ("Staging (`git add`) and `git fetch` do not prompt", "`git push upstream feature:main` is refused.", "Codex rules match whole words, so there it only prompts",
                      "that is a line of `AGENTS.md`, not a rule in these files", ".gemini/policies/git-safety.toml", "Antigravity"):
            self.assertIn(words, text)


class WorkbenchTests(unittest.TestCase):
    """Origin: tests/test_workbench.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="latex-ai-unit-")
        self.project = Path(self.temp.name).resolve()
        (self.project / "paper.tex").write_text(TEX)
        prepare_config(self.project, root="paper.tex", output_dir=".")

    def tearDown(self):
        self.temp.cleanup()

    def test_agent_guardrails_agree_and_cover_every_git_operation_the_policy_names(self):
        templates = boot.PACKAGE / "templates"
        codex, refused = set(), set()  # prompts, and pushes to the default branch that are refused (3.0.4)
        for call in ast.walk(ast.parse((templates / ".codex/rules/git-safety.rules").read_text())):
            if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "prefix_rule":
                rule = {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}
                self.assertIn(rule["decision"], {"prompt", "forbidden"})
                self.assertTrue(rule["justification"])
                alternatives = [token if isinstance(token, list) else [token] for token in rule["pattern"]]
                (codex if rule["decision"] == "prompt" else refused).update(itertools.product(*alternatives))
        settings = json.loads((templates / ".claude/settings.json").read_text())["permissions"]
        def commands(entries):  # shell rules; Claude's GitHub-tool rules (mcp__...) have no Codex counterpart
            return {tuple(entry[len("Bash("):-1].removesuffix(":*").split()) for entry in entries if entry.startswith("Bash(")}
        claude = commands(settings["ask"])
        self.assertEqual(claude, codex)  # the agents must not drift apart
        # Gemini policy TOML: Python 3.10 fallback parser must agree with tomllib on 3.11+, priorities stay in 0..999,
        # and the ask_user commandPrefix set must match Claude and Codex identically.
        policy_text = (templates / ".gemini/policies/git-safety.toml").read_text(encoding="utf-8")
        if tomllib is not None:
            self.assertEqual(tomli.loads(policy_text), tomllib.loads(policy_text))
        gemini_policy = gemini_rules()
        gemini_ask = set()
        for rule in gemini_policy:
            self.assertIsInstance(rule.get("priority"), int)
            self.assertTrue(0 <= rule["priority"] <= 999, f"Gemini CLI drops priorities outside 0..999: {rule}")
            if rule.get("decision") == "ask_user" and "commandPrefix" in rule:
                prefixes = [rule["commandPrefix"]] if isinstance(rule["commandPrefix"], str) else rule["commandPrefix"]
                gemini_ask.update(tuple(prefix.split()) for prefix in prefixes)
        self.assertEqual(gemini_ask, codex)
        for allowed in ("make check", "make build", "make lint"):
            self.assertEqual(gemini_shell_decision(allowed), "allow", allowed)
        for not_allowed in ("make check && git push origin main", "make check-extra", "git status", "git diff"):
            self.assertNotEqual(gemini_shell_decision(not_allowed), "allow", not_allowed)
        gemini_settings = json.loads((templates / ".gemini/settings.json").read_text(encoding="utf-8"))
        self.assertEqual(gemini_settings["context"]["fileName"], ["AGENTS.md", "GEMINI.md"])
        self.assertNotIn("policyPaths", gemini_settings)
        # Claude's wildcard denies (4.10.0: `git push *:main` and the like) have no Codex counterpart, which matches whole words only; the others agree.
        self.assertEqual(commands(entry for entry in settings.get("deny", []) if "*" not in entry[len("Bash("):-1].removesuffix(":*")), refused)
        # Refused outright: pushes to the default branch and merging pull requests (3.0.4); everything else prompts.
        self.assertTrue(all(command[:2] == ("git", "push") or command == ("gh", "pr", "merge") for command in refused))
        self.assertTrue(all(entry.startswith(("Bash(", "mcp__github__")) for entry in settings.get("deny", [])))
        # AGENTS.md (4.10.0, gate G1): what writes history, branches or the working tree: committing, pushing, pulling, merging, rebasing, resetting,
        # restoring, cleaning, stashing, branch changes/deletion, worktree creation/removal and history rewriting. Staging and fetch prompt no more.
        named = {("git", name) for name in ("commit", "push", "pull", "merge", "rebase", "reset", "restore", "clean", "stash", "checkout", "switch",
                                            "cherry-pick", "revert", "am", "rm", "mv", "tag", "update-ref", "filter-branch", "commit-tree")}
        named |= {("git", "branch", flag) for flag in ("-d", "-D", "--delete", "-m", "-f")}
        named |= {("git", "worktree", action) for action in ("add", "remove")}
        named |= {("git", "remote", "set-url"), ("git", "remote", "update"), ("git", "reflog", "expire")}
        self.assertFalse(named - codex, f"policy-named operations without a guardrail: {sorted(named - codex)}")
        for read_only in ("status", "diff", "log", "show", "ls-files", "rev-parse"):
            self.assertNotIn(("git", read_only), codex)  # inspection must stay prompt-free
        self.assertFalse({tuple(entry[len("Bash("):-1].removesuffix(":*").split()) for entry in settings["allow"]} & codex)
        # Claude Code already runs read-only forms of git unasked; an explicit allow would also cover `git diff --output=PATH`.
        self.assertEqual([entry for entry in settings["allow"] if "git" in entry], [])

    def test_policy_tells_agents_how_to_treat_a_suspected_workbench_defect(self):
        template = (boot.PACKAGE / "templates/AGENTS.md").read_text()
        section = template[template.index("# Suspected workbench defects"):template.index("# Writer/reviewer workflow")]
        for phrase in ("INTERNAL ERROR", "Error 70", "Do not edit `.latex-ai/`", "make issue", "nothing is sent anywhere", "need the user's approval"):
            self.assertIn(phrase, section)


if __name__ == "__main__":
    unittest.main()
