# Daily project work

The [workflow diagrams](workflow.md) show the daily loop and how validation fits
between research, manuscript edits, review, and PDF export.

At session start, read AGENTS and config and use `make status`. If you cannot place something,
`make guide` prints a short manual for this project. Edit authored files,
and validate when the requested edits are complete:

```sh
make status    # at session start
make validate  # when the requested editing batch is complete
```

Bare `make` builds the default document; `make all` builds every document one after another.
Use `make build DOC=name` for a selected document. `make check` checks all declared
documents. Command names are fixed; local overrides are the project's responsibility.

During an editing batch, `make build DOC=name` updates the active PDF for preview.
An agreed batch may contain several edits and previews; run `make validate`
before delivering it or handing work to Git. A single editing request ends its
batch at delivery. A successful preview does not mean lint or full validation
passed. Use `make validation-plan` separately only when its preview affects a
decision; `make validate` already explains the selected checks.

For agent sessions, keep complete compiler output in a generated log, preserve
the exit status, and report the result, relevant warnings, and failure context.
Reuse inspected policy, configuration, and tool information until it changes or
the context becomes unreliable. A preview is optional; do not run a separate
build, check, or planning command immediately before `make validate` merely to
repeat work that validation already performs. Questions need repository/tool
inspection only when the answer depends on that state.

## Git inspection during successive edits

At the start of an editing session, inspect the branch, status, and relevant
staged/unstaged diffs. The session may span several requests in the same chat;
answering one request, previewing a PDF, or completing its validation batch does
not automatically require a new Git checkpoint.
Known uncommitted manuscript work does not block requested edits or require
another inspection.

Before every edit, read the current target passage and patch it narrowly. This
protects concurrent manuscript edits without repeatedly dumping the repository
diff. Refresh relevant Git checks when context is stale, a branch/index change is
indicated, scope expands, unexpected changes appear, or before an approved
Git mutation sequence. At session completion or Git handoff, inspect the relevant diff,
`git diff --check`, and status. Keep existing user changes distinct from yours.
The project's existing approval rules for Git mutations still apply.
Validation may still read Git to discover changed files; this policy removes
repeated agent inspections without changing validation's dependency on Git.

Keep local notation, formatting, structure, and citation keys. Notes, Markdown,
scripts, and other project files can be edited normally alongside the manuscript.

`make validate` selects checks from the changed files; ordinary docs-only edits
skip manuscript compilation. Policy edits need structure checks and semantic
review; unrelated code needs its own relevant tests. Workbench maintainers run
their tests through the explicit package Make/CI commands; build/control changes get full checks. See
[validation routing](validation.md) for inputs, baselines, conservative
fallbacks. No general save hook or watcher is added.

`make check` runs the bibliography preflight and the build, then the compiler-log
integrity checks, then lint (so a TeX error is reported even when ChkTeX also objects; its warnings fail the check, except those a
[lint baseline](configuration.md#accepting-existing-style-warnings) lists as accepted). `make build` builds only; `make lint` runs configured ChkTeX;
`make bib-check` checks bibliography boundaries/keys/export readiness;
`make doctor` reports required tools; `make pdf-artifact` collects the configured
PDF. `make check` validates bibliography and compiler results.

Use the project's Git history for version recovery. Ordinary edits and upgrades
need neither snapshots nor new commits. A large change may warrant an explicitly
approved checkpoint commit. [Snapshots](snapshots.md) are an optional working-copy
backup selected with `"snapshots": true` at setup; they are off by default.

Do not clean routinely. Build logs, unresolved citations, references, duplicate
labels and bibliography/backend failures are errors. Typesetting and unrelated
package warnings are reported for judgment. Checks do not establish scientific
truth, freshness against Zotero, or completeness of bibliographic metadata.

## Named TeX documents

`make documents` lists targets and current build validity.
Use `make document-check DOC=NAME` to check one document and
`make pdf-artifact DOC=NAME` to export its current PDF. `make check`
covers all declared documents. See [TeX notes](tex-notes.md).

For live or abandoned builds, status
shows the owner and compiler groups; follow [recovery guidance](troubleshooting.md)
before stopping processes. Use each project's own Makefile/runtime from its root.

