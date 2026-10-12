# Version 3.0.4 verification

This records the pull-request policy release, tested on 2026-10-12 in a Linux container
(Python 3.13, GNU Make 4.3, no TeX). Hosted CI must be checked on the pull request that
carries it.

| Check | Result |
|---|---|
| `tests/test_repairs_3_0_4.py` against 3.0.3 | All 3 tests failed: the policy text was absent, and there were no `deny` / `forbidden` rules |
| `test_agents_cannot_merge_pull_requests_themselves`, added after review of the first commit of the pull request | Failed on that commit: no merge rules, and the policy lacked the "only the owner merges" sentence; passes now |
| The same tests after the change | Pass |
| `make -C workbench test` | 369 passed, 21 skipped (20 need TeX; 1 needs the real GNU Make 3.81) |
| Claude Code honouring the GitHub-tool `deny` entries | Observed: when the reference's `.claude/settings.json` gained them, the running Claude Code session that wrote this change lost `mcp__github__merge_pull_request` and `mcp__github__enable_pr_auto_merge` from its tools |
| Guardrail parity (`test_agent_guardrails_agree_and_cover_every_git_operation_the_policy_names`) | Extended: both agents refuse the same set of pushes and prompt on the same set of commands; only pushes are refused |
| Reference upgraded with `latex-ai-init upgrade ..` | `AGENTS.md`, `.claude/settings.json` and `.codex/rules/git-safety.rules` updated through the installer; `audit` reports it current |
| `validate --files-only` in the reference | Pass, including the policy structure check |
| The `pre-push` hook shown in `docs/agents.md`, in a scratch clone with a bare remote | Refuses `git push origin main` and `git push origin HEAD:main`; allows a topic branch |

## Not verified

- **Claude Code.** Not checked: that it refuses the denied *shell* commands (`git push origin main`, `gh pr merge`) in every permission mode. The GitHub-tool entries were observed to take effect (above).
  The rules follow the existing `Bash(...)` / `Bash(...:*)` syntax of the same file.
- **Codex.** Not checked: its handling of `decision = "forbidden"`. Its rules cover shell commands only, so a GitHub tool used through Codex can merge if the owner's Codex configuration allows the tool.
- **GitHub tool names.** The `mcp__github__...` entries assume the GitHub server is registered as `github`.
- **Coverage limits.** Prefix rules do not match every spelling (`git -C . push origin main`,
  a plain `git push` on a checked-out `main`). The policy text covers those cases.
