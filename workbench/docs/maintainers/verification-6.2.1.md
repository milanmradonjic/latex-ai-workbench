# Workbench 6.2.1 verification

## Scope

Policy and workflow clarification prompted by agents running branch/status/diff
before and after every small manuscript request. The operating skill and
generated/reference/adopted policy now share these rules:

- Inspect branch, status, and relevant staged/unstaged diffs at session start.
- A session may span successive requests; a reply, PDF preview, or completed
  validation batch does not by itself require another Git checkpoint.
- Before each patch, read the current target passage and preserve concurrent
  edits. Refresh relevant Git inspection when context is stale, a branch/index
  change is indicated, scope expands, unexpected changes appear, or before
  an approved Git mutation sequence.
- Inspect relevant diff, whitespace errors, and status at session completion
  or Git handoff. Existing mutation approvals remain in force.
- Reuse stable configuration/tool context and avoid redundant preview/build/
  check/planning commands before validation. Repository-independent questions
  do not need a new inspection.

Validation still finishes each requested batch before delivery or Git handoff.
Its routing, scientific scope, lint behavior, permissions, and runtime behavior
are unchanged; the only runtime source change is the version number.

## Verification

The two existing `GeneratedFilesGuard` cases and the existing policy/scope check
pass. The installer audit reports identical 6.2.1 runtime files in the reference
project; the generated policy is adopted deliberately in both projects.

A semantic read covers successive requests, a concurrent edit to the target
passage, resuming stale context, a branch/index change, expanded scope, and Git
handoff. Known uncommitted work and a completed reply do not trigger Git again;
an indicated state change or stale context does. File reads and focused patches
protect concurrent work between checkpoints. Mutation approvals are unchanged.

Canonical validation is run in both projects for delivery, with outcomes in the
local command logs and change report. These policy-only edits add no
implementation-mirroring tests and do not repeat unchanged compiler/recovery
benchmarks. Workbench may still read Git when validation discovers changed files.
