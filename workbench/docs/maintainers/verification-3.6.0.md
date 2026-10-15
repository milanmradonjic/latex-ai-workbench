# Version 3.6.0 verification

This records the release that adds `validation.ignore` (Phase 3, the safe part of F10 of [the plan after 3.0.2](plan-after-3.0.2.md)),
tested on 2026-10-12 on macOS (Darwin 25.5, Python 3.14.8, GNU Make 4.4.1 from Homebrew with `gnubin` first on `PATH`, TeX Live
with latexmk 4.88). The hosted results follow the local ones.

| Check | Result |
|---|---|
| `tests/test_validation_ignore.py` (now in `tests/test_planner.py`) against 3.5.0 | Failed first: the key was refused as `Unknown validation field: ignore`, and the message of a bad pattern named no key |
| The same after the change | All 11 pass: ignored figure, data and unclassified paths are not routed to the manuscript build and say why; other paths keep their routing; a path the build reads, a declared `manuscript_inputs` path, build and configuration files and policy files are never ignored; `./docs/*` matches like `docs/*`; a pattern that matches nothing changes nothing; bad patterns (a string, `..`, absolute, a newline, empty, a number, `null`) are refused naming `validation.ignore`; other unknown keys are still refused |
| Mutation check of the routing | Dropping the ignored branch fails 6 tests; dropping the `not ignored` guard on the figure and data suffixes fails 5. |
| The generated-files guard | Passes; no stored copy changed (the setting changes routing, not generated files) |
| Previous version (3.5.0, from `main`) installed in a scratch project, then upgraded | Upgrade succeeds, the installed version is 3.6.0, and the Makefile and the workflow are byte-identical to before |
| The installed command on that project | Without the setting, `plan --files docs/fig.png` selects the manuscript checks; with `"ignore": ["docs/**"]` it selects the file checks only and says `ignored by validation.ignore: file checks only`; with `["../x"]` it fails with `Invalid ignore pattern in validation.ignore: '../x'` and a hint |
| `make -C workbench test` | 430 tests, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks) |
| `make -C workbench portability` | 87 of 87 |
| `latex-ai-init audit` in the reference, `make latex-ai-bib-check`, `make check` | The installation is current; both checks pass |

A first run of the suite with the system's GNU Make 3.81 first on `PATH` failed 29 tests: the adopted-build ones, which need
GNU Make 4.3, and the checks of the reference copies and the handbook, which were out of date after the version bump. All
passed with Make 4.4.1 after `make -C workbench handbook` and `upgrade-reference`.

## Hosted verification

All three workflows passed for the pull request head `7680c25fbaacf64365de70b9f6768fb3aa2be420` (once on the pull request event and
once on the branch push) and for the squash-merge commit `f58b960` on `main`.

| Workflow | Result |
|---|---|
| Workbench Python compatibility | Python 3.10–3.14 each ran 430 tests successfully, with 21 expected skips: 20 requiring TeX and one requiring the actual macOS Make 3.81 parser |
| Schema-3 acceptance | Named-document PDF and export selection checks passed |
| LaTeX AI Workbench | The 430-test suite (21 expected skips) and 87/87 compiler portability checks passed |

These ran in the original, private repository, where the history of this project up to 3.7.0 is kept; no hosted timing comparison is claimed.

## Not verified

- **Python 3.10-3.13 on macOS**, **GNU Make 3.81 as `make`**, and **Windows.**
- **Real projects.** The setting was exercised on scratch projects, not on the owner's two-document test project.

## Open items

- **The ignore never narrows what the planner infers**, only what it would treat conservatively. Narrowing routing by build
  records stays out, as the plan says: a `\graphicspath` folder is one input the records would miss.
- **F9, the remaining duplicates**, is the next Phase 3 branch.
