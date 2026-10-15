# Step 3.8 verification

This records step 3.8 of [the plan after 4.4.0](plan-after-4.4.0.md), the last of its steps: the tests regrouped by component. Until now the test files were named for the release or audit that added them
(`test_scope_4_7_0.py`, `test_repairs_3_0_1.py`, `test_blind_repairs.py`), so the tests of one component were spread over many files and one file mixed many components. Now there is a module for each
component, each test class names, in its docstring, the file and release it came from, and [where the tests are](tests-map.md) says where each older file went.
Built on 4.10.0 (`a458277`). Tested on 2026-10-15 on Linux (x86_64, GNU Make 4.3, Git 2.43.0, Python 3.13.16, 3.12.13 and 3.11.17) with TeX Live 2023 from Debian.
**There is no release:** nothing the installer vendors or generates changed, and the tests are not shipped to a project. The workbench stays at 4.10.0. The hosted results are not yet in this record; they are added by the record that follows it.

| Check | Result |
|---|---|
| What moved | 541 tests in 38 test files, into 12 modules: `test_installer.py` (114 tests), `test_snapshots.py` (84), `test_receipts.py` (75), `test_planner.py` (70), `test_guide.py` (49), `test_scope.py` (32), `test_documents.py` (28), `test_diagnostics.py` (24), `test_architecture.py` (22), `test_agent_rules.py` (21), `test_bibliography.py` (12) and `test_processes.py` (10). `test_support.py` and `portability.py` stayed. The plan named four components (receipts, planner, installer, guide); the repository has eight more that those four do not cover (snapshots, the doctor and the issue report, the agent rules, documents, the bibliography, processes, the contracts between components, and what was removed), so there are twelve |
| How | By a script working on the source text, not by hand: it cut each class and method out of its file by line range with its comments, brought the helpers and imports each one uses, and wrote the module. It was a one-off and is not kept in the repository. Classes that were about several components (`ModuleTests` with 45 tests, `WorkbenchTests` with 46, the three `Repairs`, `DocumentTests`, `AuditRepairs` and others) were split by method, by a table that I wrote from the method names (by class where a class is about one component, by method where it is not) and checked against the code: every test is in it, and every name in it is a test |
| Every test unchanged | The script compared, for each of the 541 methods, the syntax tree in the new module with the one in the old file, with only the renames of helpers applied: **541 of 541 identical**. One test is edited on purpose: `test_a12_lifecycle_fixture_ignores_callers_doc_and_makeflags` runs another test by the name of its module, and now names the new one (`test_receipts.DocumentLifecycleTests...`) |
| `make -C workbench test` | 541 tests (the same number as before the move), 2 skipped (the unreadable-folder test, since this runs as root, and the test that needs GNU Make 3.81), OK on 3.13.16, 3.12.13 and 3.11.17 |
| The fixtures' own generators | `python3 -B tests/test_installer.py --generate` and `tests/test_documents.py --generate` (the scripts that refresh the stored copies of the generated files and of the document views) reproduce the stored fixtures byte for byte; their instructions in the module docstrings name the new files |
| Four deliberate breaks of the code, run against the old layout and the new | The same tests fail in both, each time (the name of a failing test is the same, and so is the count): one more weekly snapshot kept (3 fail in each layout), the manual no longer saying that `make all` stops (2), the words of the stale reason gone (3), a `.png` no longer a manuscript input (2). The tests that catch a change are the ones that did before, wherever they sit now |
| `make -C workbench portability` | All 51 scenarios pass (the script was not touched) |
| No production file changed | `git diff` against 4.10.0 holds only tests and records: no runtime module, no template, no reference file, no workflow. So the old-against-new comparison of the installer has nothing to find and was not run; the generated-files guard is among the tests that pass, and `audit-reference` reports the runtime identical |
| The records | 63 citations of an older test file, in 34 records, now say where those tests are: the first citation of each file in each section of a record carries "(now in `tests/test_x.py`)". The records otherwise keep the names they were written with. [`tests-map.md`](tests-map.md) lists both ways: each module with the files it came from, each older file with the modules its tests went to |
| Size | The tests are 9,085 lines (7,704) without `test_support.py`: 549 lines are the origin files' own docstrings, now at the head of each module, 357 are the origin lines of the classes, and the rest is the helpers that two components both need, copied once into each |

## Found on the way

- **A helper shared by a class that was split was copied only as far as it is used.** The first version copied every helper method of a split class into each piece, 1,300 lines more; each piece now keeps the lifecycle hooks and what its tests reach through `self`, transitively.
- **Helpers with one name and several meanings.** `SOURCE` had six definitions across the files, `TEX` four, and `configuration`, `generate`, `REMOVED_WORDS`, `STORED` and others two each. A definition that is identical in two files is written once; a different one keeps its name in the first file and takes its release as a suffix in the later (`SOURCE_4_6_0`).
- **Five classes shared a name** with another class that moved into the same module (`Repairs` of 3.0.2 and 3.0.3, `Init` of 4.4.0, `Commands` and `Registered` of 4.8.0) and carry their release as a suffix. The method names, which the records cite, are untouched.
- **The two scripts that refresh the fixtures** were at the foot of `test_document_views.py` and `test_generated_files_guard.py`, not tests, and the first version dropped them. They moved with their fixtures, with their instructions.
- **`FIXTURES` is defined once,** in `test_installer.py` with the guard, and the documents and scope modules import it from there, as they imported it from the guard before.
- **A mutation comparison went wrong once, in my script and not in the tests:** restoring a file after a mutation that replaced text by nothing prepended the text instead, and the next two comparisons ran on a broken file (every module failed to import in the new layout, every test in the old one). It was found because the two layouts did not fail alike; the files were restored, the script now restores from the saved original, and the two comparisons were rerun.
- **One test names `workbench/tests/test_workbench.py`** as a path in a test project it builds; it is a synthetic path, and the file no longer exists, which changes nothing.

## Judgment calls

Some tests had to be placed by what they assert, and could sit in two modules. Those that a reader might place elsewhere: the lint tests (`lint_baseline_...`, `lint_output_that_cannot_be_read...`, `full_check_builds_before_linting...`) are in `test_receipts.py` with the build; `status_...` and `help_...` tests are in `test_guide.py` though they exercise the installer's project;
`policy_names_orientation_commands...` and `policy_never_names_a_short_form...` are in `test_agent_rules.py` though they read the policy text for the manual's commands; the tests of removed features are in `test_scope.py` even where the feature belonged to the installer;
the comment-stripping tests are in `test_planner.py`, the compiler's-ownership ones in `test_processes.py`. The class docstrings say where each came from, so a test can be moved back or elsewhere without losing its history.

## Not verified

- **That the grouping is the one the owner would draw.** The plan named four components and left the rest to the step; the table that assigns each test is mine.
- **Hosted results.** The pull request is the first run of this version's workflows.
- **macOS and Windows.**

## Open items

The steps of the plan are done. What is open is the owner's: gate G3 (his own reading of the manual, and how project notes grow) and setting up the two launchd agents of 4.8.0.
