# Workbench 6.0.0 verification

This implements the [Level 2 plan](plan-level-2-validation.md): file checks or file
checks followed by one project-wide `make check`. Archives/baselines and revision
patches are exempt from manuscript checks. Automatic document/dependency routing,
package-test scheduling, routing settings and Makefile inference are removed.

Configuration schema 4 remains; the removed public `validation` object is refused
with a hint. Document build inputs retain their internal representation. The only
build-helper extension enumerates recognised command candidates, including deleted
paths, for planning; its existing build behavior remains the default. Receipt,
lock, process recovery, snapshot and export implementations are unchanged.

## Evidence

- Eight new contract tests failed against 5.0.0 before implementation (7 failures
  and 32 subtest errors) and passed after replacement; logs:
  `/private/tmp/workbench-level2-before.log` and `workbench-level2-after.log`.
- Planner tests were updated where selective routing was intentionally removed;
  source/recorder dependency assertions were retained against the build backend.
  Custom Make checks, Git read-only queries, file-integrity checks and failed-build
  recovery remain covered.
- Full local unit suite: **496 tests, 494 passed and 2 platform skips**, in
  262 seconds; `/private/tmp/workbench-level2-unit-final.log`. The skips are the
  Linux-only process-state case and the filesystem's unsupported non-UTF-8 path.
  Process ownership tests ran with host process-inspection access.
- The initial full run had nine obsolete assertions/fixtures: the removed public
  routing declarations, per-document selection, version wording, and the manual's
  size. Fixtures now express build inputs on documents; the manual still passes
  its unchanged 60-line limit. The final full run passed. After a final removal
  of the unused JSON `files` flag, all eight contract tests passed again;
  `/private/tmp/workbench-level2-contract-final.log`.
- Compiler portability: **48 scenarios passed**;
  `/private/tmp/workbench-level2-portability.log`, with synthetic projects/logs at
  `/var/folders/8w/845x3km1259d03xh1dh4zs1c0000gp/T/latex-ai-portability-xfv1hdf9`.
- A separate real-TeX, two-root project with shared output and mutual external
  references passed full checks and both verified exports. Validating broken
  historical TeX and a patch containing incomplete Python left PDF/log hashes
  unchanged. Evidence: `/private/tmp/workbench-level2-shared-2bij_hoc/verification.log`.
- Reference `make check`, `make -C workbench audit-reference`, lightweight
  syntax/policy/link checks, and `git diff --check` passed. All vendored runtime
  files match 6.0.0. The only generated-project difference is the reference's
  deliberate local AGENTS sections; permission files are unchanged.
- Hosted Python-matrix and compiler results are recorded by the implementation
  PR's checks. They are separate from these local results.

No research project was used as a fixture or modified. No subagent was used,
in accordance with the owner's current policy.
