# Version 3.0.2 verification

This records the repairs and optimizations made from the
[architecture audit of 3.0.1](architecture-audit-3.0.1.md), tested on 2026-10-12. These are
local results. Hosted CI must be checked against the published commit, and this record
does not claim it.

## Findings repaired

Each finding was reproduced before the change. Each regression test in
`tests/test_repairs_3_0_2.py` failed against 3.0.1: all 14 failed, 13 by assertion and 1
by a missing attribute.

| Finding | Reproduction | Repair | Regression |
|---|---|---|---|
| F1: per-user locks did not exclude a second user; the research task lock ran unlocked for every user after the first | Two Unix users held the `build` lock of one project at the same time. The second user entered `research.task_lock` while the lock directory belonged to the first, mode `0700` | One project lock under `.latex-ai/artifacts/locks/`, shared like the project directory, opened for writing where possible (needed on NFS); it fails closed. Fault records are per user | `test_operation_lock_excludes_a_process_with_another_temporary_directory`, `test_research_task_lock_is_the_project_lock`, `test_a_lock_that_cannot_be_created_fails_closed`, `test_fault_records_are_kept_per_user` |
| F2: an adopted-Make adapter stopped every goal on a Make without `.EXTRA_PREREQS` | `make pdf .FEATURES=` and `make latex-ai-help .FEATURES=` stopped at the `$(error)`. GNU Make 4.3 with `.FEATURES` emptied reports what 3.81 reports | The `$(error)` sits inside the build-goal condition. The installer adds a NOTE and `doctor` fails, both naming GNU Make 4.3+ | `test_make_without_extra_prereqs_still_runs_project_targets_and_help`, `test_installer_and_doctor_name_the_make_requirement` |
| F3: Latin-1 TeX sources | `init` and `plan` failed with `'utf-8' codec can't decode byte 0xe9` | `core.read_tex` decodes UTF-8 and falls back to Latin-1 for scans and file checks | `test_latin1_sources_install_plan_and_pass_file_checks` |
| F4: the first build compiled twice | `\includegraphics{fig}` with `fig.png`: 2 compilations | Discovered inputs whose change time precedes the build are certified by their hash. Inputs hashed at the start that differ, and inputs written during the build, still take the protected compilation. The static scan tracks graphicx extension candidates and local `.sty`/`.cls` files | `test_discovered_input_that_predates_the_build_needs_no_second_compilation`, `test_graphics_without_extension_track_every_file_graphicx_could_choose` |
| Found while repairing F4: adding `fig.pdf` beside a `fig.png` that `\includegraphics{fig}` used left the document `current` | Status `current` after `fig.pdf` was created | Same as F4: existing extension candidates are inputs | `test_graphics_without_extension_…` |
| F5: each input hashed about 4 times per `document-check` | A 50 MB figure was read 4 times | A per-invocation digest cache keyed by device, inode, size, mtime and ctime. Files changed within 2 s are hashed again each time | `test_unchanged_inputs_are_hashed_once_per_invocation` |
| F6: a 536 KB manifest holding every file's text twice | The reference's `.latex-ai/installation.json` | Manifest schema 2 keeps digests for files installed whole; version 1 is read and upgraded | `test_manifest_keeps_digests_for_files_installed_whole`, `test_upgrade_reads_a_version_1_manifest` |
| F12: no PID-reuse guard without `/proc` | `processes.token` returned `None` | Fallback to `ps -o lstart=` | `test_process_identity_without_proc_still_detects_a_reused_pid` |
| F14: CI steps that could never be selected | The acceptance workflow's portability step (`validation.package` is null there) | Package steps are omitted when package routing is off; the workflow is regenerated | `test_workflow_omits_package_steps_when_package_routing_is_off` |

Four existing tests changed because their premise changed on purpose:

- `test_operation_locks_are_private_to_the_user` asserted the per-user directory that F1
  replaces, so it was removed.
- Two tests needed the new lock directory accounted for:
  - The installer-lock test now expects exactly the holder's own lock file.
  - The refused-cleanup snapshot ignores the empty lock files.
- One Markdown test creates `.latex-ai/artifacts` with `exist_ok`.

## Measurements

| Case | 3.0.1 | 3.0.2 |
|---|---|---|
| Compilations in a first build with `\includegraphics{fig}` (test-fixture compiler) | 2 | 1 |
| Reads of a 50 MB figure input during one `document-check` | 4 | 1 |
| `.latex-ai/installation.json` of this reference | 536,040 bytes | 19,239 bytes |

## Local evidence

| Check | Result |
|---|---|
| `make -C workbench test`, Python 3.13.16 | 364 passed, 20 skipped (the TeX-dependent tests; no TeX Live in this environment) |
| The same suite on Python 3.10.20 | 364 passed, 20 skipped |
| Two Unix users in a group-shared project (`2775`), `umask 002` and `022` | The second user is refused by the `build` lock and by the task lock, with the specific "Another run" message. Lock files are group-writable |
| Reference upgraded from 3.0.1 with `latex-ai-init upgrade ..` (manifest 1 → 2) | Applied without conflicts; `audit` reports it current; `test_reference_matches_distribution` passes |
| The reference's own checks | `validate --files-only` (file and policy checks), `make latex-ai-bib-check` and `make status` pass. `make validate` selects the unit tests (pass, above), portability and the manuscript build, which need TeX; `doctor` reports only the missing TeX tools |

## Not verified here

- Real TeX compilation and `make portability` (87 checks): there is no TeX Live here, so
  these must run where it is installed before release.
- macOS, including the `ps` fallback and a real GNU Make 3.81.
- NFS locking.
- Hosted CI for the new commit.

At the time of the original record, the repairs had been written by the same reviewer
who wrote the audit, and their independent review was pending. The macOS review below
was performed in a separate Codex session, independently of that author.

## macOS verification and independent review

Phase 0 ran on 2026-10-12, starting from clean `main` at `f602c97`, on branch
`plan/phase-0-macos-verification`. The reviewed repair was `e8b55cf`, against the
architecture audit. No refactor preceded this verification.

Environment: Apple silicon, Darwin 25.5.0, local case-insensitive APFS,
Python 3.14.8, Homebrew GNU Make 4.4.1 and Pandoc 3.12.1, stock
`/usr/bin/make` 3.81, and TeX Live 2026 with latexmk 4.88. GNU Make 4.4.1's
`/opt/homebrew/opt/make/libexec/gnubin` was first on PATH for the modern-Make checks;
stock Make remained available for the older parser checks.

| Check against 3.0.2 | Result |
|---|---|
| `make -C workbench test`, with normal macOS process access | 364 tests ran: 363 passed, one Linux-only zombie-state test skipped; no TeX skips |
| `make -C workbench portability` | 87 of 87 passed with real TeX |
| First native latexmk build using `\includegraphics{fig}` and a real PNG | One latexmk invocation, zero "Inputs were written during the build" messages; adding `fig.pdf` made status stale |
| Actual GNU Make 3.81 after adopting `["make", "pdf"]` | **Failed:** `make pdf` stopped at `latex-ai-build-prepare: private override SHELL` with "multiple target patterns"; the installer had printed its expected NOTE |

The first suite invocation inside the Codex sandbox failed only the `ps` birth-token
test because executing `ps` was denied ("operation not permitted"). The isolated test
and the entire suite passed with normal macOS process access. The sandboxed verdict
is not used as platform verification.

### Review findings

- **F2 remains broken on an actual old parser.** Moving the `.EXTRA_PREREQS` error
  under the build-goal condition did not hide the two unsupported `private` modifiers.
  The `.FEATURES=` simulation on modern Make cannot detect this. A new regression
  reproduced the parse error before the [3.0.3 repair](verification-3.0.3.md).
- **F4 ctime certification.** Writes, rename replacement and a timestamp-preserving
  copy on local APFS are classified as written during the build; changed inputs already
  hashed at preparation always take the protected compilation. This supports the local
  behavior, under a coherent wall clock. The two-second margin does not prove correctness
  under arbitrary clock rollback, remote clock skew or stale network attributes. NFS
  certification remains unverified.
- **F5 digest cache.** Identity includes device, inode, size, mtime and ctime, and
  recent entries are not cached. A same-size write with restored mtime invalidated
  the cached digest on APFS. Filesystems with stale or unreliable metadata remain
  outside this verification.
- **F6 manifest schema 2.** Managed blocks and JSON merges retain the previous text;
  extendable whole files retain upstream text; non-extendable whole files use digests
  and refuse local modifications rather than merge them. No merge baseline needed by
  those strategies was removed. A whole-file conflict diff uses the current release's
  text, as announced, rather than reconstructing the original installed file.
- **Read-only locks.** Local macOS `flock` excludes a contender using a read-only
  descriptor and permits it after the holder exits. Failure to acquire does not enter
  the protected operation. This does not establish NFS behavior or a real second-user
  permission/ACL setup.
- **F12 residual precision limit (open).** Native `ps -o lstart=` provides a nonempty
  birth token and rejects a different start time. Its one-second precision cannot
  distinguish the same PID reused within that second. Actual rapid PID reuse was not
  forced; exact identity at finer resolution remains an open platform limitation.

The remaining killed-owner, lock-alias, installer-casing and ctime scenarios passed
against 3.0.3, whose only runtime change is the version; see its verification record.
Hosted CI, NFS, real cross-user macOS locking and other Python versions were not
verified in this Mac session.
