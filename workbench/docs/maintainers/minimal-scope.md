# The minimal scope: what this tool is for

Written after a review of the whole project. The tool began as a wish for a LaTeX workspace like OpenAI's Prism: VS Code plus two independent
AI connectors, Claude and Codex, working on the same manuscripts. It grew far beyond that. This record states what the owner needs,
decided question by question from the basic purpose down to the details, and what therefore goes. Nothing is removed by this
record: it is the brief for removing it in small steps, each with its tests (see [the order](#order-of-the-work)).

## What stays

| Area | Decision |
|---|---|
| VS Code | Generated settings and tasks for LaTeX Workshop. |
| Agents | One `AGENTS.md`; `CLAUDE.md` pointing to it; the agent skill file; Git guardrails for Claude and Codex (ask before commit or push, no push to `main`, no merge). |
| Documents | Several LaTeX documents per project (main, notes, supplementary, ...). One Make target per document (`make main`, `make notes`), generated only where the name is free; bare `make` builds the main document; `make all` builds the whole package. |
| Build | Through the tool, so that every build leaves a record. pdflatex and bibtex only, one output place per document (no separate build folder with a copy beside the source). A document may declare a `build_command` for anything unusual. |
| Stale-PDF records | Kept: a record proves a PDF was built from the current sources. |
| Build locks | Kept (14 October 2026): a second build is refused while one runs, status reports a running build as running, and a build killed hard whose compiler lives on still blocks the next one. |
| Lint | ChkTeX, with the baseline that accepts today's warnings and fails on new ones. |
| Checks | `make check`; a command that validates only what changed, with `validation.ignore`; bibliography checks tied to a Zotero export; build errors parsed from the log into short diagnostics, if that stays cheap. |
| Support | `status`, `doctor`, `issue` (a local report of a suspected defect in the tool); a minimal, project-oriented manual that can grow with the project. |
| Snapshots | A rolling backup of a project, see below. |
| Updates | By an agent, following a recipe, with a diff for the owner to read, see below. |

## What goes

- **Adopting an existing Makefile**: the Make parser, the phased ownership of a project's own build graph, and the requirement for GNU Make
  4.3 or later. A project with its own build uses `build_command` or a hand-written target. This also closes the open Phase 4 decision
  of the [plan after 3.0.2](plan-after-3.0.2.md): there is no adoption mode to default.
- **Generated CI workflows** for projects (the workflows of this repository itself are separate).
- **Non-LaTeX notes**: the Markdown module and the notes module. They are not maintained automatically.
- **Research modules**: numerics tasks, figures, freshness, provenance and the claims ledger. Figures become plain targets in the project's own
  Makefile, with a shared style file for consistent plots.
- **Engine and backend choice**: pdflatex and bibtex are fixed.
- **The installer's upgrade machinery** (`audit`, `upgrade`, `recover`, the ownership manifest and its strategies, conflict detection, the
  installation journal), and the installer profiles.
- **The long generated handbook.**

## Updates by an agent

A project is created from one template folder, with a version stamp. A release states which generated files changed. To update a project
the agent follows a recipe in the skill file: take a snapshot (or copy the folder when there is none), diff the project against the
template for the files the release names, apply the changes while keeping the project's own edits, run `make check`, and show the diff.
`make doctor` reports the project's stamp, the template's, and which generated files differ. An update never ends without a diff and a
check for the owner to read.

## Snapshots

A shadow Git repository outside the project, so that it works for projects with or without their own Git and never touches it:
`git --git-dir=$HOME/.snapshots/<project>/... --work-tree=<project>`. Build output is ignored. `make snapshot` takes a snapshot;
`make snapshots` lists them; restoring is a documented `git checkout`, done with the owner looking.

| Tier | Content | Kept | Rotation |
|---|---|---|---|
| Fine | Every `make snapshot` | 1 to 2 weeks | Two repositories, chosen by `days_since_epoch // 7` parity |
| Daily | The first snapshot of each day | 1 to 2 months | Two repositories, chosen by `year*12 + month` parity |

A `PERIOD` file in each repository records the period it holds; when it differs from the current one the repository is deleted and
started again. The script removes only folders under `~/.snapshots/<project>/` and refuses anything else. Snapshots are taken before and
after an update; a daily scheduled run is an optional step the owner sets up. It protects against mistakes, not disk failure.

## Risks accepted

- Without the upgrade machinery, a fix reaches an existing project only through the recipe, and a wrong merge is caught only by the diff
  and the check.
- A complicated project Makefile is handled by hand.

## Order of the work

Deletions first, by area, one small change each, with its tests removed or kept as the area goes, checking after each that the build
records, VS Code files and Makefile output of what remains do not change: the research modules, the Markdown and notes modules, CI
generation, the handbook, then the upgrade machinery. The changes to the build core come last: the Make adoption layer and
the per-document targets. The full version stays available as the first commit of this repository and as the frozen `latex-ai-test` repository.

## Progress

- **4.0.0** removed the research modules, the notes and Markdown modules and what served them ([verification](verification-4.0.0.md)).
- **4.1.0** removed the generator of CI workflows ([verification](verification-4.1.0.md)).
- **4.2.0** replaced the long generated handbook by a short manual ([verification](verification-4.2.0.md)).
- **4.3.0** took the upgrade machinery out of the installer, leaving `init`, `diff` and `runtime` ([verification](verification-4.3.0.md)).
- **4.4.0** removed the Make adoption layer: `init` creates files and never merges, and an existing project is migrated by a recipe ([verification](verification-4.4.0.md)).
- **4.4.1** (step 3.1 of [the plan](plan-after-4.4.0.md)) refreshed the runtime apart from the project's generated files ([verification](verification-4.4.1.md)).
- **4.4.2** (step 3.2) removed the module table's unused fields ([verification](verification-4.4.2.md)).
- **Step 3.3** removed nothing: the owner decided to keep the locks and the `running` state, so there is no release (see [the plan](plan-after-4.4.0.md)).
- **4.5.0** (step 3.4) left one engine (pdflatex), one bibliography program (BibTeX) and no installer profiles ([verification](verification-4.5.0.md)).
- **4.5.1** made `init` stop at a paper that needs lualatex, xelatex or biber and print the `--build-command` to declare instead ([verification](verification-4.5.1.md)).
- **4.6.0** (step 3.5) added `make all` and a `make NAME` for each document of a project that has several ([verification](verification-4.6.0.md)).
- **4.7.0** (step 3.6) added `make snapshot` and `make snapshots`: copies of every file outside the project, in two rotating tiers ([verification](verification-4.7.0.md)).

- **Still to do**, in this order ([the plan after 4.4.0](plan-after-4.4.0.md)): the doctor's stamp report.

## Decided since

- **The licence is MIT** (13 October 2026), with the repository owner's GitHub name as the copyright holder.
- **The locks and the `running` state stay** (14 October 2026), reversing the scope's earlier decision to remove them: a second build the workbench starts is refused, status says "running" while a build runs, and a build whose owner was killed hard but whose compiler lives on still blocks the next one. Folding `running` into `failed` would have given up the last two.
- **The `biblatex` export format goes too** (14 October 2026), with biber: the export format is `bibtex`, Zotero's Better BibTeX.
- **No biber** (14 October 2026): the engine is `pdflatex` and the bibliography backend is `none` or `bibtex`; a project that needs more declares a `build_command`.

## Not yet decided

Which exact Git guardrail rules remain; what the planner for changed files still routes (workflow files and figure scripts in particular); and what the minimal
manual contains and how project notes grow. [The plan after 4.4.0](plan-after-4.4.0.md#gates-the-owners-decisions) states each as a gate, with the options.
