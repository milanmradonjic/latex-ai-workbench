# A small research loop

Start with a concrete question and enable only the modules it needs. A numerical
notebook may use notes, numerics, figures, provenance and freshness. Add Markdown
for note checking/export and LaTeX for a manuscript. Bibliography and claims are
independent choices. Existing profiles remain starting presets, not requirements.

## Working sequence

1. Write the question, assumptions, derivation and decisions in ordinary notes.
   Keep definitions, units and unresolved questions explicit. Review the actual
   working change with `make validation-plan`; `make validate` selects checks.
   Plain note changes do not need a manuscript build or a scientific rerun.
2. Materialize parameters and units in a project-owned input file. Declare the
   complete numerical task inputs, outputs and environment specification in its
   manifest. Add model-specific cheap checks with justified tolerances.
3. Execute the selected numerical task explicitly with `make run TASK=name`.
   Checks should compare the actual generated output with the current parameters,
   as well as exercise model limits and convergence. The decay example's check does both. A self-test at fixed fixture
   parameters alone does not check a newly generated result. Preserve resolved
   parameters/units in the result and inspect the run record.
4. Plot those recorded outputs explicitly with `make figure TASK=name`. Declare
   plotting source/environment dependencies and each output format. Use the
   project's plotting tools; inspect units, legends, scales and fonts at the
   intended manuscript size. Headless plotting can keep its cache in the project.
5. Add links and figures to the notes once their targets exist. With Markdown
   enabled, `make md-check` checks the declared document set. `make md-render`
   exports HTML only when needed. A draft link to an output not yet produced is
   deliberately a broken link; it does not trigger generation.
6. Update handwritten TeX from the inspected observations. Reconcile numerical
   values, assumptions, captions and conclusions with the current data. The
   workbench does not synchronize scientific prose or convert notes into TeX.
   Run `make check`, then inspect the compiled pages and figures.
7. Update session state with established results, remaining assumptions and the
   next question. Inspect the final diff/status before any authorized Git action.

## When a parameter changes

`make freshness` reports stale producers and downstream consumers without
recalculating them. Validation can fail until required outputs are current.
Execute the numerical task, then the dependent figure task explicitly. Refresh
the observations and manuscript text, and validate again. A regenerated figure
does not establish that an old numerical statement in the prose is still true.

The changed-file plan covers the entire working change, including earlier
uncommitted scientific edits. A later note edit does not make those earlier
changes disappear from validation. The runtime's explicit `--files` option is
useful for an isolated test or a known complete scope; do not omit relevant
changes to obtain a smaller check.

## Evidence from the pilot

A synthetic scalar-decay project completed this sequence at two rate values,
using seven enabled modules and an existing headless Matplotlib environment.
Notes-only validation preserved result/figure/manuscript hashes. A parameter
change reported both producers stale; refreshing only the calculation left the
figure stale. Explicit runs, updated observations and manuscript edits restored
current outputs and passed the configured scientific and manuscript checks.
Four run records retained source/parameter/environment and output snapshots.

The pilot required ordinary project files and the existing module interfaces.
The practical refinements are the sequence and dependency/check declarations
above. Add infrastructure when a real project identifies a missing capability.

See [task manifests and provenance](research.md), [optional Markdown](markdown.md),
[module selection](modules.md) and the [verification checkpoint](maintainers/verification.md).
