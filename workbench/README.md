# LaTeX AI Workbench

A project kit for AI-assisted LaTeX manuscripts. It gives a paper, or several documents in one
project, one set of commands (`make check`, `make validate`,
`make status`), runs only the checks your changes need, keeps PDFs honest about being stale, and
gives AI coding agents clear rules, including never changing Git without your approval. It needs
Python 3.10+ and `make`; TeX, Zotero, an editor and API keys are optional.

Git is optional. Without it, installation and checks work, and validation selects
all enabled checks because there is no change history to compare.

Workbench 4 is the supported development line, with schema-3 configuration only.
Earlier experimental releases are retired from support; their historical records
remain available without adding compatibility code to this runtime.

## Start here

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run --diff   # look first
python3 /path/to/workbench/latex-ai-init init /path/to/project                    # then apply
cd /path/to/project && make help
```

Daily commands: `make status`, `make build`, `make check`, `make latex-ai-plan`,
and `make validate`. Preview selected checks after editing, then validate; run
a full check before sharing. No-TeX projects omit the build step.

- [Quickstart](docs/quickstart.md): install, first check, daily loop, when something fails.
- [I want to…](docs/tasks.md): find the command for what you are trying to do.
- In a project, `make guide` prints a short manual written with that project's own documents and command names.

## Pick a profile

| Profile | For | Modules |
|---|---|---|
| `core` | file and policy checks only | none |
| `writing` | a LaTeX manuscript | latex |

Or choose an explicit `--modules` list. An installed project is updated by an agent following [the recipe](docs/upgrading.md):
`diff` shows what differs and `runtime` refreshes the runtime files, never overwriting an edited one unless forced.

## Guides

| Getting started | Reference | Agents and updates |
|---|---|---|
| [Quickstart](docs/quickstart.md) | [Modules and profiles](docs/modules.md) | [Working with AI agents](docs/agents.md) |
| [I want to…](docs/tasks.md) | [Configuration](docs/configuration.md) | [Agent operating skill](skills/latex-ai-workbench/SKILL.md) |
| [Installing](docs/installing.md) | [Validation routing](docs/validation.md) | [Updating](docs/upgrading.md) |
| [Daily use](docs/daily-use.md) | [Bibliography](docs/bibliography.md) | [Maintainers' material](docs/maintainers/README.md) |
| | [TeX notes and named documents](docs/tex-notes.md) | |

The whole `workbench/` directory is relocatable: keep it together, because the installer needs its
sibling templates and backends. Installed projects need only their configuration, the vendored
runtime in `.latex-ai/` and its installation record; builds do not depend on where the distribution lives.

Version 3 uses one project configuration (schema 3) and one named-document
execution path. Old Workbench project schemas and migration flags are unsupported.
Each TeX document has its own receipt and PDF export; see the
[mixed notes example](examples/tex-notes/README.md).

Understand the [architecture and state](docs/architecture.md), or find the next
action in [troubleshooting](docs/troubleshooting.md).

Every manuscript build records verified input/output
hashes; PDF collection requires a current receipt. A project's own build
command, such as `make pdf` for a target of its Makefile, is run by `make latex-ai-build` like any other build command.
No particular GNU Make version is required.
An existing project is [migrated](docs/migrating.md) to the workbench's layout, not adapted to.

For automation, run the installed runtime with `--json`, for example
`python3 .latex-ai/workbench.py check --json` or `status --json`. Check, validate
and status results include status, exit code, diagnostics and structured
details. Plan and modules keep their existing JSON formats.
