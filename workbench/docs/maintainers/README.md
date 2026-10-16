# Maintainers' material

For people who change or release the workbench itself; users do not need any of this.

The records cite local evidence folders (trial transcripts, an adjudication report, smoke projects). On 13 October 2026 they were packed, unchanged, into one archive kept outside the repository, `latex-ai-evidence-3.7.0.tar.gz` (11 MB); the folder names in the records are the top-level folders of that archive. The other scratch folders of the portability and audit runs were deleted.

Workbench 6 is the supported development line. Earlier releases and their
verification records below are historical, retired from support; they are not
compatibility targets. Keep that evidence without maintaining old runtime paths.

## Where this repository starts

This repository begins with workbench 3.7.0, as one commit. The history before it, with its pull requests and hosted runs, is kept in an
earlier private repository. The run numbers, pull request numbers and commit hashes in the records below refer to that repository, and
are plain text here. The tree is that of the branch head the 3.7.0 record names (`a34b9b2`), with these changes only: links to the
earlier repository, local folder paths and the name of a private test project were removed from the records; and
`.github/workflows/workbench-python.yml` runs fewer jobs (see [the cost of the hosted checks](#the-cost-of-the-hosted-checks)).

The repository was recreated on 13 October 2026 from the same tree, with its history rewritten (author metadata in no-reply form, and a private project name
removed from one record). The first version's pull requests and runs went with it, so pull request numbers here start again at 1; the hosted results of
4.0.0 to 4.4.0 that ran there are given in the records as plain text.

- [Version 6.0.0 verification](verification-6.0.0.md): two validation levels, historical material exemptions, and retained build protections.
- [Level 2 validation plan](plan-level-2-validation.md): file checks or full project checks, archive conventions, and the completed implementation stages.
- [Version 5.0.0 verification](verification-5.0.0.md): explicit configuration, LaTeX-only projects, fixed commands, and retained safety.
- [Plan after 4.10.2](plan-after-4.10.2.md): LaTeX-only projects, explicit installation, and fixed commands; no migration support.
- [Plan after 4.4.0](plan-after-4.4.0.md): the remaining reductions in steps, with the owner's gates.
- [Lessons learned](lessons-learned.md): what building this tool taught, for this project and for others like it.
- [The minimal scope](minimal-scope.md): what the tool is for, what stays and what goes, decided question by question.
- [Release notes and release procedure](releases.md): what each release changed, and how a release is cut.
- [Version 3.0 verification](verification-3.0.md): simplification, retained safety, and remaining environment checks.
- [Architecture audit of 3.0.1](architecture-audit-3.0.1.md): assessment, findings and proposals.
- [Plan after 3.0.2](plan-after-3.0.2.md) (closed): the audit's follow-up in phases; Phase 4 retired, Phases 5 to 7 met, moot or moved.
- [Version 3.5.0 verification](verification-3.5.0.md): the pinned workflow actions, and what an upgrade does to a project's workflow.
- [Version 3.6.0 verification](verification-3.6.0.md): `validation.ignore`, and what it never ignores.
- [Version 4.8.1 verification](verification-4.8.1.md): audit repairs, source/output alias protection, graphics freshness, text integrity and bounded scans.
- [Version 4.10.2 verification](verification-4.10.2.md): code audit, export safety, custom-builder diagnostics, configuration errors, build guidance, and isolated regression fixtures.
- [Version 4.10.1 verification](verification-4.10.1.md): three messages the manual's readers found wanting, each with the test that failed before it.
- [Step 3.8 verification](verification-3.8.md): the tests regrouped by component, with every method shown unchanged and the same 541 tests passing.
- [Where the tests are](tests-map.md): the twelve test modules, and where each of the older test files went.
- [Version 4.10.0 verification](verification-4.10.0.md): the Git guardrails of gate G1, and 1,344 spellings of a push to the default branch tried against both agents' rules.
- [Version 4.9.1 verification](verification-4.9.1.md): the manual after two independent readers used it, and what each reader found.
- [Version 4.9.0 verification](verification-4.9.0.md): the doctor's stamp report, the update recipe in the skill file, and an agent other than the author following it on a copy.
- [Version 4.8.0 verification](verification-4.8.0.md): snapshots in three stores with counted retention, so that no clock decides a deletion; the launchd agents, untested.
- [Version 4.7.0 verification](verification-4.7.0.md): `make snapshot` and `make snapshots`, the deleting code held to its refusals, and a snapshot and a restore shown with and without the project's own Git.
- [Version 4.6.0 verification](verification-4.6.0.md): `make all` and a target per document, the Makefile's new lines shown by `diff`, and 232 old-against-new comparisons.
- [Version 4.5.1 verification](verification-4.5.1.md): `init` stops at a paper that needs lualatex, xelatex or biber and prints the `--build-command`, tested with the real tools.
- [Version 4.5.0 verification](verification-4.5.0.md): one engine and one bibliography program, no installer profiles, and 232 old-against-new comparisons.
- [Version 4.4.2 verification](verification-4.4.2.md): the module table's unused fields removed, and 104 runtime comparisons, old against new.
- [Version 4.4.1 verification](verification-4.4.1.md): the runtime refreshed apart from the project's files, `diff` rendering once, and 210 installer runs compared old against new.
- [Version 4.4.0 verification](verification-4.4.0.md): the Make adoption layer removed, `init` create-only, and a real paper migrated by the recipe.
- [Version 4.3.0 verification](verification-4.3.0.md): the installer reduced to `init`, `diff` and `runtime`, and what that changes for an installed project.
- [Version 4.2.0 verification](verification-4.2.0.md): the handbook replaced by a short manual, and what an upgrade leaves behind.
- [Version 4.1.0 verification](verification-4.1.0.md): CI workflow generation removed, and what an upgrade does to a project that had it.
- [Version 4.0.0 verification](verification-4.0.0.md): the research, notes and Markdown modules removed, and what that changes for an installed project.
- [Version 3.7.0 verification](verification-3.7.0.md): the duplicates of finding F9 collapsed, and where that changes behaviour.
- [Version 3.4.1 verification](verification-3.4.1.md): the viewer's output folder in the generated VS Code settings, and what it cannot solve.
- [Version 3.4.0 verification](verification-3.4.0.md): the backends take resolved views and never resolve them; Phase 2 closes.
- [Version 3.3.0 verification](verification-3.3.0.md): immutable, typed document views, and how the build record's shape was pinned.
- [Version 3.2.0 verification](verification-3.2.0.md): the import cycle broken by `schema.py`, and the `--document` message without LaTeX.
- [Version 3.1.0 verification](verification-3.1.0.md): the single command registry, and how it was shown to change nothing an installed project sees.
- [Version 3.0.4 verification](verification-3.0.4.md): the pull-request policy and the agents' refusal of pushes to the default branch.
- [Version 3.0.3 verification](verification-3.0.3.md): the real GNU Make 3.81 repair and macOS Phase 0 results.
- [Version 3.0.2 verification](verification-3.0.2.md): the audit's repairs and optimizations and how they were verified.
- [Version 3.0.1 verification](verification-3.0.1.md): the independent 3.0.0 audit, its reproduced defects and their repairs.
- [Verification record](verification.md): what was run for each release, with hosted-run links and the audit history.
- [Implementation plan](implementation-plan.md): the original design notes.
- [TeX notes and named document targets](tex-notes-plan.md): implementation scope and completion record.
- [Version 2.7 verification](verification-2.7.md): named-document validation and environment limits.
- [Version 2.7.1 verification](verification-2.7.1.md): review findings, regressions and validation of the fixes.

## Working on the workbench itself

Changing this package (a step of [the plan](plan-after-4.4.0.md), a release, a repair) is a different kind of
work from working on a manuscript with it. Only the owner starts a *workbench session*, by saying so in the task,
and the project's `AGENTS.md` ("Two kinds of session") keeps the two apart. In a manuscript session an agent reports
a suspected workbench defect and carries on; the rules below apply only in a workbench session.

**A defect found along the way** is fixed in the pull request already open, as its own commit, when all of these hold:

1. Its regression test fails before the fix and passes after it, and the generated-files guard passes unchanged.
2. The expected behaviour is clear. If it takes a design choice, ask the owner one question and wait for the answer.
3. The fix is small: about 40 lines of non-test code at most.
4. The release it joins is not yet merged, so the fix goes into the same release entry and verification record,
   with no version of its own.

Otherwise it is its own pull request, with its own version and verification record, as before. A fix made along
the way is never folded into the commit that carries the main change, so the evidence for that commit stays whole
(repeat the before-and-after comparison for each commit). The report at the end of the task lists each one: what was
wrong, which test, how large.

**Review.** The owner's review of the pull request and green CI are the review. A repair also needs an independent
(second-model) review when it touches locks (`core.operation_lock`, `research.task_lock`), build receipts (`latex.py`,
`output_transaction.py`), process handling (`processes.py`) or the installer's merge logic (`bootstrap.plan`,
`installation.py`, `adapters.merge_block`).

**What does not loosen.** A failing-first test; the guard; no hand edit of `.latex-ai/`; changes reach `main` only
through a pull request that only the owner merges.

**Git in a workbench session.** The rules, including what stays the owner's every time (merging first among them), are in the project's `AGENTS.md` ("Two kinds of session").
The agents' own permission prompts are separate: they stay as the installed rule files set them.

## Running the package's own checks

The tests are in a module for each component (`tests/test_installer.py`, `test_planner.py`, `test_receipts.py`, `test_guide.py` and so on); [where the tests are](tests-map.md) says which older file each came from.

```sh
make -C /path/to/workbench test         # installer/runtime regression checks
make -C /path/to/workbench portability  # real TeX engine tests
make -C /path/to/workbench check        # both
```

The tests that need TeX are skipped without it, and `portability` stops, naming what is missing. On a Debian or Ubuntu machine, including a cloud session, this is
enough to run both (`apt-get update` first if the package index is empty):

```sh
apt-get install -y --no-install-recommends texlive-latex-base texlive-latex-recommended texlive-fonts-recommended texlive-binaries latexmk chktex
```

The tests of what `init` tells a lualatex, xelatex or biber paper to do build one with the real tool, and skip without it; for them add
`texlive-luatex texlive-xetex biber texlive-bibtex-extra texlive-latex-extra`.

The portability script creates fresh synthetic projects under a temporary folder
(`LATEX_AI_PORTABILITY_PARENT` names another), keeps logs and PDFs, and never initializes Git. It exercises
pdfLaTeX/BibTeX, several input files with an export, a nested root and output folder,
existing Make/editor/workflow configuration, idempotence, and expected failures.
Named TeX notebooks cover per-document exports and selective
fragment checks; the mixed Markdown/TeX example is compiled and exported too.
It also builds an existing GNUmakefile project and checks the actual diagnostics
for expected failures, plus documentation-only selection and a broken-link
failure. The managed CI workflow uses the same classifier to select file checks,
package tests, compiler portability and manuscript checks. Documentation-only
runs skip the TeX container and PDF upload.
Pandoc integration regressions run when it is on PATH and otherwise report
explicit skips. The managed CI installs it when package regressions are selected.
Fixture entries are explicitly synthetic and never inserted into research
manuscripts. Remote GitHub Actions and desktop integrations need their own
human-controlled verification; local tests do not claim to exercise them.

## The cost of the hosted checks

Hosted runs use the repository owner's allowance of Actions minutes, which is not metered while the repository is public. Two things keep the runs few anyway: the
Python compatibility workflow runs on a pull request and on pushes to `main` only, not on every branch push as well, and a newer commit on a pull request cancels
the run it makes obsolete.

The Python compatibility workflow tests all five supported versions (3.10 to 3.14) on a pull request and on `main` alike. Until 14 October 2026 a pull request tested
only the oldest and the newest, which saves minutes on a private plan; the 3.12 job then failed on the pushes to `main` for 4.3.0 and 4.4.0, a version their pull
requests had not tested ([the 4.4.0 record](verification-4.4.0.md#hosted-verification)). If the repository ever goes private again, the matrix is the place to cut,
knowing what that costs; the ruleset's required checks must follow the matrix.

Neither workflow has a `paths` filter, because both are required checks and a required check that a filter skips would leave a pull request waiting for it forever.
`latex.yml` runs the file checks, then the portability tests and the reference manuscript's check in one TeX Live container; its job is `validate`. The ruleset on
`main` requires `validate` and the five Python jobs, `test (3.10)` to `test (3.14)`, so a red Python job blocks the merge. Those six names are what the ruleset matches:
renaming the job, or changing the matrix, means updating the ruleset in the same step.
