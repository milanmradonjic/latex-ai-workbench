# Workbench 6.3.0 verification

## Change and acceptance cases

Snapshots are an optional boolean project choice, off by default. The installer
reports the choice; help/manual guidance is limited to opted-in projects. Both
public snapshot commands refuse disabled projects before touching stores. Git
recovery replaces mandatory snapshot recommendations. The backend, retention,
locking, restore implementation, Make/editor fixtures, and command names remain
unchanged; there are no installation profiles or new timer-management paths.

`test_snapshots.OptionalSnapshots` covers:

- omitted/false choices refusing manual, frequent, and weekly tiers without
  creating stores, and hiding snapshot commands from normal help/manual output;
- explicit opt-in enabling commands, and disabling again preserving every
  existing store byte;
- missing/malformed configuration failing closed, and opted-in recovery when a
  TeX root is missing;
- strict boolean validation, Git required only when enabled, and setup reporting
  the selected choice without writes to snapshot storage;
- changing the snapshot choice leaving a standard document receipt current
  (explicitly declared configuration-file dependencies still hash normally).

The original five acceptance tests failed before implementation and passed after
it. Existing snapshot command fixtures now opt in explicitly; backend coverage
is retained. The generated Make/editor guard remains unchanged.

## Adoption

The reference project and Dipolar BEC explicitly choose `"snapshots": false`.
Installed runtimes are refreshed through the installer. Project-owned policy
adopts the optional workflow deliberately. No matching Dipolar snapshot timer
definitions were found under the documented LaunchAgent filename pattern.

## Results

- The full package unit run exercised 510 cases: 506 passed, two platform/filesystem
  cases skipped, and two old guide fixtures failed because they did not opt in.
  Those two fixtures now enable snapshots explicitly and both pass on the focused
  rerun; no runtime implementation changed after the full run. All seven new
  acceptance cases and the unchanged generated Make/editor guard passed.
- All 48 compiler-portability scenarios pass.
- Canonical `make validate` passes in both the reference and Dipolar projects.
  The Dipolar manuscript lint gate now passes as well; this task did not edit its
  scientific sources or lint baseline.
- Runtime audit reports identical 6.3.0 files; the Dipolar installation record and
  every vendored runtime file match the distribution.
- Live Dipolar `make help` and `make guide` omit snapshot commands, and
  `make snapshots` reports the feature disabled.

Snapshot tests use isolated temporary homes and synthetic files, never live
project stores. Full-run and focused-rerun logs are kept separately in local
verification evidence; no local full-suite success is inferred from exit 2.
