# Core, modules and profiles

The core needs Python 3.10+ and Make. It supplies configuration, safe installation
and upgrades, agent policies, file checks and command routing. TeX, numerical
libraries, Zotero, GUI applications and CI are optional. Installed projects run
from their own `.latex-ai/` files, independently of the distribution directory.
All projects use schema 3. A TeX manuscript is optional.

## Select only what a project needs

For a fresh directory containing notes or code:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --profile notebook --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/project --profile notebook
```

| Profile | Initial modules |
|---|---|
| `core` | None; shared infrastructure only |
| `writing` | LaTeX; bibliography added if declared by the detected source |
| `notebook` | Notes |
| `tex-notebook` | LaTeX notebook and TeX session-state fragment; schema 3 |
| `numerical` | Numerics, provenance, freshness |
| `research-paper` | LaTeX, notes, numerics, provenance, figures, freshness; source bibliography if used |

Use `--modules notes,bibliography` instead of a profile for an exact initial
selection. When LaTeX source declares bibliography resources, detection adds
the bibliography capability and records those paths. TeX selection still needs
a real root and any explicit engine choice required by existing build conventions.
Without either option a paper gets `latex` (and `bibliography` when its source declares one), with the
editor and CI adapters on; every profile uses schema 3.
Profiles are initialization presets, not persistent policies or upgrade defaults.
The configuration stores the resolved module choices.

New modular projects enable editor and CI adapters only with `--editor` and
`--ci`. They install project files without opening/configuring GUI applications.
No-TeX CI has no TeX container or PDF upload. Scientific environments must be provisioned by the project's own
workflow before declared scientific checks run in CI; the workbench does not
install arbitrary project dependencies.

## Configuration

An absent module is disabled. A present object enables it and supplies settings;
`{}` uses documented defaults. There is no parallel boolean enablement flag.

```json
{
  "schema_version": 3,
  "modules": {
    "notes": {"path": "journal"},
    "numerics": {"manifest": "analysis/experiments.json"},
    "figures": {"manifest": "plots/manifest.json"},
    "provenance": {"path": "results/runs"},
    "freshness": {}
  },
  "integrations": {
    "editor": false,
    "ci": {"enabled": false, "pdf_artifact": false, "texlive_version": "2026"}
  }
}
```

| Module | Settings and defaults | Available Make commands |
|---|---|---|
| `latex` | Named `documents`, `default_document`, optional shared `defaults`; every root is explicit | `build`, `lint`, `check`, `pdf-artifact`, `clean` |
| `bibliography` | `files: []`, `export: null`; see configuration for the export declaration | `bib-check`; also checked by `check` |
| `notes` | `path: notes`, `index: index.md`, `session_state: session-state.md`; configurable text formats | `research-check` |
| `markdown` | `files: ["notes/**/*.md"]`; requires Pandoc only when used | `md-check`, `md-render` |
| `numerics` | `manifest: experiments.json` | `run TASK=name` |
| `figures` | `manifest: figures/manifest.json` | `figure TASK=name` |
| `provenance` | `path: results/runs`; archives explicit numeric/figure runs | No separate execution command |
| `freshness` | `{}`; requires provenance | `freshness` |
| `claims` | `manifest: claims.json` | `claims-check` |

Core commands are `check`, `doctor`, `validation-plan`, `validate`, `help`, `status`, `modules` and `issue` (a local report about a suspected workbench defect; see [agents](agents.md#suspected-workbench-defects)).
The LaTeX module uses named `documents`, optional `defaults`, and a `default_document`. [TeX notes](tex-notes.md) describes setup,
configuration and document commands. `make check` checks
every declared document; `make latex-ai-build DOC=NAME` selects one.
`check` checks enabled modules and runs full manuscript validation when LaTeX is
enabled. `make modules` prints effective settings. Existing local target names
remain authoritative; every command except the shared `check`, `build` and `lint`
also has a reserved `latex-ai-*` name that reaches the workbench when an existing
target has the short one. Existing custom Make recipes and
workflows can still invoke tools themselves; disabling workbench modules does
not rewrite unrelated project code.

Module manifests and initial notes become project-owned after creation. The
installer never overwrites their content on upgrade or recreates one the project
deleted (it reports a note); `run`/`figure` receive `TASK` through the
environment, so its value is never parsed as shell text. Paths are configurable,
relative to the project, and checked for containment. Do not place manifests in
managed infrastructure, alias distinct manifests, or use the run archive as
task inputs/outputs. The existing directory layout can otherwise be retained.

`validation.manuscript_inputs` and `validation.ignore` remain optional top-level settings. Bibliography
export files/settings belong to `modules.bibliography`; backend selection belongs
to each `modules.latex.documents.<id>.backend`. TeX source remains authoritative for actual package
and bibliography processing. Figures and numerics do not require LaTeX or each
other. Bibliography can support a literature notebook without TeX.

## Enable and disable deliberately

Preview module changes, then apply without dry-run:

```sh
python3 /path/to/workbench/latex-ai-init configure /path/to/project --enable notes --dry-run --diff
python3 /path/to/workbench/latex-ai-init configure /path/to/project --disable figures --dry-run --diff
```

Disable dependents in the same
operation before disabling a required module (`freshness` requires `provenance`).
Enabling LaTeX in an existing no-TeX project uses `main.tex`/pdfLaTeX defaults;
for another root/engine, edit the explicit module configuration and inspect an
upgrade dry-run. No source is generated or guessed during configure.

Disabling retains notes, manifests, run records, results and source files.
It also saves the module's settings in optional `disabled_modules` configuration;
that field does not enable modules. Re-enabling restores the saved paths/settings.
Commands stop being offered/accepted for the disabled module. Managed CI is
updated; disabling LaTeX also stops its managed editor auto-build. Retained
editor tasks and unrelated workflows remain visible for deliberate review.
Upgrades never silently re-enable disabled modules. Re-enable preserves the
project's old manifests and saved settings; choices can be edited explicitly.

## Extension contract

Bundled modules are registered explicitly in `core.py`: defaults, dependencies
and name. The installer renders their managed adapters and editable initial
files; runtime code declares commands, file dependencies and check cost.
Records/manifests are versioned JSON. New modules must add configuration,
installation, routing, disable/retention and portability tests. They must keep
expensive execution separate from inspection. This is a small bundled-module
architecture; external dynamically loaded plugins are a future extension.

See [research commands and records](research.md), the [synthetic decay example](../examples/decay/README.md),
and [validation routing](validation.md).

Release 2.1 adds opt-in [Markdown checks and local HTML export](markdown.md).
Profiles retain their previous selections; plain notes do not require Pandoc.
