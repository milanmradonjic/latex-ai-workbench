# Version 3.2.0 verification

This records the release that breaks the `core` / `documents` import cycle (Phase 2, step 1 of
[the plan after 3.0.2](plan-after-3.0.2.md)), tested on 2026-10-12 on macOS (Darwin 25.5, Python 3.14.8, GNU Make
4.4.1 from Homebrew with `gnubin` first on `PATH`, TeX Live with latexmk 4.88). The hosted results for the pull
request head and for the merge commit follow the local ones.

The pull request has four commits, one concern each: the move into `schema.py`, the layering tests, the
`--document` message, and the release record. The comparison below was repeated for the first and the third.

| Check | Result |
|---|---|
| Static import graph of the runtime modules, function-local imports included, before and after the move | Before: one cyclic group of seven modules (`commands`, `core`, `documents`, `guide`, `latex`, `make_graph`, `output_transaction`), kept apart only by function-local imports. After: no cycle; `core` imports only `processes`, `schema` only `core` and `make_graph` |
| The three layering tests against the code before the move (`16f4004`) | 2 of 3 fail: the import cycle, and `core` importing `documents`. The third (each module imports on its own) passes on both, which is why the graph is read from the source |
| The same tests after the move | All 3 pass |
| `tests/test_repairs_3_2_0.py` against the code before the move | Fails: `check --document` and `bib-check --document` in a core project stop with exit 70 (`INTERNAL ERROR: No module named 'documents'`), and the disabled-LaTeX case gives no hint |
| The same tests after the move, before the `--document` commit | 4 checks fail: no hint on `check` and `bib-check`, in a project created without LaTeX and in one that disabled it. The move alone had already ended the internal error, because `schema.py` is installed in every project |
| The same tests after the `--document` commit | Pass |
| The generated-files guard after each commit | Passes; no stored copy was regenerated or edited |
| Old runtime against new, installed into identical projects, every action but `build-shell`, five argument variants, five projects (core, writing, research-paper, markdown, no configuration), comparing exit status, stdout and stderr: commit 1 against `16f4004` | 725 invocations, 698 identical. The 27 differences: 12 are `check` / `bib-check --document X` in projects without LaTeX (internal error, exit 70, before; `Module is disabled: latex`, exit 1, after), 10 are timestamps in `issue` report names, 5 are `status --json` listing the new `.latex-ai/schema.py` |
| The same comparison, commit 3 against commit 2 | 725 invocations, 703 identical. The 22 differences: the same 12 `--document` cases, which now differ only by the added `Hint:` line, and the 10 `issue` timestamps |
| `make -C workbench test` | 384 passed, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks). The compiler tests and the real-GNU-Make-3.81 test ran. The existing tests only had their module qualifier changed (`core.validate_config` to `schema.validate_config`, 96 references); no assertion was edited |
| `make -C workbench portability` | 87 of 87 |
| `latex-ai-init upgrade ..` in the reference | `.latex-ai/` refreshed in each commit that changed a runtime file; `audit` reports the installation current |
| `validate --files-only`, `make latex-ai-bib-check`, `make check` in the reference | Pass |

## Hosted verification

All three pull-request workflows passed for the exact head `17d38312d9a15108cc5b1826cf7345ab860c54f1` before
integration; the same three also passed on the branch push.

| Workflow | Result |
|---|---|
| Workbench Python compatibility | Python 3.10–3.14 each ran 384 tests successfully, with 21 expected skips: 20 requiring TeX and one requiring the actual macOS Make 3.81 parser |
| Schema-3 acceptance | Named-document PDF and export selection checks passed |
| LaTeX AI Workbench | File/policy checks, the 384-test suite (21 expected skips), 87/87 compiler portability checks, the manuscript check and the PDF upload passed |

The workbench workflow's separate bibliography and project Make-rule steps were skipped by its validation plan; the
local bibliography and `make check` runs are recorded above. The same three workflows then passed on the squash-merge
commit `49942a4` itself on `main`:
Python compatibility (Python 3.10–3.14, 384
tests each, 21 expected skips), Schema-3 acceptance
and LaTeX AI Workbench (384 tests, 87/87
portability checks). No hosted timing comparison is claimed.

## Not verified

- **Python 3.10–3.13 on macOS.** The local suite used Python 3.14.8; the matrix above ran those versions on Linux.
- **GNU Make 3.81.** The suite and portability ran on GNU Make 4.4.1. The regression that needs the real 3.81 parser ran,
  but the rest of the suite was not run with 3.81 as `make`.
- **Windows.**
- **The comparison's reach.** It excludes `build-shell` (it runs a shell command by design) and does not vary `--files`,
  `--base`, `--changed`, `--expensive-checks`, `--github-output`, `--task NAME` against real tasks, or an adopted build in
  progress. The existing suite covers those paths.
- **What the guard does not cover.** The text of `make latex-ai-help`, the `.latex-ai/` runtime files, the upgrade merge
  logic in `bootstrap.plan` and the generated `.gitignore`.
- **A name clash.** The module is called `schema`, as is a popular PyPI package. The runtime and the tests put their own
  directory first on `sys.path`, so theirs wins; no environment with that package installed was tried.

## Open items

- **`make help` and `bib-check`.** `bib-check` accepts `DOC` but `make help` shows no `DOC=NAME` for it. Kept, because
  showing it changes installed projects' help output.
- **Command names still spelled twice.** The recursion guard for a project's own build command (two sets in
  `schema.py`, formerly `documents.py`) and the Make targets the template defines (`bootstrap.py`). Phase 3, F9.
- **Phase 2, step 2** (a typed `DocumentView`; `document_settings` no longer passing an already-resolved view
  through) is a separate release.
