# Updating a project

An installed project is updated by an agent (or you) following this recipe. The installer does not merge, audit or recover:
it creates a project, shows how a project differs from a release, and refreshes the runtime files it vendored. Everything
else is text you read and edit, with a diff to check it. Project configuration schema 4 only is accepted; an older schema is
refused with a hint, and nothing is converted.

## The recipe

The agent follows [the update recipe in the skill file](../skills/latex-ai-workbench/references/installation.md#update), which is the one copy. In short:

1. **Be able to undo:** `make snapshot` ([snapshots](snapshots.md)), or the new release's `runtime.py snapshot --project PROJECT` for a project that has no such target yet.
2. **Read what changed:** `make status` (or `make doctor`) shows the project's version stamp, and the [release notes](maintainers/releases.md) say what each release since changed.
3. **See the difference:** the new release's `latex-ai-init diff PROJECT --diff` (or `make doctor LATEX_AI_TEMPLATE=/path/to/new-workbench`). It writes nothing.
4. **Refresh the runtime:** `latex-ai-init runtime PROJECT`, which backs up what it replaces; an edited runtime file is refused.
5. **Read, then edit, the files that are the project's own** (`AGENTS.md`, the Makefile, `.vscode/`, the guardrails), and `.latex-ai.json` where the notes say a setting changed.
6. **Check:** `make doctor` with the template, then `make check`, then `git diff`, for the owner to read. Commits and pushes are the owner's separate step.

## When something goes wrong

Backups are plain files under `.latex-ai/backups/<time>/`; compare before restoring one. Do not run `git restore`, `reset` or
`clean` as recovery without the owner's say-so, and do not delete `.latex-ai/installation.json` to get past a refusal. `init`
refuses a project that has the record: to start over, ask the owner.

Document receipts have one format; one that is unsupported or damaged never certifies a PDF, and the next build writes a new one.

## Maintainers

`make -C workbench audit-reference` runs `diff` against the reference project, `make -C workbench upgrade-reference` runs
`runtime` on it, and `make -C workbench test` checks that the two agree. They make no Git changes.
