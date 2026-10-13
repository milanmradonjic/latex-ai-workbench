# Installing and limits

The full reference for putting the workbench into a project. For the short version, start with the [quickstart](quickstart.md).

Python 3.10+ and Make are the core requirements. Git is optional: absent Git or
comparison history yields unavailable metadata and full validation selection.

`make latex-ai-build` always reaches the workbench's build/receipt wrapper, and the short `build` is an alias of it.
A build command of the project's own, such as `["make", "pdf"]` for a target it added to the Makefile, runs like any other build
command; no GNU Make version is required (the 3.81 that macOS ships runs the generated Makefile).
Custom builders must produce the configured PDF and compiler log, and a no-op
is accepted only when a matching verified receipt already vouches for them.
PDF export also requires that receipt; changing inputs or failing a build
invalidates it. Default latexmk builds regenerate when a current receipt is
absent, then may reuse unchanged verified outputs on subsequent checks.

## Choosing a profile and modules

For new projects choose `--profile core` or `writing`, or an explicit `--modules` list.
The editor adapter is opt-in for modular projects. Read
[module configuration and profiles](modules.md).

Every installation uses schema 3. Older project schemas are refused and never converted.
The reference uses LaTeX and bibliography.

## Package and installed project

| Layer | Location | Responsibility |
|---|---|---|
| Reusable templates | `templates/` | Agent policy, Make, editor, permissions |
| Create and refresh | `latex-ai-init`, `bootstrap.py` | `init` creates a project (detects the root, engine and bibliography; refuses to touch a file the project has); `diff` shows how a project differs from this release; `runtime` refreshes `.latex-ai/` |
| Runtime/core | `runtime.py`, `core.py`, `guide.py`, `diagnostics.py` | Vendored to `.latex-ai/`; dispatcher, config and file checks, help/status/guide, local defect reports |
| Optional backends | `latex.py`, `documents.py` | Installed when LaTeX or bibliography is enabled |
| Configuration | Project `.latex-ai.json` | Enabled modules, paths, commands, optional adapters; schema 3 only |
| Installation record | Project `.latex-ai/installation.json` | The release, and a digest of each runtime file so that a local edit shows; keep in version control |
| Operating skill | `skills/latex-ai-workbench/` | Bootstrap, writing, independent review, updates |

The entire `workbench/` directory is relocatable. Keep it together: the CLI
needs its sibling templates and backend files. Installed projects need only their
configuration, runtime, record and project files; builds do not depend on
the distribution's location. Adding this CLI to a global PATH or installing
the skill globally is optional and is outside bootstrap's scope.

## New projects

Create a real TeX root yourself or use your institution's manuscript template.
The workbench never overwrites or generates manuscript content.

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/project
make -C /path/to/project doctor
make -C /path/to/project check
```

A single plain root is detected. For multiple roots, select `--root thesis.tex`.
Magic engine comments are recognized; explicit engine choices win. For
fontspec or other conventions requiring judgment, provide
`--engine lualatex`, `--engine xelatex`, or `--engine pdflatex` after inspecting
the project. Bibliography detection follows literal inputs and recognizes
BibTeX and biblatex/Biber. Explicit `--backend` handles custom macros.

## Existing projects

`init` writes only files that are absent, or already what it would write, and refuses the rest, listing each with `CONFLICT`.
An existing project is therefore migrated, not adapted to: follow [migrating](migrating.md). Begin with the state of Git and a
snapshot to return to; setup never discards a dirty file.

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --engine lualatex --dry-run
```

The engine is read from a magic comment (`% !TeX program = lualatex`) or from the source (`directlua`, `xeCJK`) and otherwise
defaults to pdfLaTeX, except that a source loading `fontspec` must be told: `--engine lualatex` or `--engine xelatex`.
Bibliography detection follows literal inputs and recognizes BibTeX and biblatex/Biber; `--backend` handles custom macros. A build
that is not latexmk is declared with its argv, for example:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project \
  --engine lualatex --build-command '["make", "pdf"]' --dry-run --diff
```

Use the project's actual command, and set `output_dir` if its outputs are elsewhere. Never name `build`, `check` or another goal that
reaches the workbench: that would call itself. `--dry-run --diff` previews the content; new runtime files under `.latex-ai/` are listed by
name and size instead of printed, and the summary is printed last.

GitHub workflows are never written, and any a project has are left as they are. The Makefile `init` writes is named `Makefile`;
a `GNUmakefile` or `makefile` would be read instead of it, so either is a conflict.
[GNU Make filename rules](https://www.gnu.org/software/make/manual/make.html#Makefile-Names).

## After installing, and limitations

`init` is for a new project: it refuses one that already has `.latex-ai/installation.json`. To see how an installed project
differs from a release run `latex-ai-init diff PROJECT --diff`; to refresh its runtime files, `latex-ai-init runtime PROJECT`.
[Updating](upgrading.md) is the recipe an agent follows, [configuration](configuration.md) lists the supported fields, and
[bibliography](bibliography.md) covers Better BibTeX setup.

Exit status: 0 means done, current or a safe dry-run; `diff` returns 1 when a runtime file differs; 2 means ambiguity, conflicts or
invalid input (an `ERROR:` line, with a `Hint:` where there is a next step); 70 marks an `INTERNAL ERROR`, a defect in the installer
itself. `diff` and dry-runs make no project writes and never execute project builds.

Every workbench command has a reserved Make name (`latex-ai-doctor`,
`latex-ai-bib-check`, `latex-ai-help`, ...). The short name (`doctor`,
`bib-check`, `help`) is an alias of it, unless the template defines that name itself.
A project that gives a short name a recipe of its own keeps it, and the `latex-ai-` name still reaches the workbench.
The shared targets are `check`, which runs the workbench's checks and anything the
project adds to it, and `lint`; `latex-ai-build` establishes the build's receipt.

Literal include/resource detection is conservative. Macro-generated resources,
custom import layouts, external shared libraries
or changed job names need explicit declaration in `inputs`.
Schema 3 supports explicit named roots; see [TeX notes](tex-notes.md). TeX root paths with spaces
or TeX-special characters are rejected; directories containing ordinary spaces
are handled through argv. Sources outside the project are not installed or
modified. Use compiler results and local conventions to resolve uncertain
discovery rather than accepting guessed settings.
