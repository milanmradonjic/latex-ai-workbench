# Installing, auditing and limits

The full reference for putting the workbench into a project. For the short version, start with the [quickstart](quickstart.md).

Python 3.10+ and Make are the core requirements. Git is optional: absent Git or
comparison history yields unavailable metadata and full validation selection.

`make latex-ai-build` always reaches the workbench's build/receipt wrapper.
An existing `build` recipe stays yours; a new project gets `build` as an alias.
Adapted `make check` uses the wrapper exactly once before verifying the PDF.
For an adopted command such as `["make", "pdf"]`, GNU Make 4.3+ is required:
the existing target and workbench verification share the outer dependency graph,
so `check: build lint` does not launch a second compiler under parallel Make.
The installer and `make doctor` say when the `make` on PATH is older (macOS ships
3.81). With an older Make the project's own targets and the read-only commands keep
working; only the workbench's build and check goals refuse, naming the requirement.
Preparation claims the build until its parent Make process exits; failed or
interrupted builds leave an unverified receipt. Project-only targets such as
`make pdf` retain their own behavior; they do not establish a new receipt.
Custom builders must produce the configured PDF and compiler log, and a no-op
is accepted only when a matching verified receipt already vouches for them.
PDF export also requires that receipt; changing inputs or failing a build
invalidates it. Default latexmk builds regenerate when a current receipt is
absent, then may reuse unchanged verified outputs on subsequent checks.

## Choosing a profile and modules

For new projects choose `--profile core` or `writing`, or an explicit `--modules` list.
The editor adapter is opt-in for modular projects. Read
[module configuration and profiles](modules.md).

Every installation uses schema 3. Older project schemas are unsupported and are
never automatically converted. Upgrades retain supported project choices. The reference
uses LaTeX and bibliography.

## Package and installed project

| Layer | Location | Responsibility |
|---|---|---|
| Reusable templates | `templates/` | Agent policy, Make, editor, permissions |
| Setup/audit/upgrade | `latex-ai-init`, `bootstrap.py` | Detect conventions, plan safe changes, manage installation |
| Runtime/core | `runtime.py`, `core.py`, `guide.py`, `handbook.py`, `diagnostics.py` | Vendored to `.latex-ai/`; dispatcher, config and file checks, help/status/guide, local defect reports |
| Optional backends | `latex.py`, `documents.py` | Installed when LaTeX or bibliography is enabled |
| Configuration | Project `.latex-ai.json` | Enabled modules, paths, commands, optional adapters; schema 3 only |
| Upgrade state | Project `.latex-ai/installation.json` | Release and merge baselines (digests for files installed whole, text where a merge needs it); keep in version control |
| Operating skill | `skills/latex-ai-workbench/` | Bootstrap, writing, independent review, upgrades |

The entire `workbench/` directory is relocatable. Keep it together: the CLI
needs its sibling templates and backend files. Installed projects need only their
configuration, runtime, manifest and project files; builds do not depend on
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
Magic engine comments are recognized; explicit engine choices win. Where the
project has build files of its own, the engine is read from them when they name
exactly one (`latexmk -pdf`, `-lualatex`, `-xelatex`, or the engine's own name)
and reported in a note. For
fontspec or existing build conventions requiring judgment, provide
`--engine lualatex`, `--engine xelatex`, or `--engine pdflatex` after inspecting
the project. Bibliography detection follows literal inputs and recognizes
BibTeX and biblatex/Biber. Explicit `--backend` handles custom macros.

## Existing projects

Begin with status, branch, local policies, existing Makefile/build scripts and
engine settings. Preserve dirty user files. Setup may safely add to a dirty
repository; dirtiness is reported and never automatically discarded.

```sh
python3 /path/to/workbench/latex-ai-init audit /path/to/project --engine lualatex --json
python3 /path/to/workbench/latex-ai-init init /path/to/project --engine lualatex --dry-run --diff
```

Apply that same `init` command without `--dry-run --diff` after assessing the
plan. For an existing Makefile with a `build` target, the tool preserves the
file and appends a managed block: `check` gains lint plus integrity validation
that depends on `latex-ai-build`. Existing recipes remain authoritative. When the
local build target is named differently, declare its argv, for example:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project \
  --engine lualatex --build-command '["make", "pdf"]' --dry-run --diff
```

Use the project's actual command, and set `output_dir` if its outputs are
elsewhere. Never delegate to `make build` or `make check` when those targets
invoke the workbench runtime: that creates recursion. Existing direct
Makefile recipes may implement extra local conventions.

Existing AGENTS/CLAUDE/ignore files gain marked integration blocks. JSON editor
files retain ordinary preferences and unrelated tasks/recipes/tools. An
identically named but different task/tool is a conflict. JSONC with comments
or trailing commas is preserved without automatic editing; `--skip-editor`
allows setup to continue while editor integration stays manual. Agent
permission files with conflicting content are preserved and block setup for
manual reconciliation. GitHub workflows are never written, and any a project has are left as they are.

The active Makefile follows GNU Make's filename order (`GNUmakefile`,
`makefile`, `Makefile`). Its existing filename is retained. A new file that
shadows the registered Makefile blocks an upgrade until reconciled, and a
locally removed managed block is treated as a conflict rather than re-added.
[GNU Make filename rules](https://www.gnu.org/software/make/manual/make.html#Makefile-Names).

No file is changed when any conflict blocks the plan. Review `--diff` to see
proposed concrete content; new runtime files under `.latex-ai/` are listed by
name and size instead of printed, and the summary is printed last. Targets
defined in makefiles your Makefile includes by name count as existing targets.

## Audit, upgrades and limitations

```sh
python3 /path/to/workbench/latex-ai-init audit /path/to/project
python3 /path/to/new-workbench/latex-ai-init upgrade /path/to/project --dry-run --diff
```

See [upgrades](upgrading.md) for backups, conflict recovery and release
rules, [configuration](configuration.md) for supported fields, and
[bibliography](bibliography.md) for Better BibTeX setup.

Exit status: 0 means current/applied/safe dry-run; audit returns 1 for missing
components or pending updates; 2 means ambiguity, conflicts or invalid input
(an `ERROR:` line, with a `Hint:` where there is a next step); 70 marks an
`INTERNAL ERROR`, a defect in the installer itself. An audit ends with the exact
command that applies what it previewed, including the options it was given.

Every workbench command has a reserved Make name (`latex-ai-doctor`,
`latex-ai-bib-check`, `latex-ai-help`, ...). The short name (`doctor`,
`bib-check`, `help`) is added as an alias only where the Makefile has no target
of that name, so an existing recipe is never replaced and the installer notes
each name it kept. The shared targets are `check`, which runs workbench and
project checks, and `lint`, which keeps the project's convention. An existing
`build` recipe stays intact; `latex-ai-build` establishes its receipt.
Audit and dry-run make no project writes and never execute project builds.
They report inventory, Git state, detection and planned changes. Audit compares
against this package version; it is not a security scanner or a CI run.

Literal include/resource detection is conservative. Macro-generated resources,
custom import layouts, external shared libraries, unusual Make target syntax,
or changed job names need explicit adaptation.
Schemas 1/2 support one configured root. Schema 3 supports explicit named roots;
see [TeX notes](tex-notes.md). Multiple adopted Make graphs with shared or
unresolved prerequisites require an explicit adapter. TeX root paths with spaces
or TeX-special characters are rejected; directories containing ordinary spaces
are handled through argv. Sources outside the project are not installed or
modified. Use compiler results and local conventions to resolve uncertain
discovery rather than accepting guessed settings.
