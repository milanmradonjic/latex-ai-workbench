# Version 3.0.3 verification

Phase 0 of [the plan after 3.0.2](plan-after-3.0.2.md), 2026-10-12, on
`plan/phase-0-macos-verification`, based on `f602c97`. Environment and independent
review of the original repairs are in the [3.0.2 macOS record](verification-3.0.2.md#macos-verification-and-independent-review).
The independently reviewed repair was published as `63791a9` and landed on `main`
at `34c3e88` through PR #1,
with the owner's approval. Phase 0 is complete.

## Reproduction and repair

After installing a synthetic project with `build_command: ["make", "pdf"]`, actual
`/usr/bin/make` 3.81 stopped at this generated line even for the project's own `pdf` goal:

```make
latex-ai-build-prepare: private override SHELL := $(LATEX_AI_RECIPE_SHELL)
```

The diagnostic was `Makefile:30: *** multiple target patterns. Stop.` GNU Make
3.81 cannot parse `private`. The 3.0.2 modern-Make `.FEATURES=` simulation still
accepted that syntax, so the suite did not expose the defect.

`tests/test_repairs_3_0_3.py` exercises the actual old parser, and failed at `make pdf`
before the fix. The adapter now guards both private shell assignments with the
existing required `extra-prereqs` feature. No receipt, configuration or manifest
schema changes. This intentionally adds a guard to installed adopted-build Makefile
blocks; release notes announce that change.

The same regression passes after the fix: `pdf`, `help` and `status` work; workbench
build/check refuse with the GNU Make 4.3 requirement; the installer NOTE and failing
`doctor` name it. The test explicitly skips where actual Make 3.81 is unavailable.

Local issue evidence: `.latex-ai/artifacts/issues/report-20261012T082315938121Z.json`.
Failing/passing regression logs: `/private/tmp/latex-ai-phase0-regression-before.log`
and `/private/tmp/latex-ai-phase0-regression-after.log`. These are local evidence,
not repository contents or hosted results.

## macOS scenario results

Eight explicit scratch checks passed, then passed again after independent review
with Make's `PYTHON` pinned to the Python 3.14.8 interpreter. The repeat's projects,
logs and `report.json` are under `/private/tmp/latex-ai-phase0-cvqz9uzg/` on this host.
The earlier run under `/private/tmp/latex-ai-phase0-_glngshd/` selected stock Python
3.9.6 for old-Make recipes because `/usr/bin` was first on PATH; those recipe results
are superseded by the repeat using the supported interpreter.

| Scenario | Observed result |
|---|---|
| Real latexmk, extensionless graphic and PNG | One invocation, zero protected-rebuild messages; new `fig.pdf` makes the document stale |
| Real Make 3.81 and Make 4.4.1, adopted `make pdf` | 3.81 raw target/help/status succeed, build/doctor refuse as documented, installer NOTE present; modern build succeeds |
| Native process identity without `/proc` | Nonempty `ps:` token; live PID accepted, different token refused |
| `kill -9` of the Python build owner, with a delayed real latexmk child | `make status` reports running while the compiler group remains, then failed after it exits |
| Project locks through `/tmp` and `/private/tmp`, with different TMPDIR values | Second process excluded; read-only descriptor excluded while held and acquired after release |
| Case-insensitive APFS installer behavior | Lowercase `makefile` preserved through init/upgrade; unsupported `MAKEFILE` casing refused |
| APFS ctime: write, rename replacement, timestamp-preserving copy during build window | Each classified as written during the build |
| Cached digest, same-size edit and restored mtime | Digest changes; unchanged settled input retains its cached digest |

The read-only descriptor case forced the existing fallback while using real local
`flock`; it did not change Unix users. Fixtures never initialized Git.

## Release checks

The suite driver used Python 3.14.8 and GNU Make 4.4.1, with normal macOS `ps` access.
The full-suite run below preceded the review's test-environment correction: its
old-Make regression recipes used stock Python 3.9.6. The corrected regression and
the complete scratch repeat both passed with `PYTHON` pinned to Python 3.14.8;
the adapter implementation did not change during review.

| Check | Result |
|---|---|
| `make -C workbench test` | 365 tests ran in 198.311 s: 364 passed, one Linux-only zombie-state test skipped; no TeX skips |
| Actual Make 3.81 regression after review | Passed with Make's `PYTHON` pinned to the supported Python 3.14.8 interpreter; independently rerun by the reviewer |
| `make -C workbench portability` | 87 of 87 passed with real TeX |
| `make -C workbench upgrade-reference` and `make -C workbench audit-reference` | Reference upgraded without conflicts; audit current |
| `python3 -B .latex-ai/workbench.py validate --files-only` | Changed-file syntax, policy and local-link checks passed |
| `make latex-ai-bib-check` | Passed |
| Reference `make check` | Full LaTeX/bibliography check passed, including compiler integrity and chktex |
| `make -C workbench handbook` | Markdown and HTML regenerated for 3.0.3 |
| Reference generated Makefile, VS Code settings/tasks and CI workflow | Byte-identical to the pre-upgrade snapshot |

Two existing lock-fixture tests emit `ResourceWarning` for unclosed captured stdout
streams on Python 3.14. They emitted the same warnings in the native 3.0.2 baseline;
neither suite failed, and the warnings were not suppressed.

Logs on this host: `/private/tmp/latex-ai-phase0-suite-3.0.3.log`,
`/private/tmp/latex-ai-phase0-portability-3.0.3.log`, and
`/private/tmp/latex-ai-phase0-reference-check.log`. The final portability report and
compiler logs are under
`/var/folders/8w/845x3km1259d03xh1dh4zs1c0000gp/T/latex-ai-portability-ni_oci7d/`.

## Independent review

The owner authorized delegation to a separate read-only review agent. It found no
adapter correctness issue, and independently passed the actual Make 3.81 regression,
reference parity, modern `.ONESHELL`/chosen-shell ownership, and command-line shell
ownership checks. It also verified handbook parity, unchanged generated reference
files, and the failing-first, suite and portability evidence.

Its one finding was the unsupported stock Python selected by the regression's
old-Make PATH. The fixture now sets `PYTHON: sys.executable`; the writer and reviewer
independently reran it successfully, and all eight scratch scenarios passed with
that interpreter pin. No review findings remain. Reviewed-regression and scenario
logs are `/private/tmp/latex-ai-phase0-regression-reviewed.log` and
`/private/tmp/latex-ai-phase0-checks-reviewed.log`.

## Hosted verification

All three PR workflows passed for the exact repair head
`63791a943802b53ac95cdb69627075a3eb31c031` before integration:

| Workflow | Result |
|---|---|
| Python compatibility | Python 3.10–3.14 each ran 365 tests successfully, with 21 expected skips: 20 requiring TeX and one requiring the actual macOS Make 3.81 parser |
| Schema-3 acceptance | Named-document PDF and export selection checks passed |
| LaTeX AI Workbench | File/policy checks, the 365-test suite (21 expected skips), 87/87 compiler portability checks, manuscript checks and PDF upload passed |

The workbench workflow's separate bibliography and project Make-rule steps were
skipped by its validation plan. Local bibliography and reference checks passed as
recorded above. These hosted results establish the PR head; no hosted timing
comparison or separate merge-commit result is claimed.

## Not verified

- NFS locks/attributes, remote clock skew, backward wall-clock changes, real cross-user
  macOS permissions/ACLs, or Windows.
- Python 3.10–3.13 on macOS; the local suite used Python 3.14.8, while the compatibility
  matrix above ran those versions on Linux.
- Same-PID reuse within one `ps` start-time second; the residual precision limit is an
  open item in the 3.0.2 review.
