# Workbench 6.1.0 verification

This release repairs findings of an audit of 6.0.0 against the
[Level 2 plan](plan-level-2-validation.md) and the user documentation. The owner
chose the repairs: paths named in the configuration stay active, and `baseline`
stops being a historical directory name. The pilot project had already moved
its `revision/baseline/` material into `archive/`. See the
[release notes](releases.md#610--audit-repairs-archives-configured-paths-and-validation-without-git).

## What the audit found in 6.0.0

The audit used a synthetic two-root project, with a custom builder, a configured
lint baseline, editor integration and a `check` recipe that does extra work. It
ran 35 routing cases and confirmed that every row of the plan's acceptance table
behaves as written. It also exercised `validate` and failure and interrupt
recovery, export, and an upgrade from 5.0.0. The repaired gaps were:

- **Without Git, the file checks read no file.** `changed_files` fell back to
  `git ls-files`, which also fails outside a repository, so the list was empty.
  Broken JSON and a broken Markdown link passed `validate --files-only`. Inside a
  repository with an invalid base the same file failed, because `ls-files` worked
  there.
- **An archive directory hid configured controls.** A lint baseline configured at
  `lint/baseline/chktex.json` was routed "historical: file checks only". The same
  applied to roots, bibliography files and build scripts in such directories.
- **The docs overstated receipt reuse.** `execute_build` always runs the
  compiler. latexmk skips unchanged work, but a custom `build_command` reran on
  every check while `status` said `current`.
- **Messages:** `file_checks` read a `full` key that no plan has carried since
  5.0.0. The `DOC` note claimed full validation at the files level.

## Evidence

- **Failing first.** With the new tests and the 6.0.0 runtime,
  `tests/test_level2.py` failed seven times. The failures were the `baseline`
  path now expected Full, four configured paths inside an archive, the no-Git
  file list and the `DOC` wording. After the repair, all 11 tests passed.
- **Full unit suite:** 499 tests, with 494 passed, 4 platform skips and 1
  environmental failure. The failure was `test_explicit_lualatex_command`: the
  Linux container had `lualatex` but not `luaotfload`/`fontspec`, and it fails
  identically on 6.0.0. The skips are GNU Make 3.81, Biber, XeLaTeX and the
  root-readable folder case.
- **Compiler portability:** 48 of 48 scenarios passed, with TeX Live 2023
  (Debian).
- **Reference:** the runtime was refreshed by `make -C workbench
  upgrade-reference`, and `audit-reference` reports identical runtime files. The
  only other difference is the deliberate local sections of `AGENTS.md`, whose
  archive paragraph was updated to match the template. `make check`, `make
  validate` and `git diff --check` passed.
- **No-Git project:** a copy without `.git` that has a broken Markdown link now
  fails `validate --files-only` with "Broken local Markdown link".
- Hosted Python-matrix and compiler results are recorded by the pull request's
  checks.

No research project was used as a test fixture.
