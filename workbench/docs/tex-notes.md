# TeX notes and multiple documents

Schema 4 supports named LaTeX documents alongside TeX fragments. Each declared document has its own configuration, compiler outputs,
verified build receipt and exported PDF. A fragment included by a document is
checked with that document; it does not need its own document entry.

## Add an independent note

Create a complete TeX document, for example `notes/derivation.tex`:

```tex
\documentclass{article}
\usepackage{amsmath}
\begin{document}
\section*{Derivation}
Write the derivation here.
\end{document}
```

Register it by adding it under `documents` in `.latex-ai.json`:

```json
"derivation": {"root": "notes/derivation.tex"}
```

Build, check, and export with the fixed commands. `make all` builds every document;
no Makefile edits or document-name targets are needed when a document is added.

```sh
make build DOC=derivation
make document-check DOC=derivation
make pdf-artifact DOC=derivation
```

The exported PDF is `.latex-ai/artifacts/documents/derivation/document.pdf`.
Compilation defaults to that document's `build/` subdirectory. Existing custom
layouts can set `output_dir` explicitly. Output identities must not overlap
another document's compiler outputs or any exported PDF.

Use `make documents` to list targets and their validity. Each document is
`current` (built from these exact files without a LaTeX error; it does not mean the
checks passed), `stale` (files or build settings changed since it was built), `failed` (its last build failed or was interrupted),
`running` or `missing` (not built yet). `make status` lists the
documents that are not current and the command for each. An exported PDF is a
copy made by `make pdf-artifact`; rebuilding does not update it.
`make check` checks all documents and their bibliography declarations. Build, lint and export without
`DOC` select the configured default. Select a different default with
`default_document` in `.latex-ai.json`. Cleanup targets one document and
invalidates its receipt; custom builds keep their own cleanup convention.

## Bring in an existing paper

Every paper is a named document from initial setup. Prepare explicit configuration before
[installing](installing.md); existing generated-file conflicts must be resolved first. To add a note,
create its root and add it under `documents` in `.latex-ai.json`; no schema migration is needed. Custom build output
locations must agree with `output_dir`.

## Configure documents and note organization

The project configuration declares a `default_document`, optional `defaults`, and a
`documents` object keyed by stable IDs. IDs start with a letter and contain
letters, digits, underscores or hyphens (maximum 64 characters).

Each document needs a `root`. It may override `backend`, `lint`,
`output_dir`, `build_command`, `inputs` and `bibliography_files`.
`make bib-check` checks the shared bibliography and every document's own
`bibliography_files`; `DOC=name` checks one document's. Lint defaults
merge field by field. Roots, custom build commands and input declarations belong
to individual documents. Explicit `inputs` are project-relative paths/globs;
each declaration must match an existing file when building. Declare resources
that static traversal or the compiler recorder cannot discover.

## Validation and integrations

`make validation-plan` explains file checks or full validation. Full validation
runs the project's `make check` once and checks every declared document. Ordinary
Markdown/JSON/Python, historical `archive` directories, and revision patches
receive lightweight checks. A failed/interrupted build selects the full project
until it succeeds. Routing does not scan source or recorder dependencies; build
receipts and declared inputs still track actual build freshness. Use explicit
`make document-check DOC=name` when you deliberately want one document. See
[validation](validation.md) for the fixed rules and comparison scope.

Builds are serialized because custom recipes can affect shared files. The
compiler runs in its own process group, recorded as part of the build's
ownership: stopping a build stops its compiler, and if the build's own process
is killed outright, no other build starts until that compiler has exited. A build command that is a
`make` goal of the project's own Makefile runs like any other build command; whether it is incremental is Make's doing,
and a run that changes nothing is accepted only when a verified receipt vouches for the outputs. Make's `-n`, `-q` and `-t` modes
never reach the build, because the workbench's own recipes do not run under them.
Every owned compiler waits for publication of its process identity before
execution. Repeated cooperative interrupts cannot abort its cleanup;
`--json` returns one interrupted result after cleanup. SIGKILL cannot emit JSON,
but recorded live compiler groups keep other builds blocked. Linux liveness
excludes zombies and checks process birth identities. Other platforms retain
portable fallbacks; Windows and macOS behavior still require validation.
Additional targets use explicit commands.

Editor setup creates named Make tasks and recipes. Automatic builds on
save are disabled in the generated settings so a note save cannot build the
wrong default document. Existing user settings are preserved by leaving editor integration disabled when files conflict. Open the exported PDF for the selected document; no single
global compiler output directory is imposed on mixed layouts.

Source bibliography and
compiler semantics remain authoritative. A successful build establishes current
typesetting outputs, not the scientific correctness of a note.
