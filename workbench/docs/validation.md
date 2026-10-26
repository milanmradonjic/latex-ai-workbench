# File or full validation

See the [graphical workflow and decision tree](workflow.md#what-validation-selects)
for an overview of the two levels.

After a task, use the canonical project interface:

```sh
make validate         # run that selection
make validation-plan  # optional: explain the level and paths without running checks
make check            # explicitly check every declared document
```

`validate` has two levels. **Files** runs lightweight checks on the changed paths
and applicable policy structure. **Full** runs those checks and invokes `make check`
once. The project owns that command, so its additional checks run too. Full checks
cover all named documents; use `make document-check DOC=name` for an explicit
single-document check. Each document's build runs again: latexmk recompiles only
what changed, while a configured `build_command` is invoked every time (keep its
work incremental if it is expensive). The [freshness hint](configuration.md#build-receipts-and-recovery)
lets a cooperating builder distinguish permitted reuse from required regeneration.
Reference verification and configured lint run too. `make validate` prints its
plan, so a separate preview is normally unnecessary.

## Fixed routing rules

| Changed path | Level |
|---|---|
| A path `.latex-ai.json` names: a document root, bibliography file or export, lint baseline, or recognised build-command file | Full, wherever it lives |
| Inside an `archive` directory at any depth | Files, regardless of extension |
| `.diff` or `.patch` | Files; text integrity only |
| Active build controls | Full |
| Agent policy, permissions, or skills | Files plus policy structure and agent/human semantic review |
| Ordinary Markdown, JSON, Python, text, YAML or TOML | Files; use task-specific tests when relevant |
| TeX, bibliography, classes/styles, potential figures, CSV/TSV data | Full |
| Unclassified paths | Full |

`archive` is an exact, case-sensitive directory component. Thus
`revision/archive/old.tex` and `archive/Makefile` get file checks, while
`archive-old/main.tex`, `Archive/main.tex` and `revision/baseline/old.tex` select
Full. Archives are historical reference material by convention. Copy or move a
historical file out of the archive before making it an active build input; the
planner does not prove an unnamed file is unused. A path the configuration names
is active even inside an archive, so a lint baseline in `lint/archive/` is still
checked. That includes a file matched by a document's `inputs` patterns, whatever
its suffix (a declared `data/params.json` selects Full), and a path spelled with
`..` or reached through a link, which is compared in its resolved spelling.
(Workbench 6.0 also exempted `baseline` directories; 6.1 does not.)

Active build controls include Makefiles, `.latex-ai.json`, latexmk/ChkTeX
configuration, configured lint baselines, the vendored `.latex-ai/` runtime,
`.vscode/` integration, and recognised local executable/script/Makefile paths
in configured `build_command` arguments. A configured `scripts/build_documents.py`
therefore selects Full, even when deleted, while an ordinary analysis script does
not. This recognition does not interpret Python or recursively discover scripts.

Routing does not inspect TeX source dependencies, compiler recorder files, or
input aliases. Ordinary Markdown, JSON and Python remain file-only even if TeX
mentions them. This workflow transfers results deliberately into TeX or figure
files. Build dependency tracking, input declarations, receipts, and safe export
still protect actual document inputs independently of routing.

There are no project-level `validation` settings. Removed `ignore`,
`manuscript_inputs`, and `package` declarations are refused with a hint. Document
`inputs` remain available for custom/hidden build dependencies, not routing.
No file watcher or general save hook is installed.

## Comparison and recovery

By default, Git discovery includes staged and unstaged changes against HEAD,
untracked non-ignored paths, deletions, and both sides of renames. To include
committed work, use a verified comparison revision:

```sh
LATEX_AI_BASE=origin/main make validation-plan
LATEX_AI_BASE=origin/main make validate
```

Queries leave history, references and the index contents unchanged. Git diff uses
a throwaway index copy. With a split index, Git may refresh the shared index's
modification time, but its contents stay unchanged.

Missing Git/history or an invalid/all-zero base selects Full with an explanation,
and the file checks then read every project file (Git's listing where there is a
repository, otherwise a walk that skips generated trees and environments).
A clean comparison selects no manuscript check. A previous failed/interrupted build
selects Full until it succeeds, even when the source has been reverted. A mixture
of file-only and full-triggering changes selects Full. `DOC` does not narrow a
plan or validation; explicit document commands remain available.

The runtime also accepts `plan --files PATH ...` and `validate --files PATH ...`
for a precise explicit scope, including deleted/renamed paths. The caller owns
its completeness. `validate --files-only` runs the lightweight checks without a
manuscript build. `plan --json` exposes `level`, `paths`, `reasons`, `policy`,
`fallback`, `documents`, `failed_documents`, and ordered `actions` (`[]` or
`["full"]`); it does not expose per-document dependency reasons or package scheduling.

## What the checks establish

Lightweight checks reject NULs and unresolved conflict markers, parse supported
JSON/Python/rule files, check ordinary local inline Markdown links outside fenced
examples, and check canonical policy/delegation structure when selected. Patch
contents receive text-integrity checks without parsing their embedded code.
Binary PDFs are not inspected by file checks. These checks do not validate all
YAML/TOML schemas, run numerical tests, prove policy semantics, or establish science.

`make check` builds each document as needed, checks text integrity of known
manuscript inputs, verifies compiler/reference/citation results and bibliography
processing, and runs configured ChkTeX lint. It reports failures for every document.
It does not automatically rerun scientific calculations, render figures or update
delivery PDFs unless the project's own explicit build/check contract does so.
Figure changes also need visual review.

## Distribution tests

Installed projects do not locate nested Workbench packages or schedule their tests.
Maintainers and CI invoke the distribution's commands explicitly:

```sh
make -C workbench test
make -C workbench portability
make -C workbench check  # both
```

Required Python-matrix jobs run the unit suite; the compiler job runs portability
and the reference manuscript check. These are independent of change classification.
