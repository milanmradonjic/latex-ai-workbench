# Core and modules

The core needs Python 3.10+ and Make. It supplies configuration, installation,
agent policies, file checks and command routing. TeX, Zotero, GUI
applications and CI are optional. Installed projects run from their own `.latex-ai/`
files, independently of the distribution directory. All projects use schema 3. A TeX
manuscript is optional.

## Select only what a project needs

For a project that needs only the file checks and the agent rules:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --modules '' --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/project --modules ''
```

`--modules` chooses the initial modules exactly: `''` selects none (shared infrastructure only), `latex` selects LaTeX, and
`latex,bibliography` selects both. When LaTeX source declares bibliography resources, detection adds
the bibliography capability and records those paths. TeX selection still needs
a real root. Without `--modules` a paper gets `latex` (and `bibliography` when its source declares one), with the
editor adapter on; every project uses schema 3.
`--modules` only chooses the starting set; the configuration stores the resolved module choices.

New projects given `--modules` enable the editor adapter only with `--editor`. It installs
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
every declared document; `make latex-ai-build DOC=NAME` selects one to build, and `make all` builds them all in turn.
`check` checks enabled modules and runs full manuscript validation when LaTeX is
enabled. `make modules` prints effective settings. Every command except the shared `check` and `lint`
also has a reserved `latex-ai-*` name that reaches the workbench even when a project gives the short one a recipe of its own.
Custom Make recipes and workflows can still invoke tools themselves; disabling workbench modules does
not rewrite unrelated project code.

`validation.manuscript_inputs` and `validation.ignore` remain optional top-level settings. Bibliography
export files/settings belong to `modules.bibliography`; backend selection belongs
to each `modules.latex.documents.<id>.backend`. TeX source remains authoritative for actual package
and bibliography processing. Bibliography can be checked without TeX.

## Enable and disable deliberately

A module is on when `modules` in `.latex-ai.json` has it and off when it does not. Edit the file, then run `make check`;
`latex-ai-init diff . --diff` shows what the generated Makefile and editor files would now contain, and an agent applies what is
wanted by hand ([updating](upgrading.md)).

```json
"modules": {"latex": {"default_document": "main", "documents": {"main": {"root": "main.tex"}}}, "bibliography": {"files": ["refs.bib"]}}
```

Enabling LaTeX in a project without TeX needs an explicit root; no source is generated or guessed.
Removing a module keeps your source files and forgets its settings: copy them aside if you may want them back. Its commands stop
being accepted; editor tasks that were generated for it stay in `.vscode/` until you remove them.

## Extension contract

Bundled modules are registered explicitly in `core.py`: defaults, dependencies
and name. The installer renders their managed adapters; runtime code declares
commands and file dependencies. Records are versioned JSON. A new module must add
configuration, installation, routing and portability tests.
This is a small bundled-module architecture; external dynamically loaded plugins
are a future extension.

See [validation routing](validation.md).
