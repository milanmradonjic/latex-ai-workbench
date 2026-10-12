# Version 3.5.0 verification

This records the release that pins the GitHub actions of the generated workflows to commits (Phase 3, finding F14 of the
architecture audit), tested on 2026-10-12 on macOS (Darwin 25.5, Python 3.14.8, GNU Make 4.4.1 from Homebrew with `gnubin`
first on `PATH`, TeX Live with latexmk 4.88). Hosted CI must be checked on the pull request that carries it.

| Check | Result |
|---|---|
| Each pinned commit against GitHub | For `actions/checkout` v7 (`3d3c42e…`, 2026-07-17), `actions/upload-artifact` v7 (`cf430e0…`, 2026-10-07) and `xu-cheng/texlive-action` v3 (`22c0432…`, 2026-04-02), and `actions/setup-python` v6 (`ece7cb0…`, 2026-06-23): the commit exists in that action's repository, and the repository's tag list gives this commit for the tag |
| The same commits against what CI used | The "Download action repository" lines of the hosted runs of 3.4.1 record the same four commits, so pinning leaves what runs unchanged |
| `tests/test_repairs_3_5_0.py` against 3.4.0 | All 5 fail: 13 generated workflows contain unpinned actions, no pin is in the expected form, `pin_actions` does not exist, this repository's three workflows are unpinned, and there is no Dependabot file |
| The same tests after the change | All 5 pass |
| The generated-files guard | Failed first on all 13 stored workflows; after regenerating, only `uses:` lines differ (29 of texlive-action, 13 of checkout, 11 of upload-artifact; each replaced by its pinned form). No other line of any stored copy changed |
| This repository's workflows | Every `uses:` of the three is pinned. `latex.yml` came from `upgrade-reference`, `schema3-acceptance.yml` from `tests/schema3_workflow.py --generate`, `workbench-python.yml` by hand; none of them has a changed line that is not a `uses:` line |
| The previous version (3.4.1) installed with CI in a scratch project, then upgraded | `.github/workflows/latex-ai.yml` changes in its `uses:` lines only (5 actions, 10 diff lines, none else) |
| The same, with the workflow edited by hand first | The upgrade stops: `CONFLICT: .github/workflows/latex-ai.yml: Locally modified managed file: this file is installed whole and is not meant to be edited`; nothing changed |
| `make -C workbench test` | 410 passed, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks) |
| `make -C workbench portability` | 87 of 87 |
| `make latex-ai-bib-check`, `make check`, `audit` in the reference | Pass; the import graph still has no cycle |

## Not verified

- **Hosted CI with the pinned actions.** Whether GitHub accepts these exact pinned references in this repository's workflows is
  proved only by the runs of the pull request that carries this release. The pins equal the commits GitHub resolved before.
- **Dependabot.** The configuration was written but not run: whether it opens its first pull request, and whether it reads the
  tag comment as intended, is seen only after merging.
- **A generated workflow in a real project.** The upgrade was run on a scratch project; no hosted run of a project's own
  workflow was observed.
- **Python 3.10–3.13 on macOS.** The local suite used Python 3.14.8; hosted CI runs those versions on Linux.
- **GNU Make 3.81.** The suite and portability ran on GNU Make 4.4.1.
- **Windows.**

## Open items

- **Pins go stale in installed projects** until a new workbench release carries newer ones. A faster route (a Dependabot file
  generated for each project, or a command that refreshes the pins) is not built; it would be a separate decision.
- **Phase 3 continues** with `validation.ignore` (F10, the safe part) and the remaining duplicates (F9); the command-name sets
  noted in the plan belong to F9.
