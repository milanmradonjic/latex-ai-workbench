# Version 4.3.0 verification

This records the release that takes the upgrade machinery out of the installer (the fourth step of [the minimal scope](minimal-scope.md)),
tested on 2026-10-13 on macOS (Darwin 25.5, Python 3.14.8, GNU Make 4.4.1 from Homebrew with `gnubin` first on `PATH`, TeX Live with latexmk 4.88
and Biber 2.21). The hosted results of the pull request follow once it has run.

| Check | Result |
|---|---|
| `tests/test_scope_4_3_0.py` against 4.2.0 | 22 of its 25 tests fail: the four removed modes are accepted, `installation.py` exists, `disabled_modules` is accepted, `init` runs twice on one project, there is no `diff` or `runtime`, and the documents describe `upgrade`, `audit` and `configure`. The 3 that pass pin what stays: `init` uses a project's own configuration, refuses an option that would override it, and `runtime` in a folder that is not a project is a clean error (vacuously, on 4.2.0, where the mode does not exist) |
| The same after the change | All 25 pass. Eleven mutations are each caught by the test named for them: `runtime` ignoring local edits, `runtime` keeping no backup, the record written first, `init` accepting an installed project, `diff` always exiting 0, `diff` missing a deleted runtime file, `diff` and `runtime` ignoring the options only `init` reads, records of 4.2 unread, a record that keeps more than digests, `disabled_modules` accepted, and a `runtime` dry run that writes |
| `make -C workbench test` | 365 tests, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks): 363 before, 29 removed or renamed, 31 added or renamed (25 of them the scope tests) |
| `make -C workbench portability` | 68 of 68 (74 before: the six `configure` runs that registered a second document became edits of `.latex-ai.json`; `audit` and `upgrade` became `diff` and `runtime`) |
| 4.2.0 and this tree installed into identical projects, every action, five argument variants, `core`, `writing` and a project without configuration | 300 invocations, 13 differences, all intended: the hint of a disabled module (it named a removed command), the word "record" for "manifest" (`status`, `issue`), the list of installed files in `status --json` (runtime files only, not every managed file), and the `issue` report names (timestamps) |
| The same two installs compared as file trees | In both scenarios every file that is not under `.latex-ai/` is byte-identical. Under `.latex-ai/`, 5 runtime files and the record differ (the ones this release changed), and the old tree's `artifacts/locks/installation.lock` is gone |
| A 4.2.0 `writing` project taken to 4.3.0 | `init` refuses it and writes nothing; `diff` exits 1, names the 5 runtime files and `AGENTS.md`, writes nothing; `runtime --dry-run` writes nothing; `runtime` changes exactly those 5 files and the record, and backs the old files up; the old record's digests are honoured (no conflict). `make doctor`, `check`, `status`, `guide` pass. A second `runtime` says it is already current and `diff` exits 0 |
| The same with a runtime file edited | `runtime` refuses with a `CONFLICT` line and writes nothing; `--force` replaces it and the backup holds the edit |
| A 4.2.0 project that had run `configure --disable bibliography` | `runtime` refuses by name (`disabled_modules is gone`) with a hint, and writes nothing. After the hint is followed, `runtime` and `make check` pass |
| `latex-ai-init diff` in the reference, `make latex-ai-bib-check`, `make check` | Current; both checks pass |

## Found on the way

- **`diff` and `runtime` ignored the options that mean nothing to them** (`--json`, `--profile`, `--engine` and the others). Found by reading the first
  version of the new `main` against the principle that a silent skip is the dangerous kind of defect ([lessons learned](lessons-learned.md)); they are now refused, with a test per option.
- **No recovery mode was needed for an interrupted `runtime`.** The record is written last, so a refresh that dies after two of five files leaves the old record, the files not yet
  replaced still match it, and running `runtime` again does what is left (tried with a simulated power cut on a 4.2.0 project, and pinned by a test whose mutation, the record written
  first, fails it). An interrupted `init` is finished by running it again, but without `--profile`, `--modules` or `--editor`: the configuration it already wrote is used as it is, and the
  error that refuses those options now says so (tried with a power cut on the sixth file; a test pins it).
- **Setup of 85 tests used `init` after writing a configuration**, which the old installer treated as "upgrade". The new rule (a project's own `.latex-ai.json` is
  used as it is; an installed project is refused) keeps those tests meaningful and is the rule the installer says in its error.
- **A stale file stays.** `runtime` never deletes, so runtime files of earlier releases that no longer exist remain in a project, unused. The reference had none.

## Not verified

- **Hosted runs.** The pull request is the first run of this version's workflows.
- **An agent following the recipe.** `docs/upgrading.md` was written and read, and the commands in it were run by hand on a 4.2.0 project, but no agent has updated a
  project with it yet. The first real update is the test.
- **Python 3.10 to 3.13**, **GNU Make 3.81 as `make`**, **Windows.**

## Open items

Next in [the order of the work](minimal-scope.md#order-of-the-work): in the build core, the Make adoption layer, the locks and the per-document targets;
then snapshots and the update recipe's snapshot step.
