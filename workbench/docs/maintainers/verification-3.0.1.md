# Version 3.0.1 verification

This records the repairs made after an independent audit of 3.0.0
(`4270844e77edab538db338ccd24bc0b8c21639d0`) and the guide added in the same release,
tested on 2026-10-11. Local checks
below preceded publication. Hosted results must be verified against the published
commit; this local record does not claim them.

## What the audit confirmed

The 3.0.0 claims held: 305 tests without skips (19 skipped with the TeX tools
hidden), 87 of 87 portability checks, the reference check, doctor and export with
lint enabled, and the three-document schema-3 acceptance scenario. The repairs it
asked for in 3.0 (recorder `PWD` resolution, protected discovery, interrupts,
ownership, collisions, selector rejection, read-only inspection, module
disable and re-enable, installer preservation) all held under real compilers.

## Defects reproduced and repaired

Each was reproduced, with a test that failed first, before it was repaired. The
generated-input and link defects were also reproduced on 2.7.3, and 2.7.3 has no
`\bibliographystyle` handling either, so none was introduced by 3.0.

| Defect | Repair | Regression (`tests/test_repairs_3_0_1.py` (its tests are now in `tests/test_receipts.py`, `tests/test_installer.py`, `tests/test_planner.py` and others (see [where the tests are](tests-map.md)))) |
|---|---|---|
| A Make rule that generates a table or figure the document includes failed the first build and every build after a data change ("Build inputs changed during execution"), then passed on a rerun | A changed input selects the protected compilation; an input that still differs is named | `test_generated_input_is_certified_…`, `test_generator_that_cannot_settle_…`, `test_adopted_make_with_generated_table_and_figure_builds_once` |
| A link inside the project to a file outside it was untracked: the document stayed `current` and the export stale after the target changed | Tracked under the link's own name; planner, file checks and research routing accept it | `test_link_leaving_the_project_is_a_tracked_input` and three more |
| A project-local `.bst` was untracked | `\bibliographystyle` files that exist beside the document are inputs | `test_bibliography_style_beside_the_document_is_an_input`, `test_system_bibliography_style_adds_no_input` |
| Operation locks in a shared temporary directory: a second user got "permission denied" | Per-user lock directory | `test_operation_locks_are_private_to_the_user` |
| CRLF `AGENTS.md` and `.gitignore` were rewritten as LF | Installer writes in the file's own line endings and backs up the original bytes | `test_installer_keeps_the_line_endings_of_authored_files` |
| Stale-state hints lacked `DOC=` | One `document_command` helper | `test_stale_state_hints_name_the_document` |
| `recipe-shell.sh` did not trigger full validation | One `core.RUNTIME_FILES` list, tied to the installer's file set by a test | `test_every_installed_runtime_file_is_a_full_validation_trigger` |
| Configuration errors that did not name the key; raw JSON error for `--build-command`; weak schema hint | `unknown_keys` and `build_command_argument`; the hint names the format document | `test_configuration_errors_name_the_offending_key`, `test_build_command_that_is_not_json_…`, `test_invalid_schema_hint_…` |
| `make plan DOC=x` ignored the selector silently; `status` listed `make check` before "wait for this build"; the integrity line printed twice | Note, ordering, and a quiet certification gate | `test_plan_says_…`, `test_status_puts_the_running_build_…`, `test_a_clean_build_reports_its_integrity_once` |

## Simplification

Bibliography, lint and CI validation existed twice (per document and per project)
and now exist once. One helper resolves dependency names for the recorder, the
static scan and declared inputs; one finds a build command's files; one finds
declared inputs. The planner's runtime-file list is a single constant. About
thirty-five unused imports are gone and two test files now import the module that owns
the function they exercise. No configuration, receipt or installation format changed.

## The guide

The release also adds `make guide` and `make guide-html` for people who cannot place the parts of
the workbench without help (see the release notes). It adds one runtime file, `handbook.py`, and
changes no check, build or receipt. Its tests are in `tests/test_guide_3_0_1.py` (now in `tests/test_guide.py`); each of the
behaviour tests failed before the code existed.

| Property | Test |
|---|---|
| Every `make` command the text names exists in the command table, with only the selectors `DOC`, `TASK`, `TOPIC`, `ISSUE_NOTE`; every installer verb it shows exists | `test_every_command_the_guide_names_exists`, `test_every_installer_command_it_shows_…` |
| The packaged `docs/handbook.md` and `docs/handbook.html` equal what the code renders | `test_the_packaged_copies_equal_what_the_code_renders` |
| The page is one self-contained file (no script, link, image or request outside it), internal links resolve, text from the project is escaped | `test_html_is_one_self_contained_page_…`, `test_html_escapes_what_comes_from_the_project` |
| The text fits 78 columns; terminals that cannot show box drawing get plain characters in the same layout | `test_text_form_fits_a_terminal_…`, `test_a_terminal_that_cannot_show_box_drawing_…` |
| It works with a broken configuration; `guide` changes nothing, `guide-html` adds exactly `.latex-ai/artifacts/guide.html`, which Git ignores | `test_the_guide_works_when_…`, `test_the_guide_reads_and_writes_nothing`, `test_the_html_guide_is_one_ignored_file_…` |
| Commands appear under the names that work (`make latex-ai-build` where the Makefile keeps its own `build`); a project's own `guide` target is kept; `TOPIC` reaches the recipe through GNU Make | `test_how_tos_name_the_commands_…`, `test_a_project_target_named_guide_is_kept`, `test_make_passes_the_topic_…` |
| Help lists each group once and points to the guide; status names changed sources, settings and outputs | `test_help_has_one_heading_…`, `test_status_names_…`, `test_status_says_when_the_outputs_…`, `test_many_changed_sources_…` |
| `handbook.py` is a runtime file the planner treats as a full-validation trigger | `test_handbook_is_a_runtime_file`, `test_every_installed_runtime_file_is_a_full_validation_trigger` |

The page was also rendered with Chromium (light, dark and 390 px wide) and the screenshots were
inspected: the diagrams keep their alignment, the state colours always come with a text label, and
the page prints without its navigation. The how-to commands that run the installer
(`configure --enable`, `configure --document`, `upgrade`) were run with `--dry-run --diff` to confirm
that the flags exist. The wording of the how-tos was checked against the existing guides and the
messages in the code, not by users: whether a first-time reader can orient with it is not yet tested.

## Local evidence

| Check | Result |
|---|---|
| `make -C workbench test` | 351 passed, no skips |
| Same suite with TeX tools hidden | 351 run, 20 skipped (the 19 compiler-dependent tests plus the new adopted-Make scenario), no failures |
| `make -C workbench portability` | 87 of 87 |
| Reference regenerated with `latex-ai-init upgrade ..` | `test_reference_matches_distribution` passes |
| Real latexmk, GNU Make 4.3, BibTeX | generated table and figure through adopted Make; symlinked figure folder; local `.bst`; second Unix user building the same project |
| The repository's own `make check`, `make doctor`, `audit` | pass; the planner selects full validation for `.latex-ai/handbook.py` |
| `make guide`, `make guide-html`, `make help`, `make status` in a notes-only project and in a LaTeX project with a stale document | read; the stale document listed `changed since the verified build: main.tex` |

## Not verified here

Hosted CI for the new commit; TeX Live 2026 (local 2023); macOS and Windows;
editor execution. The repair was written by the same reviewer who audited it:
the independent review the repository's policy asks for before approval is still
to be done.
