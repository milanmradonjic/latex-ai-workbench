# Workbench 6.3.1 verification

## How the gaps were found

6.3.0 was exercised against its release notes, the user docs and the 6.1.x audit repairs in
synthetic projects: the snapshot opt-in with every non-boolean value, with a missing root and
with unknown settings; routing of configured paths inside `archive/`, spelled with `./`, `//`
and `..`, and through a link; a cooperating custom builder reading `LATEX_AI_BUILD_FORCE`
(1 on the first build and after an edit, 0 on an unchanged rebuild); validation without Git.
The 6.1.0 and 6.1.1 repairs hold. Three gaps were found.

| Gap | Before | After |
|---|---|---|
| A file matched by a document's `inputs` | routed by folder and suffix: `archive/table.csv` or `data/params.json` got file checks, so `make validate` passed while `make documents` reported the document stale | Full, deleted files included (patterns are matched, not globbed) |
| A configured path spelled with `..`, or a root that links into `archive/` | compared by its literal text and exempted as historical | compared in the spelling the changed paths have (`tracked_name`), as well as literally |
| `make help`/`make guide` in an opted-in project whose configuration is otherwise broken | snapshot commands hidden, although they run | shown, by the same flag-only read the commands use; missing or malformed configuration still shows none |

The snapshot docs now also say to unload timers before turning the flag off.

## Tests

Each new test failed on 6.3.0 and passes now:

- `test_level2.Level2Routing.test_declared_build_inputs_are_active_whatever_their_suffix_or_folder`
- `test_level2.Level2Routing.test_declared_paths_are_compared_in_their_canonical_spelling`
- `test_snapshots.OptionalSnapshots.test_opted_in_recovery_is_shown_when_document_paths_are_broken`

`test_planner.DocumentTests.test_deleted_declared_input_is_still_rejected_by_build` asserted
the 6.0.0 routing of a declared Markdown input (file checks); it now expects Full. The build's
own refusal of a missing declared input, which it also checks, is unchanged.

## Results

- Package unit run: 513 cases, 508 passed, 5 skipped (platform and TeX-installation guards).
- All 48 compiler-portability scenarios pass.
- `make audit-reference`: runtime files identical at 6.3.1; `AGENTS.md` differs from the
  template only in the project-owned sections, and takes the `inputs` phrase deliberately.
- Canonical `make validate` in the reference project selects Full and passes.

The Dipolar BEC project was not touched; its owner refreshes its runtime by the update recipe.
