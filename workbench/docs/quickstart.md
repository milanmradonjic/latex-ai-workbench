# Quickstart

From an existing paper or an empty folder to a first passing check. You need Python 3.10+ and
`make`. TeX (`latexmk` and an engine) is only needed when the project builds a LaTeX manuscript;
notes and numerical projects need nothing more.

## 1. Install the workbench in your project

Look first; this writes nothing and lists the files it would add. For a folder that already
holds a paper:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run
```

For a folder without a manuscript, that needs only the file checks and the agent rules:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --profile core --dry-run
```

Add `--diff` to read the content of the files your project will own; the summary comes last.
Then apply it by running the same command without `--dry-run`.

The profiles are `core` and `writing`; an explicit
`--modules` list also works. A LaTeX project needs its main `.tex` file to exist already: a single
one is detected, otherwise pass `--root`. Without a profile, a paper gets the manuscript checks
(and bibliography checks when it has one), plus VS Code settings; `--skip-editor` leaves them out. A module is turned on later by adding it to `modules` in `.latex-ai.json` ([modules](modules.md)). A paper
that is built by something other than latexmk is declared with `--build-command '["make", "pdf"]'` (a target you add to the
Makefile after `init`). A project that already has a Makefile or policy files is migrated: see [migrating](migrating.md).

The installer does not overwrite your manuscript or other project files, backs up the files it
manages before replacing them, never touches Git, and ends with a summary and the commands to try
next. An `ERROR:` names an ordinary failure; common setup errors also include a
`Hint:` with a recovery action. In the Makefile, `AGENTS.md`
and `.gitignore` it creates, anything you add above or below its text is yours. More options are in [installing](installing.md).

`latex-ai-init` is a file in the workbench package, not a command on your PATH: wherever this
guide or a hint shows it, run it as `python3 /path/to/workbench/latex-ai-init`.

## 2. Look around

Use the commands the installer printed under "Next". In a project that had no Makefile they are:

```sh
cd /path/to/project
make help      # the commands this project has
make status    # where it stands and what to do next
make doctor    # are the required tools installed?
make guide     # a short manual for this project
```

If you give `help`, `status` or `doctor` a recipe of your own, `make help` shows only your own targets. The workbench commands are then
`make latex-ai-help`, `make latex-ai-status` and `make latex-ai-doctor` (and `make latex-ai-guide`);
these long names work in every project.

## 3. Run the first check

```sh
make check
```

This runs every enabled module's checks, and builds the manuscript when LaTeX is enabled.

## 4. Work, then validate

Edit as usual. Then:

```sh
make validate         # only the checks your changed files need
make validation-plan  # preview that selection without running it
```

A documentation-only edit skips the TeX build. Selecting checks by what changed compares your
files with the last commit, so it needs the project to be a Git repository with at least one
commit; without one, every check is selected and `make status` says so. Commit the installed
files first, so that later edits are compared with them. Run `make check` before sharing. Review with `git diff`; commits are yours to make, and agents are set up to ask first.
See [daily use](daily-use.md).

## When something goes wrong

- A line starting `ERROR:` is an ordinary failure. Read its named file or tool;
  a `Hint:`, when present, gives the next action.
- `make check` builds the manuscript first and then runs ChkTeX, whose warnings fail the check. An
  existing paper usually has some. Correct them, or run `make latex-ai-lint-baseline` once: it
  records today's warnings in the document's declared baseline (by default
  `.latex-ai/lint-baselines/manuscript.json`), and from then on only new
  warnings fail. A `.chktexrc` or the `lint` settings in `.latex-ai.json` fit the checker itself
  ([configuration](configuration.md)).
- `INTERNAL ERROR` means a fault in the workbench itself, not in your project. Run
  `make latex-ai-issue ISSUE_NOTE="what you saw, and what you expected"` and pass on the local
  report it writes (nothing is sent anywhere). See [agents](agents.md#suspected-workbench-defects).
- `make help` and `make status` still work when the configuration file is broken.

## Updating

```sh
python3 /path/to/new-workbench/latex-ai-init diff /path/to/project --diff
python3 /path/to/new-workbench/latex-ai-init runtime /path/to/project
```

Read the difference, then refresh the runtime files. An agent can follow the whole recipe: [updating](upgrading.md).
