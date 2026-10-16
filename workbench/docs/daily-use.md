# Daily project work

The [workflow diagrams](workflow.md) show the daily loop and how validation fits
between research, manuscript edits, review, and PDF export.

Read AGENTS and config, then start with `make status`. If you cannot place something,
`make guide` prints a short manual for this project. Edit authored files,
preview the selected checks, and validate:

```sh
make status
make validation-plan
make validate
git diff --check
git diff
git status --short --branch
```

Bare `make` builds the default document; `make all` builds every document one after another.
Use `make build DOC=name` for a selected document. `make check` checks all declared
documents. Command names are fixed; local overrides are the project's responsibility.

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

Before a risky change (an update, a large edit, an agent let loose on the files) run `make snapshot`: it keeps a copy of every file outside the project, with or without
Git, and `make snapshots` says how to restore from it. See [snapshots](snapshots.md).

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

