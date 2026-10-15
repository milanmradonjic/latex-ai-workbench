# Workbench 5.0.0 verification

Scope: [the three-step simplification](plan-after-4.10.2.md), authorized on
15 October 2026. The 4.10.2 audit PR was merged before this implementation's delivery.
No deployed project needs conversion. Only schema 4 and the new fixed Make
interface are supported; there is no migration or compatibility implementation.

## Changes and preserved behavior

- Removed module configuration/gating and non-LaTeX execution paths. Configuration
  directly declares documents, defaults, optional shared bibliography, validation,
  and editor preference. Immutable resolved document views keep the existing
  backend representation and receipt format.
- Removed installer discovery and source/toolchain guesses. Configuration must
  exist and validate before installation writes; all declared bibliographies are
  checked during preflight. Initialization remains create-only, with previews,
  conflict refusal, and interrupted-init completion. Runtime refresh keeps backups
  and refuses locally edited files unless explicitly forced.
- Generated one fixed Make recipe per public command. Multiple documents use
  `DOC=name`; `make all` builds them in sequence. Removed reserved aliases,
  automatic document-name targets, `document-lint`, and `modules`. Fixed `all` is
  now refused as a custom build goal because that goal re-enters the builder.
- Removed guidance-only Make interpretation; retained conservative detection of
  custom project checks and custom-build recursion safeguards. Changed-file and
  per-document validation selection are retained.
- Snapshot configuration lookup uses schema 4. Storage, locking, retention,
  byte preservation, and recovery behavior are unchanged. Before installation,
  snapshot guidance still points to the distribution runtime.
- Updated templates, reference configuration/runtime, editor tasks, examples,
  current guides, and operating instructions. Historical evidence is retained.
  No manuscript or exported bibliography content was changed.

## Validation

Implementation, local validation, and the independent check are complete.
Hosted completion is tracked by the [PR checks](https://github.com/milanmradonjic/latex-ai-workbench/pull/23/checks);
the record does not claim a hosted result before those checks finish.

- `make -C workbench check`: 502 tests passed subject to two platform skips,
  followed by all 48 real-TeX portability scenarios passing. Logs:
  `/private/tmp/workbench-5.0.0-check.log`; portability evidence:
  `/var/folders/8w/845x3km1259d03xh1dh4zs1c0000gp/T/latex-ai-portability-67rvmz40/report.json`.
- After adding the shared-bibliography rejection regression,
  `make -C workbench test`: 503 tests, 501 passed, two skipped (Linux process-state
  scenario; non-UTF-8 project path unsupported by this filesystem). Log:
  `/private/tmp/workbench-5.0.0-final-unit.log`. Process-inspection tests ran with
  host process access; the sandbox alone cannot provide the `ps` identity fallback.
- The new rejection test failed before the schema repair and passed afterward:
  `/private/tmp/workbench-shared-bibliography-before.log` and
  `/private/tmp/workbench-shared-bibliography-after.log`.
- Reference `make check`, generated-file/view guards, `audit-reference`, changed-file
  `validate --files-only`, and `git diff --check` passed. The reference policy
  deliberately appends repository-specific session guidance; runtime files match
  the distribution. Permission-rule files, manuscript, and bibliography are unchanged.
- Local custom LuaLaTeX, XeLaTeX, and biber integration tests passed.
- Production Python source: 4,474 to 4,043 physical lines (431 removed, including
  comments/blank lines; excludes vendored copies and tests). No dependency was added.
- Hosted CI: the PR requires `validate` and Python `test (3.10)` through
  `test (3.14)`. Their names and matrix are unchanged; see the current PR checks.
- Independent check: one user-authorized GPT-6.1 Sol reviewer checked the finished
  implementation `9734f58..c9eb06f`. It found no actionable regression or unintended
  weakening of retained tests. The reviewer did not modify the checkout.

## Independent check

The reviewer inspected schema validation/resolution, explicit installation, fixed
commands/guidance, validation routing, build/export protections, removed test
coverage, and maintained documentation/skill vocabulary. It independently ran:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_simplification.py -k ExplicitProjects
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_simplification.py -k MultipleDocuments
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_receipts.py -k ExportSafetyAudit
```

From `workbench/`: 8 explicit-configuration, 3 multi-document/interface, and 5
export-safety tests; all 16 passed. It did not repeat the root agent's full suite,
real-TeX portability, or hosted CI. No further production repair was needed.

## Coverage changes

Removed tests covered unsupported operating modes, inference, aliases, old adapter
advice, or migration. Retained regressions were converted to explicit schema-4
fixtures. New direct-installer tests cover write-free refusals, unchanged plans
when unrelated files appear, explicit custom builders, invalid document settings,
and rejection of removed setup options. New multi-document integration tests cover
shared output folders, default/selected/all builds, exports, unknown selectors,
fixed commands, and preserving project-owned additional checks.
