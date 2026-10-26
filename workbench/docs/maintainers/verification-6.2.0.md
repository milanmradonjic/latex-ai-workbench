# Workbench 6.2.0 verification

This release addresses build and agent-workflow friction observed in a coupled
article/supplement adoption. It adds an optional freshness hint for custom
builders and explicit preview/batch guidance. Routing, receipt verification,
protected regeneration, command names, and lint matching remain unchanged.

## Regression evidence

`test_receipts.IncrementalCustomBuilds` failed before the runtime change: an
inherited force value reached the compiler unchanged, and a cooperating builder
received no hint. Both tests pass with the change. They cover required initial
regeneration, current-output reuse, configuration invalidation without a second
builder invocation, and overriding an inherited environment value.

Existing receipt, process, installer, and generated-file tests remain required.
The runtime is refreshed through the installer for the reference project and
the Dipolar BEC adoption; project-owned policy is edited deliberately.

## Validation

Local checks on 26 October 2026:

- `make -C workbench test`: 503 cases; 500 passed, two platform/filesystem
  skips, and one sandbox-specific failure because macOS `ps` could not report
  process start time. The unchanged failing process-identity test passed when
  rerun outside the sandbox. No process code or test was weakened.
- All 39 guide tests passed after updating the live manual. The full suite's
  generated Make/editor fixture guard passed unchanged.
- `make -C workbench portability`: all 48 scenarios passed with real TeX tools.
- Reference `make validate`, `make doctor` against this template, and
  `make -C workbench audit-reference` passed. Both installed runtimes match
  6.2.0 and their installation records, with no edited runtime modules.
- The coupled adoption passed 14 adapter regressions, including real
  bibliography/AUX recovery. Disposable manuscript copies verified page-reference
  propagation in both directions, cold starts, deleted/altered outputs,
  configuration invalidation, compiler failure, and subsequent recovery.
- Its live text/citation/reference checks and both receipt checks passed, as
  did forward/reverse SyncTeX queries. Its full validation exited 2 on three
  manuscript ChkTeX warnings outside this implementation. No baseline was refreshed.

## Adoption measurements

Original 6.1.1 runtime/adapter versus the 6.2.0 runtime/adaptive adapter, using
the same fixed source inputs in disposable copies. These are single local
timings including instrumented command overhead. Counts are actual executions;
latexmk may do no compiler work.

| Case | pdfLaTeX before/after | BibTeX before/after | Time before/after (s) |
| --- | ---: | ---: | ---: |
| Current PDF | 1 / 0 | 1 / 0 | 3.450 / 1.180 |
| Article prose preview | 4 / 1 | 2 / 0 | 9.816 / 3.143 |
| Prose edit, full check directly | 5 / 2 | 2 / 0 | 12.419 / 6.225 |
| Supplement prose preview | 4 / 1 | 1 / 0 | 9.013 / 2.447 |
| Bibliography edit | 3 / 1 | 3 / 2 | 9.282 / 4.530 |
| Cold build, both documents | 9 / 7 | 4 / 2 | 21.706 / 20.285 |

Full-check timings include the same lint failure in both versions. Warm and
cold cases are separate; the cold timing difference is small. No general
speedup or scientific-validity claim follows from these measurements.

No hosted checks or release publication are claimed by this local record.
