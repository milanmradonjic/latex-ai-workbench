<!-- Generated from handbook.py by `make -C workbench handbook`; do not edit it by hand. -->
# LaTeX AI Workbench 4.0.0: guide

This is the printable copy of the guide that `make guide` shows in a project and `make guide-html` writes as a web page. In a project the commands are shown under the names that work there.

## What this is

The workbench is a set of `make` commands that live inside your project. They check your files, build your PDF, remember what was built from what, and tell you when something is out of date. It never edits your writing, and it never changes Git: committing is always your decision.

You do not have to learn all of it. Five commands cover most days:

- **`make status`**: Where the project stands, and what to do next. Start here whenever you are unsure.
- **`make validate`**: After editing: run only the checks your changes need. `make validation-plan` previews them.
- **`make check`**: The full check of everything. Run it before you share the work.
- **`make build`**: Build the PDF of a LaTeX document, when LaTeX is on.
- **`make guide`**: This guide. `make guide-html` writes it as a web page.

Type commands in the project folder, the one that holds `.latex-ai.json`. If a command is not found, or does something you did not expect, your own Makefile may already use that name: see the topic `names`.

## Contents

**Understand it**

- [What lives where](#what-lives-where): The folders and files, and who owns each
- [The everyday loop](#the-everyday-loop): What to run, in what order, while you work
- [What runs when](#what-runs-when): Why `make validate` runs less than `make check`
- [Document states](#document-states): What current, stale, failed, running and missing mean
- [Command names](#command-names): Why a command can have two names, and the variables it takes

**Do something**

- [I want to put the workbench into a project](#i-want-to-put-the-workbench-into-a-project): Preview, apply, then look around
- [I just installed it. What do I do first?](#i-just-installed-it-what-do-i-do-first): Look around, then run the first check
- [I changed something. What do I run?](#i-changed-something-what-do-i-run): Preview the checks, run them, check everything before sharing
- [I want a PDF I can send](#i-want-a-pdf-i-can-send): Build it, check it, copy out the verified file
- [I see stale, failed or missing in the status. What now?](#i-see-stale-failed-or-missing-in-the-status-what-now): Find out why, rebuild that one document
- [I already had a paper, and ChkTeX warnings fail the check](#i-already-had-a-paper-and-chktex-warnings-fail-the-check): Fix them, or record today's as accepted
- [I want a second TeX document next to my paper](#i-want-a-second-tex-document-next-to-my-paper): Register another root file as a named document
- [I want to turn a module on or off](#i-want-to-turn-a-module-on-or-off): Modules are optional capabilities; switch them with the installer
- [I want to move to a newer release](#i-want-to-move-to-a-newer-release): Preview with the new package, read the plan, apply
- [I want an AI assistant to work on this project](#i-want-an-ai-assistant-to-work-on-this-project): What to tell it, and what it will ask you
- [I think the workbench itself is wrong](#i-think-the-workbench-itself-is-wrong): Write a local report instead of working around it

**Look something up**

- [Reading a message](#reading-a-message): What the messages the workbench prints are telling you
- [Glossary](#glossary): The words this tool uses

## What lives where

```text
your project folder
┌────────────────────────────────────────────────────────────────────────┐
│ YOURS: the workbench never overwrites these                            │
│   main.tex  refs.bib  notes/  data  scripts  your own Makefile rules   │
├────────────────────────────────────────────────────────────────────────┤
│ SETTINGS: you edit them, or `latex-ai-init configure` does             │
│   .latex-ai.json   which modules are on, which documents exist         │
│   Makefile         your rules, plus one marked block of workbench ones │
│   AGENTS.md        the rules an AI assistant follows here              │
├────────────────────────────────────────────────────────────────────────┤
│ THE WORKBENCH: an installed copy; never edit it by hand                │
│   .latex-ai/*.py             the code that `make ...` runs             │
│   .latex-ai/installation.json  what was installed; keep it in Git      │
├────────────────────────────────────────────────────────────────────────┤
│ WHAT IT RECORDS: written by the commands                               │
│   .latex-ai/artifacts/   build receipts, exported PDFs, reports        │
│                          (Git ignores this folder)                     │
└────────────────────────────────────────────────────────────────────────┘
```

*Four kinds of file: yours, settings, the installed workbench, and what it records.*

Rule of thumb: edit YOURS and SETTINGS, and only read the rest. If something in the workbench part looks wrong, do not repair it by hand: report it (topic `defect`).

## The everyday loop

```text
┌──────────────────────┐
│     make status      │  where do things stand, and what comes next?
└───────────┬──────────┘
            ▼
┌──────────────────────┐
│   edit your files    │  TeX, notes, data: as you always do
└───────────┬──────────┘
            ▼
┌──────────────────────┐
│ make validation-plan │  which checks do my changes need? (runs nothing)
└───────────┬──────────┘
            ▼
┌──────────────────────┐
│    make validate     │  run exactly those checks; repeat until they pass
└───────────┬──────────┘
            ▼
┌──────────────────────┐
│      make check      │  everything, once, before you share the work
└───────────┬──────────┘
            ▼
┌──────────────────────┐
│       git diff       │  you review; committing is your decision
└──────────────────────┘
```

*The loop for a normal working session. Only the last step before sharing is `make check`.*

> **Note.** Choosing checks by what changed compares your files with the last Git commit. Without a Git repository, or before the first commit, every check is selected and `make status` says so.

## What runs when

```text
 you changed                      make validate runs
┌────────────────────────────┐   ┌────────────────────────────────────────┐
│ notes, Markdown, scripts   │──▶│ quick file checks, no TeX build        │
│ AGENTS.md, permissions     │──▶│ structure checks; you review meaning   │
│ .tex, .bib, figures, data  │──▶│ build and check documents using them   │
│ Makefile, settings, CI     │──▶│ file checks, then a full check         │
│ no Git, or unknown files   │──▶│ everything, to be safe                 │
└────────────────────────────┘   └────────────────────────────────────────┘
```

*How the files you changed decide what `make validate` runs.*

`make validate` is the quick one: it asks Git which files changed and runs only the checks they need. `make check` always covers everything, though it may reuse a build whose verified record is still current.

`make validation-plan` shows the selection and the reason for each choice without running anything.

> **Note.** If your own Makefile gives `check` rules of its own, `make validate` runs `make check` so that they are never skipped.

## Document states

```text
┌─────────┐ make document-check ┌─────────┐ you edit a source ┌───────┐
│ missing ├────────────────────▶│ current ├──────────────────▶│ stale │
└─────────┘   (build succeeds)  └─────────┘ or a build setting└───┬───┘
                                     ▲                            │
                                     └────────────────────────────┘
                                    make document-check (succeeds)

A build that fails or is interrupted leaves the document   failed
A build that is in progress shows as                       running
```

*The life of a LaTeX document's build. Only `current` means its PDF can be trusted.*

- **current**: The last verified build matches the sources and settings as they are now. Nothing to do.
- **stale**: A source or a build setting changed since the verified build. `make status` lists what changed under the document; rebuild with `make document-check DOC=name`.
- **failed**: The last build failed or was interrupted. Read the first compiler error it printed, fix the source, rebuild. Restoring the old text does not clear it; only a successful build does.
- **running**: A build is in progress. Wait for it; `make status` shows its owner and compiler. docs/troubleshooting.md in the workbench package explains how to inspect it safely.
- **missing**: Never built, so there is no PDF to trust yet. `make document-check DOC=name` builds and checks it.

> **Note.** An exported PDF (`make pdf-artifact`) is a copy. Rebuilding does not update it; export again.

## Command names

```text
make build ──▶ does your Makefile already have a `build` target?
                    │ no                       │ yes
                    ▼                          ▼
      the workbench's build       your recipe runs, unchanged.
      (a short alias)             The workbench's own is
                                  `make latex-ai-build`
```

*A short name is only an alias; your own rule always wins.*

Every workbench command has a long name that starts with `latex-ai-` and always reaches the workbench. The short name (`build`, `help`, `doctor`) is added only where your Makefile has no target of that name. `make help` and this guide show the names that work in your project.

Some commands take a variable after the command, for example `make build DOC=notes`:

- **`DOC=name`**: Choose a document. Without it, the default document is used.
- **`TOPIC=name`**: Choose a part of this guide, for example `make guide TOPIC=loop`.
- **`ISSUE_NOTE="..."`**: What you saw and what you expected, for `make latex-ai-issue`.

`latex-ai-init` is not a Make target. It is a file in the workbench package that installs, upgrades, audits and reconfigures a project, so you run it as `python3 /path/to/workbench/latex-ai-init`.

## I want to put the workbench into a project

1. Look first. This writes nothing and lists what would be added:

   ```sh
   python3 /path/to/workbench/latex-ai-init init /path/to/project \
       --dry-run --diff
   ```
2. A folder with one main `.tex` file needs nothing more (with several, add `--root thesis.tex`). For an empty folder, or one without a manuscript, say what it is for: add `--profile core` (the other is `writing`).
3. If the preview is right, run the same command without `--dry-run --diff`.
4. Then, in the project folder:

   ```sh
   make help
   ```

> **Note.** The installer never overwrites your files, never touches Git, and backs up the files it manages before replacing them. A paper that has its own Makefile also needs the command that builds it (`--build-command`); the installer says so. Run it as `python3 /path/to/workbench/latex-ai-init`: it is a file in the workbench package, not a command on your PATH.

## I just installed it. What do I do first?

Run these in the project folder, one at a time.

1. See which commands this project has:

   ```sh
   make help
   ```
2. See where things stand and what to do next:

   ```sh
   make status
   ```
3. Confirm that the tools it needs are installed (LaTeX projects need a TeX distribution):

   ```sh
   make doctor
   ```
4. Run the first full check:

   ```sh
   make check
   ```

> **Note.** A paper you already had usually has some ChkTeX warnings, and they fail the check: see the topic `baseline`. If you see `INTERNAL ERROR`, see `defect`. Nothing here changes Git.

## I changed something. What do I run?

1. Preview which checks your changes need. This runs nothing:

   ```sh
   make validation-plan
   ```
2. Run those checks:

   ```sh
   make validate
   ```
3. Fix what it reports and repeat.
4. Before you share the work, check everything:

   ```sh
   make check
   ```
5. Review the changes yourself. Committing is your decision:

   ```sh
   git diff
   ```

> **Note.** Choosing checks by what changed needs a Git repository with at least one commit. Without one, every check runs and `make status` says so. The topic `checks` explains the choice.

## I want a PDF I can send

1. Build it. `DOC=name` picks a document other than the default:

   ```sh
   make build
   ```
2. Check it, including bibliography and ChkTeX:

   ```sh
   make check
   ```
3. Copy the verified PDF out:

   ```sh
   make pdf-artifact
   ```

The copy lands under `.latex-ai/artifacts/`; for a named document it is `.latex-ai/artifacts/documents/NAME/document.pdf`.

> **Note.** Export refuses a PDF whose build is not `current` (topic `states`). Rebuilding does not update an earlier copy, so export again after a rebuild.

## I see stale, failed or missing in the status. What now?

Each document has a state (topic `states`). Only `current` means its PDF can be trusted.

1. Read the lines under the document in the status. They name what changed:

   ```sh
   make status
   ```
2. Rebuild and check that one document:

   ```sh
   make document-check DOC=name
   ```
3. If it fails, read the first error it prints (it names the compiler log), fix the source, and run the same command again.
4. If it says another build is active, wait. `make status` shows who owns it. Do not delete lock or receipt files.

## I already had a paper, and ChkTeX warnings fail the check

ChkTeX warnings fail `make check`, and a paper that already exists usually has some. There are two honest choices.

1. Fix the warnings one by one. List them with:

   ```sh
   make lint
   ```
2. Or accept today's warnings as a recorded baseline. From then on only new warnings fail:

   ```sh
   make lint-baseline
   ```
3. Run `make check` again.

> **Note.** Accepting a baseline is the owner's decision, not a routine step: an assistant should ask you first. The list is saved under `.latex-ai/lint-baselines/` unless the configuration says otherwise, and belongs in version control.

## I want a second TeX document next to my paper

1. Write the new document as a complete `.tex` file, for example `notes/derivation.tex`.
2. Preview the registration, then apply it by running the same command without `--dry-run --diff`:

   ```sh
   python3 /path/to/workbench/latex-ai-init configure . \
       --document derivation --root notes/derivation.tex --dry-run --diff
   ```
3. Build and check the new document:

   ```sh
   make document-check DOC=derivation
   ```
4. Export its PDF:

   ```sh
   make pdf-artifact DOC=derivation
   ```
5. List every document and its state:

   ```sh
   make documents
   ```

> **Note.** Each document has its own build record and PDF. `make check` covers all of them, and `make build` without `DOC` uses the default document.

## I want to turn a module on or off

`make help` lists the modules that are not enabled here and prints the command that enables one.

1. Preview the change, with a module's name instead of NAME (for example `markdown`):

   ```sh
   python3 /path/to/workbench/latex-ai-init configure . \
       --enable NAME --dry-run --diff
   ```
2. If the preview is what you want, run the same command without `--dry-run --diff`.
3. To turn one off, use `--disable NAME` the same way. Your files are kept.

> **Note.** `latex-ai-init` is a file in the workbench package, not a command on your PATH: run it as `python3 /path/to/workbench/latex-ai-init`.

## I want to move to a newer release

1. Run the NEW package's installer in preview mode:

   ```sh
   python3 /path/to/new-workbench/latex-ai-init upgrade . --dry-run --diff
   ```
2. Read the plan. Conflicts are reported by name and there is no overwrite switch: reconcile them deliberately.
3. Apply it by running the same command without `--dry-run`. Files that change get a backup first.
4. Then confirm the tools and the project:

   ```sh
   make doctor
   ```
5. And check everything:

   ```sh
   make check
   ```

> **Note.** Never delete `.latex-ai/installation.json` to force an upgrade. It is what makes merging safe.

## I want an AI assistant to work on this project

1. Point it at `AGENTS.md` in the project root. That is the policy it follows, and the installer put it there.
2. Ask it to start with `make status`, to run `make validate` after its edits and `make check` before it says it is done.
3. Expect a question before any Git change: staging, committing, pushing, switching branches and the like need your approval. Answer deliberately; these prompts are guardrails, not a security boundary.
4. It must not edit `.latex-ai/` or loosen a check to get a pass. If it believes the workbench is wrong, it should write a report (topic `defect`) and tell you.

> **Note.** For a second opinion, ask another assistant to review the diff under the same `AGENTS.md`. docs/agents.md describes the writer and reviewer roles.

## I think the workbench itself is wrong

An ordinary failure prints `ERROR:`; your file or tool is at fault and the message says which. `INTERNAL ERROR` means the workbench itself failed. A check that passes when it plainly should not is the other case worth reporting.

1. Write a local report:

   ```sh
   make latex-ai-issue ISSUE_NOTE="observed ... expected ..."
   ```
2. It is saved as `.latex-ai/artifacts/issues/report-*.json`. Nothing is sent anywhere, so read it first if you like.
3. Pass it to whoever maintains the workbench, and do not trust the verdict that looked wrong until it has been looked at.

> **Note.** Do not edit the installed files in `.latex-ai/`. A repair belongs in the workbench package, with a test.

## Reading a message

- **`ERROR: ...`**: An ordinary failure with a cause you can fix. Read the file or tool it names. A `Hint:` line below it, when present, is the next action.
- **`INTERNAL ERROR`**: A fault inside the workbench, not in your project. Report it (topic `defect`).
- **`Configuration problem`**: `.latex-ai.json` is missing or cannot be read. `make help`, `make status`, `make guide` and `make latex-ai-issue` still work, and the message says how to fix it.
- **`Module is disabled: NAME`**: The command belongs to a module that is off here. The hint prints the command that turns it on (topic `module`).
- **`Another build is active`**: A build is already running, or its compiler still is. Wait; `make status` shows the owner.
- **`Build inputs changed during execution`**: A generator rewrote a file the document reads while it was being built. The message names the files; docs/troubleshooting.md in the workbench package explains the fix.

docs/troubleshooting.md in the workbench package has a table of symptoms and the next action for each.

## Glossary

- **AGENTS.md**: The rules file an AI assistant reads first. Among them: Git changes need your approval.
- **Alias**: A short command name such as `build` that points to the long `latex-ai-` name. It exists only where your Makefile has no target of that name.
- **Artifact**: A file the workbench writes under `.latex-ai/artifacts/`: build receipts, exported PDFs, reports and the web version of this guide. Git ignores them.
- **Baseline (lint)**: A recorded list of ChkTeX warnings you chose to accept. Only new warnings fail.
- **Build receipt**: The record of one build: what was compiled, with which settings, from which file contents, producing which outputs. It is what lets the workbench say a PDF is current.
- **Check and validate**: `make check` runs everything. `make validate` runs only what your changed files need.
- **Configuration**: `.latex-ai.json`: which modules are on and which documents exist.
- **Document**: A LaTeX file the workbench builds under a name of its own, with its own receipt and PDF. Your paper is one; a supplement or notes can be more.
- **Doctor**: `make doctor` checks that the tools the project needs are installed.
- **Evidence**: What the commands record about what happened: build receipts. It does not prove that your science is right.
- **Installer**: `latex-ai-init`, a file in the workbench package that installs, upgrades, audits and reconfigures a project. Run it as `python3 /path/to/workbench/latex-ai-init`.
- **Manifest**: The installation manifest `.latex-ai/installation.json` records what was installed.
- **Module**: An optional capability: latex, bibliography, markdown.
- **Plan**: The preview of which checks your changes need (`make validation-plan`).
- **Profile**: A starting choice of modules made at install time. It is not a lasting policy.
- **Reserved name**: The long `latex-ai-` name of a command, which works in every project.
- **Root**: The main `.tex` file of a document.
- **Runtime**: The workbench code installed in `.latex-ai/`. It belongs to the workbench: do not edit it.
- **Schema**: The version of the configuration format. Workbench 3 reads schema 3 only.
- **Stale**: Out of date: a document whose sources or settings changed since its verified build.
- **Verified**: Said of a PDF whose build receipt matches the sources and settings as they are now.
- **Workbench**: This tool: the commands, their checks and the records they keep.
