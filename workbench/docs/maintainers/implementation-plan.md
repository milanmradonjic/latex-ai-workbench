# Modular workbench implementation

Implement a portable core with explicitly enabled modules. Preserve the current
reference manuscript, bibliography export, editor setup and Git guardrails.
All verification uses the reference and fresh synthetic projects; Git publication
and GUI applications remain under the owner's control.

1. Extract dependency-free shared utilities and the LaTeX backend. Add schema 2
   module configuration and initialization profiles; continue reading schema 1.
   Migrate existing configuration only through an explicit reviewed operation.
2. Make installation, managed Make targets, editor and CI adapters conditional.
   Enable/disable modules explicitly, retain research artifacts on disable, and
   preserve existing build conventions and safe upgrade/backup behavior.
3. Add notes and a minimal research workflow: project-declared experiment/figure
   commands, cheap scientific checks, recoverable input snapshots and run records,
   read-only freshness reports, and an optional claim/evidence ledger.
   Never run expensive tasks as a consequence of saving files or checking freshness.
4. Exercise manuscript, notes-only, numerics-only and mixed synthetic projects;
   cover independent figures/bibliography, failures, relocation, disabling,
   migration, conflicting upgrades and selective validation/CI.
5. Update configuration, operation, portability and skill documentation; upgrade
   the reference safely, run canonical checks and inspect the final diff/status.

Profiles select initial defaults only. Project paths and commands remain
configurable. The implementation uses bundled modules with explicit contracts,
standard-library Python and versioned JSON; scientific libraries stay in each
project's own environment. A freshness result establishes matching declared
inputs, not scientific validity. The example calculation is explicitly synthetic.

## Completion

All five stages are implemented. Release 2.0 has schema 1 compatibility and
explicit schema 2 migration, eight independently selected modules, five setup
profiles, optional editor/CI adapters, safe disable/re-enable, and a complete
synthetic experiment/figure workflow. The reference enables only its existing
LaTeX/bibliography capabilities. Local validation passed 77 regressions and
54 synthetic portability checks; see [verification](verification.md).
The owner authorized publication; version 2.0.1 passed hosted CI after fixing
installer argument ordering on Python 3.12.

## Modest Markdown increment (2.1)

Add one explicitly enabled Markdown module using Pandoc's syntax tree for
link/anchor/citation checks and its HTML writer for explicit export. Preserve
plain-note profiles and source ownership, prohibit automatic code execution,
and use the same configuration/installation/Make/CI contracts. Verify read-only
checks, failure behavior, real math/citation rendering, relocation and disable
retention with synthetic fixtures. Keep formatting frameworks, publication
sites, bidirectional TeX conversion and executable notebooks out of this stage.

Implemented and verified locally: 93 regressions (including real Pandoc checks
and rendering), 54 portability checks and the reference manuscript checks.
The reference was upgraded without enabling Markdown or altering its sources,
export/editor choices or permission guardrails. The owner authorized a local
commit of this increment. Commit `da47602` was subsequently pushed and passed
hosted CI, including all 93 regressions without skips and 54 portability checks.

## Research loop pilot

A new synthetic project exercised discussion/notes, configured RK4 calculations,
headless Matplotlib figures, Markdown export and handwritten TeX. Changing the
rate marked the experiment and its figure stale without regeneration. Explicit
numeric/figure runs and manuscript edits restored current outputs. Notes-only
checks preserved scientific output hashes. Four recoverable run records and
the final report are retained; see [verification](verification.md).

The pilot supported a small [workflow guide](../research-loop.md) covering current
configuration/output checks, figure dependencies, when to add result links and
deliberate manuscript updates. No new execution or synchronization layer was
needed. The owner authorized a local commit of the workflow guide and pilot
verification updates. The runtime remains at release 2.1.
