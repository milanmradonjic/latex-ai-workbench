# Version 4.4.2 verification

This records the release that removes the module table's unused fields (step 3.2 of [the plan after 4.4.0](plan-after-4.4.0.md)).
Tested on 2026-10-14 on Linux (x86_64, GNU Make 4.3, Python 3.13.16 and 3.12.13; no TeX Live, so the 16 tests that need it skipped). The hosted results follow the local ones.

| Check | Result |
|---|---|
| `tests/test_scope_4_4_2.py` against 4.4.1 | 3 of its 5 tests fail: the module table still has `check_group`, `tools` and `requires` (two sub-failures, one per module); `module_names` still accepts a group; `modules` still prints `requires` (two sub-failures). The other two pin what must not change (the tools a project needs, and the schema's refusals of an unknown module and field, with their messages) and pass on both |
| The same after the change | All 5 pass, on 3.13.16 and 3.12.13 |
| Six mutations | Each is caught by the test named for it: a module regaining a `tools` list; `module_names` taking a group again; `module_names` reversing the table order; `required_tools` forgetting `make`; a bibliography field no longer checked; the `modules` report regaining `requires` |
| `make -C workbench test` | 361 tests (356 before, 5 new), 16 skipped (they need TeX), OK on 3.13.16 and on 3.12.13 |
| 4.4.1 and this tree, identical projects, each installed and run by its own release | 104 comparisons, 0 differences. Four projects (one document that builds; core only; two documents and a bibliography; a bibliography without LaTeX), each run through 16 actions of the installed runtime (`modules`, `doctor`, `status` with and without `--json`, `plan --json`, `documents`, `help`, `guide`, `validate --files-only`, `build`, `verify`, `check`, `clean`, and again `status` and `documents`), plus their build receipts and outputs. Six broken configurations (an unknown module; a removed one; an unknown bibliography field; bibliography settings that are not an object; schema version 2; the removed `integrations.ci`), each through `status`, `modules`, `doctor`, `check`, `plan --json` and `init --dry-run`. Exit status, output and receipts were compared. The one allowed difference is the `requires` list in the output of `modules`, removed from the old side before comparing |
| `make -C workbench upgrade-reference`, then `audit-reference` | The refresh changed `workbench.py`, `schema.py`, `core.py` and the record, the three runtime files this release changed; the audit then reports the runtime identical (and `AGENTS.md` as differing from the template, by design) |
| Size | The package is 3,948 lines (3,952 before); the tests are 5,792 lines (5,704) |

## Found on the way

- **Noise was measured, not assumed.** The comparison also ran the old release against itself on two identical projects, and only what differed there was normalised: timestamps and
  identifiers, and in the receipt of a failed build `owner_pid`, `owner_token`, a compiler group's `token` and `started_ns`. Everything else had to match.
- **`plan --json` does not list its documents in a stable order.** In the output of 4.4.1, and so of this release, the keys of `document_reasons` follow the iteration order of a set of document names,
  which changes from run to run with Python's hash seed (the same project printed `paper, notes` once and `notes, paper` the next time). The comparison pins the seed to make runs repeatable. This is not
  fixed here, so as not to widen the step; it is small, and the repair is to build the dictionary in sorted order.
- **The first comparison run crashed** because a result tuple was indexed as if it still held the command; that was the harness, not the code.
- **An import went unused** (`module_names` in `schema.py`) and was removed.

## Not verified

- **Hosted runs.** The pull request's checks and the push to `main` follow in the next record.
- **TeX.** The 16 tests that need it, and `make -C workbench portability`, were not run locally; the hosted `validate` job runs the portability tests in a TeX container.
- **Other platforms and versions locally.** macOS, Windows, and Python 3.10, 3.11 and 3.14 were not run locally; the hosted run covers all five Python versions on Linux.
- **Any reader of the `modules` output that expects `requires`.** None is known in this repository or its documents; an outside script would see the key gone.

## Open items

Next in [the plan after 4.4.0](plan-after-4.4.0.md): step 3.3, locks and interrupted-build recovery, which starts with a design question the owner is asked. The gates (Git guardrails, changed-file routing, the manual) are still the owner's.
