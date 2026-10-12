# TeX notes and multiple documents

Schema 3 supports named LaTeX documents alongside TeX fragments and Markdown
notes. Each declared document has its own configuration, compiler outputs,
verified build receipt and exported PDF. A fragment included by a document is
checked with that document; it does not need its own document entry.

## Start a TeX notebook

Create the project directory, then preview and apply setup:

```sh
mkdir -p /path/to/notebook
python3 /path/to/workbench/latex-ai-init init /path/to/notebook --profile tex-notebook --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/notebook --profile tex-notebook
cd /path/to/notebook
make latex-ai-doctor
make check
```

This creates `notes/index.tex` as the `notebook` document and includes
`notes/session-state.tex` as an editable fragment. The profile enables LaTeX and
notes, without Pandoc. It uses pdfLaTeX unless you select `--engine lualatex` or
`--engine xelatex`. ChkTeX is enabled by default. Editor and CI integration are
explicit options (`--editor`, `--ci`). An unrelated existing Make `build` recipe
is retained; the new notebook uses its own compiler wrapper.

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

Register it, then build and export it explicitly:

```sh
python3 /path/to/workbench/latex-ai-init configure . --document derivation --root notes/derivation.tex --dry-run --diff
python3 /path/to/workbench/latex-ai-init configure . --document derivation --root notes/derivation.tex
make latex-ai-document-check DOC=derivation
make latex-ai-pdf-artifact DOC=derivation
```

The exported PDF is `.latex-ai/artifacts/documents/derivation/document.pdf`.
Compilation defaults to that document's `build/` subdirectory. Existing custom
layouts can set `output_dir` explicitly. Output identities must not overlap
another document's compiler outputs or any exported PDF.

Use `make latex-ai-documents` to list targets and their validity. Each document is
`current` (its verified build matches its sources), `stale` (sources or build
settings changed since), `failed` (its last build failed or was interrupted),
`running` or `missing` (not built yet). `make latex-ai-status` lists the
documents that are not current and the command for each. An exported PDF is a
copy made by `make latex-ai-pdf-artifact`; rebuilding does not update it.
`make check` checks all documents and enabled shared modules. Build, lint and export without
`DOC` select the configured default. Select a different default with
`configure . --default-document derivation`. Cleanup targets one document and
invalidates its receipt; custom builds keep their own cleanup convention.

## Adopt an existing paper

Every paper is a named document from initial setup. Preview installation on the
existing project, specifying its engine or raw build target where detection
requires clarification. To add a note, create its root and use `configure
--document ID --root PATH`; no schema migration is needed. Custom build output
locations must agree with `output_dir`. Existing Make recipes and authored
sources are preserved; the adapter boundaries below still apply.

## Configure documents and note organization

The LaTeX module declares a `default_document`, optional `defaults`, and a
`documents` object keyed by stable IDs. IDs start with a letter and contain
letters, digits, underscores or hyphens (maximum 64 characters).

Each document needs a `root`. It may override `engine`, `backend`, `lint`,
`output_dir`, `build_command`, `inputs` and `bibliography_files`.
`make latex-ai-bib-check` checks the shared bibliography and every document's own
`bibliography_files`; `DOC=name` checks one document's. Lint defaults
merge field by field. Roots, custom build commands and input declarations belong
to individual documents. Explicit `inputs` are project-relative paths/globs;
each declaration must match an existing file when building. Declare resources
that static traversal or the compiler recorder cannot discover.

The notes module independently selects `path`, `index` and `session_state`.
Entry-point paths resolve inside `path`; defaults remain `index.md` and
`session-state.md`. They can have different formats, for example a Markdown
index and a TeX session-state fragment. New `.md` and `.tex` files have seed
templates; other text formats must already exist. Existing notes remain
project-owned through upgrade and module disable/re-enable. LaTeX checks apply
to declared documents; Markdown checks require the optional Markdown module.

## Validation and integrations

`make latex-ai-plan` lists affected document IDs and the reasons for each. Editing an
input checks every consuming document; unrelated Markdown does not build TeX.
A document whose last build failed stays selected until it builds.
Deleted declared inputs remain selected. Unknown TeX/resources and shared build
policy conservatively select all documents. `make latex-ai-validate` executes
that selection and identifies failed documents, leading with the first TeX
error from the compiler log. When the project's Makefile has its own `check`
rule, it runs `make check` instead so that rule is not skipped. It never runs
scientific tasks implicitly.

Builds are serialized because custom recipes can affect shared files. The
compiler runs in its own process group, recorded as part of the build's
ownership: stopping a build stops its compiler, and if the build's own process
is killed outright, no other build starts until that compiler has exited. Simple
adopted Make builds retain their existing recipe and incremental behavior; GNU
Make 4.3+ and POSIX are required for prepare/finish hooks. The adopted goal's
recipe shell is supervised without replacing the outer dependency graph;
parallel prerequisites, recursive Make jobserver descriptors, `.ONESHELL`,
automatic variables and inherited input are preserved. Target-specific
`SHELL`/`.SHELLFLAGS` overrides need an explicit project adapter. Plain original
build goals still work outside the workbench; they do not create a verified
receipt. Make's `-n`, `-q` and `-t` modes do not create receipt ownership.
Every owned compiler waits for publication of its process identity before
execution. Repeated cooperative interrupts cannot abort its cleanup;
`--json` returns one interrupted result after cleanup. SIGKILL cannot emit JSON,
but recorded live compiler groups keep other builds blocked. Linux liveness
excludes zombies and checks process birth identities. Other platforms retain
portable fallbacks; Windows and macOS behavior still require validation.
Additional targets use explicit
commands. Ambiguous shared custom build ownership needs an explicit adaptation.
Multiple simple adopted commands that share declared Make targets are rejected
until an explicit adapter gives them separate ownership; the workbench does not
silently run a shared prerequisite in two nested Make graphs.
An existing `check` that already runs an additional adopted document also needs
an adapter: its raw prerequisite would otherwise run outside that document's
serialized ownership phase. This includes parent goals such as `all: check note`.
Computed prerequisite ownership is unresolved when additional adopted targets
are registered; an explicit adapter is required.

Editor setup creates named Make tasks and recipes. Automatic builds on
save are disabled in the generated settings so a note save cannot build the
wrong default document. Existing user settings are preserved by the normal
three-way merge. Open the exported PDF for the selected document; no single
global compiler output directory is imposed on mixed layouts.

Generated CI consumes the same selected IDs and project-check decision, checks
each selected document (or the project's complete `make check`) and
uploads separately named PDFs after verification. Source bibliography and
compiler semantics remain authoritative. A successful build establishes current
typesetting outputs, not the scientific correctness of a note.
