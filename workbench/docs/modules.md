# Core, modules and profiles

The core needs Python 3.10+ and Make. It supplies configuration, safe installation
and upgrades, agent policies, file checks and command routing. TeX, Zotero, GUI
applications and CI are optional. Installed projects run from their own `.latex-ai/`
files, independently of the distribution directory. All projects use schema 3. A TeX
manuscript is optional.

## Select only what a project needs

For a project that needs only the file checks and the agent rules:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --profile core --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/project --profile core
```

| Profile | Initial modules |
|---|---|
| `core` | None; shared infrastructure only |
| `writing` | LaTeX; bibliography added if declared by the detected source |

Use `--modules latex,bibliography` instead of a profile for an exact initial
selection. When LaTeX source declares bibliography resources, detection adds
the bibliography capability and records those paths. TeX selection still needs
a real root and any explicit engine choice required by existing build conventions.
Without either option a paper gets `latex` (and `bibliography` when its source declares one), with the
editor adapter on; every profile uses schema 3.
Profiles are initialization presets, not persistent policies or upgrade defaults.
The configuration stores the resolved module choices.

New projects chosen by profile or module list enable the editor adapter only with `--editor`. It installs
project files without opening/configuring GUI applications.

## Configuration

An absent module is disabled. A present object enables it and supplies settings;
`{}` uses documented defaults. There is no parallel boolean enablement flag.

```json
{
  "schema_version": 3,
  "modules": {
    "bibliography": {"files": ["refs.bib"]}
  },
  "integrations": {
    "editor": false
  }
}
```

| Module | Settings and defaults | Available Make commands |
|---|---|---|
| `latex` | Named `documents`, `default_document`, optional shared `defaults`; every root is explicit | `build`, `lint`, `check`, `pdf-artifact`, `clean` |
| `bibliography` | `files: []`, `export: null`; see configuration for the export declaration | `bib-check`; also checked by `check` |

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

`validation.manuscript_inputs` and `validation.ignore` remain optional top-level settings. Bibliography
export files/settings belong to `modules.bibliography`; backend selection belongs
to each `modules.latex.documents.<id>.backend`. TeX source remains authoritative for actual package
and bibliography processing. Bibliography can be checked without TeX.

## Enable and disable deliberately

Preview module changes, then apply without dry-run:

```sh
python3 /path/to/workbench/latex-ai-init configure /path/to/project --enable bibliography --dry-run --diff
python3 /path/to/workbench/latex-ai-init configure /path/to/project --disable bibliography --dry-run --diff
```

Enabling LaTeX in an existing no-TeX project uses `main.tex`/pdfLaTeX defaults;
for another root/engine, edit the explicit module configuration and inspect an
upgrade dry-run. No source is generated or guessed during configure.

Disabling retains source files. It also saves the module's settings in optional
`disabled_modules` configuration; that field does not enable modules. Re-enabling
restores the saved paths/settings. Commands stop being offered/accepted for the
disabled module. Disabling LaTeX also stops its managed editor auto-build. Retained
editor tasks remain visible for deliberate review. Upgrades never silently re-enable disabled modules.

## Extension contract

Bundled modules are registered explicitly in `core.py`: defaults, dependencies
and name. The installer renders their managed adapters; runtime code declares
commands and file dependencies. Records are versioned JSON. A new module must add
configuration, installation, routing, disable/retention and portability tests.
This is a small bundled-module architecture; external dynamically loaded plugins
are a future extension.

See [validation routing](validation.md).
