# Quickstart

A project needs Python 3.10+, Make, an existing LaTeX root, and explicit schema-4
configuration. Native builds also need latexmk, pdflatex, and ChkTeX; BibTeX is
needed when declared. A custom command can supply another compiler.

## 1. Declare the project

Prepare `.latex-ai.json` using [the minimal example](../examples/minimal/.latex-ai.json):

```json
{
  "schema_version": 4,
  "default_document": "manuscript",
  "documents": {"manuscript": {"root": "main.tex"}},
  "integrations": {"editor": false}
}
```

The root must exist. Declare additional documents, bibliography files, lint settings,
output directories, and custom commands explicitly; nothing is inferred from source.
See [configuration](configuration.md) and [the multi-document example](../examples/tex-notes/README.md).
Set `integrations.editor` to `true` to create VS Code settings and tasks.

## 2. Preview, then install

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/project
```

`latex-ai-init` is a file in the distribution, invoked with Python. Keep that whole
folder together. `init` preserves the configuration and authored sources, refuses
conflicting existing generated files, and never changes Git. Resolve conflicts
explicitly before installing; it does not merge Makefiles, editor files, or policy.
See [installing](installing.md) for limits.

## 3. Inspect and check

```sh
cd /path/to/project
make help
make status
make doctor
make check
```

The fixed command names are the same in every installation. `make check` builds,
verifies, and lints every declared document. Help and status still explain a broken
configuration. For one document use `make document-check DOC=name`.

## 4. Work, then validate

```sh
make validation-plan
make validate
```

Ordinary Markdown/JSON/Python edits receive file checks. Active TeX, figures,
bibliography, build controls, and uncertain inputs select full document checks.
Historical `archive` directories and revision patches stay file-only.
Without a Git repository and comparison history, validation selects full checks. Run `make check` before
sharing. Inspect `git diff`; existing project/session approvals govern Git writes.

## When something fails

An `ERROR:` names an ordinary failure; read its file/tool and any `Hint:`. Fix
compiler, bibliography, and lint findings. The owner may deliberately accept existing
style warnings with `make lint-baseline DOC=name`; never refresh a baseline merely
to hide a new error. See [configuration](configuration.md).

`INTERNAL ERROR` indicates a workbench defect. Capture a local report with
`make issue ISSUE_NOTE="observed ... expected ..."`; nothing is sent anywhere.
Never repair the vendored runtime or disable checks in passing.

For later releases, follow [updating](upgrading.md). Prior schemas are unsupported;
there is no migration or compatibility interface.
