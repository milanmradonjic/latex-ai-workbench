# Version 4.2.0 verification

This records the release that replaces the long generated handbook by a short manual (the third step of [the minimal scope](minimal-scope.md)),
tested on 2026-10-13 on macOS (Darwin 25.5, Python 3.14.8, GNU Make 4.4.1 from Homebrew with `gnubin` first on `PATH`, TeX Live with latexmk 4.88
and Biber 2.21). The hosted results of the pull request follow once it has run.

| Check | Result |
|---|---|
| `tests/test_scope_4_2_0.py` (its tests are now in `tests/test_scope.py` and `tests/test_guide.py`) against 4.1.0 | Fails: the handbook, its copies and the `guide-html` command are all still there, the guide still takes a topic, and a project's Makefile still exports `TOPIC` |
| The same after the change | All 4 pass. Four mutations (`guide-html` back, `handbook.py` a runtime file again, the manual past 60 lines, `TOPIC` exported again) are each caught |
| The rewritten guide tests | 14 tests of orientation pass: the manual shows the project's documents and states, names the commands that work in the project (`make latex-ai-build` where the Makefile keeps its own `build`), says so when names differ, names no command that does not exist, drops the document commands in a project without LaTeX, and reads and writes nothing |
| `make -C workbench test` | 363 tests, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks) |
| `make -C workbench portability` | 74 of 74 |
| The generated-files guard | Regenerated on purpose and read: in every fixture's Makefile exactly the `guide-html` targets go, `export DOC TOPIC` becomes `export DOC`, and the `guide` recipe loses `--topic "$$TOPIC"`; the editor files are byte-identical |
| 4.1.0 and this tree installed into identical projects, every surviving action, five argument variants, `core`, `writing` and a project without configuration | 300 invocations, 21 differences: the six `issue` report names (timestamps), six `guide` (the new manual), six `help` (one line: "a short manual" for "pictures, how-tos, glossary") and three `status --json` (the installed-files list, which no longer has the handbook) |
| A 4.1.0 `writing` project upgraded by this tree | A dry run writes nothing and says `.latex-ai/handbook.py` is retained. The upgrade succeeds and changes five runtime files and the Makefile block (nine lines, the ones above); the editor files are byte-identical. `.latex-ai/handbook.py` stays in the project, unused. `make guide` prints the new manual (44 lines), `make guide-html` no longer exists, and a second upgrade says "Already current" |
| `latex-ai-init audit` in the reference, `make latex-ai-bib-check`, `make check` | Current; both checks pass |

## Found on the way

- **A stale file stays.** The installer never deletes, so a project installed before keeps its `.latex-ai/handbook.py` and a note, "Previously managed
  ... retained", on every upgrade. In this repository's own reference the file and its manifest entry were removed by hand. The upgrade machinery goes in
  one of the next steps, so no code was added to delete files.
- **The manual is code, not a project file.** It grows with the tool. The alternative, a file the project owns and edits, was not built; it is the
  natural next step if the manual should grow with a single project.

## Not verified

- **Hosted runs.** The pull request is the first run of this version's workflows.
- **A reader.** Nobody but the author has read the manual; its 44 lines are a first draft of what the owner needs, to be corrected by using it.
- **Python 3.10 to 3.13**, **GNU Make 3.81 as `make`**, **Windows.**

## Open items

Next in [the order of the work](minimal-scope.md#order-of-the-work): the upgrade machinery; then, in the build core, the Make adoption layer, the locks and
the per-document targets.
