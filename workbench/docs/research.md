# Explicit research commands and records

For the everyday discussion → notes → calculation → plot → manuscript sequence,
see the [research loop guide](research-loop.md).

Enable numerics and/or figures with their own manifests. Provenance and freshness
are optional; freshness requires provenance. Notes and claims are independently
usable. No simulation or plotting command runs on saving a file, `plan`, `audit`,
`doctor`, or `freshness`.

## Task manifests

Both experiment and figure manifests use the same versioned task contract:

```json
{
  "schema_version": 1,
  "tasks": {
    "sweep": {
      "description": "Project-specific parameter sweep",
      "command": [".venv/bin/python", "analysis/sweep.py", "configs/sweep.json"],
      "inputs": ["analysis/sweep.py", "analysis/model.py", "configs/sweep.json", "requirements.lock"],
      "outputs": ["results/sweep.json"],
      "checks": [
        {"command": [".venv/bin/python", "analysis/check_limits.py"], "cost": "cheap"},
        {"command": [".venv/bin/python", "analysis/check_convergence.py"], "cost": "expensive"}
      ],
      "environment": {
        "command": [".venv/bin/python", "-m", "pip", "freeze"],
        "files": ["requirements.lock"]
      },
      "rng": {"generator": "project choice", "seed": 12345}
    }
  }
}
```

A manifest the installer creates has an empty `tasks` object and, beside it, an `example`
holding one sample task to copy under a name of your choice; `example` itself is never
read as a task.

Commands are argv arrays executed at the project root, without shell expansion.
They can invoke any installed project tool; Python is only an example. Paths
must be project-relative files. Inputs/outputs must be nonempty, distinct lists
and must not overlap. Declare imported source, data, parameter configuration,
environment specifications and implicit dependencies explicitly. Local file
arguments to commands/checks are also fingerprinted when present, and so is a
project script executed directly as `command[0]` (a file starting with `#!`);
interpreters and links such as `.venv/bin/python` are recorded as executables
instead. The runner does not infer a complete Python import graph or inspect
scientific parameter semantics. Checks need an explicit `cheap` or `expensive` cost.

Deleted inferred script paths remain dependencies. Prior run records preserve
other inferred file arguments when those files disappear, and changed/deleted
command paths participate in validation selection even before a first run.
Declare inputs explicitly whenever possible; inference cannot reconstruct an
imported dependency that was never declared or observed.

Execution, freshness and validation share a task graph. Duplicate producers and
dependency cycles are configuration errors and stop execution before outputs or
run records are written, including projects without freshness enabled. Stale
upstream results are a separate, documented warning. Refresh suggestions and
status guidance list producers before consumers regardless of manifest order.

Each inspection loads manifests once, indexes the latest archived runs in memory,
and hashes each canonical dependency once. JSON records remain authoritative;
there is no persistent cache to become stale. Archives and snapshots are retained,
so projects with large data should continue to plan their storage explicitly.

Use `make latex-ai-history` for a newest-first index of all archived attempts:
timestamp, module/task, status, and `record.json` path. Direct structured use is
`python3 .latex-ai/workbench.py history --json`. History needs only provenance;
it includes records for task modules that have since been disabled. It reads the
existing archive and never executes tasks, writes an index, or prunes snapshots.
Open the named record for definitions, checks, hashes, and snapshot locations.
Disabling provenance retains the files but hides this command until re-enabled.

```sh
make run TASK=sweep
make figure TASK=phase-diagram
make research-check
make freshness
```

Validation and freshness never launch a declared task. A project's own build command is a
different matter: if it regenerates a file as part of building the paper (a Makefile rule
such as `pdf: figures`), that happens on every check and leaves no run record. Declare such
a step as a task, or keep it out of the build command, when you want it recorded.

`run`/`figure` execute exactly the selected command and its cheap checks. They
never run upstream tasks automatically; when a task that produces one of the
inputs is stale, the run proceeds, prints a warning naming it and lists it under
`stale_upstream` in the record. Outputs/parents should be produced by
the project command. Missing inputs or outputs, failing commands/checks, or
inputs changing during execution fail the run. Repeated successful runs create
new records. Existing target collisions have `latex-ai-run`/`latex-ai-figure`
aliases.

A successful run meets a narrow, mechanical contract. For each declared output the
runner compares the file's identity (modification and change times, size, inode)
before and after the command: it must have changed (rewriting identical bytes
counts), or the latest successful record must already vouch for it. Vouching means
the same task definition, the same input fingerprints and an output matching the
recorded hash, which is what a tool that skips up-to-date targets (for example
`make`) does; such paths are listed under `unchanged_outputs`. Otherwise an exit-0
command that skips an output, or writes it elsewhere, fails and is recorded as failed
instead of reusing a previous result. Without the provenance module there is no
record to vouch, so every output must change (force such tools, for example `make -B`).

This does **not** establish that an output's content came from the current inputs.
A `touch`, `chmod` or any other operation that changes file identity satisfies the
contract, as does a concurrent writer, and it relies on POSIX change times. Two aids
help but prove nothing: when an output has the same bytes as the previous successful
run although the declared inputs or task definition changed, the runner prints a
warning and stores it under `warnings` in the record (legitimate when the change did
not affect the result, but worth a look). Attribution is otherwise the project's job:
declare a cheap check that compares each output with the inputs it should reflect, as
the decay example's check does with the stored `resolved_parameters` and samples, so
that a stale or touched result fails the run, `make check` and CI.

One explicit run of a task at a time: starting a second run of the same task while the
first is in progress is refused ("Another run of ... is in progress") instead of
racing the first run's unfinished record. The lock is the project's own operation lock,
an empty file under `.latex-ai/artifacts/locks/` (ignored by Git), so it holds for every
user and process working in the project; a run that cannot take it does not start. Runs of
different tasks are independent. To explicitly include expensive checks:

```sh
python3 .latex-ai/workbench.py run --task sweep --expensive-checks
```

`check`, `validate` and `research-check` print the freshness report, run declared
cheap checks and fail on stale results when selected/enabled. A cheap check that
fails is reported with its task, and with the commands that refresh the task when
it is stale. Cheap checks should be small, suitable for CI,
and avoid rebuilding canonical outputs. Scientific tolerances, units, limits,
normalization, conservation laws and convergence criteria belong to the model's
own checks, not a universal scientific test suite. A passing check is evidence
only for its specified observable/domain/tolerance.

## Provenance and freshness

With provenance enabled, each explicit run gets a unique directory under its
configured archive. A record includes:

- Complete task definition, command, RNG declaration and definition hash.
- Declared input SHA-256 hashes and copies of their bytes, including source,
  data and configuration; these preserve relevant dirty/untracked input state.
- Read-only Git HEAD/status when available; no Git repository is required.
- Host/Python description, resolved command executables, and captured output of
  the declared environment command (for example package versions).
- Run status (`success`, `failed`, or `interrupted` by Ctrl-C/SIGTERM; a process killed
  outright cannot update its record and stays `running`), error, passed/skipped checks, timestamps, output
  hashes/copies for a successful run, the paths accepted as already current
  (`unchanged_outputs`) and any `warnings`.

Parameter overrides/resolved values/units must be materialized by the project
command into a declared input or result. A Git SHA/seed alone does not preserve
all execution state. Snapshots cover declared dependencies, not unrelated files
or hidden imports. Run records contain declared inputs and captured command output. The runner
does not look up credentials or dump environment variables. Choose environment commands
whose output is appropriate to retain.

`freshness` only reads configuration, records, inputs and outputs. It reports
missing/failed runs, changed task definitions, changed/missing inputs or outputs,
and stale upstream producers. A failed latest attempt remains visible even if
an older result exists. It exits nonzero for stale results; it never changes a
claim status or regenerates results. `current` means matching declared content,
not correct physics, complete dependency declarations, byte-identical reruns on
another machine, or verification of the current live package environment.
Include environment lock/specification files as inputs to detect their changes;
the captured package versions support later reconstruction/review.

Records and input/output snapshots can consume substantial space. Keep small
canonical records/results in Git when appropriate; make a deliberate archival
and `.gitignore` policy for large data. The workbench retains them on disable
and does not garbage-collect or upload them. External data must be materialized
or represented by a durable project-owned input; external data fetching and
environment provisioning are project-specific extensions.

## Notes and claim review

The notes module initially provides `index.md` and `session-state.md` in the
configured directory. They are editable project files; additional derivations,
meetings and decisions can use any layout. There is no automatic conversation
capture or journal generator. Once created they belong to the project: upgrades
never overwrite them and never recreate one the project deleted. The notes check
still expects both files, so after deleting one either recreate it or disable
the notes module.

The optional claim ledger uses `schema_version: 1` and a `claims` array. Each
claim has unique `id`, nonempty `text`, explicit human-assigned `status`
(`proposed`, `supported`, `needs-review`, `rejected`), optional `notes`, and
`evidence` containing project-relative file paths. Supported entries require at
least one existing evidence file. `claims-check` checks structure and links,
and `validate` runs it whenever the ledger or any file it cites changes or is
deleted; it does not determine scientific support or automatically promote/reject claims.
Literature evidence can be a note that cites stable bibliography keys.

The [synthetic example](../examples/decay/README.md) exercises a complete
configuration → RK4 calculation → scientific checks → record → SVG → freshness
workflow without TeX or third-party Python packages.


### Path identity

Dependency matching uses resolved project-local paths, including existing hard
links, instead of raw spellings. For example, `result.csv` and `./result.csv`
identify one output. Input/output aliases and duplicate producers are rejected;
producer staleness propagates through aliases. The original task declaration is
retained in provenance, while input snapshot names are canonical project-relative
paths. Older records using noncanonical input names can become stale once after
upgrading and require an explicit rerun. Run records are published atomically so
readers see complete JSON, including during interruption.
