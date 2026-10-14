# Plan after 3.0.2

> **Closed on 14 October 2026.** Phases 0 to 3 are done; Phase 4 is retired, and Phases 5 to 7 are met, moot or moved (see each below). The work continues in [the plan after 4.4.0](plan-after-4.4.0.md). This file stays as the record of the audit's follow-up.

The plan for finishing the [architecture audit](architecture-audit-3.0.1.md). It was written
when `main` was at `e8b55cf` (workbench 3.0.2), to be worked through in later sessions, the
first of them on macOS. Each phase stands alone: read this file, the audit and the
[3.0.2 verification record](verification-3.0.2.md), then start the next phase that is not
marked done.

## Rules every phase follows

These come from the repository's `AGENTS.md`, plus what 3.0.2 taught.

- **Git.** Work on a branch per phase (`plan/phase-N-<topic>`). Commits, pushes and merges to
  `main` need the owner's approval.
- **Repairs.** A defect gets a regression test that fails before the fix and passes after it.
  New tests go in a file named for the release (`tests/test_repairs_<version>.py`), until
  Phase 7 reorganises the tests. A small defect found along the way may be fixed in the open
  pull request, under the conditions in [Working on the workbench itself](README.md#working-on-the-workbench-itself).
- **Reference parity.** After any change under `workbench/`, run `make -C workbench upgrade-reference`
  and commit the regenerated `.latex-ai/` and `.latex-ai/installation.json` with it.
  `test_reference_matches_distribution` checks this.
- **Generated copies.**
  - Bumping `core.VERSION`, or changing `handbook.py`, means running `make -C workbench handbook`.
  - Changing the CI generator means running `python3 -B workbench/tests/schema3_workflow.py --generate`.
- **Installed projects must not churn.** A refactor must leave the generated Makefile block,
  editor files and CI workflow **byte-identical**, unless the phase intends a change and its
  release notes announce it. Compare the generated files before and after (see Phase 1).
- **Before pushing**, all of these must pass:
  - `make -C workbench test`. Locally the suite takes about 2.5 minutes, and CI runs it on
    Python 3.10–3.14.
  - `make -C workbench portability` where TeX is installed.
  - In the reference: `python3 -B .latex-ai/workbench.py validate --files-only` and
    `make latex-ai-bib-check`.
- **Release record.** Each release gets an entry in `releases.md` and a verification record
  that lists what was *not* verified.
- **Review.** The repairs in 3.0.2 were written by the session that wrote the audit, so they
  still need an independent review. Phase 0 provides one.

## Phase 0 — verify 3.0.2 on macOS and review it independently (first Mac session)

**Done — 2026-10-12, workbench 3.0.3, landing commit `34c3e88` (PR #1).**
The macOS verification and the independent review of
`e8b55cf` are recorded in [verification-3.0.2.md](verification-3.0.2.md#macos-verification-and-independent-review).
The actual Make 3.81 parser exposed a further F2 defect, repaired as 3.0.3 on
`plan/phase-0-macos-verification`; see [verification-3.0.3.md](verification-3.0.3.md).
The repair's independent review and hosted CI passed; the owner approved integration
into `main`. Remaining platform limits are recorded in the verification records.

This is what a Mac session can do and the Linux container could not. Do it before any
refactor, because a refactor would hide where a defect came from.

**Setup.** Install these with Homebrew:
- `python@3.12`, or any Python 3.10+
- `pandoc`
- `make`, which installs GNU Make 4.4 as `gmake`, with a `gnubin` directory
- a TeX distribution: MacTeX, or BasicTeX plus `sudo tlmgr install latexmk chktex`

Keep `/usr/bin/make` (GNU Make 3.81) reachable, because the old-Make checks need it.

1. **Suite and portability with real TeX.** Run these on GNU Make 4.x (with the gnubin
   directory first on `PATH`):
   - `make -C workbench test`. Expect 364 tests with no TeX skips.
   - `make -C workbench portability`. Expect 87 of 87.

   The 20 compiler-dependent tests, including
   `test_adopted_make_with_generated_table_and_figure_builds_once`, have never run against
   3.0.2.
2. **F4 with latexmk.** In a scratch project with `\includegraphics{fig}` and `fig.png`, the
   first `make build` should compile once. Count the "Inputs were written during the build"
   messages: there should be none. Then add a `fig.pdf` beside the PNG; the document should be
   `stale` in `make status`.
3. **F2 on a real Make 3.81.** In a scratch project, adopt `["make", "pdf"]` (see `docs/installing.md`).
   With `/usr/bin/make` first on `PATH`:
   - `make pdf`, `make help` and `make status` work.
   - `make latex-ai-build` stops with "requires GNU Make 4.3".
   - `make doctor` fails, naming GNU Make 4.3+.
   - The installer prints its NOTE.

   With gnubin first on `PATH`, the build works.
4. **F12, process identity through `ps`.** macOS has no `/proc`, so `processes.token` uses
   `ps -o lstart=`.
   - Run `test_process_identity_without_proc_still_detects_a_reused_pid` (it runs the real path
     here).
   - Start a long build, `kill -9` the Python owner, and check that `make status` shows the
     compiler group as `running` until it exits, and `failed` afterwards.
5. **macOS filesystem behaviour.**
   - `/tmp` is a link to `/private/tmp`, and `TMPDIR` is a per-user folder: check that the locks
     under `.latex-ai/artifacts/locks/` still exclude a second terminal.
   - APFS is case-insensitive: the `makefile` / `Makefile` casing checks in `bootstrap.plan`
     depend on that.
   - Check that the ctime rule in F4 holds on APFS: a file edited during a build must be
     reported as written.
6. **Independent review of `e8b55cf`.** Read the diff (`git show e8b55cf -- workbench/`) against the
   audit, with these questions in mind:
   - Is the ctime certification in `latex.finish_build` and `written_during` sound? Think of
     rename, copy with `cp -p`, network mounts and clock skew.
   - Can the digest cache (`latex.file_digest`, `SETTLED_NS`) ever return a stale hash?
   - Does manifest schema 2 lose anything a three-way merge needs?
   - Do lock files opened read-only behave correctly?

   Record findings in the verification record.

**Done when** the verification record has a macOS section, and any defect found is either
fixed (as 3.0.3, with a failing-first test) or recorded as an open item.

## Phase 1 — F8: one command registry

**Done — 2026-10-12, workbench 3.1.0, landing commit `b4d815f` (PR #4).**
The generated-files guard landed first, on its own (PR #3,
`4f50f75`). `commands.py` is now the one table of the 30 actions; `runtime.dispatch` is a lookup of one `do_<name>`
handler per action; `guide.COMMANDS`, the argument choices, the `--document` / `--json` / module rules, the Makefile
recipes and the `make help` hints derive from it; the guard passed unchanged. The verification record,
[verification-3.1.0.md](verification-3.1.0.md), has the hosted CI results and what was not verified.
No action name is spelled in more than one of the six tables, as the plan required; two other places that name
commands remain (Phase 3, F9), and two open items are recorded: the internal error for `check --document` and
`bib-check --document` in a project without LaTeX (resolved in 3.2.0, Phase 2 step 1), and the missing `DOC=NAME` hint
for `bib-check` in `make help`.

The facts about each command (which module it needs, whether it takes `--document`, whether
its JSON output is native) live in six places today: `runtime.ACTIONS`,
`runtime.DOCUMENT_ACTIONS`, the `action_module` and `required` dictionaries in
`runtime.dispatch`, `guide.COMMANDS`, and the `--document` set in
`adapters.module_make_targets`. They already disagree.

1. **Guard first.** Before refactoring, add a test that renders, for every fixture
   configuration the suite already uses (profiles, adopted Make, multi-document, no-TeX),
   the generated Makefile block, `.vscode/` files and workflow, and compares them with
   stored expected copies (`tests/fixtures/generated/`). Commit the expected copies
   *before* the refactor, so the refactor cannot change them silently.
2. Create an `Action` table, for example in `commands.py`, a new runtime file: add it to
   `core.RUNTIME_FILES` and `core.runtime_sources`. Each entry holds:
   - `name` and `handler`
   - `module` (required module)
   - `document` (accepts `DOC`)
   - `native_json`
   - the Make names (`short`, `reserved`)
   - the guide group and description
3. Derive these from the table:
   - `guide.COMMANDS`
   - argparse `choices`
   - the recipe generation in `adapters.module_make_targets`
   - the module checks in `dispatch`
4. Replace the `if/elif` in `runtime.dispatch` with handler functions, one per action, and
   remove the `_backend` injection through `globals()` in `runtime.py`.

**Done when** the suite and the generated-file guard pass unchanged, `runtime.dispatch` is a
lookup, and no action name is spelled in more than one table. Release as 3.1.0 (internal),
or fold it into the next release.

## Phase 2 — F7: layering and a typed document configuration

**Step 1 done — 2026-10-12, workbench 3.2.0, landing commit `49942a4` (PR #7).**
The configuration schema, its validation and the declared documents moved into `schema.py`, directly above `core`
(named `schema`, not `config`, because `config` is a parameter name in nearly every function). The static import graph,
function-local imports included, has no cycle, three tests in `test_architecture.py` keep it so, and `core` imports only
`processes`. The same pull request carried the `--document` message for a project without LaTeX (the first open item
under Phase 1). See [verification-3.2.0.md](verification-3.2.0.md#hosted-verification) for the hosted CI results.
**Step 2 done — 2026-10-12**, in two pull requests. Workbench 3.3.0, landing commit `6c36ff8` (PR #10):
a resolved document is an immutable `DocumentView` and what a project shares with every document is a `SharedSettings`,
both frozen dicts whose JSON, the one a build record stores, `tests/fixtures/views.json` pins from the code before the
change. Workbench 3.4.0, landing commit `4446af8` (PR #11): `document_settings` takes a project
configuration only, `latex.py` never resolves one, and the function-local imports of modules every project has are
module-level imports; only imports of optional modules (`latex`, `research`, `markdown`, `documents`,
`output_transaction`) stay lazy, as they are installed only with their module. The hosted CI results are in
[verification-3.3.0.md](verification-3.3.0.md#hosted-verification) and
[verification-3.4.0.md](verification-3.4.0.md#hosted-verification).
**Phase 2 is done.**

Do it in two steps, each its own branch and pull request.

1. **Break the cycle.**
   - Move schema validation (`validate_config`, `validate_document_settings`, the `check_*`
     helpers, `unknown_keys`) and `documents.resolve`/`specifications` into a `config.py`
     that depends only on `core` utilities.
   - `core` must not import `documents`, `latex` or `guide`.
   - Add a test that imports each runtime module on its own, in a fresh interpreter, and
     checks the import graph has no cycle. `test_architecture.py` is the place for it.
2. **Typed document settings.**
   - Introduce a frozen `DocumentView` dataclass: name, root, engine, output directory,
     build command, lint, bibliography, validation and inputs.
   - Backend functions in `latex.py` take it instead of calling `document_settings(config)`
     on entry (16 calls today).
   - **Constraint:** the in-progress build record stores the settings as JSON
     (`"configuration"`), and `finish_build` compares them. Keep that JSON shape exactly,
     through a `to_json()` that reproduces today's `Document.view`. Otherwise every build
     that is running during an upgrade fails, and a test should pin the shape.

**Done when** there is no function-local import used only to dodge a cycle, `document_settings`
no longer passes an already-resolved view through, and the suite and guard pass.

## Phase 3 — small and safe items

**Done — 2026-10-12.** F14 in workbench 3.5.0 (landing commit `83a1d47`), the safe part of F10 in 3.6.0 (`f58b960`) and F9 in
3.7.0 (verified on its branch head `a34b9b2`; this repository starts from that tree). Records:
[3.5.0](verification-3.5.0.md), [3.6.0](verification-3.6.0.md), [3.7.0](verification-3.7.0.md). Where the work differed from the
text below: F9's "skip these folders" call sites share `core.GENERATED_TREES` except the installer's own additions and the
reserved module paths; the recursion guard now lives in `schema.py` and reads `commands.RECURSIVE_GOALS`; and the second
`.csv`/`.tsv` of the planner's lists was unreachable, so it was removed and not merged into a table. Phase 4 needs the owner's
decision before any code.

Each was one short branch.

- **F14 action pinning.** Pin `actions/checkout`, `actions/upload-artifact`,
  `actions/setup-python` and `xu-cheng/texlive-action` to commit SHAs, with the tag in a
  comment, both in the generator (`adapters.py`) and in this repository's workflows. Add a
  Dependabot configuration for `github-actions` so the pins get updated. Every installed
  project's workflow changes on upgrade, so announce it in the release notes.
- **F10, safe part only.** Add `validation.ignore` globs, for example `docs/**`, so that
  paths the owner declares are never routed to the manuscript build. Validate them like
  `manuscript_inputs`, and document them in `docs/configuration.md` and `docs/validation.md`.
  Do **not** narrow routing by build records: `\graphicspath` folders are one case that
  would be missed.
- **F9, the remaining duplicates.**
  - The recursion guard for a project's own build command (`documents.py`) names `check`, `document-check`,
    `validate` and the `latex-ai-` forms in two sets, and `bootstrap.py` lists the Make targets the template already
    defines. Derive the first from the command registry, and see whether the second can be read from the template
    (found in Phase 1).
  - Collapse the Markdown link check in `runtime.file_checks` into one function.
  - Give the planner one suffix table (`.csv`/`.tsv` are in two lists today).
  - For the six "skip these folders" sets, decide per call site. The installer skipping
    `build/`, `out/` and `workbench/` is deliberate; the others should share one
    `core.GENERATED_TREES`.

## Phase 4 — F11: run `make <goal>` as the default for adopted builds (owner decision first)

**Retired — not done, 13 October 2026.** The owner decided that the Make adoption layer is not needed: a project with its own build uses
`build_command` or a hand-written target ([the minimal scope](minimal-scope.md)). There is no adoption mode left to choose a default for.

**Decision to put to the owner before any code:** should *new* installs that adopt
`["make", "<goal>"]` default to the simple mode (the workbench runs `make <goal>` as a child
under the build record), with today's shared-graph "phased" mode kept as an opt-in?
Existing installations keep their mode either way.

**Design** (if approved):
- Add `"make_ownership": "command" | "phased"` per document.
- The installer records `phased` for documents that already have it, so upgrades don't churn.
- In `command` mode, `adapters.make_adapter` uses the existing non-phased path: `latex-ai-build`
  runs `build --document`, and `compile_document` runs `make <goal>`.

**Hard case:** the project's own `check` also reaches `<goal>`. Under `make -j check`, the
outer `<goal>` and the child `make <goal>` would compile at the same time. Either make
`latex-ai-build` order-only after `<goal>`, or refuse with a hint. Order-only means `<goal>`
is built outside the record first, the child finds it up to date, and `finish_build`
regenerates once.

**Tests:**
- every adopted-Make test, with both modes (`grep -l "build-prepare\|EXTRA_PREREQS\|adopted" workbench/tests/*.py`)
- portability on GNU Make 3.81 *and* 4.x
- `make -j4 check` with an existing `check: pdf`

**Done when** command mode works on Make 3.81 without `.EXTRA_PREREQS`, phased mode is
unchanged, and the release notes describe the default. Release as 3.1.0.

## Phase 5 — F14: one TeX container in CI

**Met in 4.1.0 — 13 October 2026.** `latex.yml` runs the portability tests and the reference manuscript's check in one TeX Live container; the
per-document steps and `schema3-acceptance.yml` went with the workflow generator ([4.1.0](verification-4.1.0.md)).

- **Change.** Replace the per-document `xu-cheng/texlive-action` steps with either a job-level
  `container:` image (pinned TeX Live) or a matrix over `document_ids`.
- **Upload conditions.** Keep the per-document upload conditions, and keep
  `schema3-acceptance.yml` passing.
- **Validation.** This can only be proved on GitHub Actions. Iterate on a branch, and compare
  run times before and after in the verification record.

## Phase 6 — F13: run-archive layout (only when archives grow)

**Retired — moot, 14 October 2026.** The run archives belonged to the research modules, which 4.0.0 removed ([4.0.0](verification-4.0.0.md)).

- **Layout.** New records go under `results/runs/<module>/<task>/<stamp>-<uuid>/`, as record
  schema 2, with snapshots in content-addressed `results/runs/blobs/<sha256>`.
- **Old records.** Old flat records are evidence: read them forever, and never move or
  rewrite them.
- **Lookup.** `research.load_records` (8 callers) finds the latest record per task by listing
  directories.

## Phase 7 — F15: tests by component

**Moved — 14 October 2026.** This is now step 3.8 of [the plan after 4.4.0](plan-after-4.4.0.md). The components named below that no longer exist
(Make adapters, research, Markdown) drop out, and locks go with step 3.3.

- **Regroup.** Regroup `workbench/tests/test_*` by component: receipts, locks, planner,
  installer, Make adapters, research, Markdown, guide.
- **Origins.** Keep each test's origin in its docstring ("3.0.1 audit: …").
- **References.** Update the test-file names cited in the verification records.
- **Separate work.** Shared in-process fixtures, to bring the suite under a minute, are a
  separate task.

## Starting a session

This plan is closed. Start from [the plan after 4.4.0](plan-after-4.4.0.md#starting-a-session).
