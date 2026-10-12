# Version 3.0 simplification verification

This records the 3.0 development tree based on
`52519e6b704c4ea82c4cedd231d91ef05acda45f` (2.7.3), tested on
2026-10-11. Local checks below preceded publication. Hosted results must be
verified against the published commit; this local record does not claim them.

## Completed design changes

Configuration schema 3 is the sole supported project model, including no-TeX
profiles. Initialization creates it directly. Schema-1/2 readers, migration
flags, v0 adoption metadata, legacy backend views, and the singular manuscript
receipt/export path have been removed. A single paper is a named document too.

Document resolution produces one settings shape used by compilation, lint,
receipts, dependency inspection, and PDF export. Current receipts use receipt
schema 3 and store build identity directly rather than a historical project
configuration. Old receipts do not certify current outputs. Installation
manifests, move journals, task definitions, lint baselines, and scientific run
records retain their own independent format versions.

Make, editor, and CI generation use the named-document path. Editor tasks are
generated directly; the unused task template is removed. The public mixed-notes
example supplies the new generated `Schema-3 acceptance` workflow. It forces
full selection, installs from the distribution, checks three roots, exports
their PDFs, and verifies fragment/shared-resource selection.

Safe installation merges and transactions, disabled-module settings, source
preservation, scientific execution boundaries, output recovery, process birth
tokens, and GNU Make recipe supervision remain. Compiler ownership has one
`compiler_groups` representation. No new research module or portability shim
was introduced. Public architecture, configuration, and troubleshooting guides
describe the reduced model.

## Defects found during implementation review

Each runtime defect below was reproduced before its regression passed.

| Failure | Structural repair | Evidence |
|---|---|---|
| A root written as `./main.tex` lost durable recorder dependencies after the `.fls` was removed. | One validated receipt-input reader compares canonical root identities and is shared by input-role and dependency inspection. | Real pdfLaTeX macro-computed input: current after recorder removal, stale after editing the hidden input. Independent symlink-root probe also passes. |
| Malformed stored receipt paths could break inspection. | The same reader rejects malformed digests, noncanonical names, and escaping paths before using stored inputs. | Documents report stale and dependency inspection completes for an escaping receipt path. |
| `--document` on project commands discarded enabled modules. | One explicit document-action set rejects selectors on plan/validate/modules/doctor/documents before resolution. | All five unsupported uses fail clearly. |
| CI omitted selected research/Markdown checks when full validation was split into individual documents. | Shared action planning retains those preflight actions for split checks; local execution consumes the same list once. A project-wide `make check` subsumes them. | Fail-first action regressions; a genuine three-document fixture with a missing notes index fails both local validation and the generated CI preflight. No-TeX and project-owned check paths are independently verified. |

The independent reviewer also found a retained test writing the old recorder
location. It now uses the named build directory and a `.txt` input, with
false-before/true-after assertions, so conservative extension routing cannot
make it pass accidentally. Other retained fixtures use current configurations,
receipt identity, and named artifact paths. Pure compatibility-only tests were
removed; their retained functional purposes were ported.

## Expanded blind review and current-version repairs

Ten independent cheap testers used public guides/examples and temporary projects,
without implementation, package tests, maintainer records, or previous findings.
Their reports and parent reproductions are retained in
`/workspace/latex-ai-blind-round-10/`. The repository was unchanged by that round.
The new regressions are `tests/test_blind_repairs.py`; twelve tests pass without
skips. Fail-first logs are retained in `/workspace/latex-ai-blind-fixes/`.

| Finding | Current structural repair | Verification |
|---|---|---|
| Relative recorder inputs used the root directory instead of recorded `PWD`, causing a first custom-build failure and stale PDF certification after changing an input. | One recorder reader resolves canonical contained paths from `PWD` and feeds dependency inspection, input roles, receipts, and plans. Relative recorder inputs without context fail clearly. | Real compiler matrix covers native/custom commands, nested roots, spaces, computed inputs, recorder removal, stale verification/export refusal, and successful recovery. Symlink/working-directory recorder probes pass. |
| Native first-build discovery could hash a newly observed input after TeX consumed older bytes, then certify/export the old PDF. | Every backend uses one compiler execution path and one protected discovery rebuild. The complete observed input set must remain unchanged through that pass. | Independent actual in-flight mutation reproduced false success before repair; after repair the PDF contains current text. A second protected-pass mutation fails. This defect and the recorder-path defect both reproduce on published 2.7.3 and predate this simplification. |
| Existing receipts created without these discovery guarantees could still certify incomplete dependencies after recorder removal. | Receipt format 3 is the only accepted format. Earlier receipts and their stored input lists are rejected; rebuild establishes the current guarantee. No conversion reader or backport was added. | Fail-first rejection probe for a format-2 receipt; installed reference rebuilt and writes format 3. |
| Adding documents hid the effect of shared lint defaults. | Installer human/JSON summaries expose resolved document settings; configure explains defaults and CLI help scopes `--no-lint`. | Configure preview and JSON probes distinguish inherited enabled lint from a per-document override. The inheritance behavior is intentional, not a corrected semantic defect. |
| Missing-root errors lacked recovery guidance; quickstart promised hints on every error. | Common setup failure includes a hint; the guide accurately limits the general promise. | Missing-root configure fails with a source/path recovery hint and no installation writes. |
| Using a notebook's installed runtime from another project's cwd gave an internal optional-backend import error. | One dispatcher boundary validates runtime/project identity before imports or issue writes. | Wrong context fails as an ordinary error with `--project` guidance; correct cwd, explicit own project, canonical symlink aliases, and malformed-config orientation work. |
| Successful bibliography checks hid their document/file scope. | Human and structured scope comes from the exact checker results for the selected documents. | Default checks name both documents; explicit document JSON names only that document's bibliography. Shared/export bibliography handling remains unchanged. |
| Repeated run archives were cumbersome to inspect. | Read-only history uses existing records and the shared command registry; no new persistent index, retention policy, or pruning. | Actual success/failure archives remain visible after disabling task modules. History JSON/Make execution changes no files. |
| Hard-killed owners left safe but confusing live-child ownership. | Status and build guards share one live-process interpretation; status exposes owner PID and compiler groups. POSIX recovery is documented. | Independent SIGTERM restores displaced outputs byte-for-byte; SIGKILL retains live-child ownership. Recovery after stopping only fixture processes succeeds and retires journals. |

The additional independent implementation review was read-only and used real
latexmk/pdfLaTeX for compilation and interruption probes. It found and verified
the native discovery defect above, then rechecked the repaired transitions.
Temporary compiler fixtures explicitly disabled lint; the reference policy did not.
The proposed conditional-Make warning was based only on a dry run and remains
an unproven suggestion, not a defect. No blanket warning or parser was added.

Earlier releases are retired from support. Historical release notes and
verification records are retained; no Git tags, branches, releases, or history
were deleted. Only current code is repaired.

## Validation evidence

Local environment: Linux x86-64, Python 3.12.14, GNU Make 4.4.1, latexmk 4.86,
TeX Live 2025/dev Debian pdfLaTeX/LuaLaTeX/XeLaTeX, BibTeX 0.99d, Pandoc 3.1.11.1.
ChkTeX and Biber are absent. Network/package installation and Docker access
were unavailable; extra-permission attempts were cancelled and were not retried.

| Check | Outcome |
|---|---|
| `make -C workbench test` | 305 passed, no skips, 109.654 s, after the final runtime repairs. |
| Affected checks | Twelve blind-review repair regressions passed. Fourteen lifecycle checks passed; the full suite subsequently rechecked them and all 96 module/interface checks. Earlier simplification/action checks are also included in the full suite. |
| Environment isolation | 21 targeted checks passed in each of three environments: `LATEX_AI_BASE` unset, a real revision, and all zeros; external `DOC` and `MAKEFLAGS` were present. |
| Unmodified full portability suite | Blocked at preflight by missing ChkTeX and Biber. No full portability pass is claimed. |
| Temporary compiler-only portability copy | 81/81 passed with real compilers and BibTeX. Fixture lint was explicitly disabled; four ChkTeX and two LuaLaTeX/Biber checks were omitted. The distribution suite and reference policy were not weakened. |
| Schema-3 acceptance fixture, local temporary copy | Three current documents and independent PDF exports passed; a fragment selects only the notebook, a shared resource selects all roots. Final shared research/full plan and preflight also pass. Temporary fixture lint was disabled. |
| Reference compilation and export | Real pdfLaTeX rebuild after receipt invalidation, citation/reference verification, actual bibliography scope, and named PDF export passed. |
| Reference `make check` / doctor | Correctly fail for missing ChkTeX. The configured lint policy remains enabled. |
| Installer regeneration and audit | Runtime regenerated only through `upgrade`; audit reports no changes or conflicts. |
| Independent implementation/integration review | Completed read-only; all actionable findings repaired and rechecked. No remaining actionable findings in reviewed scope. |
| Blind user acceptance | Initial smaller acceptance passed. The later ten-tester round found the recorder defect; parent and independent review exposed its stale-export and native-discovery consequences. All confirmed findings were repaired and affected transitions rechecked. |
| File/policy checks and `git diff --check` | Passed. |

Evidence is retained under `/workspace/latex-ai-simplification-evidence/`:
fail-first logs, final regression and isolation logs, the compiler-only report,
environment inventory, fixture commands, source hashes, and installer reports.
Independent probes are retained under `/tmp/workbench-3-review-*`.
The blind report is `blind-test.md` in the evidence directory. Its minor lint
discovery friction is addressed by explaining shared defaults and the scope of
`--no-lint` in the configuration guide. The tester's disposable fixture had lint
disabled and did not exercise Biber or a distinct older-release transition.

The final repair suite, compiler-only 81-check report, full-portability missing-tool
preflight, installed reference upgrade/audit/build/export, schema-3 acceptance
commands, and independent review are retained under
`/workspace/latex-ai-blind-fixes/`. Its compiler-only package is a fresh copy of
the final distribution. Only that copy's temporary fixtures disable lint and omit
the six unavailable-tool checks. The final schema-3 fixture checks/exports all
three roots and verifies fragment/shared-resource selection.

The controlling-terminal blind-round follow-up additionally verified Linux
foreground Ctrl-C for Make and direct runtime, including failed receipts and
direct exit 130. This closes that narrow Linux probe, not desktop-editor or
macOS acceptance. No reproducible defect remains in the repaired review scope;
the release still has the environment and hosted validation requirements below.

The reference's `main.tex` and `bibliography/zotero.bib` match their recorded
pre-change SHA-256 hashes. Its explicit output directory and accepted-baseline
location are preserved as ordinary document settings.

## Remaining release checks

The implementation can be reviewed locally; release verification remains
incomplete until the full 87-check portability suite and reference lint pass
with genuine ChkTeX/Biber, and hosted jobs succeed on the exact published commit.
The new schema-3 hosted workflow is prepared and locally exercised, but has not
run on GitHub. Python 3.10–3.14 hosted coverage must also be repeated for this
release. No Git mutations were performed during the recorded local validation;
publication is a separate, explicitly authorized step.

macOS acceptance, desktop-editor execution, Windows, and TeX Live 2026 execution
remain open. This iteration establishes schema-3 reference/fixture coverage
locally; it does not close those platform or hosted coverage gaps.
