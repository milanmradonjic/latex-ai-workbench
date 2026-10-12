# Version 3.3.0 verification

This records the release that makes resolved document views immutable, typed mappings (Phase 2, step 2, first half of
[the plan after 3.0.2](plan-after-3.0.2.md)), tested on 2026-10-12 on macOS (Darwin 25.5, Python 3.14.8, GNU Make 4.4.1
from Homebrew with `gnubin` first on `PATH`, TeX Live with latexmk 4.88). The hosted results for the pull request head and
for the merge commit follow the local ones.

| Check | Result |
|---|---|
| `tests/fixtures/views.json`, generated from the 3.2.0 code before any change | 14 configurations (the 13 of the generated-files guard and one that sets every key a document can carry), 13 documents, 10 keys in a view (`bibliography`, `build_command`, `ci`, `engine`, `inputs`, `lint`, `name`, `output_dir`, `root`, `validation`) |
| `tests/test_document_views.py` against 3.2.0 | The type tests fail (there is no `DocumentView`, `SharedSettings`, `to_json()` or read-only behaviour); the test that compares every view with `views.json` passes, as it must before and after |
| The same tests after the change | All 8 pass: every view equals the stored JSON; the build record's canonical text equals `json.dumps(view, sort_keys=True)`; a view equals the dict a build record was loaded into; every change is refused at every depth; the typed properties; `to_json()` and deep copies are plain mutable data; a project without LaTeX gets `SharedSettings`; `document_settings` still passes a view through |
| Existing tests | Two mutated a view (`test_per_document_defaults_are_independent`, `test_unchanged_inputs_are_hashed_once_per_invocation`) and now take a copy with `to_json()`. Nothing else in the workbench mutated a view |
| Old runtime (`main`, 3.2.0) against new, installed into identical projects, every action but `build-shell`, five argument variants, five projects, comparing exit status, stdout and stderr | 725 invocations, 715 identical. The 10 differences are the timestamps in `issue` report names |
| The generated-files guard | Passes; no stored copy was regenerated or edited |
| `make -C workbench test` | 392 passed, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks). The compiler tests and the real-GNU-Make-3.81 test ran |
| `make -C workbench portability` | 87 of 87 |
| `latex-ai-init upgrade ..` in the reference | `.latex-ai/schema.py` and `core.py` refreshed; `audit` reports the installation current |
| `make latex-ai-bib-check`, `make check` in the reference | Pass |

## Hosted verification

All three pull-request workflows passed for the exact head `201b30a3f739dbe38542ce42bb984e4e923ec9d4` before integration; the same three also passed on the
branch push.

| Workflow | Result |
|---|---|
| Workbench Python compatibility | Python 3.10–3.14 each ran 392 tests successfully, with 21 expected skips: 20 requiring TeX and one requiring the actual macOS Make 3.81 parser |
| Schema-3 acceptance | Named-document PDF and export selection checks passed |
| LaTeX AI Workbench | The 392-test suite (21 expected skips) and 87/87 compiler portability checks passed |

The same three workflows then passed on the squash-merge commit `6c36ff8` itself on `main`:
Python compatibility (Python 3.10–3.14, 392 tests each), Schema-3 acceptance
and LaTeX AI Workbench (392 tests, 87/87 portability checks). No hosted timing comparison is claimed.

## Not verified

- **Python 3.10–3.13 on macOS.** The local suite used Python 3.14.8; the matrix above ran those versions on Linux.
- **A build running across an upgrade.** The shape a build record stores is pinned, and a view equals the dict it was
  loaded into, but no build was actually interrupted by an upgrade and finished by the new runtime.
- **Speed.** Each `.view` access now builds frozen containers instead of one plain dict. Not measured.
- **GNU Make 3.81.** The suite and portability ran on GNU Make 4.4.1. The regression that needs the real 3.81 parser ran,
  but the rest of the suite was not run with 3.81 as `make`.
- **Windows.**
- **The comparison's reach.** It excludes `build-shell` and does not vary `--files`, `--base`, `--changed`,
  `--expensive-checks`, `--github-output`, `--task NAME` against real tasks, or an adopted build in progress. The
  existing suite covers those paths.

## Open items

- **The dual mode remains.** `document_settings` still passes an already-resolved view through, and `latex.py` still
  calls it at 16 entry points. The next release removes both, and converts the project-configuration callers of the
  bibliography checks explicitly, as Phase 2 step 2 intends.
- **Function-local imports** that no longer dodge a cycle (the list under Phase 2 in the plan) are for that release too.
