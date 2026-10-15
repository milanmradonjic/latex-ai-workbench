# Version 4.9.1 verification

This records the release that corrects the manual (`make guide`) after two independent readers used it: gate G3 of [the plan after 4.4.0](plan-after-4.4.0.md) asked for "a reader other than its author", and the 4.2.0 record
had said that nobody but the author had read it. The owner asked for the readers and for the manual to be improved by what they found; the owner's own reading is still to come, when the manual is in use.
Built on 4.9.0 (`c45c374`). Tested on 2026-10-15 on Linux (x86_64, GNU Make 4.3, Git 2.43.0, Python 3.13.16, 3.12.13 and 3.11.17) with TeX Live 2023 from Debian.
The hosted results are at the end of this record (added by the record of 4.10.1).

| Check | Result |
|---|---|
| `tests/test_scope_4_9_1.py` (now in `tests/test_guide.py`) against 4.9.0 | All 15 of its tests fail: no file named in the Documents line and "is missing" for a document never built, no folder for the PDF, "verified" in the states, nothing about where `make all` stops, an undefined reference or the Hint, Git, FILE, ChkTeX, what the agents ask about, the update pointer, or what `validation-plan` does without Git |
| The same after the change | All 15 pass, and so does the older `tests/test_guide_3_0_1.py` (now in `tests/test_guide.py`), whose three assertions were changed on purpose (the Documents line and the stale reason now read as below) |
| What the new tests hold the manual to | Each claim is checked against what the tool does: the PDF folder the manual names is the one a build writes into (the usual `.latex-ai/artifacts/documents/NAME/build/`, taken from the same rule as the build, or a document's own `output_dir`); an undefined reference makes a build fail and leaves the document `failed`; a snapshot of a project under Git holds a file that was never committed, and `make snapshots` prints the FILE the manual says to replace; `validation-plan` in a project without Git selects full validation; the installed rule files ask before `git commit`, `push`, `reset`, `clean` and `restore` and deny pushes to `main` and `gh pr merge`, as the agents line says; `docs/upgrading.md` exists. `make all` stopping at the first failure is pinned by `test_scope_4_6_0.py` (its tests are now in `tests/test_installer.py`, `tests/test_documents.py` and `tests/test_guide.py`); the new test pins that the manual says so |
| Twenty mutations | All 20 caught by a test named for it: the file dropped from the Documents line; "missing" shown again; the PDF folder always the usual one, or a single document's folder shown with its name; `current` or `stale` saying "verified" again; the states header silent about the checks; `make all` not said to stop; an undefined reference not called an error; every error promised a Hint; Git, FILE or uncommitted files dropped from the snapshot lines; "the owner's decision" back; "any Git change" back; the default branch not named; the quickstart pointer back; `validation-plan` silent about Git; the stale reason or the status step saying "verified" again. **One was missed on the first run** (uncommitted files dropped from the snapshot line); a test that takes a snapshot of a project with a never-committed file was added, and the mutation is now caught |
| `make -C workbench test` | 529 tests (the 514 of 4.9.0 and the 15 new), 2 skipped (the unreadable-folder test, since this runs as root, and the test that needs GNU Make 3.81), OK on 3.13.16, 3.12.13 and 3.11.17 |
| `make -C workbench portability` | All 51 scenarios pass |
| 4.9.0 and this tree, identical projects, each installed and run by its own release | 232 comparisons, 0 differences, none skipped as noise: the eight projects of the earlier comparisons. Masked, because they are the change: the version, the manual's whole text, the words of the states `current` and `stale` (also in the next steps `status` proposes), the stale reason "changed since the build" and "no build yet" in `status`. Every receipt, every policy and editor file and every other action's output is identical |
| The generated-files guard | Unchanged: the Makefile did not change. The reference's Makefile needed no edit |
| `make -C workbench upgrade-reference`, then `audit-reference` | The refresh changed `core.py`, `guide.py`, `latex.py` and `schema.py` in the reference's `.latex-ai/` (and the stamp), and the audit then reports the runtime identical |
| Size | The package is 4,413 lines (4,396 before; `cat workbench/*.py`); `bootstrap.py` is still 579. The tests are 7,869 lines (7,685). The manual is 55 lines in this repository's reference (52 before; the cap is 60, which a project with three documents also meets) |

## The two readers

Each was a fresh agent given a project made by 4.9.0's installer and told to behave as a reader: use only the output of `make guide`, and `make help` where the manual points to it; not read the workbench's source, `AGENTS.md` or other
documents; report guesses and confusion instead of reading around them; label each claim observed or inferred. Both worked in a scratch copy with their own home and snapshot folders. I gave them no hint of what I expected.

- **Reader A, a newcomer, no Git** (seven tasks: first state and first step, produce the PDF, change a sentence and run the checks the change needs, the full check, a snapshot and a restore after ruining a file, an error made on purpose, how to
  learn the version and update). One slip against its rules: it redirected one command's output to a scratch file outside the project, read it and deleted it; it saw `AGENTS.md` and `CLAUDE.md` in a listing and opened neither.
- **Reader B, an owner, two documents under Git** (seven tasks: the documents and their states, the checks a source edit needs, rebuilding one document, what agents may do and what to do first, restoring a ruined file, a warning and `lint-baseline`, the words
  it misread). My fixture's `paper.tex` already had an undefined `\ref`, so the failure meant for its task 6 met it in tasks 1 and 2; that exposed more than planned.

What they found, and what changed:

| Finding | Reader | What changed |
|---|---|---|
| The manual never says where `make build` leaves the PDF (found mid-log) | A, B | The build line names the folder, from the rule the build uses |
| "manuscript (default) is missing" read as a missing file | A, B | "manuscript = main.tex (default): not built yet"; the table keeps the state's name `missing` |
| No map from a document's name to its file | B | The Documents line gives the file |
| "verified" (build, PDF) read as "the checks passed"; `current` stayed after a failed `validate` | A, B | The states say what is true (built from these files without a LaTeX error); the header says they are not a check result; `status` follows |
| `make all` stops at the first failure and the manual did not say so (slides were never built) | B | Said in the manual (behaviour unchanged: pinned in 4.6.0) |
| An undefined reference or citation is an ERROR and fails the build, which the manual never said | A, B | Said; checked by a build in a test (an undefined citation was tried on a project too) |
| The manual promises a Hint on every ERROR; the unresolved-reference error has none | B | "and its Hint, if it has one" (the error itself is unchanged, see below) |
| "ChkTeX", "baseline", "the owner's decision" unexplained (the reader was the owner) | A, B | "accept today's ChkTeX style warnings so that only new ones fail; your decision, never for an ERROR" |
| "the Git command that restores from one" in a project without Git; FILE to be replaced by hand; the restore overwrites | A, B | Git must be installed, the project need not use it; uncommitted files are kept; replace FILE; the file is overwritten |
| `make check` does not say what it covers | A, B | "build, references, citations and, if on, lint" |
| "They ask before any Git change": does that include a commit? May they edit files? "default branch" with only `master` | B | "They edit your files. They ask before committing, pushing or anything that rewrites or discards work, and never push to the default branch (main or master)"; true of the installed rules now and after the Git guardrail change the owner decided |
| `validation-plan` and `validate` select everything in a project without Git, and the manual was silent | A | "nothing runs; without Git, all of them" |
| How to learn the version and how to update: "docs/quickstart.md in the workbench package" has no place a reader can find | A | The version is the manual's first line; "follow docs/upgrading.md in a newer workbench folder (the one you installed from)" |

Reported by the readers and **not changed**, because they are outside the manual's wording (each is a candidate for a later step, and none was fixed here):

- The ERROR summary line is cut at about 80 characters (A: `... ended by \end{docume`); the full text is in the log it names.
- The unresolved-reference ERROR has no Hint line (B; seen again here), though most errors have one.
- `status` offers `make document-check` where the manual's loop says `make validate` (A), and after a failed `validate` it offers `make validate` again and never says that nothing is pending (B).
- A change to `slides.tex` is routed as "manuscript input or potential figure", and the checks are named "files" and "manuscript" (B); the words mean the documents and the text checks.
- `make lint` and `make document-lint` print nothing on success and are only in `make help`; `make document-check` stops at a failed build, so its lint never runs (B).
- `make build` does not print where the PDF is; the manual now says.
- A reader suggested ending `status` with "all green: commit", and a line on `git restore FILE`; neither was added (the first is `status`'s behaviour, the second is ordinary Git).

**Update (4.10.1):** the missing Hint, the cut-off ERROR line and the failed document's log in `status` were fixed in [4.10.1](verification-4.10.1.md); the others stay as listed.

## Found on the way

- **Claims checked, not copied.** I verified the reader claims the new text rests on before writing it: `make all` stops at the first failure (the loop in `do_build` and the 4.6.0 test), undefined references and citations both fail a build and leave `failed`, the PDF folder pattern, and that the integrity error has no Hint line.
- **The state words are shared.** `STATES` in `schema.py` feeds both the manual's table and `status`, so one correction reaches both; the two other places that said "verified build" (the stale reason in `latex.py`, the no-build step in `guide.py`) changed with them. The state names, the JSON and the receipts did not.
- **A custom folder is shown as it is.** In this repository's reference the manuscript builds beside its source, so the manual says "build the PDF (into ./)"; with several documents that set their own folders, each is named.
- **A test of mine was wrong, not the tool,** twice: a document's source file must exist before the configuration is valid, and the documents are listed in alphabetical order.

## Hosted verification

All six required checks passed on the pull request ([#18](https://github.com/milanmradonjic/latex-ai-workbench/pull/18): [`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38711302394) in 1m58s with TeX Live 2026; the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38711302351), 2m04s to 2m45s each), and again on the merge commit `ac737c1` on `main` ([`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38712404040); the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38712404070)).

## Not verified

- **The owner's reading.** The readers are language models told to behave as newcomers. They found wording that misled them; whether the manual suits the owner is for the owner, and G3 stays open for it.
- **How project notes grow** (the second question of G3) is not decided; the recommendation is in the plan.
- **The PDF folder for a project whose documents mix the usual folder and their own:** each is named, as tested with three documents that all set their own; the mixed case was not run.
- **macOS and Windows.**

## Open items

G3 still waits for the owner's reading and the decision about project notes. The rule files of the Git guardrails are not yet changed (the decision is in [the plan](plan-after-4.4.0.md)); the manual's agents line is true before and after. Next in the plan: step 3.8, the tests regrouped by component.
