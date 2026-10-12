# Version 2.7.1 verification

Release 2.7.1 repairs defects found by an independent review of 2.7.0 (commit
`486e3ed`). Each was reproduced first in a fresh synthetic project with real
tools, then covered by a regression that failed on 2.7.0
(`tests/test_document_lifecycle.py`, 14 cases).

## Hosted evidence for 2.7.0

Both workflows passed on `486e3ed`: LaTeX AI Workbench run 38072672391 and
Workbench Python compatibility run 38072672435 (Python 3.10–3.14). This settles
the Python matrix that [the 2.7 record](verification-2.7.md) listed as pending.
Step outcomes were read through the GitHub API; the job logs were not reachable
from the review environment, so hosted test counts were not re-read.

## Reproduced defects and repairs

| ID | Failure in 2.7.0 | Repair |
|---|---|---|
| F1 | A paper built by its own Make rule failed every `make check` after schema-3 migration, a Makefile edit or a build outside the workbench ("Build did not rewrite .pdf"); touching sources did not help and cleanup was refused. | Unverified outputs of a custom build are moved aside and the command runs once more; if it cannot recreate them they are restored and the check fails with a hint. |
| F2 | Schema-3 `make validate` skipped the project's own `check` prerequisites, which schema 2 ran. | Validation runs `make check` when the project's Makefile has its own `check` rule. |
| F3 | After a failed build was fixed by restoring committed text, `validate` passed and `status` said "Nothing pending" above a stale document. | `failed` state; status lists the fixing command; validation selects failed documents. |
| F4 | Killing or terminating only the build's Python process left the compiler running while a second build wrote the same outputs. | Compiler runs in its own recorded process group; termination stops it, and a killed owner keeps ownership until the group exits. |
| F5 | `make latex-ai-bib-check` ignored non-default documents' `bibliography_files` and `DOC`. | Checks every document's declarations or the selected one; plans route those files. |
| F6 | Changing the default document (or lint/CI settings) marked unaffected builds stale. | Receipts compare a build identity; the Makefile counts only for Make builds, without the managed block. |

Smaller corrections: the human plan lists selected documents, compiler failures
lead with the first TeX error plus a hint, configure names the document it
changes, and duplicated Make rule extraction in `adapters.py` is shared.

## Validation

Environment: Python 3.13.16 (plus 3.11 and 3.12 for the affected suites),
GNU Make 4.3, TeX Live 2023 (pdfTeX, LuaHBTeX, XeTeX), latexmk, BibTeX,
Biber 2.19 with biblatex 3.19, ChkTeX 1.7.8, Pandoc 3.1.3.

- `make -C workbench test`: all 262 tests pass on Python 3.13.16, without skips
  (248 existing plus 14 lifecycle regressions). The architecture regression for
  incremental custom builds now asserts regeneration instead of a permanent
  failure; its invariant (no receipt revived from a failed attempt) is kept.
  The document, architecture and lifecycle suites (67 tests) also pass on
  Python 3.11 and 3.12.
- The first hosted run of the 2.7.1 branch failed one pre-existing test,
  `test_installation_and_audit_without_git`: it inherited CI's `LATEX_AI_BASE`,
  which GitHub sets to all zeros when a branch is first pushed, so the runtime
  reported an unusable revision instead of missing Git. 2.7.0 fails the same
  way under that value. The test now runs without the variable; the full suite
  passes with `LATEX_AI_BASE` unset, set to a revision and set to all zeros.
- `tests/portability.py`: 87 of 87 command checks pass with ChkTeX and Biber
  present, the full lint/backend matrix the 2.7 record left pending.
- Reference: upgraded through the installer (`make -C workbench upgrade-reference`);
  audit reports no changes or conflicts; `make check`, PDF export and
  bibliography check pass with its lint policy, bibliography and sources unchanged.
- The review's reproduction script passes every case on 2.7.1 and fails each
  on 2.7.0.

Not covered here: TeX Live 2026, macOS and Windows, desktop editor execution,
and hosted execution of the generated schema-3 workflow.
