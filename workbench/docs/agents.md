# Working with AI agents

The workbench gives agents one policy (`AGENTS.md`), prompts before Git mutations, and a way to report a suspected fault in the workbench itself. A short orientation for an agent: `make help` lists the project's commands by the names that work there and `make status` says where it stands and what comes next (`make help` and `make status` are the same commands wherever the project had no targets of those names; the policy names the forms that always reach the workbench).

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
before the Git commands that write history, branches or the working tree; a regression
test keeps the two files identical and covering what `AGENTS.md` names: committing, pushing,
pulling, merging, rebasing, resetting, restoring, cleaning, stashing, branch
changes and deletion, worktree creation and removal, and history rewriting (plus
neighbours such as `cherry-pick`, `revert`, `rm`, `mv`, `tag`, `update-ref`, `init`, `clone`
and `remote set-url`). Staging (`git add`) and `git fetch` do not prompt: they change no commit, no
branch and no file of the working tree, and the commit or merge that follows does prompt.
Read-only commands (`status`, `diff`, `log`, `show`, `worktree list`,
`remote -v`) stay prompt-free; the allow list holds no Git entry because Claude Code
already runs read-only forms of `git` unasked, and an explicit `git diff:*` allow would
also cover `git diff --output=PATH`. In a workbench session of this repository the agent's own
commits and pushes to a topic branch need no prompt of the owner's, once the task's work is done:
that is a line of `AGENTS.md`, not a rule in these files, which keep their prompts for every project.

Pushes that target the default branch are refused outright rather than prompted: `deny`
rules in `.claude/settings.json` and `forbidden` rules in the Codex file cover
`git push [-u|--set-upstream|-f|--force|--force-with-lease] origin <ref>` for `main`, `master`,
`HEAD:main`, `HEAD:refs/heads/main` and their `+` forms. Claude's file adds wildcard rules
(`git push * main`, `git push *:main`, `git push *:refs/heads/main`, with and without arguments after
them, and the same for `master` and the `+` forms), which refuse any remote, any option and any source:
`git push upstream feature:main` is refused. Codex rules match whole words, so there it only prompts,
as every push does. This carries the policy that changes
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

## Optional: standing approval to refresh a lint baseline

By default `AGENTS.md` makes every refresh of a lint baseline the owner's decision: ask first, and never do it to
get a passing check. That is the right default, and the workbench does not change it. It does cost a question each
time an ordinary edit makes an already accepted warning look new. A baseline entry is identified by the file, the
ChkTeX warning number and the full text of the source line, so editing, reflowing or moving a line makes its
old warning "new" although nothing about it changed.

An owner who is willing to let agents handle that case can say so in the project's own `AGENTS.md`, replacing the
sentence about the baseline. The clause below comes from a real manuscript project and is offered as a
starting point; it grants nothing unless you copy it in, and you should edit it to your own conventions.

```markdown
A document's configured lint baseline lists the style warnings the owner accepted.
Warnings are matched by file, warning number, and full source-line text, so an
edit can make an unchanged offending construct appear new. Prefer straightforward
source fixes for genuine warnings rather than accepting them into the baseline.

The owner grants standing approval to refresh an existing ChkTeX baseline without
further confirmation when all of the following conditions hold:

- Every added or changed entry is an unchanged, previously accepted warning on
  an edited, reflowed, or moved line, or a verified false positive for a local
  typographic convention already accepted by the owner. Compare the warning
  number, message, offending construct, context, and occurrence count with the
  previous source and baseline. A familiar warning number alone is insufficient;
  explain any increase in occurrences individually. Obsolete entries may be
  removed when their warnings no longer occur.
- The diagnostics have been reviewed for their actual meaning. The refresh
  accepts no unresolved TeX, mathematical, citation/reference, or scientific
  problem. Compilation and text/reference integrity checks must pass; inspect
  the rendered output when the warning or edit could affect typography or layout.
- Every current warning in the affected document is already accepted or meets
  these conditions: `make lint-baseline` captures all current warnings, so it
  must not sweep unrelated or unreviewed diagnostics into the baseline.
- Use `make lint-baseline DOC=name`, inspect the baseline diff against the
  reviewed diagnostics, and finish with `make validate`. Report what was newly
  accepted or matched again, what was removed, and any remaining failures.

Creating a baseline, accepting a genuinely new warning or local convention,
changing lint settings, or disabling checks still requires explicit approval.
If a warning's safety or provenance is uncertain, fix it or obtain the owner's
decision before refreshing that document. Never accept an unreviewed or
substantive diagnostic merely to make a check pass.
```

The clause keeps the rule that matters: a baseline is never refreshed to make a check pass. It only moves the
question from "may I refresh?" to "does this refresh meet the four conditions?", which the agent must show in its report. It does not touch
the Git rules above; committing the refreshed baseline still needs the owner's approval. Do not
weaken the guardrail files for this: it is a line of `AGENTS.md`, like the topic-branch line mentioned earlier.

## Suspected workbench defects

The workbench tells its own faults apart from ordinary failures. A failed check or a malformed file is reported as `ERROR:` with exit status 1. Anything
else, such as an unexpected exception inside the workbench, is reported as `INTERNAL ERROR`
with exit status 70 and a pointer to the report command (`make` reports the recipe as `Error 70`
but exits 2 itself, so the label is the reliable signal); the traceback is kept in the OS
temp directory, never in the project, so read-only commands stay read-only. (Hand-edited
configuration was fuzzed so that bad data gives a diagnostic and not this label.)

`make issue ISSUE_NOTE="observed ... expected ..." ISSUE_COMMAND="the command"` (or
`python3 .latex-ai/workbench.py issue --note ...`) writes one local file,
`.latex-ai/artifacts/issues/report-*.json` (ignored by Git), holding the version, how the
installed files compare with the record, the configuration, the validation plan,
tool versions, Git branch and head, and recent internal faults. It works even when
the configuration is broken or the defect lies in the code that gathers part of the evidence (that
section then records the failure and the rest of the report is still written), never includes
environment variables, and nothing is sent anywhere: review it and pass it to whoever maintains the workbench. `AGENTS.md` tells agents
what counts as a suspected defect, to stop trusting that verdict, never to edit `.latex-ai/`
or weaken a check, to capture a report and tell you; a repair belongs in the distribution,
with a failing test first and an independent review. The fixed report command is
`make issue`; a local override of that target is the project's responsibility.

This catches faults that announce themselves. A plausible wrong result that passes every check
does not, which is why the review of a change matters more than any flag.
