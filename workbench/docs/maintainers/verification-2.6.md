# Version 2.6 verification

This release implements the six reproduced architecture findings: deleted
inferred inputs escaping validation, existing Make builds bypassing receipts,
invalid graphs being ignored during execution, stale default PDF export,
installation without Git, and dependency ordering in refresh guidance.

Regression cases were run against version 2.5 first and failed. Fixes were
applied in the distribution; the reference runtime is updated only through its
installer. Manuscript and bibliography source inputs are preserved.

Local implementation is based on repository snapshot
`06c287db4929c79dbc027ed15c91082a514ff2dd`, reviewed on 2026-10-10.

## Validation

- `make -C workbench test`: 210 tests pass on Python 3.12.14 and GNU Make 4.4.1,
  including 19 installed-workflow regressions from this review.
- Reference installer upgrade and `make -C workbench audit-reference`: pass;
  audit reports no changes or conflicts. Installed copies are generated through
  the installer, and the parity regression compares them with the distribution.
- Real reference PDF compilation, bibliography/integrity verification and
  `make latex-ai-pdf-artifact`: pass.
- `make check`: compilation/integrity pass, then lint fails because ChkTeX is
  absent. The reference lint configuration and accepted-warning policy remain
  unchanged.
- `make -C workbench portability`: blocked at preflight because ChkTeX and Biber
  are absent; writes an aggregate JSON report without a traceback. The full
  compiler/backend portability matrix has not passed in this environment.
- Independent user walkthroughs cover fresh core/notebook/numerical projects,
  structured JSON, an explicit experiment/figure/freshness loop, writing
  build/export/stale-export, and adopted Make builds. Those walkthroughs pass.
- Independent code review exercised dependency aliases, no-Git installations,
  JSON decoding, legacy defaults, parallel and incremental Make, recursion,
  concurrent builds, interruption, and read-only commands. Findings were fixed
  and retested before delivery.

Synthetic compiler fixtures isolate Make and receipt behavior; real pdfLaTeX
fixtures also cover the default and adopted builders. Some synthetic projects
disable lint deliberately; the reference does not.

## Hosted verification

Code commit c5f8d44
passed both workflows on 2026-10-10:

- Python compatibility:
  Python 3.10, 3.11, 3.12, 3.13 and 3.14 all pass the distribution/reference suite.
- Full validation:
  210 host tests (four real-compiler tests skipped on the host), all 58 compiler
  portability checks, reference build/lint/integrity, and verified PDF upload pass.
  The portability run exercises pdfLaTeX, LuaLaTeX, XeLaTeX, BibTeX and Biber,
  existing Makefiles, negative integrity cases, and research workflows.

The four host skips reflect unavailable host TeX tools. Local regression testing
ran all 210 tests without skips; hosted portability uses the complete TeX Live
2026 container. This resolves the local lint/portability verification gap without
changing the reference checks.

## Compatibility and preserved inputs

Configuration schemas and provenance record formats remain unchanged. The
normalized configuration, shared graph and latest-record/hash indexes exist
within a command; JSON provenance remains authoritative. Installer adapters and
transactions are extracted into their own modules. No database is introduced.

Adopted single-target Make commands use an order-only preflight barrier, require
GNU Make 4.3+, and share one compiler target under parallel execution. Existing
raw project recipes remain intact. Incomplete attempts cannot establish a
verified receipt; concurrent workbench builds are rejected. Custom indirect
dependencies still need declaration, and an invalidated receipt requires a
regeneration rather than an incremental no-op.

The manuscript, Zotero bibliography export, project configuration and agent
permission guardrails match the retrieved source snapshot. Git publication is
performed separately after these local checks, under the user's explicit
commit/push authorization. Shell access to GitHub remains blocked by the
unavailable configured proxy; source retrieval and publication use the GitHub
connector.
