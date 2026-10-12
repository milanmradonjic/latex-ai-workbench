# Version 2.7 verification

The named-document implementation follows
[the TeX notes plan](tex-notes-plan.md). It was implemented against the 2.6.0
reference and prepared for publication on 2026-10-10. The evidence below records
local verification; hosted results are recorded separately after publication.

## Validation

- `make -C workbench test`: all 248 tests pass on Python 3.12.14 and GNU Make
  4.4.1, without skips. This includes 38 named-document regression cases.
- Reference installer upgrade and audit pass with no pending changes or
  conflicts. Installed runtimes are regenerated through the installer and
  compared with distribution files by the parity regression.
- Reference `make latex-ai-build`, runtime verification and verified PDF export
  pass. `make check` builds and verifies, then correctly fails for missing
  ChkTeX; its lint policy and baseline are unchanged.
- Twenty-four real compiler workflow steps pass across pdfLaTeX, LuaLaTeX and
  XeLaTeX: fresh notebook setup, adding a note, parallel full checks, independent
  exports, note-only validation, repeated checks and audit. These synthetic
  fixtures explicitly disable lint to isolate compiler/receipt behavior.
- Independent review confirms receipt/export isolation, deleted/shared/aliased
  dependency selection, migration through symlinks, live ownership exclusion,
  read-only inspection, aggregate selected failures and adopted Make behavior.
  Review findings were fixed and retested. Malformed receipt shapes are covered
  by a defensive planning regression and independent probes.
  Additional adopted targets already reached by an existing full-check goal
  or parent are rejected, preventing duplicate and overlapping compilers.
  Saved disabled definitions do not require operational Make ownership.
- Blind user validation confirms notebook setup, named note registration,
  compilation, export, status and mixed-example dependency selection. It found
  an omitted export setting in the example; the example now explicitly enables
  local PDF export while keeping CI/editor disabled.
  The corrected example passes seven direct installed-workflow steps: setup,
  full check, export, stale-export refusal, targeted recheck, re-export and
  current status. Paper/notebook receipts remain unchanged during the note
  recheck. Lint is disabled only in this synthetic compiler fixture.
- Changed-file JSON/Python syntax, conflict-marker, policy-structure and local
  Markdown-link checks pass. Schema-3 generated workflow YAML parses with
  unique step IDs and three distinct artifact uploads. Editor tasks are checked
  through installed-workflow regressions.

The complete portability runner now has 87 command checks, including named
notebooks across pdfLaTeX, LuaLaTeX and XeLaTeX, independent exports, selective
fragment checks and the mixed TeX/Markdown example. Local preflight requires
ChkTeX and Biber, which are absent; no tools or passing results are simulated.
The complete lint/backend matrix remains pending in a full TeX environment.
Python 3.10–3.14 compatibility, generated named-document hosted CI and desktop
editor execution are also pending; only the local versions above were exercised.

## Compatibility and boundaries

Schemas 1 and 2 retain their layouts, default commands and explicit migration
contract. Schema-3 migration preserves resolved legacy output paths and lint
baselines. Native named documents use separate compiler, receipt and export
paths. Project-wide ownership serializes builds, including adopted Make phases.

The adopted default shares the original Make graph under parallel checks.
Additional documents run sequentially. Multiple adopted graphs with shared or
unresolved ownership require an explicit project adapter. No generalized Make
parser, notebook execution or cross-document reference engine is introduced.

Reference configuration, scientific sources, bibliography exports and agent
permission files are preserved. Runtime and policy guidance are regenerated
through the installer; Git safety rules are unchanged. Generated CI and editor
files are covered locally, but remote execution and desktop behavior need
separate verification.
