# Version 3.4.0 verification

This records the release in which the backends take resolved views and never resolve them (Phase 2, step 2, second
half of [the plan after 3.0.2](plan-after-3.0.2.md)), tested on 2026-10-12 on macOS (Darwin 25.5, Python 3.14.8, GNU Make
4.4.1 from Homebrew with `gnubin` first on `PATH`, TeX Live with latexmk 4.88). The hosted results for the pull request head and
for the merge commit follow the local ones.

| Check | Result |
|---|---|
| The build record's JSON shape, pinned by `tests/fixtures/views.json` since 3.3.0 | Passes unchanged; the file was not regenerated |
| The generated-files guard | Passes; no stored copy was regenerated or edited |
| The suite with `document_settings` refusing a resolved view and `latex.py` no longer resolving | Failed first, as intended: 57 failures and errors, in two groups. One was production code: `build_shell` read the in-progress build's `configuration` back from JSON as a plain dict and passed it on, which the old pass-through had hidden (`AttributeError: 'dict' object has no attribute 'name'` inside real adopted-Make builds). It now rebuilds a `DocumentView` where it reads the JSON. The rest were tests that passed a project configuration to a backend function and relied on the silent resolution; about 30 lines now resolve it first, with `schema.document_settings(config)` |
| `tests/test_document_views.py` (now in `tests/test_documents.py`) and `tests/test_architecture.py` (now in `tests/test_architecture.py`), new tests | `latex.py` never contains `document_settings`; `bibliography_check` and `declared_bibs` refuse a project configuration (`AttributeError`) instead of checking nothing, and work with the resolved settings; function-local imports name only modules that not every project has (the test found three redundant `import make_graph` lines in `guide.py`, now removed); `document_settings` refuses a view |
| Static import graph, nested imports included | No cycle; the only function-local imports left are of optional modules (`research`, `documents`, `latex`, `markdown`, `output_transaction`) |
| Old runtime (`main`, 3.3.0) against new, installed into identical projects, every action but `build-shell`, five argument variants, five projects, comparing exit status, stdout and stderr | 725 invocations, 715 identical. The 10 differences are the timestamps in `issue` report names |
| `make -C workbench test` | 395 passed, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks). The compiler tests and the real-GNU-Make-3.81 test ran |
| `make -C workbench portability` | 87 of 87 |
| `latex-ai-init upgrade ..` in the reference | `.latex-ai/` refreshed in each commit that changed a runtime file; `audit` reports the installation current |
| `make latex-ai-bib-check`, `make check` in the reference | Pass |

## Hosted verification

All three pull-request workflows passed for the exact head `a7400f4130df84b92b2d1f2e8247b4489958f78f` before integration; the same three also passed on the
branch push.

| Workflow | Result |
|---|---|
| Workbench Python compatibility | Python 3.10–3.14 each ran 395 tests successfully, with 21 expected skips: 20 requiring TeX and one requiring the actual macOS Make 3.81 parser |
| Schema-3 acceptance | Named-document PDF and export selection checks passed |
| LaTeX AI Workbench | The 395-test suite (21 expected skips) and 87/87 compiler portability checks passed |

The same three workflows then passed on the squash-merge commit `4446af8` itself on `main`:
Python compatibility (Python 3.10–3.14, 395 tests each), Schema-3 acceptance
and LaTeX AI Workbench (395 tests, 87/87 portability checks). No hosted timing comparison is claimed.

## Not verified

- **Python 3.10–3.13 on macOS.** The local suite used Python 3.14.8; the matrix above ran those versions on Linux.
- **`build-shell` under the comparison.** It was excluded because it runs a shell command by design; the adopted-Make tests of
  the suite exercise it through real Make recipes, and they are what caught the production bug above.
- **A build running across an upgrade.** The shape of the stored record is pinned and unchanged, but no build was
  actually interrupted by an upgrade and finished by the new runtime.
- **GNU Make 3.81.** The suite and portability ran on GNU Make 4.4.1. The regression that needs the real 3.81 parser ran,
  but the rest of the suite was not run with 3.81 as `make`.
- **Windows.**
- **The comparison's reach.** It does not vary `--files`, `--base`, `--changed`, `--expensive-checks`,
  `--github-output`, `--task NAME` against real tasks, or an adopted build in progress. The existing suite covers those paths.

## Open items

- **`make help` and `bib-check`.** `bib-check` accepts `DOC` but `make help` shows no `DOC=NAME` for it. Kept, because
  showing it changes installed projects' help output.
- **Command names still spelled twice.** The recursion guard for a project's own build command (two sets in `schema.py`)
  and the Make targets the template defines (`bootstrap.py`). Phase 3, F9.
- **Phase 2 is complete** with this release: the cycle is gone (3.2.0), views are typed and immutable (3.3.0), and the
  backends take them as they are (3.4.0).
