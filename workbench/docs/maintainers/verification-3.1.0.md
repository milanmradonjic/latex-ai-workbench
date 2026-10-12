# Version 3.1.0 verification

This records the command-registry release (Phase 1 of [the plan after 3.0.2](plan-after-3.0.2.md)), tested on
2026-10-12 on macOS (Darwin 25.5, Python 3.14.8, GNU Make 4.4.1 from Homebrew with `gnubin` first on `PATH`,
TeX Live with latexmk 4.88). The hosted results for the pull request head follow the local ones.

This is a refactor, not a repair, so the safety net is the generated-files guard
(`tests/test_generated_files_guard.py`), which was merged on its own before this change: 13 configurations, 46
stored copies of the Makefile block, editor files and CI workflow.

| Check | Result |
|---|---|
| The guard, after each step (`guide`, then `adapters`, then `runtime`, then the version bump) | Passes; no stored copy was regenerated or edited |
| Old `guide.COMMANDS` (read from `HEAD`) against the commands derived from the registry, by a one-off script | 28 rows identical in every field and in order; the `--document` actions, module requirements, document-view actions, native-JSON actions, standalone actions, recipe `--document` set and help hint sets all equal the six tables they replace |
| Old runtime (`HEAD`) against the new one, installed into identical projects, every action but `build-shell` in 5 argument variants (none, `--json`, `--document paper`, `manuscript`, `nope`) on 5 projects (core, writing, research-paper, markdown, no configuration), comparing exit status, stdout and stderr | 725 invocations: 698 identical. The 27 differences: 12 are `check` / `bib-check --document X` in projects without LaTeX, an internal error in both runtimes that differs only in the path of the kept traceback; 10 are timestamps in `issue` report names; 5 are `status --json` listing the new `.latex-ai/commands.py` as unmodified |
| `tests/test_commands_registry.py` | 7 tests pass: one handler per action and none left over, `dispatch` has no `elif` and never compares `args.action`, the parser offers exactly the registered actions, the flags of each action agree, JSON-native set, every runtime carries `commands.py`. Not run against 3.0.4, where `commands.py` did not exist |
| `make -C workbench test` | 378 passed, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks). The compiler tests and the real-GNU-Make-3.81 test ran. No existing test was edited |
| `make -C workbench portability` | 87 of 87 |
| `latex-ai-init upgrade ..` in the reference | `.latex-ai/workbench.py`, `core.py` and `guide.py` updated, `commands.py` created, `installation.json` refreshed; `audit` reports it current |
| `validate --files-only`, `make latex-ai-bib-check`, `make check` in the reference | Pass |

## Hosted verification

All three pull-request workflows passed for the exact head `e5a2361760ac9394ab419ecc178a1a3a3d3fd5a7` before
integration; the same three also passed on the branch push.

| Workflow | Result |
|---|---|
| Workbench Python compatibility | Python 3.10–3.14 each ran 378 tests successfully, with 21 expected skips: 20 requiring TeX and one requiring the actual macOS Make 3.81 parser |
| Schema-3 acceptance | Named-document PDF and export selection checks passed |
| LaTeX AI Workbench | File/policy checks, the 378-test suite (21 expected skips), 87/87 compiler portability checks, the manuscript check and the PDF upload passed |

The workbench workflow's separate bibliography and project Make-rule steps were skipped by its validation plan;
the local bibliography and `make check` runs are recorded above. These hosted results establish the pull-request
head. No hosted timing comparison is claimed.

The same three workflows then passed on the squash-merge commit `b4d815f` itself on `main`:
Python compatibility (Python 3.10–3.14,
378 tests each, 21 expected skips), Schema-3 acceptance
and LaTeX AI Workbench (378 tests, 87/87
portability checks; the bibliography and project Make-rule steps skipped by its validation plan).

## Not verified

- **Python 3.10–3.13 on macOS.** The local suite used Python 3.14.8; the matrix above ran those versions on Linux.
- **GNU Make 3.81.** The suite and portability ran on GNU Make 4.4.1. The regression that needs the real 3.81 parser ran, but
  the rest of the suite was not run with 3.81 as `make`.
- **Windows.**
- **The differential run's reach.** It excludes `build-shell` (it runs a shell command by design) and does not vary
  `--files`, `--base`, `--changed`, `--expensive-checks`, `--github-output`, `--task NAME` against real tasks, or an
  adopted build in progress (`build-prepare` / `build-finish` with an owner). The existing suite covers those paths.
- **What the guard does not cover.** The text of `make latex-ai-help`, the `.latex-ai/` runtime files, the upgrade merge logic in
  `bootstrap.plan` and the generated `.gitignore`.

## Open items

- **Internal error without LaTeX (pre-existing, unchanged).** In a project without the LaTeX module, `check --document X`
  and `bib-check --document X` stop with `INTERNAL ERROR: No module named 'documents'`, because `dispatch` imports
  `documents` for any `--document` while `documents.py` is installed only with the LaTeX module. Present in 3.0.4 and
  found by the differential run. It needs its own failing-first repair and release. Resolved in [3.2.0](verification-3.2.0.md).
- **`make help` and `bib-check`.** `bib-check` accepts `DOC` but `make help` shows no `DOC=NAME` for it. Kept, because
  showing it changes installed projects' help output. It is now one field of the registry (`usage`).
- **Command names left in `documents.py`.** The recursion guard for a project's own build command names `check`,
  `document-check`, `validate` and the `latex-ai-` forms in two sets. They are policy, not command attributes, and were
  left for Phase 3 (F9).
