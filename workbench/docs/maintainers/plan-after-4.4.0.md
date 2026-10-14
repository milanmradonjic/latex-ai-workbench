# Plan after 4.4.0

The plan for finishing [the minimal scope](minimal-scope.md). It was written on 14 October 2026, when `main` was at `ac4f0b6` (workbench 4.4.0, the MIT
licence and a test-only repair). It replaces [the plan after 3.0.2](plan-after-3.0.2.md), which is closed. Each step stands alone: read this file, the scope and
the verification record of the last release, then start the next step that is not marked done and does not wait for a gate.

## Where things stand

- **Done.** 4.0.0 to 4.4.0 removed the research, notes and Markdown modules, CI generation, the long handbook, the installer's upgrade machinery and the Make
  adoption layer ([progress](minimal-scope.md#progress)).
- **Size.** The runtime is 3,948 lines in 12 files (about 6,800 at the 3.7.0 freeze; the scope estimates 2,000 to 2,500 kept). The suite is 351 tests in 5,615 lines.
- **Hosted checks.** At `ac4f0b6` the [five supported Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38477410380) and
  [`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38477410344) passed.
- **Decided.** The licence is MIT (13 October). No biber (14 October): the engine is `pdflatex`, and the bibliography backend is `none` or `bibtex`.
  The locks and the `running` build state stay (14 October): see step 3.3. The `biblatex` export format goes with biber (14 October): see step 3.4.
- **Not yet decided.** The three gates below.

## Rules every step follows

These come from the repository's `AGENTS.md`, plus what 4.0.0 to 4.4.0 taught.

- **Git.** One topic branch and one pull request per step (`plan/<step>-<topic>`). The agent opens the pull request itself once the branch is pushed
  ([`AGENTS.md`](../../../AGENTS.md)); the owner merges, after `validate` has passed.
- **Failing first.** A change in behaviour gets a test that fails before it and passes after it, and each new test is mutated once to see it fail. New tests go in
  `tests/test_scope_<version>.py` until step 3.8 regroups them.
- **Old against new.** Where output must not change, install the previous release and this tree into identical projects, run every action, and compare. The
  generated Makefile and editor files stay byte-identical unless the step says otherwise and the release notes announce it.
- **Removals.** What goes is refused by name, with a hint, as the removed modules were in 4.0.0; a configuration that only uses what stays keeps working
  unchanged. [`migrating.md`](../migrating.md) and [`upgrading.md`](../upgrading.md) say what a project does.
- **Reference parity.** After any change under `workbench/`, run `make -C workbench upgrade-reference` and commit the regenerated `.latex-ai/` with it.
- **Before pushing,** these must pass: `make -C workbench test`; `make -C workbench portability` where TeX is installed; and in the reference
  `python3 -B .latex-ai/workbench.py validate --files-only`.
- **Hosted proof.** Every pull request runs all five supported Python versions (since step 2), and the ruleset requires them with `validate`: a red Python job
  blocks the merge.
- **Release record.** Each release gets release notes, and a verification record with the hosted results, what was not verified, and the runtime's line count.
- **No personal data.** No personal email address, local path or private project name in any file, commit message or pull-request text. Before pushing, run
  `git log --format='%an <%ae> | %cn <%ce>' origin/main..HEAD` and check that every address is one meant to be public: the host's no-reply form, or an agent's.
- **Review.** A change to receipts, locks or process handling needs an independent review, as [the README](README.md#working-on-the-workbench-itself) says.

## Step 1: records (docs only)

**Done — 14 October 2026**, [pull request #2](https://github.com/milanmradonjic/latex-ai-workbench/pull/2) (`aa33b79`).

Close the plan after 3.0.2 (a status for Phases 4 to 7, and its session prompt replaced); add this plan; record the scope's decisions and what is still to do; correct
the stale "Workbench 3" statements and the README's link to the verification record; give 4.3.0 and 4.4.0 their hosted results and say that the repository was
recreated; add the lessons of the recreation.

**Done when** the pull request has merged, `validate --files-only` passes and no record points an agent at removed work. The two error strings in `schema.py`
that still say "Workbench 3" are runtime files, so they change in step 3.1.

## Step 2: test every supported Python on pull requests, and require them

**Done — 14 October 2026**, [pull request #3](https://github.com/milanmradonjic/latex-ai-workbench/pull/3) (`d1a0b45`). The ruleset on `main` requires `validate` and the five Python jobs.

`workbench-python.yml` tested only 3.10 and 3.14 on a pull request, to save a private plan's Actions minutes. The repository is public, so the saving is gone, and it
had a cost: the 3.12 job failed on the pushes to `main` for 4.3.0 and 4.4.0, a version their pull requests did not test.

- **Change.** Test all five versions on pull requests, and rewrite [the cost of the hosted checks](README.md#the-cost-of-the-hosted-checks), which also still named
  two generated workflows that no longer exist.
- **Decided, 14 October 2026.** The five Python jobs are required checks, with `validate`, so a red one blocks the merge. That takes two changes: the workflow loses its
  `paths` filter (a required check that a filter skips would wait forever on a pull request that touches no matching path; public runs are unmetered), and the owner adds
  `test (3.10)` to `test (3.14)` to the ruleset on `main` once the workflow has merged, never before, or no pull request could pass.
- **Done when** a pull request shows five Python jobs and `validate`, and the ruleset requires all six.

## Gates: the owner's decisions

Each is settled before the step that depends on it.

- **G1, Git guardrails.** The rule files hold 148 deny and 121 ask entries for Claude Code and 43 rules for Codex, pinned to the policy by `test_workbench.py`. The
  scope asks for less: ask before commit or push, no push to `main`, no merge. Options: keep the set; or keep the generated deny set (pushes to `main`, merges) and
  prompt only on commands that write history, branches or the working tree. Also decide whether the record-merge exception (`merge_record_pr.py`) stays, and add a
  test of equivalent command spellings in both agents' rules: `git push origin feature:main` only prompts today. Settle this before any change to the rule files.
- **G2, changed-file routing.** The planner routes lightweight checks, affected documents, bibliography, package tests and a conservative fallback. Decide three
  things. Workflow YAML is ordinary text in the code but a protected build control in `validation.md`. Figure scripts get syntax checks only, so they must be declared in
  `validation.manuscript_inputs`, and the manual should say so. A project without Git always falls back to a full check; revisit that once snapshots exist, if the full
  check is too slow there.
- **G3, the manual.** Ratify the 44-line draft (`make guide`, capped at 60 lines by a test); choose how project notes grow, since the manual lives in code; and have a
  reader other than its author follow it.
- **G4, decided on 14 October 2026:** no biber. See step 3.4.

## Step 3: the reductions, safest first

Each step is one release and one pull request.

- **3.1 The runtime refresh apart from project files.** `do_runtime` renders the policy, Makefile and editor templates and keeps only the `.latex-ai/` files; `do_diff`
  renders twice, once directly and once through `runtime_differences`. Give the runtime files their own function and render once in `diff`. The two "Workbench 3"
  error strings in `schema.py` change in this release. **Done when** `diff` and `runtime` print the same on identical projects before and after, and the
  overwrite safeguards are untouched. **Done — 14 October 2026**, [pull request #4](https://github.com/milanmradonjic/latex-ai-workbench/pull/4) (`975663c`), workbench 4.4.1.
- **3.2 The dormant module machinery.** Both modules have empty `tools` and `requires`, and `module_names(group=...)` has no caller that passes a group. Remove them.
  **Done when** configuration, receipts and generated files compare identical. **Done — 14 October 2026**, [pull request #5](https://github.com/milanmradonjic/latex-ai-workbench/pull/5) (`75f4d4f`), workbench 4.4.2.
- **3.3 Locks and interrupted-build recovery.** **Decided 14 October 2026: keep. Done — 14 October 2026**, [pull request #7](https://github.com/milanmradonjic/latex-ai-workbench/pull/7) (`3a3b8a9`), no release. The scope listed the locks among what goes and accepted the risk that two
  simultaneous builds corrupt a record. The owner chose to keep the `running` state and the locks instead, so the workbench still refuses a second build and still
  tells the truth from another terminal while one runs, and a build killed hard whose compiler lives on still blocks the next one until that compiler ends. Nothing is
  removed: `operation_lock` (about 40 lines in `core.py`), `output_transaction.py` (99) and `processes.py` (150, which also starts and stops the compiler) stay, with their
  tests and the lock directory. There is no code change, so no release, and no independent review, which the rules above reserve for a change to locks. The behaviour is
  already pinned by `test_terminated_build_owner_stops_its_compiler`, `test_killed_build_owner_keeps_ownership_while_its_compiler_runs` and
  `test_active_adopted_build_blocks_other_cleanup_and_export`, and `troubleshooting.md` describes it under "Interrupted builds". The scope listed these among what goes, so check its
  estimate of the kept size before relying on it. Reconsider only on evidence: a build wrongly refused, or a platform where the liveness checks cannot work (macOS and
  Windows are still untested).
- **3.4 Engine, backend and profile choices.** Decided: `engine` is `pdflatex`, `backend` is `none` or `bibtex`, there is no biber and there are no installer profiles.
  Remove `--engine`, `--backend`, `--profile` and `core.PROFILES`; the `lualatex`, `xelatex` and `biber` paths in `latex.py`, `schema.py` and `diagnostics.py`; their
  portability scenarios; and the engine and backend inference in `detect_config`. Keep `build_command` for anything unusual. A configuration that says
  `engine: pdflatex` or `backend: none` or `bibtex` keeps working; anything else is refused by name with a hint that points at `build_command`. **Decided 14 October 2026:** the
  `biblatex` export format, which existed to feed biber, goes too, so the export `format` is `bibtex`. **Done when** projects that use only what stays compare byte-identical (generated
  files and receipts), and the tests that mention profiles are rewritten, not deleted blindly. **Done — 14 October 2026**,
  [pull request #8](https://github.com/milanmradonjic/latex-ai-workbench/pull/8) (`4243706`), workbench 4.5.0; at the owner's request 4.5.1 then added a guard to `init` for a paper that needs another toolchain.
- **3.5 Per-document targets.** `make main` and `make notes`, generated only where the name is free; bare `make` builds the default document and `make all` the whole
  package. **Decided 14 October 2026** (by the plan, since no design question arose): `make all` builds every document one after another through one action, `build --all`, since the
  build lock refuses two builds at once; `make NAME` builds that document; a project with one document gets `all` and no `NAME`; a name is free unless the workbench uses it or a
  document's `build_command` names it as a goal (then `all` is not refused as recursive either, being the conventional name of a project's own rule). **Done when** the generated-files guard is updated on purpose, the release notes name the changed lines of the Makefile block, `make guide` names the
  targets, and `diff` shows an existing project exactly what differs. **Done — 14 October 2026**,
  [pull request #10](https://github.com/milanmradonjic/latex-ai-workbench/pull/10) (`ffdc597`), workbench 4.6.0.
- **3.6 Snapshots.** `make snapshot` and `make snapshots`: a shadow Git repository under `~/.snapshots/<project>/` in two rotating tiers, as the scope describes. The
  script removes only folders under that path. Its tests run with a temporary `HOME`. **Decided 14 October 2026** (the owner accepted the recommended answers): everything in the
  project is kept except `.git`, build output and files over 25 MB (named in the output), and the project's `.gitignore` does not apply; the store is
  `~/.snapshots/<name>-<hash of the project's path>/`, with `LATEX_AI_SNAPSHOT_DIR` to change it; the fine tier (every snapshot, one to two weeks) and the daily tier (the first of each
  day, one to two months) each use two repositories by turns, and one older than the previous period is deleted; restoring is Git's own `checkout`, printed by `make snapshots`
  (no `make snapshot-restore`). **Done when** a snapshot and a restore are shown on a project with and without
  its own Git, and `upgrading.md` and `migrating.md` take `make snapshot` as their first step. **Done — 14 October 2026**,
  [pull request #11](https://github.com/milanmradonjic/latex-ai-workbench/pull/11), workbench 4.7.0.
- **3.7 The doctor's stamp report, and the update recipe in the skill file.** `make doctor` reports the project's stamp, the template's and which generated files
  differ; the recipe moves into the skill file, as the scope says. **Done when** an agent other than the author has followed the recipe on a copy, and its diff and
  `make check` result are in the verification record.
- **3.8 Tests regrouped by component.** Receipts, planner, installer and guide, with each test's origin kept in its docstring and the test names cited in the records
  updated. This is the old Phase 7, and it comes last because it renames files the records cite.

After each release, update the scope's progress and this plan, and record the measured line count. Do not promise savings that were not measured.

## Only on evidence

- **Resolve document settings once per command.** `Document.configuration` is a JSON string, and every `.view` access parses and freezes it again. It is the build record's
  format, so touching it risks receipts; do it only if profiling shows a cost, and with a receipt comparison.
- **Explicit configuration instead of inference.** After step 3.4 most of `detect_config`'s inference is gone. Decide then whether a small configuration template should
  replace the rest, trading automatic setup for fewer branches.
- **The latest snapshot as the planner's base** for projects without Git, after step 3.6 and only if the full check proves too slow there.
- **Trim `bootstrap.py`.** What remains is root and bibliography detection and the reporting of `main` ([the 4.4.0 record](verification-4.4.0.md#found-on-the-way)).

## Starting a session

Paste this as the first message of a new session in a clone of this repository:

> This is a workbench session. Read `workbench/docs/maintainers/plan-after-4.4.0.md`, `minimal-scope.md` and the 4.4.0 verification record. Work on the first step not
> marked done, and never on a step that waits for a gate. Follow the plan's rules: branch per step, failing-first tests, reference parity, and no personal data in any
> file or message. Create your topic branches, commit, push them and open the pull requests yourself and report each; merge only a record pull request, and only with
> `.github/scripts/merge_record_pr.py`; never push to `main`, or rewrite or discard work without asking me. Report what passed, what failed and what you could not verify.

Mark a step done here (with the commit and release) when it lands on `main`.
