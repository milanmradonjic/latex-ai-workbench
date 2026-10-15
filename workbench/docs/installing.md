# Installing and limits

Start with [quickstart](quickstart.md). Prepare `.latex-ai.json` before invoking
`init`; only schema 4 is supported. Every project declares at least one LaTeX
root and its default document. Bibliography checking and editor integration are
optional settings within that project. Non-LaTeX and standalone bibliography
projects are unsupported.

## Explicit configuration

Use [the minimal example](../examples/minimal/.latex-ai.json) or the
[multiple-document example](../examples/tex-notes/.latex-ai.json). Installation
validates exactly those declarations. It does not search for roots, add bibliography files to configuration, inspect
engine hints, or choose a toolchain. Source and recorder dependency tracing still
protects actual build inputs during checks. Set another compiler through a
document's `build_command` argv and matching `output_dir` in configuration.
See [configuration](configuration.md) for all fields and custom-build limits.

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/project
make -C /path/to/project doctor
make -C /path/to/project check
```

The only init switches are previews (`--dry-run`, `--diff`) and structured output
(`--json`). Document, bibliography, lint, and editor choices belong in the file.
Missing/invalid declarations fail before installation writes. The installer never
creates manuscript content or initializes Git.

## Files and conflicts

`init` creates absent files and accepts identical files. Any differing destination
is a `CONFLICT` and no planned installation is applied. Existing Makefiles and editor
files are not adopted or merged. Choose a fresh directory or resolve conflicts
explicitly while preserving local content and guardrails. Set `integrations.editor`
to `false` when editor files should remain wholly project-managed.

The generated file is named `Makefile`; an existing `GNUmakefile` or `makefile` is
also a conflict because Make would read it instead. Workflows are never generated
or changed. After installing, projects may append their own targets. Public
workbench targets have fixed names, without aliases or generated document-name
rules; local overrides are the project's responsibility.

## Runtime and refresh

Keep the distribution folder intact for installation. Every project receives the
same standalone runtime in `.latex-ai/`, plus an installation record containing
version and file digests. Builds do not need the original distribution location.
Python 3.10+ and Make are required; Git metadata is optional. No particular GNU
Make version is required. Editor tasks and CI use the canonical Make interface.

An installed project is refused by `init`. `latex-ai-init diff PROJECT --diff`
compares it with a release without writing; `latex-ai-init runtime PROJECT`
refreshes runtime files with backups and refuses locally edited files unless
explicitly forced. See [updating](upgrading.md). No old-schema conversion is provided.

Exit statuses: 0 is success or a safe preview; `diff` returns 1 for differing runtime
files; 2 means conflicts or invalid input; 70 means an `INTERNAL ERROR`. Preview and
diff never execute project builds. Custom scripts and TeX are not sandboxed by
configuration validation; declare their actual inputs and outputs.
