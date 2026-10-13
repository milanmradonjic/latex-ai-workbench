# LaTeX AI Workbench

A project kit for AI-assisted LaTeX manuscripts. It gives a paper, or several documents in one
project, one set of commands (`make check`, `make validate`,
`make status`), runs only the checks your changes need, keeps PDFs honest about being stale, and
gives AI coding agents clear rules, including never changing Git without your approval. It needs
Python 3.10+ and `make`; TeX, Zotero, an editor and API keys are optional.

Git is optional. Without it, installation and checks work, and validation selects
all enabled checks because there is no change history to compare.

Workbench 3 is the supported development line, with schema-3 configuration only.
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
- [The guide](docs/handbook.md): pictures of how the parts fit, how-tos and a glossary. In a project,
  `make guide` prints it and `make guide-html` writes it as a web page ([ready-made copy](docs/handbook.html)).

## Pick a profile

| Profile | For | Modules |
|---|---|---|
| `core` | file and policy checks only | none |
| `writing` | a LaTeX manuscript | latex |

Or choose an explicit `--modules` list. Supported schema-3 projects can be updated: the installer previews
every change, preserves your files and has no overwrite switch.

## Guides

| Getting started | Reference | Agents and upgrades |
|---|---|---|
| [Quickstart](docs/quickstart.md) | [Modules and profiles](docs/modules.md) | [Working with AI agents](docs/agents.md) |
| [I want to…](docs/tasks.md) | [Configuration](docs/configuration.md) | [Agent operating skill](skills/latex-ai-workbench/SKILL.md) |
| [Installing and auditing](docs/installing.md) | [Validation routing](docs/validation.md) | [Upgrading](docs/upgrading.md) |
| [Daily use](docs/daily-use.md) | [Bibliography](docs/bibliography.md) | [Maintainers' material](docs/maintainers/README.md) |
| [The guide: pictures, how-tos, glossary](docs/handbook.md) | [TeX notes and named documents](docs/tex-notes.md) | |

The whole `workbench/` directory is relocatable: keep it together, because the installer needs its
sibling templates and backends. Installed projects need only their configuration, the vendored
runtime in `.latex-ai/` and the manifest; builds do not depend on where the distribution lives.

Version 3 uses one project configuration (schema 3) and one named-document
execution path. Old Workbench project schemas and migration flags are unsupported.
Each TeX document has its own receipt and PDF export; see the
[mixed notes example](examples/tex-notes/README.md).

Understand the [architecture and state](docs/architecture.md), or find the next
action in [troubleshooting](docs/troubleshooting.md).

Every manuscript build records verified input/output
hashes; PDF collection requires a current receipt. Adopted Make recipes are
preserved and invoked through `make latex-ai-build`.
Adopted single-target Make builds require GNU Make 4.3+; parallel checks share
the existing compiler target and reject overlapping build attempts.

For automation, run the installed runtime with `--json`, for example
`python3 .latex-ai/workbench.py check --json` or `status --json`. Check, validate
and status results include status, exit code, diagnostics and structured
details. Plan and modules keep their existing JSON formats.
