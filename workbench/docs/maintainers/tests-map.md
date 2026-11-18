# Where the tests are

Step 3.8 of [the plan after 4.4.0](plan-after-4.4.0.md) regrouped the tests by the component each one is about. Until then the files were named for the release or audit that added them
(`test_scope_4_7_0.py`, `test_repairs_3_0_1.py`, `test_blind_repairs.py`), so a test of the validation plan could be in any of eleven files. Now there is a module for each component, and each test class says,
in its docstring, which file and release it came from. No test was renamed, and only one was edited (it runs another test by its module's name, and now names the new module): the method names are what the records cite, and the same 541 tests run. The records still cite the old files, as they were
when the records were written; the first citation of each in a section of a record now says where those tests are.

`test_support.py` (the shared fixtures) and `portability.py` (the real-TeX scenarios) are not tests of a component and did not move.

## By component

| Module | Tests | What it tests | Came from |
|---|---|---|---|
| `tests/test_agent_rules.py` | 21 | The agents' rule files and policy: what prompts, what is refused, the pull-request rule | 5 older files |
| `tests/test_architecture.py` | 22 | Contracts between components: the command registry, import layering, one table for each fact, the repository's own workflows | 5 older files |
| `tests/test_bibliography.py` | 12 | The bibliography checks: parsing, duplicate keys, the export and the backend logs | 6 older files |
| `tests/test_diagnostics.py` | 24 | The doctor, the issue report and the labelling of internal faults | 5 older files |
| `tests/test_documents.py` | 28 | Named documents and their views: defaults, selectors, notes, `make all` and a target for each | 5 older files |
| `tests/test_guide.py` | 49 | What the tool says to a person: the manual, help, status, the reasons and the hints | 6 older files |
| `tests/test_installer.py` | 114 | The installer and the files it writes: init, diff and runtime, the configuration and its errors, the generated Makefile, editor and policy files | 20 older files |
| `tests/test_planner.py` | 70 | The validation plan: which checks a change needs, change discovery, the lightweight file checks and what routes to the manuscript build | 10 older files |
| `tests/test_processes.py` | 10 | The processes a build starts: locks, ownership of a build, interruption and the compiler's cleanup | 4 older files |
| `tests/test_receipts.py` | 75 | Build receipts and a document's state: what a build records, freshness, the output and its safety, the recorder, lint and the full check | 13 older files |
| `tests/test_scope.py` | 32 | What the workbench no longer does: each removal of a release, pinned so that it stays removed | 6 older files |
| `tests/test_snapshots.py` | 84 | Snapshots: the three stores, retention, exact bytes, isolation, the timers | 3 older files |

## By older file

| Older file | Tests | Now in |
|---|---|---|
| `test_architecture.py` | 11 | `tests/test_architecture.py` |
| `test_audit3_repairs.py` | 17 | `tests/test_receipts.py` (8), `tests/test_processes.py` (4), `tests/test_planner.py` (3), `tests/test_agent_rules.py` (1), `tests/test_installer.py` (1) |
| `test_blind_repairs.py` | 10 | `tests/test_receipts.py` (7), `tests/test_bibliography.py` (1), `tests/test_diagnostics.py` (1), `tests/test_processes.py` (1) |
| `test_commands_registry.py` | 7 | `tests/test_architecture.py` |
| `test_document_lifecycle.py` | 13 | `tests/test_receipts.py` (7), `tests/test_planner.py` (3), `tests/test_processes.py` (2), `tests/test_bibliography.py` (1) |
| `test_document_views.py` | 10 | `tests/test_documents.py` |
| `test_documents.py` | 25 | `tests/test_planner.py` (8), `tests/test_receipts.py` (8), `tests/test_documents.py` (7), `tests/test_bibliography.py` (1), `tests/test_installer.py` (1) |
| `test_generated_files_guard.py` | 2 | `tests/test_installer.py` |
| `test_guide_3_0_1.py` | 14 | `tests/test_guide.py` |
| `test_modules.py` | 45 | `tests/test_guide.py` (14), `tests/test_installer.py` (14), `tests/test_diagnostics.py` (8), `tests/test_receipts.py` (3), `tests/test_agent_rules.py` (2), `tests/test_planner.py` (2), `tests/test_architecture.py` (1), `tests/test_bibliography.py` (1) |
| `test_one_table_each.py` | 15 | `tests/test_planner.py` (10), `tests/test_receipts.py` (4), `tests/test_installer.py` (1) |
| `test_repairs_3_0_1.py` | 17 | `tests/test_receipts.py` (9), `tests/test_installer.py` (3), `tests/test_planner.py` (3), `tests/test_guide.py` (2) |
| `test_repairs_3_0_2.py` | 9 | `tests/test_processes.py` (3), `tests/test_receipts.py` (3), `tests/test_diagnostics.py` (1), `tests/test_installer.py` (1), `tests/test_planner.py` (1) |
| `test_repairs_3_0_3.py` | 1 | `tests/test_installer.py` |
| `test_repairs_3_0_4.py` | 4 | `tests/test_agent_rules.py` |
| `test_repairs_3_2_0.py` | 3 | `tests/test_documents.py` |
| `test_repairs_3_4_1.py` | 10 | `tests/test_installer.py` |
| `test_repairs_3_5_0.py` | 2 | `tests/test_architecture.py` |
| `test_review_fixes.py` | 5 | `tests/test_installer.py` (2), `tests/test_receipts.py` (2), `tests/test_architecture.py` (1) |
| `test_scope_4_0_0.py` | 8 | `tests/test_scope.py` |
| `test_scope_4_10_0.py` | 12 | `tests/test_agent_rules.py` |
| `test_scope_4_1_0.py` | 5 | `tests/test_scope.py` |
| `test_scope_4_2_0.py` | 4 | `tests/test_scope.py` (3), `tests/test_guide.py` (1) |
| `test_scope_4_3_0.py` | 25 | `tests/test_installer.py` (18), `tests/test_scope.py` (7) |
| `test_scope_4_4_0.py` | 19 | `tests/test_installer.py` (11), `tests/test_scope.py` (6), `tests/test_documents.py` (2) |
| `test_scope_4_4_1.py` | 5 | `tests/test_installer.py` |
| `test_scope_4_4_2.py` | 5 | `tests/test_installer.py` |
| `test_scope_4_5_0.py` | 12 | `tests/test_installer.py` (7), `tests/test_scope.py` (3), `tests/test_receipts.py` (2) |
| `test_scope_4_5_1.py` | 9 | `tests/test_installer.py` |
| `test_scope_4_6_0.py` | 16 | `tests/test_installer.py` (7), `tests/test_documents.py` (6), `tests/test_guide.py` (3) |
| `test_scope_4_7_0.py` | 52 | `tests/test_snapshots.py` |
| `test_scope_4_8_0.py` | 31 | `tests/test_snapshots.py` |
| `test_scope_4_8_1.py` | 27 | `tests/test_receipts.py` (17), `tests/test_planner.py` (7), `tests/test_bibliography.py` (1), `tests/test_installer.py` (1), `tests/test_snapshots.py` (1) |
| `test_scope_4_9_0.py` | 15 | `tests/test_diagnostics.py` (13), `tests/test_installer.py` (2) |
| `test_scope_4_9_1.py` | 15 | `tests/test_guide.py` |
| `test_simplification.py` | 4 | `tests/test_receipts.py` |
| `test_validation_ignore.py` | 11 | `tests/test_planner.py` |
| `test_workbench.py` | 46 | `tests/test_planner.py` (22), `tests/test_installer.py` (13), `tests/test_bibliography.py` (7), `tests/test_agent_rules.py` (2), `tests/test_diagnostics.py` (1), `tests/test_receipts.py` (1) |

## Classes that took a new name

Five classes shared a name with another class that moved into the same module, so the later one carries its release as a suffix:

- `test_repairs_3_0_2.py` `Repairs` is `Repairs_3_0_2` in `tests/test_receipts.py`
- `test_repairs_3_0_3.py` `Repairs` is `Repairs_3_0_3` in `tests/test_installer.py`
- `test_scope_4_4_0.py` `Init` is `Init_4_4_0` in `tests/test_installer.py`
- `test_scope_4_8_0.py` `Commands` is `Commands_4_8_0` in `tests/test_snapshots.py`
- `test_scope_4_8_0.py` `Registered` is `Registered_4_8_0` in `tests/test_snapshots.py`

## Finding a test

By name: `grep -rn "def test_the_name" workbench/tests`. By origin: each class docstring ends with `Origin: tests/<older file>[, workbench X.Y.Z]`, so `grep -rn "Origin: tests/test_scope_4_7_0.py" workbench/tests` lists the classes of that file.
The helpers a class needs (its fixtures, constants, base classes) were moved with it; a helper that two older files defined differently is in the module once for each, the later one with its release as a suffix (`SOURCE_4_6_0`).
