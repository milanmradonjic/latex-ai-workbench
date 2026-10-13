# Working with AI agents

The workbench gives agents one policy (`AGENTS.md`), prompts before Git mutations, and a way to report a suspected fault in the workbench itself. A short orientation for an agent: `make latex-ai-help` lists the project's commands by the names that work there and `make latex-ai-status` says where it stands and what comes next (`make help` and `make status` are the same commands wherever the project had no targets of those names; the policy names the forms that always reach the workbench).

## Writer and reviewer

Codex and Claude can interchange writer/reviewer roles using subscription
authenticated local tools. Preserve existing authentication; the package never
requests credentials or calls an AI API. Start a reviewer through your usual
CLI/editor workflow with the same AGENTS policy, the exact diff, and validation
results. The [review procedure](../skills/latex-ai-workbench/references/review.md)
provides a concrete prompt and distinguishes errors from preferences.

Cross-model review is useful for consequential scientific or structural changes;
it is optional for trivial edits. Do not let the reviewer silently rewrite the
writer's work. Worktree creation, branch changes, commits, integration and
worktree removal require explicit approval. If approval has not been granted,
review the existing working diff without creating a worktree.

## Agent permission guardrails

`.claude/settings.json` and `.codex/rules/git-safety.rules` make the agents prompt
before Git mutations; they are generated from one list and a regression test keeps
them identical and covering what `AGENTS.md` names: staging, committing, pushing,
pulling, merging, rebasing, resetting, restoring, cleaning, stashing, branch
changes and deletion, worktree creation and removal, and history rewriting (plus
neighbours such as `cherry-pick`, `revert`, `rm`, `mv`, `tag`, `update-ref`,
`remote set-url` and `fetch`, which writes objects, `FETCH_HEAD` and remote-tracking
references). Read-only commands (`status`, `diff`, `log`, `show`, `worktree list`,
`remote -v`) stay prompt-free; the allow list holds no Git entry because Claude Code
already runs read-only forms of `git` unasked, and an explicit `git diff:*` allow would
also cover `git diff --output=PATH`.

Pushes that target the default branch are refused outright rather than prompted: `deny`
rules in `.claude/settings.json` and `forbidden` rules in the Codex file cover
`git push [-u|--set-upstream|-f|--force|--force-with-lease] origin <ref>` for `main`, `master`,
`HEAD:main`, `HEAD:refs/heads/main` and their `+` forms. This carries the policy that changes
reach the default branch only through a pull request, where the hosting service cannot
enforce it (branch protection on a private repository needs a paid GitHub plan). An agent
pushes a topic branch and opens a pull request; only the owner merges it, on the hosting
service or from their own terminal, because a pull request its author merges unreviewed
gains nothing over a direct push. Merging is therefore refused too: `gh pr merge` in both
rule files, and the GitHub tools `mcp__github__merge_pull_request` and
`mcp__github__enable_pr_auto_merge` in Claude's `deny` list. Those tool names assume the GitHub
server is registered as `github`; a server under another name needs the same entries under
its name. Codex rules cover shell commands only, so a GitHub tool used through Codex is held
by the policy alone. Not every route is matched: a local `git merge` into `main` followed by
a plain `git push` only prompts, as every merge and push does; the policy covers it, and the
hook below refuses it on your machine.

For enforcement on your own machine, independent of the agent, a local `pre-push` hook can
refuse pushes to the default branch. The workbench never writes Git configuration or hooks,
so install it yourself, in each clone where you want it; it does not bind cloud sessions:

```sh
cat > .git/hooks/pre-push <<'HOOK'
#!/bin/sh
# Refuse pushes to the default branch; merge a pull request instead.
while read local_ref local_sha remote_ref remote_sha; do
  case "$remote_ref" in
    refs/heads/main|refs/heads/master)
      echo "pre-push: $remote_ref is updated only through pull requests" >&2; exit 1 ;;
  esac
done
HOOK
chmod +x .git/hooks/pre-push
```

These are prompts, not a security boundary, and Anthropic's
[permissions documentation](https://code.claude.com/docs/en/permissions) says the same of
Bash ask and deny rules: `git -C . push`, `git -c ... push`, `git 'push'`, an absolute
path to `git` and `sh -c '...'` are not matched. Some gaps are choices, not
impossibilities: `git branch NAME`, `git config` writes and the option-prefixed forms
(`-C`, `-c`, `--git-dir`, `--work-tree`) could be gated, at the price of a prompt on
ordinary inspection such as `git -C dir status`, and Claude rules may put a `*` before the
subcommand. They were left ungated. For enforcement beyond prompts the documentation
points to a `PreToolUse` hook that inspects the full command, or to the sandbox. Aliases
and Git run through a script or program cannot be covered by command rules. `AGENTS.md`
is therefore the policy and these files only supplement it.

## Suspected workbench defects

The workbench tells its own faults apart from ordinary failures. A failed check or a malformed file is reported as `ERROR:` with exit status 1. Anything
else, such as an unexpected exception inside the workbench, is reported as `INTERNAL ERROR`
with exit status 70 and a pointer to the report command (`make` reports the recipe as `Error 70`
but exits 2 itself, so the label is the reliable signal); the traceback is kept in the OS
temp directory, never in the project, so read-only commands stay read-only. (Hand-edited
configuration was fuzzed so that bad data gives a diagnostic and not this label.)

`make latex-ai-issue ISSUE_NOTE="observed ... expected ..." ISSUE_COMMAND="the command"` (or
`python3 .latex-ai/workbench.py issue --note ...`) writes one local file,
`.latex-ai/artifacts/issues/report-*.json` (ignored by Git), holding the version, how the
installed files compare with the manifest, the configuration, the validation plan,
tool versions, Git branch and head, and recent internal faults. It works even when
the configuration is broken or the defect lies in the code that gathers part of the evidence (that
section then records the failure and the rest of the report is still written), never includes
environment variables, and nothing is sent anywhere: review it and pass it to whoever maintains the workbench. `AGENTS.md` tells agents
what counts as a suspected defect, to stop trusting that verdict, never to edit `.latex-ai/`
or weaken a check, to capture a report and tell you; a repair belongs in the distribution,
with a failing test first and an independent review. The long name is the one the installer
always provides: a project's own `issue` target is kept, so the short `make issue` is only an
alias where nothing else uses that name, and the guidance never relies on it.

This catches faults that announce themselves. A plausible wrong result that passes every check
does not, which is why the review of a change matters more than any flag.
