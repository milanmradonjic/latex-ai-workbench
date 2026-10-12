# Version 2.7.2 verification

This records the unpublished repair working tree based on independently verified
main `0498378f49f7f0b8866ded2b1eedc24306543a41`. No hosted run is claimed for
these edits. The previous release's verification claims were audited separately;
its successful hosted logs include six compiler-dependent unittest skips.

## Architecture of the repairs

Three Make-text consumers now share `make_graph.py`: integration generation,
document ownership validation and project-check detection. It collects lexical
facts without executing Make. Consumers keep their own conservative decisions;
computed ownership still requires an adapter, while uncertain checks select the
complete project check. This reduces parser drift without attempting to emulate
Make's evaluator. Literal includes also supply receipt dependencies.

`processes.py` owns process identity, zombie-aware Linux liveness, jobserver
descriptor inheritance, execution gating and cooperative cleanup. `core.run`
keeps inherited stdin. Compiler launch and publication share a short lock;
children wait for publication before exec and exit on gate EOF if the owner
dies. Parallel phased recipes retain every live compiler group. Their shell
supervision preserves the existing outer graph and ordinary raw build goals.

`output_transaction.py` records intent before displacement, uses unique attempt
directories, restores missing originals on failure and recovers abrupt owner
death before the next build. It never overwrites a replacement. Terminal
restores retire recovery entries; remaining original backups are archived.
Path containment is shared across legacy and named compiler output paths.

Receipt inputs carry source/policy roles. Compiler-consumed or explicitly
declared Makefiles win over policy normalization. A policy marker forces one
rebuild of 2.7.0/2.7.1 receipts. Local validation and generated schema-3 CI use
the same `project_check` decision; PDF collection stays inside TeX actions.

## Audit finding coverage

IDs refer to the independent audit of 2.7.1. Each original finding has a
fail-first regression in `tests/test_audit3_repairs.py`; the disk-move fixture
was corrected before its baseline failure was recorded.

| ID | Introduced in | Repair and regression evidence |
|---|---|---|
| A1 | 2.7.1 | Real TeX consuming Makefile content invalidates verification/export after source changes; declared managed text is hashed in full. Included Make policy changes also regenerate a different real PDF. |
| A2 | Earlier | Schema-1/2 PDF/log symlinks escaping a temporary project are rejected before compilation, preserving the outside sentinel. |
| A3 | Earlier | Kill the outer parallel Make while a compiler lives: another build is refused. Shell overrides cannot bypass ownership; gate failure injection prevents execution before publication. |
| A4 | Earlier | Blank/comment-separated and conditional recipes, variable targets, assignment-contained `eval`, local `latex-ai-*` prerequisites and missing generated optional includes retain project checks. Generated CI replays the canonical project check. |
| A5 | 2.7.1 | A genuine pdflatex adapter receives supplied pipe input and verifies its output. |
| A6 | 2.7.1 | Second move failure restores the first displaced output. Interrupted journals recover once; completed rollback does not block later output cleanup. |
| A7 | 2.7.1 | Recorded bibliography list/null/string/scalar identities become stale, with normal documents/status/verify outcomes and successful rebuilding. |
| A8 | 2.7.1 | A new latexmk startup failure cannot report the preceding real TeX undefined-macro log. |
| A9 | Earlier | SIGINT/SIGTERM produce one interrupted JSON result after cleanup; repeated SIGINT cannot leave a compiler that ignores cooperative signals running. |
| A10 | Earlier | An unreaped zombie owner is not considered running on Linux. |
| A11 | Earlier | Ordinary `check::` remains valid. Conditional mixed-colon rules and custom recipe prefixes refuse installation before writes. |
| A12 | Earlier pattern | All fixture suites share environment isolation. A caller's DOC/MAKEFLAGS/PYTHON cannot redirect fixture builds; tests opt into operational settings explicitly. |

Independent read-only review also found intermediate repair regressions in plain
raw goals, `.ONESHELL`, command-line shell overrides, question/touch modes,
no-op phased goals and terminal journals. These were reproduced and fixed;
the new tests cover those interactions rather than only fresh installations.
Git init/clone now have matching approval prefixes in both agent templates.

## Validation record

Final local validation completed on 2026-10-10. The environment provides Python
3.12.14, GNU Make 4.4.1, latexmk 4.86, TeX Live 2025/dev/Debian (pdfTeX 1.40.26,
LuaHBTeX 1.18.0, XeTeX 0.999996), BibTeX 0.99d and Pandoc 3.1.11.1. ChkTeX and
Biber are missing. Shell network transport is unavailable, so they could not be
installed. Genuine compiler fixtures explicitly disable lint where necessary;
this does not alter the reference's lint policy.

| Check | Outcome | Evidence and limits |
|---|---|---|
| Full regressions, `LATEX_AI_BASE` unset | **289 passed, no skips**, 90.597 s | `make -C workbench test`; includes the existing 262 tests and 27 repair tests. |
| Full regressions, base `0498378f49f7f0b8866ded2b1eedc24306543a41` | **289 passed, no skips**, 89.444 s | Same completed implementation. |
| Full regressions, base forty zeroes | **289 passed, no skips**, 88.270 s | Same completed implementation; invalid comparison history remains isolated from fixture state. |
| Independent read-only repair review | **27 passed**, 20.951 s; no open implementation finding in exercised paths | Fresh installed integration probes also cover parallel/nested Make, raw goals, `.ONESHELL`, dry/query/touch modes, owner death, publication gating, repeated interruption and recovery. Conditional/eval plus selector preservation passed separately (2 tests, 4.782 s). |
| Required portability matrix | **Blocked**, exit 2 before checks | Preflight requires ChkTeX and Biber. Zero executed checks are not reported as passing or skipped coverage. |
| Temporary compiler-only portability | **81/81 passed** | Real pdfLaTeX/LuaLaTeX/XeLaTeX and BibTeX, notebooks, fragments, examples, exports and adopted Make. The temporary driver explicitly disables fixture lint and omits lint/Biber fixtures; it does not replace the complete 87-check matrix. |
| Real 2.7.1 installed-project upgrade | **Passed**, exactly one rebuild | Genuine pdfLaTeX compilation counts: old check 1; upgrade 1; first new parallel check 2; repeated check 2. |
| Reference `make check` | **Blocked at lint**, exit 2 | Real compilation and citation/reference integrity pass, then missing ChkTeX fails the command. No complete-check success is claimed. |
| Reference verification, bibliography check and export | **Passed** | Bibliography structure/key checks establish local readiness; Biber execution is not established. |
| Installer audit after reference upgrade | **Clean** | No changes or conflicts. Installed runtime was regenerated only through the installer. |
| File/policy checks, diff whitespace and Git objects | **Passed** | Lightweight syntax/link/policy checks, `git diff --check` and `git fsck --full`. Scientific source, bibliography and configuration are byte-identical to HEAD; lint policy is unchanged. |

The full regression command uses
`PYTHON='env DOC=external MAKEFLAGS=n python3'` as its Make variable: contamination
is injected into the test process, rather than suppressing the outer Make
invocation. The independent reviewer additionally used an unavailable caller
`PYTHON`. Shared fixture isolation clears these values; tests that exercise them
restore their own settings explicitly.

Logs and machine-readable outcomes are retained under
`/workspace/latex-ai-audit-3/`: `full-regressions-final-report.json` and its three
logs, `portability-required.log`, `portability-compiler-only-validated.log`,
`upgrade-real-2.7.1/report.json`, reference logs, and `repair-review/report.md`.
`completed-source-hashes.json` and the independent review's final source hashes
pin the implementation. Earlier failing runs are retained as intermediate
evidence, not substituted for the final matrix. Fail-first evidence includes the
corrected disk-move fixture and the final conditional/eval checks.

No reproducible implementation defect remains in the exercised paths. The
repair tree is ready with the documented validation limitations; full toolchain
and exact-published-commit hosted checks remain necessary before claiming a
fully verified release. Nothing has been staged, committed or pushed.

## Remaining coverage

No new hosted execution of a generated schema-3 workflow, Python 3.10–3.14
matrix, TeX Live 2026 beyond the previously published reference, macOS, Windows,
or editor execution is claimed. Local Linux process tests do not establish real
PID/PGID reuse or hardware/power-loss durability. Journals preserve recoverable
state when I/O fails; they cannot promise recovery from lost storage.

The working repository has the exact original commit/tree objects and remote
tracking branch, with a shallow boundary at 2.7.0. The original no-Git workspace
is preserved. Shell transport still lacks working DNS/proxy connectivity;
read-only GitHub API access verified the current main. Publishing requires
separate Git authorization and subsequent exact-commit hosted validation.
