# Version 4.4.0 verification

This records the release that removes the adoption of a project's own Makefile (the fifth step of [the minimal scope](minimal-scope.md)): `init` only creates files,
and an existing project is migrated by a recipe. Tested on 2026-10-13 on macOS (Darwin 25.5, Python 3.14.8, GNU Make 4.4.1 from Homebrew with `gnubin` first on `PATH`,
the system GNU Make 3.81 for one test, TeX Live with latexmk 4.88 and Biber 2.21). The hosted results follow the local ones.

| Check | Result |
|---|---|
| `tests/test_scope_4_4_0.py` (its tests are now in `tests/test_installer.py`, `tests/test_scope.py` and `tests/test_documents.py`) against 4.3.0 | 12 of its 19 tests fail: the parser, the adapter and the recipe shell exist, the hooks are actions, `init` merges into a project's files and accepts a `GNUmakefile`, the Make 4.3 requirement exists, the old adapter is not recognised, and `migrating.md` does not exist. The 7 that pass pin what stays: a project's own Make targets, added after `init`, build as an ordinary command and stay incremental; `make -n`, `-q` and `-t` run nothing; a fresh Makefile has no hook; `validate` runs a project's own `check`; the project's other files are never touched |
| The same after the change | All 19 pass. Eleven mutations are each caught by the test named for them: `init` merging into a differing file, ignoring `GNUmakefile`, listing only the first conflict, or treating an identical file as one; `validate` never running the project's `check`, or not suspecting an include; the old adapter not recognised; `status` silent about it; the removed hooks answering "invalid choice"; the Makefile no longer an input of a Make build; `build` no longer a recursive goal |
| `make -C workbench test` | 351 tests, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks): 365 before, 35 removed or renamed, 21 added or renamed (19 of them the scope tests) |
| `make -C workbench portability` | 65 of 65 (68 before: the scenarios that merged into an existing `.vscode/settings.json`, a Makefile and a `GNUmakefile` now check that `init` refuses or writes beside them) |
| The generated-files guard | Its fixtures for a fresh install are unchanged; the five for an adopted Makefile and their stored copies are deleted. The Makefile and editor files of every fresh install are byte-identical to 4.3.0's |
| The system GNU Make 3.81, the real one | A fresh project's `help`, `status`, `doctor` and `check` run under it and the document is current. The Make 4.3 requirement is gone |
| 4.3.0 and this tree installed into identical projects, every action, five argument variants, `core`, `writing` and a project without configuration | 270 invocations (30 fewer: the two hooks), 9 differences, all intended: the `status --json` list of runtime files (without `make_graph.py` and `recipe-shell.sh`) and the six `issue` report names (timestamps) |
| The same two installs as file trees | Every file outside `.latex-ai/` is byte-identical in both scenarios. Inside it the runtime files this release changed differ, and the two removed files are absent |
| A plain 4.3.0 `writing` project taken to 4.4.0 | `diff` exits 1; `runtime` changes eight files (seven runtime files and the record); `doctor`, `check`, `status` and `guide` pass; `diff` then exits 0. `make_graph.py` and `recipe-shell.sh` stay in the project, unused |
| A 4.3.0 project that had adopted its Makefile (`["make", "pdf"]`, with the adapter block) | It keeps running on its own 4.3.0 runtime (`check` passes). `runtime` refuses with a pointer to `migrating.md` and writes nothing; this release's `status` says so; the removed hook answers with the pointer. Following the recipe (block out, `.latex-ai/` and the generated files cleared, `init`, the project's `pdf` rule carried back) gives a project whose `check` passes and whose document is current |
| **The real paper, a copy of the owner's two-document test project** (no Git, installed by 3.5.0, two coupled documents with their own build script) | The recipe was followed step by step. Conflicts: `AGENTS.md` and `.gitignore` only (`CLAUDE.md`, `.claude/` and `.codex/` were identical to the templates). After moving them aside, `init` added 15 files. The project's section of `AGENTS.md`, three `.gitignore` lines and one editor preference (`files.exclude`) were carried back, the old workflow removed, the ChkTeX warnings (92 and 37) accepted as a baseline per document. `make doctor`, `make check` and `make status` pass, both documents current. `diff` afterwards lists exactly the three files that hold the project's own content, and says the runtime is identical. The real project was not touched |
| `make -C workbench audit-reference`, `make check` in the repository | Current; the check passes |

## Found on the way

- **The first trial of the recipe was with the 4.3.0 `init`, which appended a second policy** after the project's own section, because the old generated policy was still there.
  That is why `init` stopped merging and why step 4 says to clear an older workbench's generated text first.
- **My test of "stays incremental" was wrong, and the code right.** A custom build command runs every time; the incrementality of `make main.pdf` is Make's. The test now uses a
  file target and asserts one compilation in three checks.
- **A mutation was missed, and it showed a case.** Replacing the end of `project_check_rule` by `False` failed no test, so the last line was unreachable by the test cases; dropping it
  exposed a rule whose recipe sits behind an `ifeq`, which the old parser knew as not ending a rule. The scan now knows it too, and the mutation is caught.
- **A Makefile that a project includes is no longer followed** when it is a recorded input of a `make` build. Declare it in `inputs`. The whole Makefile is hashed, no longer without
  the managed block (there is none), so a project with a `make` build sees one rebuild after refreshing.
- **On a case-insensitive filesystem the receipt lists both `Makefile` and `makefile`** as inputs. Already so in 4.3.0 and harmless; left.
- **The installer shrank less than hoped:** `bootstrap.py` 614 to 557 lines. What remains is the detection of root, engine and bibliography (82 lines) and the reporting of `main`
  (101 lines), including `--json`. Trimming them is a separate decision.

## Hosted verification

The runs of this release's pull request and of its push to `main` were in the first version of this repository, which was later recreated; they are given as plain text.

| Run | Result |
|---|---|
| Pull request: `validate`, `test (3.10)`, `test (3.14)` | passed |
| Push to `main`: `validate` | passed |
| Push to `main`: Workbench Python compatibility, five versions | `test (3.12)` failed; the other four passed |

The failure was in a test, not in the runtime. Five subtests of `test_scope_4_3_0.test_the_installer_has_three_modes_and_refuses_the_removed_ones_by_name` asserted
the exact quoted wording of argparse's invalid-choice message, which Python 3.12.13 prints without quotes. It was reproduced locally on 3.12.13 and repaired by
one assertion, the usage line `{init,diff,runtime}`, which also fails if a fourth mode is added (the old assertion did not). The repair is proved by a [manual run of the
full matrix](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38476470076) on its branch and, on `main` at `ac4f0b6`, by the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38477410380) and [`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38477410344). This release's runtime is
unchanged by it.

## Not verified

- **An agent other than the author following `migrating.md`.** I followed it on the copy of one real paper and on a synthetic adapted project; the first real use by an agent on the owner's
  own project is the test of the wording.
- **`make -n`, `-q` and `-t` on other Make versions** (4.4.1 only, besides the 3.81 test of the generated Makefile), **Python 3.10 to 3.13 on macOS** (covered on Linux by the hosted runs above), **Windows.**

## Open items

Next in [the order of the work](minimal-scope.md#order-of-the-work): the locks and the interrupted-build recovery, and the per-document targets (`make main`, `make all`); then snapshots; the full list is [the plan after 4.4.0](plan-after-4.4.0.md).
Migrating the owner's real two-document test project is the owner's call and needs a copy or a Git repository first.
