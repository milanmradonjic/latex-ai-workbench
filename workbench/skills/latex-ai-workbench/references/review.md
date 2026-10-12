# Independent review and human handoff

## Review a writer's diff

Identify the exact baseline/current diff and which changes predate the writer.
Use read-only Git commands. Read AGENTS, configuration, Make, changed TeX and
enough adjacent definitions/macros to understand the claims. Inspect related
labels/citations and bibliography provenance. Preview validation using the
verified review baseline (`LATEX_AI_BASE=<revision> make validation-plan`), then
run the selected checks when permitted. Use `make check` for manuscript/build
changes or when dependency uncertainty warrants it. When execution is not
permitted, assess concrete supplied validation output with its limitations.

Review separate categories:

| Category | Questions |
|---|---|
| Correctness | Does the requested behavior/content hold? Are definitions and consumers consistent? |
| Science/mathematics | Are assumptions, units, signs, derivations and limiting cases sound? What needs source evidence? |
| LaTeX/build | Does canonical validation pass? Are logs and PDF outputs consistent with config? |
| Citations | Are keys resolved, entries genuine and generated files respected? Does the source support the claim? |
| Local style | Are existing macros, notation and formatting preserved? |
| Scope | Were unrelated changes or configuration weakening introduced? |
| Preference | Is a suggestion merely taste with no demonstrated problem? |

Prioritize actionable findings with a file/line, concrete consequence, evidence
and smallest reasonable correction. Distinguish verified errors, plausible
concerns needing evidence and optional preferences. A clean build does not
prove the equations or references correct. Report no findings when justified;
do not manufacture objections to demonstrate activity.

A reviewer normally reports findings without editing. Writer fixes are scoped
to accepted findings; rerun relevant validation when fixes change source.
If the review request explicitly includes repair, keep edits attributable and
do not overwrite a concurrent writer's work.

## Cross-model prompt

Either model may use this handoff, through a user-authorized local CLI/editor
or chat workflow. Do not send it to another chat or service unless authorized.

```text
Review the specified working diff independently. Read this project's AGENTS.md
and .latex-ai.json first. The intended change is: [concrete scope]. The baseline
is: [verified revision or working-diff boundary]. Existing user changes are:
[paths/context]. Validation performed: [commands, results, warnings].

Do not edit files or mutate Git. Evaluate correctness, scientific/mathematical
reasoning, LaTeX/build integrity, bibliography/citations, local style and scope.
Separate demonstrated errors, uncertainties requiring evidence and optional
stylistic preferences. Cite precise locations and consequences. Select validation
from the actual changed files and verified baseline; use make check for manuscript
inputs/build changes. Do not rebuild for ordinary docs-only work. If execution
is permitted, run the selected deterministic checks. Report unresolved
assumptions and verification limits.
```

Keep credentials and private unrelated content out of the prompt. Prefer the
user's existing subscription login; do not introduce API-key dependencies or
require both models for every edit.

## Parallel agents and worktrees

Use parallel writers only when the user authorizes delegation and there is
useful independent scope. Worktrees are a Git mutation under this workbench's
policy. Prepare concrete base, branch and destination choices and obtain
approval before creating one. Read `git worktree list` first; reuse a suitable
authorized tree when possible. Do not create branches or remove old agent
worktrees autonomously.

Choose a verified committed base. A new worktree does not include uncommitted
user changes; explain that constraint and keep those changes in place. Do not
secretly commit or stash to move them. Assign nonoverlapping tasks and shared
semantic policy. Each writer validates its own tree. Review combined changes
for label/key/macro collisions and scientific consistency before integration.

Cherry-picking, merging, committing, branch changes and removing worktrees need
explicit authorization for that step. Preserve every writer's result until
integration is reviewed; use diffs for a read-only combined review when Git
mutations have not been approved. Worktree cleanup never discards unreviewed
or untracked user work.

## Prepare approval

Present a concrete change, affected paths, canonical check results, important
warnings, review findings addressed and remaining scientific assumptions.
Inspect final diff/status and distinguish your work from pre-existing changes.
State the exact Git or external action requiring approval only after the
change is ready. Do not stage, commit, push or publish as part of preparing it.

When blocked on a desktop action, name the exact app, one action, value/path,
and result to report; preserve the rest of the completed work. Resume from
that checkpoint when the user reports the result.
