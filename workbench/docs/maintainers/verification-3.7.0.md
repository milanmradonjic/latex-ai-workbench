# Version 3.7.0 verification

This records the release that collapses the duplicates of finding F9 (Phase 3 of [the plan after 3.0.2](plan-after-3.0.2.md)),
tested on 2026-10-12 on macOS (Darwin 25.5, Python 3.14.8, GNU Make 4.4.1 from Homebrew with `gnubin` first on `PATH`, TeX Live
with latexmk 4.88). The hosted results follow the local ones.

| Check | Result |
|---|---|
| `tests/test_one_table_each.py` (its tests are now in `tests/test_planner.py`, `tests/test_receipts.py` and `tests/test_installer.py`) against 3.6.0 | 16 of its 18 tests failed or errored: the constants did not exist (`GENERATED_TREES`, `RECURSIVE_GOALS`, `RESERVED_PREFIX`, the suffix tables, `broken_markdown_link`), and the static checks found the copies (five modules listing the folders, `{"build", "lint", "check"}` in `bootstrap.py`, the goals typed twice in `schema.py`). The two that passed pin what must not change: every file name routes as before, and a project's own `build`, `lint` or `paper` target is not refused |
| The same after the change | All 18 pass, among them: the six goals equal the six names 3.6.0 spelled out; each is refused as a `build_command`, and so is any `latex-ai-` name; a project's own `build`, `lint`, `paper` are not; every file name routes as 3.6.0 routed it (41 names, recorded from the old code before the change); four tests of the Markdown link check, covering fences, anchors, queries, quoted and angle-bracket targets, links that leave the project |
| Mutation check of the new tests | Ten mutations, each caught: a goal dropped from the registry-derived set; the prefix test dropped; the old Markdown-walk, task-path and Markdown-pattern lists put back (2, 5 and 4 tests fail); `out` dropped from the installer's extras; the data suffixes left out of the manuscript table; fences not removed, and links outside the project checked, in the link check; the literal `{"build", "lint", "check"}` put back |
| The generated-files guard | Passes with no stored copy regenerated: the Makefile, workflow and editor files are byte-identical |
| Old runtime (`main`, 3.6.0) against new, installed into identical projects, every action, five argument variants, five projects, comparing exit status, stdout and stderr | 725 invocations, 715 identical; the 10 differences are the timestamps in `issue` report names |
| The same for `plan --files` and `validate --files-only --files` over 61 file names (every suffix the planner knows, the skipped folders, the Markdown link cases), in three projects, with the generated Makefile, workflow and editor settings compared | 366 invocations per version, 0 differences, generated files identical |
| 3.6.0 installed in a scratch project, then upgraded | Succeeds; the installed version is 3.7.0; the Makefile and the workflow are byte-identical to before |
| `make -C workbench test` | 448 tests, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks) |
| `make -C workbench portability` | 87 of 87 |
| `latex-ai-init audit` in the reference, `make latex-ai-bib-check`, `make check` | The installation is current; both checks pass |
| The import graph | `schema` now imports `commands`, which imports only `core`; `tests/test_architecture.py` (now in `tests/test_architecture.py`) allows that and no more, and there is still no cycle |

## Where behaviour changes, and was not exercised on real projects

These follow from using one list and are listed in the release notes. None showed in the comparisons above, because no scratch
project had a folder of those names where it matters: the Markdown walk skips `site-packages` and `dist-packages`; `markdown.files`
patterns and task paths are refused when they start in a folder that is now on the list; the installer's walk skips
`__pycache__`, `site-packages` and `dist-packages`. Each is covered by a test in `test_one_table_each.py` (its tests are now in `tests/test_planner.py`, `tests/test_receipts.py` and `tests/test_installer.py`).

## Hosted verification

All three workflows passed for the pull request head `a34b9b22dea6e64711f858e7fc0bfe2d1eccf864`, once on the pull request event and
once on the branch push, in the original, private repository.

| Workflow | Result |
|---|---|
| Workbench Python compatibility | Python 3.10–3.14 each ran 448 tests successfully, with 21 expected skips: 20 requiring TeX and one requiring the actual macOS Make 3.81 parser |
| Schema-3 acceptance | Named-document PDF and export selection checks passed |
| LaTeX AI Workbench | The 448-test suite (21 expected skips) and 87/87 compiler portability checks passed |

That pull request was not merged there: this repository starts from the same tree, with the changes recorded in the README of these
records. No run of this repository's own workflows is claimed here.

## Not verified

- **Python 3.10-3.13 on macOS**, **GNU Make 3.81 as `make`**, and **Windows.**
- **Real projects with such folders.** The owner's two-document test project was not upgraded or run with this version.

## Open items

- **Reserved module paths** (`.vscode`, `.github`, `.codex`, `.claude`, and the names of project files) in `schema.py` are a
  different fact from the generated trees and stay one list there.
- **The check of the template's targets** reads the template as the Makefile reader sees it; a template that defined its targets
  through `include` or computed names would need the reader's unresolved-syntax handling, which the installer does not use there.
- **Phase 3 is complete** with this release and the two before it; Phase 4 waits for the owner's decision.
