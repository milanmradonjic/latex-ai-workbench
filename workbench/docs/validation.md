# Validation follows the changed files

Ordinary notes, documentation, scripts and other files belong alongside the
manuscript. Creating or saving them does not start the workbench runtime. The
single-document editor's existing `onSave` setting builds saved TeX documents;
schema-3 generated settings use explicit named tasks and disable builds on save.
The workbench adds no general file watcher or save hook.

After a task, use the canonical Make interface:

```sh
make validation-plan  # explain the selected checks without running them
make validate         # execute that selection
```

With LaTeX enabled, `make check` always performs full manuscript validation. It is available
for an explicit complete check or when a human/agent knows an input dependency
that the classifier cannot discover. For unrelated code, also run the relevant
tests for that code: parsing Python is not a substitute for executing its tests.

| Changed files | Selected work |
|---|---|
| Ordinary Markdown, text, JSON, YAML, TOML or unrelated Python | Lightweight file checks; no manuscript build |
| AGENTS/CLAUDE, skills or agent permission files | File/structure checks and human/agent review of policy semantics |
| Workbench Python helpers/regression tests | File checks and package regression tests (only where the project hosts the distribution; see below) |
| Portability test runner | Regression and compiler portability tests |
| TeX/BibTeX, classes/styles, potential figures or CSV/TSV data | Manuscript `make check` |
| Makefiles, project/runtime/build configuration, editor integration, CI or workbench templates | File/policy checks, package regression/portability tests when distributed here, and manuscript `make check` |
| Unclassified inputs or unavailable comparison history | Conservative manuscript/full validation |

Package routing (the rows about workbench helpers, tests and templates) applies only
to a project that hosts this distribution. It is found at `validation.package`, or
else at `workbench/` when that directory has both a `Makefile` and the distribution's
`latex-ai-init`; an unrelated directory called `workbench` is not mistaken for it, and
`"package": null` turns the routing off. The package tests run with `make -C` in that
directory, and the generated CI workflow uses the same path.

A Markdown or code file included by LaTeX belongs to the manuscript category.
Routing recognizes literal inputs/listings, configured bibliography exports,
local build-command files, any braced file-name literal in the manuscript
sources that ends in an extension (for example `\verbatiminput{data/results.txt}` or
`\input{data/result file.txt}`, whatever macro reads it; spaces are fine) and recorder
(`.fls`) inputs. The recorder file lists everything a local build actually read, including
names that macros built, but it exists only after a local build and is not committed. A
fresh checkout (CI) therefore relies on the source scan, which cannot see names assembled
by macros or loops; declare those under `validation.manuscript_inputs`. Deleted paths and
both sides of renames count. Potential figure/data formats remain conservative even when
the current manuscript does not consume them.

For macro-generated, preprocessing or other inputs not reliably discovered,
declare additional project-relative globs in the optional configuration:

```json
"validation": {
  "manuscript_inputs": ["analysis/*.json", "generated/*.md"]
}
```

These patterns can add manuscript checks; they cannot exempt build inputs.

Conversely, paths that are never part of the manuscript build, such as a folder of notes with figures, would still
be treated conservatively: a `.png`, `.pdf` or `.csv` anywhere, or a file the planner cannot classify, selects the
manuscript checks. Declare those paths under `validation.ignore`:

```json
"validation": {
  "ignore": ["docs/**", "slides/*.pdf"]
}
```

Patterns are project-relative globs, validated like `manuscript_inputs` (no `..`, no absolute path), and `*` also
matches across folders, so `docs/*` and `docs/**` cover the same paths. An ignored path gets the file checks and
nothing from the manuscript build. Three kinds of path are never ignored, whatever is declared: what the build reads
(its dependencies and `manuscript_inputs`), build and configuration files (a `Makefile`, `latexmkrc`, the workflows,
`.latex-ai/`, the editor settings), and the agent's policy files (`AGENTS.md`, `CLAUDE.md`, `.claude/`). The planner
does not narrow routing from build records: an ignored folder that a `\graphicspath` reads is a mistake the
dependency scan will not always see, so ignore only what the manuscript does not use.
Inspect the plan and dependency declarations when adopting an existing project.

## Scope and comparison

The default is the complete working change against `HEAD`: staged and unstaged
tracked edits plus untracked, non-ignored files. No Git mutation is performed:
queries run with `GIT_OPTIONAL_LOCKS=0`, and `git diff` (which ignores that setting and
would rewrite a stale `.git/index`) runs against a throwaway copy of the index, so
`.git/index`, history and references are never changed. One thing no read can avoid: in a
repository that uses a split index, Git itself refreshes the modification time of the
shared-index file whenever any command loads the index (so `gc` will not prune it); its
contents do not change.
For an already committed change or a review, use a verified revision:

```sh
LATEX_AI_BASE=origin/main make validation-plan
LATEX_AI_BASE=origin/main make validate
```

The comparison is between that revision and the current working tree. Invalid,
all-zero, missing or unavailable history selects full validation. A clean
working tree selects no build; use `make check` to check the manuscript anyway.
A document whose last build failed or was interrupted stays selected until it
builds, even when its sources are back to the committed text.

With schema-3 named documents, validation checks only the selected documents.
Selected research and Markdown checks stay explicit in the shared action list
when full TeX validation runs as individual document checks. A project-wide
`make check` already covers enabled modules and subsumes those actions.
If the project's own Makefile gives `check` prerequisites or a recipe of its own
(outside the workbench block), `make validate` runs `make check` instead, so
those project-owned checks are never skipped. The JSON plan includes
`project_check`, and generated schema-3 CI consumes that same decision. Blank
lines/comments before recipes, variable targets and unresolved or missing
optional includes select the full project check conservatively. This costs
selective document validation when the scanner cannot prove a narrower scope;
it never expands Make code during planning. Ordinary double-colon `check::`
rules keep their rule style on installation. PDF verification and collection
run inside the same TeX container as compilation, before host artifact upload.
Existing local `validate` targets are preserved on adaptation: the reserved
`make latex-ai-plan` and `make latex-ai-validate` targets always expose this
workbench's selection.

For a precise known list, the project runtime also accepts `plan` or `validate`
with `--files README.md notes.md`. This list is explicit scope, not automatic
discovery; include deleted/renamed paths and all relevant changes. `plan --json`
provides machine-readable decisions. Planning never invokes validation tools.

## What the lightweight checks establish

They reject NULs and leftover `<<<<<<<`/`>>>>>>>` conflict marker lines (a lone
`=======` line is a valid Markdown/RST heading underline), parse changed JSON and Python/rule syntax,
check ordinary local inline Markdown links outside fenced examples, and verify
CLAUDE delegation when policy changes. They do not run formatters, access remote
links, parse every Markdown construct, validate arbitrary YAML/TOML schemas, or
prove policy semantics. Apply appropriate format-specific tools and judgment
when the task requires them. Generated Zotero data and permission guardrails
retain their existing editing restrictions.

Without LaTeX, `make check` applies the same file checks to every ordinary
project file: Git's view (tracked plus untracked and not ignored, so
`.gitignore` applies) when available, otherwise a directory walk. Both skip VCS
and workbench state, caches, `node_modules`, installed packages
(`site-packages`), Python virtual/conda environments (detected by `pyvenv.cfg` or
`conda-meta`, whatever the directory is called) and the run archive.

With the optional [Markdown module](markdown.md) enabled, declared notes use
Pandoc for local/reference-style links, Markdown anchors and citation-key checks.
Validation checks that document set after project changes so incoming links also
catch deleted targets. Planning requires no Pandoc invocation; validation does
not render HTML or run numerical snippets. Other Markdown retains the core's
lightweight inline-link check. Missing comparison history checks all enabled
modules. The plan's `markdown` flag also controls CI's Pandoc/Markdown step.

## CI

The workflow still starts on every push and pull request. Its always-present
`validate` job compares the push's previous revision or the pull request's base
against the checkout and uses the same runtime classifier. Missing history
falls back to full checks. Checkout includes history so ordinary comparisons
work without an extra Git mutation in the runtime.
The baseline comes from [GitHub's event context](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#github-context).

Every run checks the selected files/policy. Workbench regressions run only when
selected. The TeX container runs only for manuscript or portability checks;
PDF collection/upload runs only for manuscript checks. A documentation-only
push therefore reports a completed lightweight job without a TeX build or PDF
upload. CI selection does not affect local save behavior.

To run every selected check regardless of what changed (for example to confirm a release after
pushes that each selected only part of it), start the workflow by hand: **Actions, LaTeX AI
Workbench (Research AI Workbench in a project without LaTeX), Run workflow** (or `gh workflow run`, naming the workflow file). A manual run has no
previous revision, so the comparison base is empty and the runtime falls back to full checks, the
same as for a branch's first push. Ordinary pushes stay change-aware.

## Optional modules

A disabled module is never selected. Missing comparison history selects
all enabled checks, without introducing a TeX dependency into notes/numerics-only
projects. Module/control changes select their relevant full checks; package
compiler portability is selected only in a LaTeX-enabled distribution project.

Research manifests declare file dependencies and check cost. Changes to a task's
inputs/outputs select its module's cheap checks and freshness (when enabled).
Notes-only edits select notes structure/file checks; they do not run scientific
checks or require previously generated results to be current. Claims-only edits
check claim structure/links, and so do changes or deletions of a file cited as
evidence by any claim. Core routing includes `research_modules` so local
validation and CI's `make latex-ai-research-validate` use the same selection. Explicit
`make research-check` checks all enabled research modules.

`make run TASK=name` and `make figure TASK=name` are execution commands and are
never invoked by validation/freshness. A stale report fails a selected check and
leaves recomputation to an explicit task command. No new filesystem watcher or
save hook is installed. See [module configuration](modules.md) and
[records/freshness](research.md) for the limits of declared dependency checks.


## Local and CI execution contract

The JSON plan now includes an ordered `actions` list. The shared action table
in `core.py` defines package tests, compiler portability, full project checks,
and selected bibliography/research/Markdown checks. GitHub outputs named
`check_<action>` select those same actions; the original routing booleans remain
available for tool installation and artifact decisions. Full checks subsume the
individual module checks, preventing duplicate execution. Package unit tests and
portability are separate actions both locally and in CI.

Module runtime files, check groups and base tool requirements are registered in
`core.MODULES`. Planning and installation use schema 3 with module defaults. Compilation uses
one resolved settings representation per document; inspection never rewrites
the persisted project configuration.

## Document selection (schema 3)

Plans include `documents` and `document_reasons`. A changed input selects each
document consuming it, including hard-link aliases and deleted declared inputs.
Unknown TeX/resources and shared build policy select all targets. Selective
validation uses canonical document Make commands and reports every failed
selected target. The `manuscript` boolean reports whether any TeX validation is selected. See [TeX notes](tex-notes.md).

