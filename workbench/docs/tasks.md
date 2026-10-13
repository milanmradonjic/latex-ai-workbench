# I want to…

Every command is run from the project root. `make help` lists the ones your project has. Where
your own Makefile already had a target of one of these names, your recipe was kept and the
workbench command is the `latex-ai-` form: `make latex-ai-help` always works and shows which
names apply. `latex-ai-init` below is a file in the workbench package, run as
`python3 /path/to/workbench/latex-ai-init`.

| I want to… | Run | More |
|---|---|---|
| See what this project can do | `make help` | [quickstart](quickstart.md) |
| Read a short manual for this project | `make guide` | [quickstart](quickstart.md) |
| See where things stand and what to do next | `make status` (a stale document lists what changed) | [quickstart](quickstart.md) |
| Check that my tools are installed | `make doctor` | [installing](installing.md) |
| Check everything before sharing | `make check` | [daily use](daily-use.md) |
| Check only what I changed | `make validate` (preview: `make validation-plan`) | [validation](validation.md) |
| Build the PDF | `make build` (`make lint`, `make bib-check`, `make pdf-artifact`) | [daily use](daily-use.md) |
| Add another LaTeX document (notes, a supplement) | `latex-ai-init configure . --document NAME --root FILE` | [TeX notes](tex-notes.md) |
| Check one named TeX document | `make latex-ai-document-check DOC=NAME` | [TeX notes](tex-notes.md) |
| Adopt the style check on a paper that already has warnings | `make lint-baseline` (accepts today's warnings; new ones still fail) | [configuration](configuration.md#accepting-existing-style-warnings) |
| Turn a module on or off later | `latex-ai-init configure . --enable NAME` (or `--disable NAME`); `make help` prints the command; replace `/path/to/workbench` with where you keep the package | [modules](modules.md) |
| Change what is checked | edit `.latex-ai.json` | [configuration](configuration.md) |
| Set up Zotero and Better BibTeX | follow the guide | [bibliography](bibliography.md) |
| Upgrade to a newer release | `latex-ai-init upgrade . --dry-run --diff` | [upgrading](upgrading.md) |
| Report a suspected workbench defect | `make latex-ai-issue ISSUE_NOTE="..."` | [agents](agents.md#suspected-workbench-defects) |
| Let an AI agent work safely | it reads `AGENTS.md`; Git changes prompt you | [agents](agents.md) |
| Have a second model review a change | use the review procedure | [agents](agents.md#writer-and-reviewer) |
| Understand how a release was verified | maintainers' record | [maintainers](maintainers/README.md) |
