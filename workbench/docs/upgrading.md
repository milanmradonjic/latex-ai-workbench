# Updating a project

An installed project is updated by an agent (or you) following this recipe. The installer does not merge, audit or recover:
it creates a project, shows how a project differs from a release, and refreshes the runtime files it vendored. Everything
else is text you read and edit, with a diff to check it. Project configuration schema 3 only is accepted; an older schema is
refused with a hint, and nothing is converted.

## The recipe

1. **Be able to undo.** `git status` is clean, or your work is committed on a branch: that is the snapshot to return to
   (a rolling `make snapshot` is planned; see [the minimal scope](maintainers/minimal-scope.md)).
2. **Read what changed.** `.latex-ai/installation.json` and `make status` give the project's version; the
   [release notes](maintainers/releases.md) say what each release since changed. A removed setting is refused by name, with a hint.
3. **See the difference.** From the new release's directory:

   ```sh
   python3 /path/to/new-workbench/latex-ai-init diff /path/to/project --diff
   ```

   It lists the runtime files that differ (`RUNTIME differs` or `missing`) and the other files (policy, Makefile, editor settings)
   that differ from what a new project would get. It writes nothing; it exits 1 when a runtime file differs.
4. **Refresh the runtime.**

   ```sh
   python3 /path/to/new-workbench/latex-ai-init runtime /path/to/project --dry-run
   python3 /path/to/new-workbench/latex-ai-init runtime /path/to/project
   ```

   It replaces `.latex-ai/*.py`, backs the old files up under `.latex-ai/backups/`, and rewrites the record. A runtime file
   that was edited, or that the record does not know, is refused; restore it from version control, or `--force` to replace it
   (the runtime is not meant to be edited: report a defect with `make issue` instead).
5. **Read, then edit, the files that are yours.** `AGENTS.md`, `CLAUDE.md`, the Makefile, `.gitignore`, `.vscode/` and the
   guardrails (`.claude/`, `.codex/`) belong to the project. Take over what the diff shows as new and wanted; never weaken a
   permission or a Git guardrail, keep the stricter rule when two differ, and do not paste over local content.
6. **Edit `.latex-ai.json` by hand** where the release notes say a setting changed. To turn a module on, add it to `"modules"`; to
   turn it off, remove it (its files stay).
7. **Check.** `make doctor`, then `make check`, then `git diff`. Report what changed and what did not run. Commits and pushes
   are the owner's separate step.

## When something goes wrong

Backups are plain files under `.latex-ai/backups/<time>/`; compare before restoring one. Do not run `git restore`, `reset` or
`clean` as recovery without the owner's say-so, and do not delete `.latex-ai/installation.json` to get past a refusal. `init`
refuses a project that has the record: to start over, ask the owner.

Document receipts have one format; one that is unsupported or damaged never certifies a PDF, and the next build writes a new one.

## Maintainers

`make -C workbench audit-reference` runs `diff` against the reference project, `make -C workbench upgrade-reference` runs
`runtime` on it, and `make -C workbench test` checks that the two agree. They make no Git changes.
