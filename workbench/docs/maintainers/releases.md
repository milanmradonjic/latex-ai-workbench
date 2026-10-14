# Maintaining a release, and what each release changed

Workbench 4 is the supported development line. Entries for earlier releases are
retained historical records, with no backports or compatibility commitment.

## 4.5.0 — one engine, one bibliography program, no installer profiles

Step 3.4 of [the plan after 4.4.0](plan-after-4.4.0.md), with the owner's decisions of 14 October 2026: no biber, and the `biblatex` export format goes too.

- **Removed from `init`:** `--engine`, `--backend` and `--profile` (`core.PROFILES` with it). `--modules` chooses what a profile chose: `--modules ''` was `--profile core`,
  `--modules latex` was `--profile writing`. The installer no longer reads the source for an engine (a `% !TeX program` comment, `luacode`, `xeCJK`, `fontspec`) or for biber
  (`biblatex`, `\addbibresource`); it still finds a BibTeX bibliography by `\bibliography{...}`.
- **Refused by name, with a hint that points at `build_command`:** an `engine` other than `pdflatex`, a `backend` other than `none` or `bibtex`, and an export `format` other than
  `bibtex`, in a document, in `latex.defaults` or in `bibliography.export`. A configuration that says `pdflatex`, `none`, `bibtex` keeps working unchanged.
- **Removed from the runtime:** the `-lualatex` and `-xelatex` flags of the default build; Biber's `ERROR -`, `FATAL -` and `WARN -` log patterns, and `Biber` in the rerun
  pattern; `lualatex`, `xelatex` and `biber` from `doctor`'s tool list and from the diagnostic report. A project that builds with biber declares a `build_command`; the workbench
  reads the compiler's `.log` for LaTeX's own errors and does not read Biber's `.blg`.
- **Changed output:** `status`, `help` and `guide` print the hint of a refused configuration ("edit .latex-ai.json: remove the engine setting ...") in place of the advice to restore a last good copy,
  which after an upgrade is the same configuration. A problem with no hint of its own keeps the old advice.
- **A loss:** a paper that uses biblatex, even with `backend=bibtex` (BibTeX does the processing), is no longer recognised by `init`: it gets `backend: none` and no bibliography module.
  List its files in `bibliography.files` and set `backend` to `bibtex` by hand.
- **Changed text:** the sentence of the policy template (`AGENTS.md`) that named "BibTeX/Biber" now says BibTeX. A project that `diff` compares with this release sees `AGENTS.md`
  differ, as it does for any file it may have added to.
- **Unchanged:** every project that uses only what stays. 232 comparisons of 4.4.2 against this tree, on eight kinds of project (four with a real `latexmk`, `chktex` and `bibtex`),
  found no difference: the generated files, the output of every installer preview and runtime action, the build receipts, and the arguments `latexmk` was called with
  ([the record](verification-4.5.0.md)). The generated Makefile and editor files are byte-identical (the guard's fixtures, renamed from `profile-*`, hold the same text).
- **Size:** the package is 3,936 lines, from 3,948: most of what went was a table entry or a branch, not a module, and the clearer refusals and the hint in `status` took some back. Tests: 361 before, 373 now (12 new).

See [the verification record](verification-4.5.0.md).

## 4.4.2 — a module declares only what something reads

Step 3.2 of [the plan after 4.4.0](plan-after-4.4.0.md): a removal of fields nothing used.

- **Removed:** the `tools` and `requires` lists and the `check_group` of both entries of `core.MODULES` (both lists were empty for both modules, and no caller passed a group),
  the `group` parameter of `module_names`, and the check in `validate_config` that the modules a module requires are enabled (it could not fail).
- **Changed output:** `make modules` no longer prints a `requires` list for each module; it was always `[]`. Nothing else it prints changes.
- **Unchanged:** the order of the modules, what the schema accepts and refuses (messages included), the tools `doctor` asks for, the generated files and the build receipts:
  104 comparisons of 4.4.1 against this tree, on four kinds of project and six broken configurations, found no difference beyond the `requires` list
  ([the record](verification-4.4.2.md)).
- **Size:** the package is 3,948 lines, from 3,952. Tests: 356 before, 361 now (5 new).

See [the verification record](verification-4.4.2.md).

## 4.4.1 — refreshing the runtime no longer renders a project's files

Step 3.1 of [the plan after 4.4.0](plan-after-4.4.0.md): a refactor that changes nothing `init`, `diff` or `runtime` print or write.

- **Changed:** `bootstrap.runtime_files(config)` is the runtime half of `desired_files`, which now builds on it. `runtime` refreshes from it, so it no longer renders the
  policy, Makefile and editor files only to discard them, and no longer depends on them being renderable for the project. `diff` renders once, where it rendered twice, and
  reads each runtime file once, where it read a differing one twice.
- **Fixed:** the two schema errors that said "Workbench 3 supports only project configuration schema 3" say Workbench 4, and the header of this file no longer calls
  Workbench 3 the supported line.
- **Unchanged:** what `init`, `diff` and `runtime` print and write, apart from the version and the two schema messages (which travel in the vendored `core.py` and
  `schema.py`): 210 comparisons of 4.4.0 against this tree, on five kinds of project, found no difference ([the record](verification-4.4.1.md)). The generated Makefile,
  editor files and build receipts are untouched.
- **Size:** the package is 3,952 lines, from 3,948: this step removes duplicated work and a coupling, not lines. Tests: 351 before, 356 now (5 new).

See [the verification record](verification-4.4.1.md).

## 4.4.0 — the workbench no longer adapts to a project's own Makefile; existing projects are migrated

The fifth step of [the minimal scope](minimal-scope.md), and the owner's decision after 4.3.0: not to cope with any existing project, but to
migrate it to the workbench's layout.

- **Removed:** `make_graph.py` (the lexical Make parser and rule graph, 174 lines), `adapters.py` (the adapter that merged a block into a project's Makefile,
  `merge_block` and the policy-text blocks, 204 lines), `recipe-shell.sh`; the actions `build-prepare`, `build-finish` and `build-shell` (the hooks of a wrapped
  Make build) with `--build-owner`, `--shell` and `latex.build_phase`; the check of the adopted Make graph in `schema.py` (shared targets, recursion through
  prerequisites, unresolved ownership); the requirement of GNU Make 4.3 and its check in `doctor` and in `init`; the merging of JSON editor files and of
  `AGENTS.md`, `CLAUDE.md` and `.gitignore`; the reading of a project's Makefile and build files to guess the engine or a `build_command`;
  the notes "kept your Makefile target" and the managed-block normalisation of Make-policy input digests.
- **`init` is create-only.** A file that is absent is written; one that is already what `init` would write is left; one that differs, in any
  of `AGENTS.md`, `CLAUDE.md`, `.gitignore`, the Makefile (under any of its three spellings), `.vscode/*`, `.claude/`, `.codex/` or `.latex-ai/`, is a `CONFLICT`, and
  nothing is written until none is left. The message names `docs/migrating.md`.
- **`docs/migrating.md`** is the recipe an agent follows to bring an existing project over: snapshot, read, decide the build, clear an older workbench's generated files,
  find the conflicts, `init`, carry the project's content back after what `init` wrote, replace a stale workflow, accept a lint baseline (the owner's decision), verify.
- **A project's own Make targets** go after what `init` wrote. A `build_command` of `["make", "pdf"]` runs like any other build command; the Makefile is then a
  recorded input of the build (hashed whole; an included Makefile is no longer followed, so declare it in `inputs`). The short `build` joins the goals a
  `build_command` may not name, since it is always the workbench's alias now.
- **`validate`** still runs `make check` when the Makefile gives `check` anything beyond what `init` wrote, now decided by a few lines of `guide.project_check_rule`
  instead of the parser, and conservatively (an include, an eval, a computed target, a second recipe, prerequisites).
- **A project that an older release adapted** (its Makefile carries the block with `latex-ai-build-prepare`) keeps running on its own 4.3 runtime. `runtime` refuses to refresh
  it, `status` says so, and the removed hooks answer with a pointer instead of "invalid choice". Migrating it is the recipe's fourth step.
- **Unchanged:** the generated Makefile and editor files of every fresh install are byte-identical (the guard's fixtures), the build, the receipts and the locks. What the
  fresh Makefile asks of Make is nothing: the 3.81 that macOS ships runs it (tested).
- **Size:** the package is 3,948 lines, from 4,511; `bootstrap.py` 614 to 557. Tests: 365 before, 351 now: 19 new scope tests, 2 adapted, 35 gone with the adoption.

See [the verification record](verification-4.4.0.md).

## 4.3.0 — the installer creates projects; it no longer audits, upgrades, configures or recovers

The fourth step of [the minimal scope](minimal-scope.md).

- **Removed:** the installer modes `upgrade`, `audit`, `configure` and `recover` and the options only they used (`--enable`, `--disable`,
  `--document`, `--default-document`); `installation.py` (the installation transaction, its lock and interruption journal
  `.latex-ai/transaction.json`, and the ownership checks); the three-way merge of JSON and text; the record of every managed file with the
  installed and upstream text kept as merge baselines; and the configuration field `disabled_modules` (a module is on when `modules` has
  it, off when it does not, and its settings are not kept).
- **Added:** `latex-ai-init diff PROJECT [--diff]`, which says how a project differs from this release (runtime files that differ or are
  missing, and policy, Makefile and editor files that differ from what a new project would get) and writes nothing, exit 1 when a runtime
  file differs; and `latex-ai-init runtime PROJECT [--dry-run] [--force]`, which refreshes the vendored `.latex-ai/*.py` files and the record,
  backs up what it replaces, and refuses a file that was edited locally unless `--force` is given. `diff` and `runtime` refuse the options
  only `init` reads instead of ignoring them.
- **`init`** writes the same files as before, byte for byte (see the verification), and now refuses a project that already has
  `.latex-ai/installation.json`; a project's own `.latex-ai.json` is used as it is.
- **The record** `.latex-ai/installation.json` holds the release and a digest of each runtime file, nothing else. A record written by 4.2
  or earlier is still read, so a project installed by them is refreshed by `runtime` without a conflict. `status` and `issue` say "record"
  where they said "manifest".
- **Updating** is a recipe an agent follows, written in `docs/upgrading.md` (be able to undo; read these notes; `diff`; `runtime`; read and edit
  the files that are the project's; `make doctor`, `make check`, `git diff`), not a command. The skill's installation reference follows it.
- **A project that disabled a module** with `configure --disable` has `disabled_modules` in `.latex-ai.json`; this release refuses it by name,
  with a hint (delete it, or copy its settings into `modules`). Nothing is written before that.
- **Not removed:** the merging of `init` into a Makefile, policy and editor files a project already has (`make_adapter`, the Make adoption layer, goes in
  the build-core step), and the build locks. The runtime files of earlier releases that no longer exist (for example `.latex-ai/handbook.py`) stay in
  a project; `runtime` never deletes.
- **Size:** `bootstrap.py` and `installation.py` were 803 lines, `bootstrap.py` alone is now 614; `diagnostics.py` 206 to 171. Tests: 363 before,
  365 now: 25 new scope tests, 6 adapted, 23 gone with the machinery.

See [the verification record](verification-4.3.0.md).

## 4.2.0 — the long generated handbook is replaced by a short manual

The third step of [the minimal scope](minimal-scope.md).

- **Removed:** `handbook.py` (724 lines: the pictures, twelve how-tos, the glossary, and three renderers for them), its generated copies
  `docs/handbook.md` and `docs/handbook.html`, `make handbook`, the `guide-html` command and its web page, the `TOPIC` variable and the
  `--topic` option, and the guide's own tests.
- **Added:** `make guide` prints a short manual of one screen, `guide.manual_text`: the project's modules and documents with their states,
  the everyday loop, what to run for one document, what the states mean, what to do when something goes wrong, and how AI agents work here.
  It is written with the command names that work in that project (where the Makefile keeps its own `build`, the manual says
  `make latex-ai-build`) and reads and writes nothing. A test keeps it under 60 lines.
- **Generated files:** the Makefile block of every installed project loses the `guide-html` targets and `export DOC TOPIC` becomes
  `export DOC`; the editor files are byte-identical. An upgrade rewrites the block; a `.latex-ai/handbook.py` an earlier release installed
  stays in the project as a retained file (the installer does not delete), and nothing uses it.
- **Tests:** the handbook's tests went, the guide's tests are rewritten for the manual, and 4 new ones pin what is gone (371 tests after 4.1.0, 363 now).

See [the verification record](verification-4.2.0.md).

## 4.1.0 — the workbench no longer generates CI workflows

The second step of [the minimal scope](minimal-scope.md). The releases of this series remove features in minor releases:
what a project had that is now gone is refused by name, with a hint, or, where it is only a setting, dropped by the upgrade.

- **Removed:** the generator of `.github/workflows/latex-ai.yml` (about 180 lines of `adapters.py`: the workflow for a project with
  and without LaTeX, the table of pinned actions and the code that applied it), the options `--ci`, `--no-ci` and `--no-artifact`, the
  setting `integrations.ci` (`enabled`, `pdf_artifact`, `texlive_version`), the `ci` entry of every document's resolved view, the
  `--github-output` option of `plan` with the `check_*` outputs it wrote, and the stage field of the validation actions.
- **An upgrade of an older install** removes `integrations.ci` from `.latex-ai.json` and says so; the runtime refuses a configuration that
  still has it, with a hint. A workflow an earlier release wrote stays in `.github/workflows/` as the project's own file, no longer
  tracked by the manifest; the workbench never writes, changes or removes a workflow now.
- **Unchanged:** the Makefile block and the editor files are byte-identical, and `make pdf-artifact` still copies the verified PDF to
  `.latex-ai/artifacts/` (it was switched by `pdf_artifact` and is always on now).
- **This repository's own workflows** were generated by that generator; they are plain files now. `latex.yml` runs the file checks and then,
  in one TeX Live container, the portability tests and the reference manuscript's check, on pull requests and on pushes to `main`
  (its job is still called `validate`, the check the ruleset requires). The acceptance workflow for the several-document example and its
  generator are gone: the portability tests cover that example. The Python workflow is unchanged.
- **Tests:** the 14 tests of the generator went (379 to 365) and 6 new ones make 371; `tests/test_scope_4_1_0.py` pins what is gone and fails against
  4.0.0 in every part.

See [the verification record](verification-4.1.0.md).

## 4.0.0 — the research, notes and Markdown modules are removed

The first step of [the minimal scope](minimal-scope.md): what the owner does not need goes, so that what remains is small enough to
keep in mind. This is a breaking release. Nothing of a project's own files is touched.

- **Removed modules:** `numerics`, `figures`, `provenance`, `freshness`, `claims`, `notes` and `markdown`, with the code that served
  them (`research.py`, `task_graph.py`, `markdown.py`: about 800 lines), the profiles that needed them (`notebook`, `tex-notebook`,
  `numerical`, `research-paper`; `core` and `writing` remain), their Make targets and commands (`run`, `figure`, `freshness`, `history`,
  `claims-check`, `research-check`, `research-validate`, `md-check`, `md-render`), the `--task`, `--changed` and `--expensive-checks`
  options, the decay example, the Markdown example, their documents (`research.md`, `research-loop.md`, `markdown.md`) and their
  parts of the guide, the policy text and the skill. The Markdown link check of the file checks is not the module: it stays.
- **A configuration that names a removed module** is refused, by name, with a hint to remove it from `"modules"` and
  `"disabled_modules"` in `.latex-ai.json`; no file is changed. Notes, manifests, run records and results stay where they are.
- **Generated files:** the Makefile and editor files of a project with LaTeX and bibliography are byte-identical. The workflow loses the
  step that installed Pandoc (three lines), and `AGENTS.md` loses the paragraphs about research tasks, freshness and Markdown. The
  workflow of a project without LaTeX is named `AI Workbench` and no longer `Research AI Workbench`.
- **JSON shapes:** `plan --json`, `validate --json` and `status --json` no longer carry `research`, `research_modules`, `markdown`,
  `freshness` and `freshness_error`; `check --json` no longer carries `expensive_checks_executed`; `modules` lists two modules. The GitHub
  outputs `research`, `markdown`, `check_research` and `check_markdown` are gone.
- **Tests:** about a quarter of the suite described what is gone and went with it (448 to 379 tests); the rest were rewritten
  where they used a removed profile only to get a project without TeX. `tests/test_scope_4_0_0.py` pins what is gone, and fails
  against 3.7.0 in every part.

See [the verification record](verification-4.0.0.md).

## 3.7.0 — each fact the code spelled twice is spelled once

Phase 3, finding F9 of the architecture audit. A change to one copy of a list had to be made again in the others, and the
copies had drifted: six lists of folders to skip, no two equal. No generated file changes, so an upgrade replaces runtime files
and nothing else.

- **The goals that run a build again.** A project's own `build_command` of `make GOAL` is refused when `GOAL` would make it call
  itself, in its argument list and in the Make graph it reads. The six names were typed twice in `schema.py`; they are now
  `commands.RECURSIVE_GOALS`, derived from the registry (the names of `check`, `validate` and `document-check`, and
  `latex-ai-build`), and the reserved prefix is `commands.RESERVED_PREFIX`. A test pins the six.
- **The folders no check treats as sources.** `core.GENERATED_TREES` (`.git`, `.latex-ai`, `.venv`, `__pycache__`, `node_modules`,
  `site-packages`, `dist-packages`) replaces the lists of the file walk, the Markdown walk, the check of Markdown input patterns
  and the check of task paths. The installer keeps its own additions on top of it (`workbench`, `build`, `out`), on purpose.
  The list of reserved module paths (`.vscode`, `.github`, `.codex`, `.claude`) is a different fact and stays where it is.
  **Where this changes behaviour:** the Markdown walk now also skips `site-packages` and `dist-packages`; `markdown.files`
  patterns may not start in `__pycache__`, `site-packages` or `dist-packages`; task inputs and outputs may not start in
  `node_modules`, `__pycache__`, `site-packages` or `dist-packages`; the installer's walk skips `__pycache__`, `site-packages`
  and `dist-packages`. A configuration that named such a folder is refused with the message it already has.
- **The planner's suffixes.** One table each (`MANUSCRIPT_SUFFIXES`, `DOCUMENT_SUFFIXES`, `CHECKED_SUFFIXES`, and
  `DATA_SUFFIXES` shared by two of them) replaces three inline lists. The second `.csv`/`.tsv` of the list of ordinary
  documents could never be reached, because the manuscript list takes them first; it is gone. Every suffix routes as before.
- **The Markdown link check** of the file checks is a function, `runtime.broken_markdown_link`, with its own tests; its
  behaviour and messages are unchanged.
- **The Make names of the template.** The installer no longer lists `build`, `lint` and `check` itself: it reads the targets
  of the template it is about to extend, so a target added to the template is never given a second alias.

Regressions: `tests/test_one_table_each.py` (it also fails if a list of those folders appears again outside `core`). See [the
verification record](verification-3.7.0.md).

## 3.6.0 — `validation.ignore`: paths the owner declares are never routed to the manuscript build

Phase 3, the safe part of finding F10. The planner treats any figure or data format (`.png`, `.pdf`, `.csv`, …) and any
file it cannot classify as a possible manuscript input, so a folder of notes or slides changed in a commit selected a
full manuscript build with no way to say otherwise.

- **The setting.** `validation.ignore` is a list of project-relative globs, for example `["docs/**"]`. An ignored path gets
  the file checks and nothing from the manuscript build; `validation-plan` names it as "ignored by validation.ignore".
  The patterns are validated like `validation.manuscript_inputs`, and a bad one names the key it was in.
- **What is never ignored.** What the build reads (its dependencies, and `validation.manuscript_inputs`), build and
  configuration files (a `Makefile`, `latexmkrc`, the workflows, `.latex-ai/`, the editor settings) and the agent's policy
  files keep their routing whatever is declared. A path is ignored only where it would otherwise have been treated
  conservatively.
- **Not done, on purpose.** Routing is not narrowed from build records: a `\graphicspath` folder is one input the records
  would miss. The setting is the owner's declaration; the planner infers nothing from it.
- **Installed projects.** An upgrade replaces the runtime files and touches nothing generated: the Makefile block, the
  workflow and the editor files are byte-identical to 3.5.0's.

Regressions: `tests/test_validation_ignore.py`, failing before. See [the verification record](verification-3.6.0.md).

## 3.5.0 — workflow actions are pinned to commits

Phase 3, finding F14 of the architecture audit (the first of its small items). A tag such as `actions/checkout@v7` is
resolved again on every CI run, so a moved or hijacked tag would change what CI executes, with the project's checkout and
token in reach. A commit cannot move.

- **The pins.** Every action of the workflows the workbench generates is pinned to a commit, with the tag in a comment:
  `uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7`. The table is `PINNED_ACTIONS` in `adapters.py`.
  Each commit is the one GitHub resolved for its tag in the last hosted runs and the one the action's own repository lists
  for that tag, so pinning changes nothing about what runs today.
- **No action slips in unpinned.** An action the table has no pin for is refused when the workflow is generated, with a hint
  to add its commit.
- **Installed projects.** On upgrade, the `uses:` lines of `.github/workflows/latex-ai.yml` change and nothing else in it. A
  workflow someone edited by hand blocks the upgrade with the usual `CONFLICT`, as any whole-file edit does. The Makefile
  block and the editor files are unchanged. A pin goes stale until a new workbench release carries a newer one; a fix to an
  action therefore reaches installed projects with a release, not on its own.
- **This repository.** Its three workflows are pinned (two regenerated by their generators, the Python one by hand), and
  `.github/dependabot.yml` has Dependabot propose monthly, grouped updates of the pins, reading the tag in the comment.
  Generated workflows do not get a Dependabot file.

Regressions: `tests/test_repairs_3_5_0.py`, failing before. See [the verification record](verification-3.5.0.md).

## 3.4.1 — LaTeX Workshop's View PDF finds where each document is built

A test project (`revision/main.tex` and `revision/supplementary.tex`, both built into `revision/build/`) showed that
the generated `.vscode/settings.json` never set `latex-workshop.latex.outDir`. LaTeX Workshop therefore looked for
each PDF beside its root file while the build wrote it elsewhere, and **View PDF** opened a blank viewer that reported
a zero-byte PDF; opening `revision/build/main.pdf` directly worked. The setting had been generated up to 1.0.1 and was
dropped when named documents arrived in 2.7, because one string has to serve several documents.

- **The rule.** `outDir` is one string; its placeholders expand per root file and a relative value starts at the
  root's folder. Setup now derives the first value that gives every document its real output directory: nothing when
  each is built beside its root, where the viewer already looks; `%DIR%/<folder>` when each document builds into the
  same folder beside its own root (the reported project gets `%DIR%/build`); `%WORKSPACE_FOLDER%/<folder>` when all
  share one folder.
- **When no single value fits** (documents that build in different places, which includes several documents left on the
  default per-document folders) setup sets none and prints a note naming the documents and their folders, instead of
  pointing the viewer at the wrong place for some of them. Giving them the same `output_dir` fixes it.
  [Configuration](../configuration.md#make-editor-and-ci-boundaries) says so.
- **Upgrading.** The three-way merge adds the key to settings that still match what the workbench wrote and leaves an
  identical hand-set value alone. A different hand-set value stops the upgrade with a `CONFLICT` naming the key, and
  nothing is changed; `--skip-editor` keeps the file.
- **Installed projects** with a single document on the default layout, or documents sharing an output folder, gain
  one line in `.vscode/settings.json` on upgrade. The Makefile block and the CI workflow are unchanged.

Regressions: `tests/test_repairs_3_4_1.py`, failing before. See [the verification record](verification-3.4.1.md).

## 3.4.0 — the backends take resolved views and never resolve them (internal)

Phase 2, step 2, second half of [the plan after 3.0.2](plan-after-3.0.2.md), and with it the end of audit finding F7:
a parameter called `config` no longer holds either a project configuration or a resolved document.

- **`document_settings` takes a project configuration only.** Given an already-resolved view it raises `TypeError`
  instead of passing it through. `latex.py` no longer calls it: its 16 entry points take a `DocumentView` or a
  `SharedSettings` and use them as they are. A caller that holds a project configuration (the bibliography checks of
  the installer, the Markdown check and `runtime`, and `runtime`'s dependency lookup) resolves it itself, as the
  callee used to do for it, so behaviour is unchanged.
- **A mistake is loud.** Where a backend function only read optional keys with defaults (`bibliography`, `lint`,
  `ci`), a project configuration passed by mistake would have meant "nothing to check". Those functions now read the
  typed attributes, and a project configuration raises `AttributeError`.
- **The build record's view is typed again where it is read.** `build_shell` rebuilds a `DocumentView` from the
  JSON of the in-progress build, whose shape is unchanged (pinned since 3.3.0).
- **Function-local imports.** `guide`, `diagnostics`, `handbook`, `make_graph` and `core` are imported at module level
  where they were imported inside functions; only optional modules (`latex`, `research`, `markdown`, `documents`,
  `output_transaction`) stay lazy. A test in `tests/test_architecture.py` says so.
- **No change for installed projects.** The generated Makefile block, editor files and CI workflow are byte-identical
  to 3.3.0's. An upgrade updates `.latex-ai/guide.py`, `handbook.py`, `latex.py`, `make_graph.py`, `schema.py` and
  `workbench.py`, and the version.

Tests: three new ones (`tests/test_document_views.py`, `tests/test_architecture.py`); about 30 test lines that passed a
project configuration to a backend function now resolve it first. This closes Phase 2. See
[the verification record](verification-3.4.0.md).

## 3.3.0 — resolved document views are immutable, typed mappings (internal)

Phase 2, step 2, first half of [the plan after 3.0.2](plan-after-3.0.2.md), the second half of audit finding F7.
A parameter called `config` could hold the project configuration or a resolved document, and nothing stopped a
caller changing a view. This release gives the resolved things a type; the next removes the dual mode.

- **`DocumentView` and `SharedSettings`** (in `schema.py`). A resolved document is a `DocumentView`. What a project
  shares with every document (bibliography, validation declarations, CI) is `SharedSettings`; a project without
  LaTeX has only that, and a `DocumentView` is one too. Both are `dict` subclasses frozen at every depth, so equality
  with the dict a build record was loaded into, `json.dumps` and `{**view}` behave as before, and any attempt to
  change one raises `TypeError`. Typed properties name the keys the LaTeX backend reads (`name`, `root`, `engine`,
  `output_dir`, `build_command`, `lint`, `inputs`, `bibliography`, `validation`, `ci`). `to_json()` and
  `copy.deepcopy` return plain data a caller may change.
- **The build record is unchanged.** What it stores as `configuration` is exactly what 3.2.0 stored, for builds
  running across an upgrade too. `tests/fixtures/views.json` pins it for the 13 configurations of the generated-files
  guard and one that sets every key, and it was generated from the code before this change.
- **Nothing in the workbench changed a view**; two tests did, and now take a copy.
- **No other change for installed projects.** The generated Makefile block, editor files and CI workflow are
  byte-identical to 3.2.0's. An upgrade updates `.latex-ai/schema.py` and the version.

Tests: `tests/test_document_views.py`. See [the verification record](verification-3.3.0.md).

## 3.2.0 — the configuration and the documents sit below the runtime (internal)

Phase 2, step 1 of [the plan after 3.0.2](plan-after-3.0.2.md), finding F7 of the architecture audit.
`core` imported `documents` in three places and `documents` imported `core` back, so seven runtime modules
(`commands`, `core`, `documents`, `guide`, `latex`, `make_graph`, `output_transaction`) formed one import cycle
that only function-local imports kept from failing.

- **`schema.py`.** The schema and its validation (`validate_config`, `load_config`, the `check_*` helpers,
  `unknown_keys`), the declared documents (`specifications`, `resolve`, `Document`, the validators for the LaTeX
  module and for adopted Make ownership), `document_settings` and `required_tools` now live in `schema.py`,
  directly above `core`. `core` imports nothing but `processes`; `schema` imports only `core` and `make_graph`.
  `documents.py` keeps what needs the LaTeX backend: dependency routing, build states and failed builds. The
  Makefile readers (`MAKEFILES`, `active_makefile`, `makefile_text`) moved from `guide` to `make_graph`;
  `guide` re-exports them.
- **The layering is tested.** Three tests in `tests/test_architecture.py`: each runtime module imports on its
  own; the static import graph, function-local imports included, has no cycle; `core`, `schema` and
  `make_graph` import only what is below them.
- **`--document` without LaTeX.** `check --document X` and `bib-check --document X` in a project created without
  LaTeX used to stop with an internal error (`No module named 'documents'`). Moving the configuration into
  `schema.py`, which every project has, already ended that. They now also say how to turn LaTeX on, as
  `build --document X` does, in a project that never had LaTeX and in one that disabled it. Regressions:
  `tests/test_repairs_3_2_0.py`, failing before.
- **No other change for installed projects.** The generated Makefile block, editor files and CI workflow are
  byte-identical to 3.1.0's (the generated-files guard). An upgrade adds `.latex-ai/schema.py` and updates
  `workbench.py`, `core.py`, `guide.py`, `make_graph.py`, `latex.py` and `documents.py`.

Step 2 of Phase 2 (a typed `DocumentView`) is not part of this release. See
[the verification record](verification-3.2.0.md).

## 3.1.0 — one command registry (internal)

Phase 1 of [the plan after 3.0.2](plan-after-3.0.2.md), finding F8 of the architecture audit.
What the workbench knows about each command used to be written in six tables that disagreed in
places. It is now written once, in `commands.py`.

- **One table.** For each of the 30 actions it holds the module the action needs, whether it takes
  `--document`, whether its `--json` output is its own, the view of the configuration it works on,
  whether it runs without a configuration, and the Make names that reach it, with their group and
  description. `runtime` derives the argument choices, the `--document` and `--json` rules and the
  module check from it; `guide.COMMANDS` is derived from it; `adapters` derives the Makefile recipes
  from it; `make help` derives its `TASK=` / `DOC=` hints from it.
- **Dispatch is a lookup.** `runtime.dispatch` finds the action's handler, the function `do_<name>`,
  and calls it. The `if/elif` chain is gone, and so is the `globals()` injection of the LaTeX backend
  functions, which are now nine explicit functions of the same names.
- **No change for installed projects.** The generated Makefile block, editor files and CI workflow
  are byte-identical to 3.0.4's, which `tests/test_generated_files_guard.py` (added before this
  change, in its own pull request) checks for 13 configurations. Commands, options, output and exit
  statuses are unchanged. An upgrade adds `.latex-ai/commands.py` and updates `workbench.py`,
  `core.py` and `guide.py`.
- **Two behaviours kept on purpose.** `make help` still shows no `DOC=NAME` for `bib-check`,
  although it accepts `DOC`; showing it would be a visible change for a later release. And
  `check --document X` or `bib-check --document X` in a project without the LaTeX module still ends
  in an internal error (`No module named 'documents'`), as it did in 3.0.4; it is recorded as an
  open defect for its own repair.

Tests: `tests/test_commands_registry.py`. See [the verification record](verification-3.1.0.md).

## 3.0.4 — changes reach the default branch through pull requests

- **Policy.** `AGENTS.md` (and the integration block added to a project's own `AGENTS.md`)
  states that changes reach the default branch (`main` or `master`) only through a pull
  request from a topic branch, never by a direct push, merge or fast-forward.
- **Agent rules.** Pushes to the default branch are refused, not prompted: `deny` rules in
  `.claude/settings.json` and `forbidden` rules in `.codex/rules/git-safety.rules`, generated
  from one list of options and targets. Every other push still prompts; nothing is weakened.
- **Only the owner merges.** Agents open pull requests and never merge them: a pull request
  its author merges unreviewed gains nothing over a direct push. `gh pr merge` is refused in
  both rule files, and Claude's `deny` list also refuses the GitHub tools
  `mcp__github__merge_pull_request` and `mcp__github__enable_pr_auto_merge`.
  The parity test now compares the refused set of both agents as well as the prompted one.
- **Why here.** On a private repository of GitHub's free plan, branch protection and rulesets
  are not enforced, so the policy and the agents' rules carry it. `docs/agents.md` explains
  the limits (prefix rules do not match every spelling) and shows an optional local `pre-push`
  hook that the owner installs; the workbench never writes Git hooks.
- Installed projects receive the new policy text and rule files on upgrade. A project whose
  rule files differ from the installed ones gets the usual conflict and keeps its files.

Regressions: `tests/test_repairs_3_0_4.py`, each failing before the change.

## 3.0.3 — actual GNU Make 3.81 parsing of adopted builds

Phase 0 on macOS found that 3.0.2 still stopped every adopted-Make goal on the
stock GNU Make 3.81: it cannot parse the `private` target-variable modifier, which
was outside the build-goal guard. Simulating missing `.EXTRA_PREREQS` on modern
Make did not exercise that parser difference.

The two `private override` assignments are now guarded by the phased build's
required `extra-prereqs` feature. The project's `pdf` target and workbench `help`
and `status` work on 3.81; workbench build/check goals still refuse with the
GNU Make 4.3 requirement, and `doctor` still reports the missing feature.
The regression in `tests/test_repairs_3_0_3.py` failed on the actual 3.81 parser
before the fix and passes afterwards.

Upgrades change the managed Makefile block for adopted phased builds to add this
guard. Modern-Make build ownership is unchanged. Editor files and CI workflows
are unchanged. See [the verification record](verification-3.0.3.md).

## 3.0.2 — repairs and optimizations from the architecture audit of 3.0.1

Every change answers a finding of [the architecture audit](architecture-audit-3.0.1.md). Each was
reproduced first, and each has a regression in `tests/test_repairs_3_0_2.py` that failed before the
change; see [the verification record](verification-3.0.2.md).

- **Locks are shared by everyone who works in the project.** 3.0.1 moved operation locks to a
  per-user temporary directory, so two users (or two processes with different `TMPDIR`) could build
  the same project at once, and the research task lock silently ran *unlocked* for every user after
  the first. All locks are now empty files under `.latex-ai/artifacts/locks/` (ignored by Git),
  shared as the project directory is, opened for writing where possible (NFS needs it), and an
  operation that cannot take its lock stops instead of running unlocked.
- **An older GNU Make keeps the project's own targets.** With an adopted `["make", "pdf"]` build, a
  Make without `.EXTRA_PREREQS` (macOS ships 3.81) stopped every goal, `make pdf` and `make help`
  included. Only the workbench's build and check goals refuse now, and the installer and
  `make doctor` say when the `make` on PATH is too old.
- **TeX sources in an 8-bit encoding** (`\usepackage[latin1]{inputenc}`) no longer stop
  `init`, `plan`, `status` and builds with an unexplained codec error; static scans read them as
  Latin-1, as the compiler does.
- **First builds compile once.** The 3.0.1 generated-input repair recompiled every build in which the
  compiler discovered an input the static scan had not named, which included most first builds. An
  input that existed unchanged before the build began is now certified by its hash; only inputs
  written during the build (and inputs hashed at its start that differ) take the protected
  compilation.
- **Inputs graphicx and LaTeX find by search are tracked.** `\includegraphics{fig}` without an
  extension tracks each existing `fig.pdf`, `fig.png`, ... beside the document, so adding a `fig.pdf`
  that graphicx would now prefer makes the document stale (it stayed `current`). Local packages and
  classes (`\usepackage{mystyle}` with `mystyle.sty` beside the document) are tracked before the first
  build. A document that uses them rebuilds once after the upgrade because its input set grew.
- **Each file is hashed once per command** while it stays unchanged (files changed within two seconds
  are hashed afresh, as Git treats racy entries): `document-check` read a large figure four times.
- **The installation record keeps text only where a merge needs it** (manifest schema 2). Files
  installed whole are recorded by digest; managed blocks, merged settings and extendable files keep
  their text. The reference's record shrank from 536 KB to 19 KB. Version-1 records are read and
  rewritten on the next upgrade; `--diff` of a locally modified runtime file compares it with this
  release's text.
- **Process identity without `/proc`** (macOS, the BSDs) uses the start time `ps` reports, so a reused
  PID no longer keeps a dead build "running".
- **Generated CI** omits the package test and portability steps when `validation.package` is null,
  since they could never be selected; the schema-3 acceptance workflow is regenerated.
- Internally, Markdown export uses the shared atomic writer, and fault records live in a per-user
  directory. No configuration or receipt format changed.

## 3.0.1 — repairs from the independent 3.0.0 audit, and a guide

Every defect below was reproduced before it was repaired; each has a regression in
`tests/test_repairs_3_0_1.py`, and see [the verification record](verification-3.0.1.md). The
release also adds a guide for people who cannot place the parts of the workbench (the last
three bullets); it is in this release rather than a later one because it changes no behaviour of
any check, build or receipt.

- **Generated inputs.** A build whose own rules write a file the document includes (a Make
  rule that builds a table or a figure) failed its first build and every build after a data
  change with "Build inputs changed during execution", then passed on a rerun. A changed input
  now selects the existing protected compilation; the receipt certifies the digests that
  compilation re-verifies. A file that still differs afterwards is named in the error. An
  edit made while the first compilation runs is picked up by that compilation instead of
  failing the attempt.
- **Links that leave the project.** A symbolic link inside the project to a file or directory
  outside it was not tracked, so changing the target left the document `current` with a stale
  PDF. It is tracked under the link's own name with the content it leads to; system TeX files
  remain an adapter boundary. Changed links are accepted by the planner.
- **Bibliography styles.** A project-local `.bst` named by `\bibliographystyle` is a tracked
  input (BibTeX reads it, so the TeX recorder never listed it). A document with such a style, or
  with a link leaving the project, rebuilds once after the upgrade because its input set grew.
- **Locks.** Operation locks live in a per-user directory; a second user of the same machine
  no longer meets "permission denied" on the first user's directory.
- **Line endings.** The installer writes a file in the line endings it already has and backs up
  the original bytes. A CRLF `AGENTS.md` or `.gitignore` is no longer rewritten as LF.
- **Hints.** Stale-state hints name the document (`DOC=`) and use the project's own command
  names; `make plan DOC=x` says that the selector is ignored.
- **Planner.** `recipe-shell.sh` triggers full validation like the other installed runtime
  files; one list (`core.RUNTIME_FILES`) serves the planner and a test ties it to what the
  installer ships.
- **Configuration errors** name the unknown key or value, `--build-command` that is not a JSON
  array gets an actionable message, and the schema-3 hint says where the format is described.
- **Orientation.** `status` puts "wait for this build" before commands that would start another,
  and a clean `make check` reports bibliography integrity once.
- Documentation: stale "Schema 2" wording and the profile list in the quickstart.
- **The guide.** `make guide` prints, and `make guide-html` writes as one self-contained page
  (`.latex-ai/artifacts/guide.html`, which Git ignores), pictures of how the parts fit (what lives
  where, the everyday loop, what runs when, document states, research tasks, command names), twelve
  how-tos, a "reading a message" table and a glossary. `TOPIC=name` selects one part. One source
  (`handbook.py`) renders the terminal text, the page and the Markdown copies `docs/handbook.md` and
  `docs/handbook.html`; a test keeps those equal (`make -C workbench handbook` regenerates them),
  and another checks that every command the text names exists. Commands are shown under the names that
  work in the reader's project (`make latex-ai-build` where the Makefile keeps its own `build`), topics
  that need a module that is off say so, and terminals that cannot show box drawing get plain
  characters. It works while the configuration is broken, and it only reads the project; the page is
  its one write.
- **Status gives reasons.** A stale document lists what changed: sources, build settings or outputs
  (also in `status --json` and `make documents`).
- **Help.** Each group is listed once (Manuscript appeared twice), a "Start here" line comes first, and
  the last line points to the guide.

Internally, the bibliography, lint and CI validators exist once instead of twice, one helper
names dependencies, build-command files and declared inputs are found in one place each, and
unused imports are gone; the tests share one project fixture (`test_support.ProjectCase`). No
configuration, receipt or installation format changed. One runtime file is added, `handbook.py`, which
`latex-ai-init upgrade` installs.

## 3.0.0 — one supported project and document model

This breaking release supports configuration schema 3 exclusively, including
projects without TeX. Initialization constructs it directly. Schema-1/2 readers,
migration flags, v0 adoption, and special manuscript receipt/export paths are
removed. Current task, installation, journal, and scientific record formats have
independent version numbers and retain their existing contracts.

All documents share one resolved settings shape and a named artifact layout.
Receipts store build identity directly. One validated receipt-input reader keeps
canonical/symlink dependencies durable and prevents malformed stored paths from
breaking inspection. Unsupported document selectors fail before project checks
can be suppressed. Compiler ownership uses one plural process-group representation.

Compiler recorder inputs are resolved from recorded `PWD`. Builds that
discover new dependencies receive one forced compilation under protected input
hashes before certification. This fixes a pre-existing stale-PDF certification
defect and first-build retry failure, including native first-build input discovery.
Configure previews show resolved lint and
output settings, bibliography success reports its actual document/file scope,
and installed runtimes diagnose a foreign project before importing its optional
backends. Status exposes live build ownership, recovery guidance explains hard
termination, and a read-only history command indexes existing run records without
changing retention or adding another archive format.

Make/editor/CI generation has one document path. CI consumes the shared validation
action flags, and the public mixed-notes example has a generated hosted acceptance
workflow. Installer ownership, safe updates, interruption recovery, scientific
execution boundaries, source preservation, and current GNU Make 4.3 support remain.

Read [the architecture](../architecture.md), [troubleshooting](../troubleshooting.md),
and [verification](verification-3.0.md) for local evidence and remaining release checks.

## 2.7.3 — portable adopted recipe supervision

- GNU Make 4.3 can now run adopted `.ONESHELL` builds through receipt ownership.
  A small installer-owned shell script forwards the recipe instead of placing
  a quoted program in `.SHELLFLAGS`. The script is invoked by `/bin/sh`, so it
  does not depend on an executable permission bit.
- The regression covers `.ONESHELL` and ordinary recipes, selected POSIX/bash
  shells, `-c`/`-ec` flags and project paths containing spaces.

See [the 2.7.3 verification record](verification-2.7.3.md).

## 2.7.2 — shared build ownership, dependencies and recovery

- One Make scanner supplies adapters, ownership validation and project-check
  detection. It preserves ordinary double-colon checks and selects complete
  project validation for unresolved/generated includes. Unsupported recipe
  prefixes and ambiguous rule styles are refused before installation writes.
- Receipts distinguish full manuscript inputs from normalized Make policy.
  Compiler-consumed Makefiles and literal included Make policy now invalidate
  stale PDFs. Older receipts rebuild once; malformed recorded identities are
  stale instead of internal errors.
- Every configuration schema validates compiler output children against path
  escapes. Adopted phased recipes share process ownership, preserve stdin,
  recursive jobservers and `.ONESHELL`, and retain ordinary raw build goals.
  An execution gate prevents compilers from starting before their identities
  are recorded. Linux zombie owners no longer block recovery.
- Output regeneration uses per-attempt journals, restores completed moves on
  failure and recovers interruption without overwriting replacements. Finished
  restores no longer prevent later cleanup/rebuild transitions.
- Cooperative interruption emits one JSON result after compiler cleanup;
  repeated signals cannot abandon cleanup. Compiler diagnostics use only a log
  changed by the current invocation.
- Local validation and schema-3 CI consume one project-check decision. Verified
  PDF collection stays with compilation in the TeX container.
- Fixture environments isolate selectors, Make state, TeX search paths and Git
  bindings. Git init/clone gain matching approval rules in both agent templates.

See [the 2.7.2 verification record](verification-2.7.2.md) for evidence and gaps.

## 2.7.1 — receipt lifecycle and validation coverage fixes

- A build run through an existing Make rule or custom command no longer gets
  stuck when its outputs predate any verified receipt (after schema-3
  migration, a workbench upgrade, a Makefile edit or a build outside the
  workbench). The unverified PDF and log are moved aside and the command runs
  once more; if it cannot recreate them, they are put back and the check fails.
- Receipts certify a build identity (root, engine, output, command,
  bibliography). Changing the default document, lint or CI settings keeps
  builds current. A Makefile counts only for Make-based builds, without the
  workbench's managed block, so later upgrades no longer invalidate builds.
  Receipts written by 2.7.0 are rebuilt once after upgrading.
- Schema-3 `make validate` runs `make check` when the project's own Makefile
  has a `check` rule, as schemas 1 and 2 did, instead of skipping it.
- Document states include `failed`. Status lists every document that is not
  current with the command that fixes it, and never reports "Nothing pending"
  while a build has failed; validation keeps selecting a failed document.
- `make latex-ai-bib-check` covers each document's own bibliography files and
  honors `DOC`; plans route those files to the bibliography check.
- The compiler runs in its own recorded process group. Terminating a build
  stops its compiler; a killed owner keeps ownership until its compiler exits.
- Failed documents lead with the first TeX error and a hint; the human plan
  lists selected documents; configure names the document it changes.

See [the 2.7.1 verification record](verification-2.7.1.md).

## 2.7.0 — TeX notes and named documents

- Schema 3 declares independent LaTeX documents with target-specific engines,
  inputs, outputs, lint baselines, verified receipts and PDF exports.
- Existing schemas remain supported. Explicit migration preserves legacy
  output locations and accepted lint warnings; ordinary upgrade retains config.
- The `tex-notebook` profile seeds a standalone notebook and included session
  fragment. Notes can independently use Markdown, TeX or existing text formats.
- Changed-file validation selects consuming documents, including shared,
  deleted and aliased inputs; uncertain build inputs select all documents.
- Make, editor tasks and CI use named canonical commands. Adopted default
  Make builds retain one compiler invocation under parallel project checks.
  Multiple adopted graphs with shared or unresolved ownership require an adapter.
- Read-only status reports per-document validity. Failed builds and live
  adopted ownership prevent stale export or unsafe cleanup.

See the [user guide](../tex-notes.md) and
[verification record](verification-2.7.md), which distinguishes local evidence
from hosted verification.

## 2.6.0 — consistent dependency and artifact validation

- Shared task graph covers producer ownership, cycles, inferred/recorded paths,
  affected-module selection and producer-first refresh guidance.
- Every builder creates verified input/output receipts. Export rejects stale
  PDFs; reserved Make build wrappers cover existing custom build recipes.
- Installation works without Git; read-only metadata uses one optional adapter.
- Adapter generation and installation transactions have separate modules.
  Runtime configuration is normalized at dispatch without rewriting project files.
- Provenance has a per-inspection latest-run index and dependency hash cache.
  JSON remains authoritative and snapshots are retained.
- Check/status/validate/run commands provide structured JSON outcomes while
  plan/modules/freshness retain their established JSON shapes.
- Portability checks preflight all required tools, accept an output parent via
  `LATEX_AI_PORTABILITY_PARENT`, and preserve aggregate results on failure.
- Distribution CI adds Python 3.10–3.14 compatibility testing. Reference parity
  is checked by audit and the existing architecture regression.

Validation results and environment limits are recorded in
[the 2.6 verification note](verification-2.6.md).

## Maintaining a package release

`core.py:VERSION` is the release version and `schema_version` is the
configuration/manifest protocol. Increment the release for changed templates,
installer behavior or validation. Use semantic versions: bug fix patch,
compatible new capability minor, incompatible workflow/schema major. A new
schema requires explicit scope, fixtures, and documentation. Workbench 3
accepts only schema 3; do not restore old-release conversion paths or silently
reinterpret unsupported configurations.

Before distributing a release, run safety/merge unit tests and real compiler
portability tests, regenerate the reference through the installer, validate and
audit it. Add regression fixtures for demonstrated failures. Historical release
records describe their original supported contracts; they are not current
compatibility requirements.

The guide (`make guide`, `make guide-html`) is written once, in `handbook.py`. After changing its
text or the commands it names, run `make -C workbench handbook` to regenerate `docs/handbook.md` and
`docs/handbook.html`; `tests/test_guide_3_0_1.py` fails while they differ, and also fails when the
guide names a command that no longer exists.

Existing remote CI action versions are preserved in the reference. Release
maintenance should verify supported action tags, TeX Live availability and
container requirements against their primary documentation, then review the
CI diff. Remote CI is confirmed only after a user-approved commit/push or PR;
a local passing check does not prove the hosted job ran.

## Release 2.5.0

- Canonical dependency identities close input/output alias and stale-producer
  gaps, including symlinks and existing hard links. Root aliases produce normal
  configuration errors.
- Custom LaTeX builds require a verified receipt before reusing unchanged PDF/log
  artifacts. Inputs and outputs are fingerprinted; failed attempts invalidate
  prior receipts. Indirect dependencies must be declared.
- Module capabilities and validation actions are shared by runtime, installer
  and generated CI. Both configuration schemas remain supported on disk.
- Installer transactions are locked, journaled and explicitly recoverable after
  process interruption; installation manifests commit last. Run records use
  atomic replacement.
- Regression coverage includes equivalent paths, verified incremental builds,
  forced process death, subsequent user edits, and profile/CI action parity.

Release 1.0.1 fixes removed-block handling, active Makefile selection,
commented-out root detection and stale backend logs when bibliography processing
is disabled. It adds a package Makefile and a conditional package unit-test step
to managed CI. Configuration schema remains 1.

Release 1.1.0 adds `make validation-plan` and `make validate`, selective CI,
documentation/file checks and change-aware agent/reviewer procedures. Explicit
`make check` retains full manuscript validation. Optional
`validation.manuscript_inputs` globs cover indirect inputs. Existing custom
`validate` targets are retained; reserved workbench aliases remain available.
Configuration schema remains 1, with existing project choices preserved.

Release 2.1.1 fixes findings from an independent audit; configuration and
manifest schemas are unchanged. A run is no longer recorded as successful when
its command left an existing declared output untouched unless the latest
successful record already vouches for it (`unchanged_outputs` in the record).
A project script executed directly as `command[0]` is now a task input. Claim
evidence changes select the claims check. Files named in braced literals of the
manuscript sources route as manuscript inputs without a local recorder file. A
lone `=======` line is no longer a merge-conflict marker. No-TeX full checks use
Git's file view or skip Python environments by marker. `TASK` reaches Make
recipes through the environment. Deleted seed notes/manifests no longer block
upgrades. Upgrade installed projects with the usual dry-run first; installed
runtime files and any `run`/`figure` Makefile block change.

Release 2.1.2 records a run stopped by Ctrl-C or SIGTERM as `interrupted`, with
a finish time, instead of leaving it `running`; freshness already treated both as
stale. A process killed outright still cannot update its record. Schemas are
unchanged, and installed projects need only the usual upgrade.

Release 2.1.3 makes the structural duplicate-key check follow the backend: with
BibTeX, keys differing only by case are duplicates (BibTeX itself fails on them),
reported before any build; Biber and unprocessed exports keep them distinct, since
Biber accepts them. Exact duplicates remain errors everywhere. Schemas are unchanged.

Release 2.1.4 closes three smaller audit items. Every Git query the installer and
runtime make now runs with `GIT_OPTIONAL_LOCKS=0`, and the one `git diff` (which
ignores that setting) runs against a throwaway copy of the index; previously an
`audit` or `plan` over a stale index rewrote `.git/index`, which is Git state even
though it is only a cache.
`make doctor` names the interpreter that is actually running instead of whatever
`python3` is first on PATH. In Markdown notes a bare `@name` is a citation only when
the bibliography module is enabled (bracketed citations always resolve), and the
error names the `\@name` escape. Schemas are unchanged.

Release 2.1.5 widens the agent permission guardrails to every Git operation
`AGENTS.md` names that they missed (worktree creation/removal, branch rename/copy/force,
`cherry-pick`, `revert`, `am`, `rm`, `mv`, `tag`, `update-ref`, `filter-branch`,
`remote set-url` and similar; 33 additional prompt rules in each agent's file). Nothing
is weakened and read-only commands stay prompt-free. Both files are managed whole files,
so an unmodified installation updates on upgrade, while a locally edited guardrail is a
conflict to reconcile by hand. Schemas are unchanged.

Release 2.1.6 stops the installed runtime assuming this repository's layout. Routing of
the distribution's own helpers, tests and templates now applies where `validation.package`
(or a `workbench/` directory containing the distribution's `latex-ai-init`) says the
project hosts it; before, any `workbench/Makefile` triggered it, so an unrelated
directory of that name could select `make -C workbench` checks. The directory is
configurable, `null` disables it, the test commands and the generated CI workflow use it,
and the two copies of the `validation` checks in the core are one. Existing hosts of the
distribution need no configuration change. Schemas are unchanged.

Release 2.1.7 states the limits of the run contract that 2.1.1 introduced, after an
independent review showed a `touch` could satisfy it: file identity proves a write
happened, not that the content came from the current inputs. The documentation now says
so; a run whose output has the previous bytes although its inputs or definition changed
prints a warning and records it; the decay example's check compares its result with the
current parameters (a project's own checks should do the same); and two concurrent runs
of one task, which used to reject each other's still-current output, now fail fast for
the second run through an advisory temp-directory lock. Schemas are unchanged and the
record only gains an optional `warnings` list.

Release 2.1.8 closes the remaining findings of an independent review of 2.1.1 to 2.1.6.
Consumed TeX file names containing spaces are now found by the source scan. A
`validation.package` path is restricted to a quotable subdirectory (letters, digits,
space and `. _ - /`; never `.`), and the generated CI quotes it; before, a space broke the
CI command and `.` routed nothing. Environments are recognised by markers on disk, so one
whose `pyvenv.cfg` Git ignores is still skipped. `git fetch` and `git remote update` are
now gated by both agents' guardrails, and the redundant `git diff`/`git status` allow
entries are removed. Documentation now says what holds: split-index repositories have
their shared-index mtime refreshed by Git itself on any read, macro-built names are found
only through a local build's `.fls`, and prefix rules are prompts rather than a boundary.
Schemas are unchanged; the guardrail files are managed whole files, so unmodified ones
update on upgrade.

Release 2.2.0 adds a way to flag workbench defects as they are met. Unexpected
exceptions inside the runtime or installer are now labelled `INTERNAL ERROR` with exit
status 70 and kept apart from ordinary `ERROR` diagnostics (status 1, installer 2); a new
`issue` command (`make issue`) writes a local, ignored evidence report; and `AGENTS.md`
gains a short rule on how to treat a suspected defect. A fuzz of hand-edited configuration,
manifests, claims and run records found stray exceptions that would otherwise have been
mislabelled, so they now give diagnostics: unhashable values in checks, claims, engines,
backends and export formats, a missing root or export path, a missing `ci` section in the
workflow generator, and damaged run records. `diagnostics.py` is a new installed file and the
`issue` Make target is added to managed Makefiles. Schemas are unchanged.

Release 2.2.1 hardens the report command after a trial in which agents followed the 2.2.0
policy: when the defect sat in shared code that `make issue` itself calls (a `KeyError` in task
expansion), the command crashed with the same fault and captured nothing. Every evidence section
is now collected on its own and a failure is written into the report, so a broken plan, manifest
or tool lookup can no longer stop it; a configuration that fails to load for any reason is
recorded as `configuration_error`. Documentation also says what holds for the exit status: the
workbench exits 70 on an internal fault, but `make` reports the recipe as `Error 70` and exits 2
itself, so the `INTERNAL ERROR` label is the reliable signal, and the policy no longer names the
status. Schemas and installed file lists are unchanged.

Release 2.4.0 simplifies what had grown by accretion and addresses the blind trial of 2.3.3 (three
fresh agents on a stand-in project; all reached their goals, twelve graded findings). One format:
every new installation is written in schema 2, including a plain install on a paper, with the same
defaults as before (editor and CI adapters on); turning a module on later needs no migration step.
Schema 1 projects are read as before and migrate only on request. One command table:
`guide.COMMANDS` now carries each command's runtime action and the modules that enable it, and
the installer generates every reserved Make target from it; the templates keep only the shared
`check`, `build` and `lint`, and tests tie the names used by the policy, the skill, the documents
and the generated workflows to the table. A generated workflow holds only the steps of modules
that are on. New capability: a lint baseline. Both newcomers in the trial got past the ChkTeX gate
by silencing warning kinds; `make latex-ai-lint-baseline` instead records today's warnings in
`.chktex-baseline.json` (by file, warning number and source line), after which only new warnings
fail, an edited line counts as new, and fixed ones are reported as leftovers. Lint now reads
ChkTeX through a machine format and fails if it cannot read the result. Writing or refreshing the
baseline is the owner's decision and the policy says so; a change to the file selects full
validation. Smaller fixes from the trial: the TeX engine is read from the project's own build files
when they name exactly one, and reported; status lists the commands that refresh stale results
before `make validate`, tells a project without tasks to declare one, and says when validating
builds the paper; an adapted Makefile's `check` ends with "Workbench checks passed"; `make doctor`
ends with "All required tools found"; the validation plan shows run records as one line; a new
task manifest carries an `example` to copy; the policy no longer points to a path an adopted project
lacks and says that a project's own build may regenerate files without a record; the quickstart no
longer calls the default "the fullest setup". Deliberately not done: marked blocks for every
installed file (it would rewrite every project's files for no user-visible gain over 2.3.3), a
quieter TeX log, and a way to register existing results without a run (the trial gave no evidence
either way). Installed projects get a regenerated Makefile, policy, runtime files and, where CI is
enabled, workflow on upgrade. Configuration schemas are unchanged; manifests accept the optional
`example` key.

Release 2.3.3 fixes the thirteen findings of a user trial of 2.3.2 (ten journeys through the user
documents, with the commands as printed). Blocking ones first. `make check` builds and verifies the
manuscript before running ChkTeX, so a TeX error is no longer hidden behind a style warning, and a
lint failure carries a hint naming `.chktexrc`, `lint.args` and `lint.enabled`. A syntax error in any
project JSON file (configuration, task manifests, claims, run records, ordinary data files) names the
file. In a project that had no Makefile, `AGENTS.md`, `CLAUDE.md` or `.gitignore`, the installed
text is now the managed part of those files: lines added above or below it are kept on upgrade and
not reported by `make status`; a change inside it still blocks, with a message that says so and
`--diff` printing the change. `--diff` lists new runtime files by name and size instead of printing
them (a new paper's preview shrinks from about 2,300 lines to a few hundred) and the summary is
printed last. Then the smaller ones. Output is line-buffered, so through a pipe an `ERROR:` no
longer overtakes the lines that explain it. Research checks print the freshness report first; a
failing task check names the task and, when the task is stale, the commands that refresh it; command
failures show the whole command; `run`/`figure` warn when a producer of their inputs is stale and
record it as `stale_upstream`. Manifest errors name the manifest and show the expected form, and
status and hints point to `docs/research.md` when no task is declared. The installer sees targets in
makefiles included by literal name, notes what the default paper install adds (`--skip-editor`,
`--no-ci`), suggests `make status` among the next steps, and gives hints for a missing folder, an
undetermined engine and a profile passed to an installed project. The full agent policy names every
command by its `latex-ai-` form except the shared `check`, `build` and `lint`. Without Git history
the fallback note says so in plain words. Generated recipes are quiet, a full check ends with a
"passed" line, the doctor hint names what provides each missing tool, `bib-check` is described as
what it checks, and status counts uncommitted files as files. Installed projects get changed
Makefiles (quiet recipes; `check` now depends on the integrity target before `lint` in adapted
Makefiles), policy text and runtime files on upgrade. Schemas are unchanged; run records gain the
optional `stale_upstream` list.

Release 2.3.2 fixes the fifteen findings of a code review of releases 2.2.2 to 2.3.1; nearly all
were in the 2.3.0 orientation and summary work. Naming: `doctor`, `bib-check`, `pdf-artifact` and
`clean` gain reserved `latex-ai-` names like every other command (only `check`, `build` and `lint`
stay shared with the project, by design), so `make help`, the installer's next steps and the hints
never present a project's own recipe as the workbench's; the agent policy names
`make latex-ai-help` and `make latex-ai-status`, and the generated CI workflows call only `check`
and reserved names, so a project's own `md-check` or `research-validate` target cannot stand in for
a workbench check. Makefiles: help, status and the installer now agree on GNU Make's own filename
order through one shared function (a `GNUmakefile` beside a `Makefile` no longer empties `make
help`, and the installer's summary works for `GNUmakefile` and `makefile`). Status: seeded notes
and manifests, managed blocks and merged editor settings are no longer reported as changed
installation files; `Nothing pending` is said only when that is known (without Git history it
suggests the full check, and a changed installed file suggests an audit); a damaged
`installation.json` gives a diagnosis from `make status` and an `ERROR:` with a hint from the
installer, not `INTERNAL ERROR`; a missing `.latex-ai.json` is explained in plain words by help and
status too. Installer: an audit ends with the exact command that applies it, including the options
it was given and the installer's real path; a record-only change is described as such instead of
"current" beside exit status 1; installer errors print `Hint:` lines, and a folder without a TeX
root is pointed to the profiles (the quickstart now shows that command). Hints: enabling a module
names `--migrate-config` on a schema 1 project and shows the installer as
`python3 /path/to/workbench/latex-ai-init`; an empty `TASK` is answered by the runtime, which
lists the declared tasks and an example under the name that works, in place of a second, poorer
message in the Makefile. Installed projects get a changed Makefile (or managed block), policy
text and, where CI is enabled, workflow on upgrade; a LaTeX project adapted from an existing
Makefile gains `latex-ai-clean` (and `clean` where it had none) unless it uses a custom build
command. Schemas are unchanged.

Release 2.3.1 lets the generated CI workflows be started by hand (`workflow_dispatch`). Release
2.3.0's checks were spread over pushes that each selected only part of them, and a push of the same
code is the only other way to get every job to run. A manual run has no previous revision, so the
comparison base is empty and the planner's existing fallback selects full validation; ordinary pushes
and pull requests stay change-aware. Both generated workflows (LaTeX and core) gain the trigger, and
installed projects get it on upgrade. Schemas and installed file lists are unchanged.

Release 2.3.0 makes the workbench easier to pick up. `make help` lists the commands a project
actually has, read from its Makefile (a project's own `help` or `issue` target is kept and the
reserved `latex-ai-*` name is shown instead), with the declared task names and the modules that
could be turned on; `make status` is one read-only screen of installed version against the
manifest, modules, Git branch and uncommitted count, the checks the current changes need,
research freshness, and the exact commands to run next. Both work when the configuration is
broken. `guide.py` is a new installed file and `help` and `status` are new Make targets with
the usual reserved aliases. The installer's text output ends in plain words (nothing changed on
an audit or dry run; how many files were added or updated and where backups went; the next
commands), and a NOTE names the workbench command whenever a project's own target took a name the
workbench would have aliased. Expected errors can carry a `Hint:` line: a disabled module says how
to enable it, a missing or unknown task lists the declared ones, stale outputs name the exact
`make run` / `make figure` commands, a missing tool says to install it and run `make doctor`, and a
directory without `.latex-ai.json` says to run from the project root or install. The user documents
are reorganised: a short README, a quickstart, an "I want to…" page, and topic pages for installing,
daily use and working with agents; the verification record, the implementation plan and the release
notes moved under `docs/maintainers/`. Schemas are unchanged.

Release 2.2.2 fixes the command the defect policy tells agents to run. The installer keeps a
project's own `issue` Make target and supplies only `latex-ai-issue`, so in an adopted project
that already had such a target `make issue` ran the project's recipe and wrote no report. The
policy, the short policy added to existing `AGENTS.md` files, the internal-fault message, the skill
and the README now name `make latex-ai-issue`, which every installed project has had since
2.2.0; the short alias is unchanged. Existing installs get the corrected policy on upgrade.
Schemas and installed file lists are unchanged.

Release 2.0 separates the core, LaTeX and research backends. Version 2.0.1 also
accepts installer options before or after the project path on Python 3.10 and
later; the initial hosted run exposed a Python 3.12 argument-parsing difference.
Schema 2 enables
modules explicitly and supports projects without TeX. Schema 1 remains readable;
`--migrate-config` explicitly converts it with backups. Profiles select initial
choices only; `configure --enable/--disable` changes installed module selection.
Research files are editable initial seeds retained on upgrade/disable. Optional
commands, editor and CI adapters follow enabled modules. Read
[modules and migration](../modules.md) and research commands.
