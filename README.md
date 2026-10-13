# LaTeX AI Workbench reference

This repository is the working reference and distribution source for the
[LaTeX AI Workbench](workbench/README.md). The manuscript is configured in
[.latex-ai.json](.latex-ai.json); agent semantic policy lives in [AGENTS.md](AGENTS.md).
Workbench 3 supports schema 3 only: this reference is one named document.

```sh
make help     # the commands this project has
make status   # where it stands and what to do next
make doctor
make check
```

For everyday notes, documentation, policy, code and manuscript edits, use
`make validation-plan` to preview relevant checks and `make validate` to run
them. Ordinary documentation-only work skips the manuscript build. See the
[change-aware validation guide](workbench/docs/validation.md).
The [TeX notes guide](workbench/docs/tex-notes.md) covers independent note documents
and several documents in one project (schema 3).

The reusable package lives entirely under `workbench/`. Copy that directory to
a convenient location inside your permitted filesystem scope to use it with
other projects. Its CLI never initializes or mutates Git.

See the [quickstart](workbench/docs/quickstart.md), the [task finder](workbench/docs/tasks.md), the [workbench overview](workbench/README.md),
[configuration reference](workbench/docs/configuration.md),
[bibliography integration guide](workbench/docs/bibliography.md),
[upgrade guide](workbench/docs/upgrading.md), and
[agent operating skill](workbench/skills/latex-ai-workbench/SKILL.md).

The [current verification record](workbench/docs/maintainers/verification-4.1.0.md) records local
test results, preserved files and remaining human setup steps.

The reference deliberately contains no example literature citations. Its
verified Better BibTeX auto-export is `bibliography/zotero.bib`, from the
owner's `LaTeX AI Workbench test` collection. Validation now requires this
nonempty local file. Builds work without Zotero running; the export is a
repository input. The manuscript has no bibliography commands yet, so its
backend remains `none`. Both real exported entries passed a separate offline
BibTeX build. When actual manuscript citations are introduced, enable the
appropriate backend and source commands as described in the guide.
