# LaTeX AI Workbench

A project kit for AI-assisted LaTeX manuscripts. It gives a paper, or several documents in one
project, one set of commands (`make check`, `make validate`,
`make status`), selects file checks or full document checks, keeps PDFs honest about being stale, and
gives AI coding agents clear rules, including never changing Git without your approval. It needs
Python 3.10+ and `make`; native builds need a TeX toolchain. Zotero, an editor and API keys are optional.

Git is optional. Without it, installation and checks work, and validation selects
all project checks because there is no change history to compare.

Workbench 6 is the supported development line, with schema-4 configuration only.
Earlier experimental releases are retired from support; their historical records
remain available without adding compatibility code to this runtime.

## Start here

Prepare `.latex-ai.json` from [the minimal example](examples/minimal/.latex-ai.json), declaring existing LaTeX roots, then preview installation:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run --diff   # look first
python3 /path/to/workbench/latex-ai-init init /path/to/project                    # then apply
cd /path/to/project && make help
```

Daily commands: `make status`, `make build`, `make check`, `make validation-plan`,
and `make validate`. Preview selected checks after editing, then validate; run
a full check before sharing. Use `make build DOC=name` for one document and `make all` for every document.

See the [workflow diagrams](docs/workflow.md) for the research pipeline, daily loop,
and file/full validation decision.

- [Quickstart](docs/quickstart.md): install, first check, daily loop, when something fails.
- [I want to…](docs/tasks.md): find the command for what you are trying to do.
- In a project, `make guide` prints a short manual written with that project's own documents and command names.

## What a project gets

`init` reads explicitly prepared configuration and installs a project-local runtime,
agent instructions, fixed Make commands, and optional editor tasks. Every project
has one or more LaTeX documents. Shared bibliography/export checks are optional.
The native toolchain is pdflatex/BibTeX; other toolchains use a custom argv command.
`diff` previews generated-file differences; `runtime` refreshes runtime files safely.

## Guides

| Getting started | Reference | Agents and updates |
|---|---|---|
| [Quickstart](docs/quickstart.md) | [Configuration](docs/configuration.md) | [Working with AI agents](docs/agents.md) |
| [I want to…](docs/tasks.md) | [Configuration](docs/configuration.md) | [Agent operating skill](skills/latex-ai-workbench/SKILL.md) |
| [Installing](docs/installing.md) | [Validation routing](docs/validation.md) | [Updating](docs/upgrading.md) |
| [Daily use](docs/daily-use.md) | [Bibliography](docs/bibliography.md) | [Maintainers' material](docs/maintainers/README.md) |
| [Snapshots](docs/snapshots.md) | [TeX notes and named documents](docs/tex-notes.md) | |

The whole `workbench/` directory is relocatable: keep it together, because the installer needs its
sibling templates and backends. Installed projects need only their configuration, the vendored
runtime in `.latex-ai/` and its installation record; builds do not depend on where the distribution lives.

Workbench 6 uses one explicit project configuration (schema 4) and one named-document
execution path. Old Workbench project schemas and migration flags are unsupported.
Each TeX document has its own receipt and PDF export; see the
[mixed notes example](examples/tex-notes/README.md).

Understand the [architecture and state](docs/architecture.md), or find the next
action in [troubleshooting](docs/troubleshooting.md).

Every manuscript build records verified input/output
hashes; PDF collection requires a current receipt. A project's own build
command, such as `make pdf` for a target of its Makefile, is run by `make build` like any other build command.
No particular GNU Make version is required.
Installation refuses conflicting files; it does not adopt an existing Makefile.

For automation, run the installed runtime with `--json`, for example
`python3 .latex-ai/workbench.py check --json` or `status --json`. Check, validate
and status results include status, exit code, diagnostics and structured
details. Plan keeps its native JSON format.
