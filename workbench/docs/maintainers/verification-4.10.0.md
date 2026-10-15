# Version 4.10.0 verification

This records the release that carries gate G1 of [the plan after 4.4.0](plan-after-4.4.0.md), the Git guardrails, as the owner decided it on 15 October 2026: the deny set stays, the prompts are for the commands that write history, branches or the
working tree (so `git add` and `git fetch` no longer prompt), commit and push keep their prompts in every generated project, and the equivalent spellings of a push to the default branch are tested. The agents' own commits and pushes of a topic branch in a
workbench session stay a line of this repository's `AGENTS.md`, not a rule of the generated files.
Built on 4.9.1 (`ac737c1`). Tested on 2026-10-15 on Linux (x86_64, GNU Make 4.3, Git 2.43.0, Python 3.13.16, 3.12.13 and 3.11.17) with TeX Live 2023 from Debian.
The hosted results are at the end of this record (added by the record of 4.10.1).

| Check | Result |
|---|---|
| `tests/test_scope_4_10_0.py` (now in `tests/test_agent_rules.py`) against 4.9.1 | 6 of its 12 tests fail: 1,200 of the 1,344 spellings of a push to the default branch are not refused by Claude's rules (the 144 refused all name `origin`, a bare branch or `HEAD` as the source, and the listed options); `git add` and `git fetch` still prompt (7 spellings tried); there are no wildcard denies; the policy still says staging needs approval; the docs say nothing of either; an installed project gets none of it. The six that pass are controls: the matcher against the permissions page, topic branches left alone, what writes still prompting, `init` and `clone` still prompting, inspection prompt-free, and this repository's rule files being the templates |
| The same after the change | All 12 pass. The existing parity test `test_agent_guardrails_agree_and_cover_every_git_operation_the_policy_names` was changed on purpose: the policy-named operations no longer include `add` and `fetch`, and the deny comparison skips Claude's wildcard rules, which Codex cannot express. `test_repairs_3_0_4.py` (now in `tests/test_agent_rules.py`) and `test_audit3_repairs.py` (its tests are now in `tests/test_receipts.py`, `tests/test_processes.py`, `tests/test_planner.py` and others (see [where the tests are](tests-map.md))) pass unchanged |
| What the new tests hold the rule files to | Claude Code's matching as its permissions page describes it (a `*` is any text anywhere, a trailing ` *` or `:*` also matches the bare command, deny then ask then allow), implemented in the test and first checked against eleven examples of that page; Codex's whole-word prefix rules. **1,344 spellings of a push to `main` or `master`** (three remotes, eight option sets, source empty, `HEAD`, a branch name, `+` forms, `refs/heads/`, with and without a trailing argument): every one is refused by Claude and every one at least prompts in Codex. **Nine pushes of a topic branch** (`feature/main-fix`, `domain`, `maintenance`, `mainline`, `HEAD:refs/heads/mainstream`, `-u origin` a branch of the session, a force-with-lease of a topic): none is refused and every one prompts in both agents. 27 writing commands, bare and with an argument, prompt in both |
| Eighteen mutations | All 18 caught by a test named for it: `git add` or `git fetch` prompting again (in Claude, and `add` in Codex); `git commit` or `git reset` no longer prompting; `init` no longer prompting; the `:main` wildcard gone, or without its trailing-argument form; the `master` wildcard gone; the `+refs/heads/master` form gone; the `refs/heads` wildcard gone; a wildcard written without the space before `main` (it then refuses `domain`); the `gh pr merge` deny or the GitHub merge tool's deny gone; the policy saying staging needs approval again; the docs losing a sentence; this repository's rule file differing from the template. **Two tests were weak on the first run and are strengthened:** the prompt test tried only bare commands, so removing the `git commit:*` form was caught only by the template-equals-reference test (it now tries each command with an argument too), and a docs mutation survived because the test matched a phrase that survived it (it now matches the sentence with its full stop) |
| `make -C workbench test` | 541 tests (the 529 of 4.9.1 and the 12 new), 2 skipped (the unreadable-folder test, since this runs as root, and the test that needs GNU Make 3.81), OK on 3.13.16, 3.12.13 and 3.11.17 |
| `make -C workbench portability` | All 51 scenarios pass |
| 4.9.1 and this tree, identical projects, each installed and run by its own release | 232 comparisons, 0 differences, none skipped as noise: the eight projects of the earlier comparisons. Masked, because they are the change: the version (the pattern now takes two-digit minors), the contents of the three agent files, the policy's approval sentence in the dry-run diff and the line counts of the two rule files. Every receipt, every editor file and every other action's output is identical |
| The generated-files guard | Unchanged: the Makefile and the editor files did not change |
| `make -C workbench upgrade-reference`, then `audit-reference` | The refresh changed `core.py` in the reference's `.latex-ai/` (the version), and the audit then reports the runtime identical. This repository's `.claude/settings.json` and `.codex/rules/git-safety.rules` are the templates (a test holds that); `latex-ai-init diff` lists only `AGENTS.md`, which carries the project's own sections |
| Size | The package is 4,413 lines, unchanged (the code did not change; the version did): `bootstrap.py` is still 579. The tests are 8,051 lines (7,869). Claude's file has 172 deny entries (148, plus the 24 wildcards) and 117 ask entries (121); Codex's file has 34 prompt rules (36) and 7 forbidden |

## What changed, and what did not

- **Dropped from the prompts:** `git add` and `git fetch` only. The owner's rule is "prompt only on commands that write history, branches or the working tree"; staging writes the index, and fetch writes objects and remote-tracking references, neither a commit, a branch of
  the project nor a working-tree file. They were the frequent ones, and the commit or merge that follows still prompts.
- **Kept although they write none of the three:** `git init` and `git clone`. A repair after an earlier audit put them into both files on purpose (`test_git_initialization_and_cloning_have_matching_approval_rules`), they are rare, and so they cost no noise.
- **Kept as they were:** the destructive forms of `branch`, `worktree`, `remote`, `reflog` and `submodule`, which are already specific; commit and push, in every generated project, as the owner chose; the merge denies.
- **Added:** 24 wildcard denies in Claude's file. The existing literal push denies (144 entries) stay beside them rather than being replaced: if a Claude Code did not read `*` in the middle of a rule, the literal ones would still hold.
- **Not changed:** that the agents' own commits and pushes need no prompt in a workbench session. That stays a line of this repository's `AGENTS.md` ("Git in a workbench session"), as the owner chose; the generated files keep their prompts, so a manuscript project's agent still asks.

## Found on the way

- **The policy and the rules had to move together.** `AGENTS.md` said that Git mutations including staging need approval; with `git add` unprompted, an agent that follows the text would still ask in chat, and the change would have bought nothing. The approval sentence now names what writes history, branches or the working tree, and says that staging and fetch need none of their own.
- **The wildcard is easy to write too wide.** `git push *main` (no space) would also refuse `domain` and `remain`; the test of topic branches caught it, and the rules use ` main`, `:main` and `refs/heads/main` as whole destinations.
- **Codex cannot say "any source".** Its rules are whole words, so `git push origin feature:main` can only prompt there; the docs say so, and the test asks of Codex only that no such push is silent.
- **An agent updating a project will not take the relaxation.** The update recipe tells it to keep the stricter rule where two differ, and `latex-ai-init diff` only shows the three files; the owner reads them and takes what they want. The release notes say so.

## Hosted verification

All six required checks passed on the pull request ([#19](https://github.com/milanmradonjic/latex-ai-workbench/pull/19): [`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38715847657) in 2m30s with TeX Live 2026; the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38715847656), 2m06s to 2m30s each), and again on the merge commit `a458277` on `main` ([`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38718340499); the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38718340736)).

## Not verified

- **Claude Code's own engine.** The matcher in the test is written from the permissions page and checked against its examples; no Claude Code was run here against these rules. The 3.0.4 record observed that the GitHub-tool denies took effect in a running session; the shell denies, old or new, were not observed.
- **Codex's handling of `decision = "forbidden"`,** as in 3.0.4.
- **An older Claude Code** that does not read `*` inside a rule: the literal denies stay, and the wildcard ones would not apply. Which versions do is not recorded here.
- **What the rules do not match, as the docs say:** `git -C . push origin main`, `git -c ... push`, a quoted `'push'`, an absolute path to `git`, `sh -c '...'`, a plain `git push` on a checked-out `main`. The policy covers them, and the optional `pre-push` hook of `docs/agents.md` refuses them on a machine that installs it.
- **The owner's own settings,** which can allow commit and push locally; they are the owner's file and not tested here.
- **macOS and Windows.**

## Open items

Next in [the plan](plan-after-4.4.0.md): step 3.8, the tests regrouped by component. G3 still waits for the owner's reading of the manual and the decision on how project notes grow.
