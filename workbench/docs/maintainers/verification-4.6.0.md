# Version 4.6.0 verification

This records the release that adds `make all` and a `make NAME` for each document of a project that has several (step 3.5 of [the plan after 4.4.0](plan-after-4.4.0.md)).
Tested on 2026-10-14 on Linux (x86_64, GNU Make 4.3, Python 3.13.16, 3.12.13 and 3.11.17) with TeX Live 2023 from Debian: `latexmk`, `chktex`, `bibtex`, `lualatex`, `xelatex` and `biber`.
The hosted results are at the end of this record (added by [the next record](verification-4.7.0.md)'s pull request).

| Check | Result |
|---|---|
| `tests/test_scope_4_6_0.py` (its tests are now in `tests/test_installer.py`, `tests/test_documents.py` and `tests/test_guide.py`) against 4.5.1 | 13 of its 16 tests fail: the Makefile has no `all` and no document's target; the registry does not know `all`; `build --all` does not exist, so `make all`, `make notes`, the parallel `make -j4 all`, the stop at the first failure and the refusal of `--all` with a document or on another action all fail; the guide and help name no target; `diff` has nothing to show a 4.5 project. The other three pin what must not change and pass on both: bare `make` builds the default document only (twice: in the Makefile and in a run), and a one-document project gets no `make NAME` |
| The same after the change | All 16 pass. The runs use `make` itself on projects with two documents: `make notes` builds only `notes`; `make -j4 all` builds both without the build lock refusing the second; a failing document stops `make all` and names itself, and the documents after it are not tried |
| Thirteen mutations | Each is caught by the test named for it: the registry losing `all`; a one-document project getting a target; a taken name getting a target; a name the project's build command owns getting one; the alias `all` generated over the project's own; a document's target building the default document; `--all` building the first document only, going on after a failure, accepting `--document`, or accepted by any action; `all` a refused goal again; the guide and the help no longer naming the targets. The first run missed the help (only the manual was asserted), so the test now reads both |
| `make -C workbench test` | 398 tests (382 before, 16 new), 1 skipped, OK on 3.13.16, 3.12.13 and 3.11.17 |
| `make -C workbench portability` | All 51 scenarios pass |
| 4.5.1 and this tree, identical projects, each installed and run by its own release | 232 comparisons, 0 differences, none skipped as noise: the eight projects of the earlier comparisons (four built with a real `latexmk`, one with two documents so that it gets per-document targets). Masked, because they are the change: the version, the Makefile's new lines (`all`, `latex-ai-build-all` and a target per document), the lines of `help` and the manual that name them, and the Makefile's line count in a unified diff's header (89 to 94). The generated `.vscode` files, the policy files, the receipts and every other action's output are identical |
| `diff` on a 4.5 project | The Makefile differs by the added lines and by nothing else (the test removes them from a fresh project's Makefile and reads `diff --diff`: only `+` lines, each of them one of those); `runtime` leaves the Makefile alone |
| The generated-files guard | Regenerated on purpose and read: `core-only` is unchanged; `latex` and `latex-no-editor` gain the five lines of `all`; `multi-document` gains those and three lines for each of its three documents. The editor files are byte-identical |
| `make -C workbench upgrade-reference`, then `audit-reference` | The refresh changed `commands.py`, `core.py`, `guide.py`, `schema.py` and `workbench.py` (the runtime files this release changed) and the record; the reference's own Makefile, which is edited by hand, gained the five lines of `all` as `diff` listed them, and the architecture test that the reference still contains what `init` would write passes |
| Size | The package is 4,009 lines (3,963 before) and `bootstrap.py` 579 (the ceiling the 4.4.0 test sets is 580); the tests are 6,312 lines (6,121) |

## Found on the way

- **`all` is the project's word.** The first version made `all` a refused goal, like `build` and `check`, and an existing test, written in 4.4 to say that a project's own targets are not refused, failed on `make all`. A project that has `all: paper.pdf` and names it in `build_command` would have been refused for the most common name a Makefile has. So `all` is not a recursive goal, a build command that names it keeps the project's own, and the installer writes no alias for it there; `latex-ai-build-all` is refused like every `latex-ai-` name. The same rule keeps a document's target out where its build command names it.
- **A rule written once for two places.** Finding the goals a build command names was written in `schema.py` for the recursion check, and was needed again in the installer; it is now one function in `core.py`, and it brought the installer under the size ceiling.
- **A test that pinned an exact list.** The recursive goals were recorded as a literal set; the new reserved name is added to it, on purpose.
- **A name that is free at `init` may not stay free.** The Makefile is written once; a project that later adds its own rule of the same name as a document gets two rules (GNU Make then keeps the later recipe and says so). `migrating.md` says to delete the generated lines for the name it keeps.
- **A document added later has no target** until its lines are added; `make guide` and `make help` say so, and say `make build DOC=NAME`.

## Hosted verification

All six required checks passed on the pull request ([#10](https://github.com/milanmradonjic/latex-ai-workbench/pull/10): [`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38584637962) in 2m01s with TeX Live 2026; the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38584637942), 59s (3.11) to 1m50s (3.14) each), and again on the merge commit `ffdc597` on `main` ([`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38585239685); the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38585239650)).

## Not verified

- **The hosted unit tests with real TeX.** The Python jobs have no TeX Live, so the tests that follow a hint with real tools skip there; `validate` runs `portability`, not the unit tests.
- **A project that already has its own `all` or document-named rule, upgraded:** the rules are merged by GNU Make (a recipe in both is overridden with a warning); not exercised beyond the generated Makefile's text.
- **Other platforms and versions locally.** macOS (which ships GNU Make 3.81; the targets are plain rules and `.PHONY`), Windows, and Python 3.10 and 3.14.

## Open items

Next in [the plan after 4.4.0](plan-after-4.4.0.md): step 3.6, snapshots (`make snapshot` and `make snapshots`, a shadow Git repository under `~/.snapshots/`), which touches the owner's machine outside the project and so has design questions for the owner. The gates (Git guardrails, changed-file routing, the manual) are still the owner's.
