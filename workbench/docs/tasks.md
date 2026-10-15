# I want to…

Run commands from the project root. `make help` lists the fixed interface.
`latex-ai-init` is a file in the distribution, invoked with
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
| Build one named document, or every document | `make build DOC=NAME`, `make all` | [TeX notes](tex-notes.md) |
| Add another LaTeX document (notes, a supplement) | add it under `documents` in `.latex-ai.json` | [TeX notes](tex-notes.md) |
| Check one named TeX document | `make document-check DOC=NAME` | [TeX notes](tex-notes.md) |
| Adopt the style check on a paper that already has warnings | `make lint-baseline` (accepts today's warnings; new ones still fail) | [configuration](configuration.md#accepting-existing-style-warnings) |
| Change what is checked | edit `.latex-ai.json` | [configuration](configuration.md) |
| Set up Zotero and Better BibTeX | follow the guide | [bibliography](bibliography.md) |
| Keep a copy to return to before a risky change, and restore from it | `make snapshot` (`SNAPSHOT_NOTE="why"`), `make snapshots` | [snapshots](snapshots.md) |
| Have snapshots taken for me while I work (Mac) | two launchd agents: one asks every 30 minutes (the newest 60 kept), one asks every day (one a week, the newest 6 kept) | [snapshots](snapshots.md#timers-on-a-mac-launchd) |
| Update to a newer release | `latex-ai-init diff . --diff`, then `latex-ai-init runtime .` (an agent follows the recipe) | [updating](upgrading.md) |
| Report a suspected workbench defect | `make issue ISSUE_NOTE="..."` | [agents](agents.md#suspected-workbench-defects) |
| Let an AI agent work safely | it reads `AGENTS.md`; Git changes prompt you | [agents](agents.md) |
| Have a second model review a change | use the review procedure | [agents](agents.md#writer-and-reviewer) |
| Understand how a release was verified | maintainers' record | [maintainers](maintainers/README.md) |
