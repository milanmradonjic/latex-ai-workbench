# Maintainers' material

For people who change or release the workbench itself; users do not need any of this.

The records cite local evidence folders (trial transcripts, an adjudication report, smoke projects). On 13 October 2026 they were packed, unchanged, into one archive kept outside the repository, `latex-ai-evidence-3.7.0.tar.gz` (11 MB); the folder names in the records are the top-level folders of that archive. The other scratch folders of the portability and audit runs were deleted.

Workbench 3 is the supported development line. Earlier releases and their
verification records below are historical, retired from support; they are not
compatibility targets. Keep that evidence without maintaining old runtime paths.

## Where this repository starts

This repository begins with workbench 3.7.0, as one commit. The history before it, with its pull requests and hosted runs, is kept in an
earlier private repository. The run numbers, pull request numbers and commit hashes in the records below refer to that repository, and
are plain text here. The tree is that of the branch head the 3.7.0 record names (`a34b9b2`), with these changes only: links to the
earlier repository, local folder paths and the name of a private test project were removed from the records; and
`.github/workflows/workbench-python.yml` runs fewer jobs (see [the cost of the hosted checks](#the-cost-of-the-hosted-checks)).

- [Lessons learned](lessons-learned.md): what building this tool taught, for this project and for others like it.
- [The minimal scope](minimal-scope.md): what the tool is for, what stays and what goes, decided question by question.
- [Release notes and release procedure](releases.md): what each release changed, and how a release is cut.
- [Version 3.0 verification](verification-3.0.md): simplification, retained safety, and remaining environment checks.
- [Architecture audit of 3.0.1](architecture-audit-3.0.1.md): assessment, findings and proposals.
- [Plan after 3.0.2](plan-after-3.0.2.md): the remaining audit work in phases, starting with macOS verification.
- [Version 3.5.0 verification](verification-3.5.0.md): the pinned workflow actions, and what an upgrade does to a project's workflow.
- [Version 3.6.0 verification](verification-3.6.0.md): `validation.ignore`, and what it never ignores.
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

Changing this package (a phase of [the plan](plan-after-3.0.2.md), a release, a repair) is a different kind of
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

**Git in a workbench session.** Starting one pre-approves creating its topic branches, commits, pushes of those
branches and opening their pull requests; they are reported afterwards, with how to undo each. Every time, the
owner's: merging (with the one exception below), updating their clone, any push to `main`, anything that rewrites or
discards work, Git configuration and the agents' permission rules. The wording is in the project's `AGENTS.md`
("Two kinds of session"). The agents' own permission prompts are separate: they stay as the installed rule files set them.

**Merging a record pull request.** The owner delegates one merge: a pull request that changes only
`plan-after-3.0.2.md` or `verification*.md` here, the records of what landed. `.github/scripts/merge_record_pr.py NUMBER`
squash-merges it and deletes its branch on GitHub, after checking that it is open, not a draft, aimed at `main`, clean and
mergeable, that no check is pending or failing, and that every changed file is a record; `--dry-run` only reports. It merges
against the exact commit it inspected, never switches the owner's local branch, and refuses everything else, among it this
README, `releases.md`, code, policy, permission rules, workflows and itself. `tests/test_record_merge.py` pins each refusal.
The agents' rule files still deny a raw `gh pr merge`, so the script is the only way in. To run it without a prompt each
time, the owner may add `{"permissions": {"allow": ["Bash(python3 .github/scripts/merge_record_pr.py:*)"]}}` to the
untracked `.claude/settings.local.json`; the installed `.claude/settings.json` is left as it is.

## Running the package's own checks

```sh
make -C /path/to/workbench test         # installer/runtime regression checks
make -C /path/to/workbench portability  # real TeX engine tests
make -C /path/to/workbench check        # both
```

The portability script creates fresh synthetic projects alongside the reference
under `Projects/`, keeps logs and PDFs, and never initializes Git. It exercises
pdfLaTeX/BibTeX, LuaLaTeX/Biber/multiple inputs, XeLaTeX/nested root/output,
existing Make/editor/workflow configuration, idempotence, and expected failures.
Named TeX notebooks cover all three engines, per-document exports and selective
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

Hosted runs use the repository owner's allowance of Actions minutes (unmetered if the repository is public). The Python
compatibility workflow was by far the largest user, so it runs on a pull request and on pushes to `main` only, not on every branch
push as well; a newer commit on a pull request cancels the run it makes obsolete; and a pull request tests the oldest and the newest
supported Python (3.10 and 3.14), while a push to `main` tests all five. A change that touches only the workflow file is therefore
first proved on its pull request with two versions, and in full after it is merged. The two generated workflows
(`latex.yml`, `schema3-acceptance.yml`) are the workbench's own output for projects, and still run on both events.
