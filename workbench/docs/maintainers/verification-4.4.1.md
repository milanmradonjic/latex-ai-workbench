# Version 4.4.1 verification

This records the release that separates refreshing a project's runtime from generating its other files (step 3.1 of [the plan after 4.4.0](plan-after-4.4.0.md)).
Tested on 2026-10-14 on Linux (x86_64, GNU Make 4.3, Python 3.13.16 and 3.12.13; no TeX Live, so the 16 tests that need it skipped). The hosted results follow the local ones.

| Check | Result |
|---|---|
| `tests/test_scope_4_4_1.py` (now in `tests/test_installer.py`) against 4.4.0 | 4 of its 5 tests fail: `runtime_files` does not exist (three sub-failures, one per configuration); `diff` renders twice (`2 != 1`); `runtime` reaches into the template rendering (internal error 70 where 0 is expected); the schema says "Workbench 3". The fifth pins what must not change (a missing and a changed runtime file are each reported once, with the count) and passes on both |
| The same after the change | All 5 pass, on 3.13.16 and 3.12.13 |
| Five mutations | Each is caught by the test named for it: `runtime_files` dropping its last file; `diff` rendering a second time; `runtime` rendering every project file again; `diff` no longer reporting a missing runtime file; the schema saying Workbench 3 again. The first run missed the first one (see below) |
| `make -C workbench test` | 356 tests (351 before, 5 new), 16 skipped (they need TeX), OK on 3.13.16 and on 3.12.13 |
| 4.4.0 and this tree, identical projects, installer actions | 210 comparisons, 0 differences. Five projects, each installed by its own release: one document with the editor files; core only; editor off; two documents and a bibliography; no configuration, so that `init` detects it. For each: `init` (dry run, dry run with the diff, JSON, real), then `diff`, `diff --diff`, `runtime --dry-run`, `runtime`, and `runtime --force` after a runtime file was deleted, another edited, the record deleted, the Makefile deleted or edited, the configuration deleted or broken. Exit status, output (paths, versions and backup stamps normalised) and the resulting file trees were compared; runtime files are compared by name, since `core.py` and `schema.py` differ on purpose |
| `make -C workbench upgrade-reference`, then `audit-reference` | The refresh, which ran the new `runtime`, changed `core.py`, `schema.py` and the record only; the audit then reports the runtime files identical (it also says `AGENTS.md` differs from the template, as it does by design: the reference's policy has sections the template has not) |
| Size | The package is 3,952 lines (3,948 before), `bootstrap.py` 561 (557); the tests are 5,704 lines (5,615). Nothing shrinks: the step removes duplicated work and a coupling |

## Found on the way

- **A test that could not fail.** The first version of the test for `runtime_files` compared it with the runtime part of `desired_files`. Since `desired_files` now builds on
  `runtime_files`, a bug in the one is in the other, and the mutation that dropped a file passed unnoticed. The test now compares with the package's own files for the modules
  in use, derived from `core.runtime_sources`, and the mutation is caught. It was the mutation check that showed it.
- **A real difference, intended.** `runtime` used to render the project's policy, Makefile and editor files first, so a project whose configuration made that fail could not
  refresh its runtime. It can now; the unit test shows it with `desired_files` made to raise. No project of the five exercises it.
- **The comparison's first runs were wrong, not the code.** The "no configuration" project had two root files, so `init` refused identically on both sides and the later steps
  had nothing to compare; and a first fixture for the new tests lacked its root file. Both were fixed before the numbers above.
- **The header of `releases.md`** still called Workbench 3 the supported development line; it is corrected in this release.

## Hosted verification

All six required checks passed on the pull request ([`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38536879296) in 3m25s; the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38536879028), 1m13s to 1m35s each), and again on the
merge commit `975663c` on `main` ([`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38537952987); the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38537953045)). The `validate` job runs the portability tests and the reference
manuscript's check in a TeX container, which the local runs could not.

## Not verified

- **TeX.** The 16 tests that need it, and `make -C workbench portability`, were not run locally; the hosted `validate` job ran the portability tests in a TeX container and passed.
- **Other platforms and versions locally.** macOS, Windows, and Python 3.10, 3.11 and 3.14 were not run locally; the hosted run covers all five Python versions on Linux.
- **A project whose files cannot be rendered**, which `runtime` now survives, beyond the unit test that makes `desired_files` raise.

## Open items

Next in [the plan after 4.4.0](plan-after-4.4.0.md): step 3.2, the dormant module machinery. The gates (Git guardrails, changed-file routing, the manual) are still the owner's.
