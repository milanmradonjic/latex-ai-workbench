# Synthetic decay workflow

Copy this directory into a fresh project. It uses only Python's standard library
and Make, and has no TeX or editor dependency. No generated result is a literature
claim or a real research result. The example solves `da/dt = -gamma*a` with RK4,
checks its analytic limit/convergence, then plots the recorded data.

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/copied-decay
make -C /path/to/copied-decay doctor
make -C /path/to/copied-decay run TASK=decay
make -C /path/to/copied-decay figure TASK=decay
make -C /path/to/copied-decay check
make -C /path/to/copied-decay freshness
```

Editing `parameters.json` makes the experiment and downstream figure stale.
Checking freshness reports this without recalculating. Run the experiment and
figure explicitly to refresh them. `results/runs/` retains declared source/config
snapshots, generated output snapshots and records for successful or failed runs.
Units and effective parameter values are written into the result.

The SVG generator is a small dependency-free test fixture. Use the project's
normal plotting library for publication figures and declare its environment.
Checks are model-specific examples; configure suitable observables, tolerances
and convergence tests for each actual research project.

The cheap check also compares the stored result with the current `parameters.json`
(its `resolved_parameters` and the samples against the analytic solution). File
timestamps cannot show that a result was derived from the current inputs, so a stale
or merely touched `results/decay.json` fails that check instead of passing as current.
