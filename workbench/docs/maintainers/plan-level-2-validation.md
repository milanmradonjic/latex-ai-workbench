# Level 2 validation routing

Status: Step 1 complete (specification only), 15 October 2026. Runtime behavior
is unchanged. Resume at Step 2. This plan supersedes the earlier plan's retained
selective-routing requirement only in the areas described here.

## Workflow and scope

The owner chose Level 2: lightweight file checks, or those checks followed by full
project validation. Ordinary Markdown, JSON, and Python do not feed the manuscript
directly; results are transferred manually or by an agent into TeX or figure files.
The Dipolar BEC project is a structural example, not an implementation fixture.
Use synthetic documents, figures, analysis scripts, and archives for package tests.

Multiple LaTeX documents, shared output directories, custom argv builders, and
manual document selection remain supported. Scientific calculations, figure
rendering, and typesetting remain separate operations. Validation must not start
numerical calculations, regenerate figures, or replace delivery PDFs implicitly.

## Step 1 — Specify the contract and acceptance cases (complete)

### Routing contract

`make validation-plan` retains a read-only explanation of the chosen level and
triggering paths. `make validate` executes that selection:

- **Files:** existing lightweight syntax, text-integrity, local-link, and applicable
  policy/delegation checks. These are not scientific or numerical tests.
- **Full:** the file checks above, followed by the project's canonical `make check`
  once. This covers every declared document and preserves any custom check work.
  Current build receipts can avoid recompilation; verification and lint still run.

Apply the following rules in order, after the existing inventory exclusions for
generated state, environments, and caches:

| Changed path | Level |
|---|---|
| Inside a directory named exactly `archive` or `baseline`, at any depth | Files, regardless of extension |
| A `.diff` or `.patch` file | Files; check text integrity without interpreting patch contents as source |
| Active build controls: project configuration, Makefiles, latexmk/ChkTeX configuration, lint baselines, vendored runtime, editor integration, and recognised local files in configured build commands | Full, regardless of extension |
| Agent policy, permission files, or skills | Files and policy structure; the agent separately reviews semantics |
| Ordinary Markdown, JSON, Python, and the existing ordinary-document suffixes | Files |
| TeX, bibliography, classes/styles, potential figures, or CSV/TSV data | Full |
| Other unclassified paths | Full |

Archive/baseline directory names are case-sensitive, exact path components;
`archive-old` and `baseline-results` do not match. The convention applies to
historical material, including historical Makefiles and TeX files. The planner
does not inspect or prove its disconnection from the build. A historical file
must move outside those directories before becoming an active build input.

Build-command exceptions use the existing recognised local command-file handling,
not Python interpretation or recursive script discovery. Do not inspect TeX inputs,
compiler recorder files, filesystem identities, or receipt dependency graphs to
decide a changed path's level. Those protections remain in the build machinery.

For automatic discovery, retain staged, unstaged, untracked, deleted, and renamed
paths, the default comparison with HEAD, and `LATEX_AI_BASE`/`--base`. Preserve
read-only Git handling. Missing or invalid comparison history selects Full.
Keep explicit `--files` scope and the existing `--files-only` execution override.

A mixed change selects the higher level. A clean comparison selects no manuscript
check unless an existing failed/interrupted build needs recovery. Preserve that
recovery safeguard, promoting it to Full rather than selecting individual roots.
An explicit `make check` always checks all documents. Manual `make document-check
DOC=name`, bibliography checks, and PDF export remain available independently.

### Acceptance cases

| Synthetic change or state | Expected result |
|---|---|
| `README.md`, `analysis/results.json`, or `analysis/calculate.py` | Files; no compiler or analysis execution |
| `AGENTS.md`, `CLAUDE.md`, or an agent permission file | Files plus policy structure |
| `revision/main.tex` or `revision/figures/plot.pdf` | Full; both roots checked |
| A shared bibliography or class/style | Full |
| `.latex-ai.json`, editor settings, a lint baseline, or the configured `scripts/build_documents.py` | Full despite JSON/Python extension |
| `archive/old.pdf`, `archive/main.tex`, or `revision/baseline/old.bib` | Files; no manuscript check |
| `archive/Makefile` or `revision/baseline/old-builder.py` | Files; historical material stays exempt |
| A `.diff` or `.patch` recording a scientific revision | Files, without parsing its embedded source as code |
| A documentation change together with an active figure change | Full |
| A deleted or renamed active input | Full; both rename sides participate |
| A clean Git comparison with no failed build | No manuscript check |
| A prior failed/interrupted build, even after source reversion | Full until a successful build |
| No Git, an unborn repository, or an invalid base | Full with an explanation |
| A project with extra work in its `check` recipe | Full executes that recipe once |
| The Workbench distribution's Python source changes | Files locally; package tests run explicitly through package Make/CI |

These cases specify future behavior; they are not claims that the current runtime
already implements it. Lightweight checks do not inspect binary PDF contents.

## Step 2 — Replace planner and execution together

Change `runtime.validation_plan`, action selection, and `validate_changes` as one
coherent change. Add the new routing tests first and replace assertions for
deliberately removed behavior. Retain relevant Git/file-integrity regressions.

Remove automatic affected-document selection, routing dependency scans, routing
identity comparisons, standalone bibliography scheduling, and Makefile inspection
used to choose between `check` and individual document checks. Preserve recursive
build protection and the validation recursion guard. Full always calls `make check`.

Keep concise text and JSON plans with level, paths, reasons, fallback, and the
actual actions. Full plans identify all documents; remove per-document dependency
reasons and custom-check inference. Update status/issue consumers of the plan.
Do not keep unused plan fields for compatibility.

Run the focused planner/execution tests and prove that custom `check` work runs
once, file-only selection invokes no compiler, and failed builds force Full.
Do not change receipts, locking, process recovery, or export implementation.

## Step 3 — Remove routing configuration and package special cases

Remove `validation.ignore`, `validation.manuscript_inputs`, and `validation.package`
and their schema, resolution, examples, and test machinery. Refuse removed settings
with a clear hint; do not silently ignore them or provide a conversion layer.
Keep document `inputs`: they still protect build identity and custom-build inputs.

Remove package-location inference and unit/portability scheduling from the vendored
runtime. The distribution retains explicit `make -C workbench test`, `portability`,
and `check`; its hosted jobs already invoke the package checks explicitly. Audit
those jobs and retain required check names and complete release coverage.

Run focused schema, installer, planner, and CI-contract tests. Verify that an
installed project neither discovers nor launches another nested package.

## Step 4 — Update guidance and generated reference

Update validation/configuration docs, the command descriptions, generated agent
policy, skill instructions, and maintained examples to explain the two levels,
archive convention, build-command exceptions, and separate research pipeline.
Remove obsolete selection advice and stale non-LaTeX validation text. Preserve
historical verification records and stricter project-specific Git guardrails.

Version the changed public contract under the release policy. Regenerate the
reference runtime with `make -C workbench upgrade-reference`; never edit `.latex-ai/`
by hand. Check generated-file guards and reference parity. The plan/validate Make
names and explicit document commands remain; no new command is necessary.

## Step 5 — Verify and deliver

Run `make -C workbench check`, reference `make check`, generated-file guards, and
lightweight policy/file checks. Use a synthetic two-root/shared-output project
to exercise the acceptance table, current receipts, exports, and failure recovery.
Show that build freshness still follows real dependencies even though routing no
longer uses them. Inspect the final diff and status; record local passes, skips,
and hosted results separately.

Deliver through a regular topic-branch PR; only the owner merges. No subagent is
part of this plan under the current single-agent policy. If implementation would
require changing protected receipt/lock/process behavior, stop that expansion and
scope it separately rather than folding it into routing simplification.

Do not update or execute the Dipolar project's research pipeline as part of the
package change. Updating its installed integration after the release is a separate
owner-authorized task.

## Resume in a later session

Read this plan and the repository's `AGENTS.md`, inspect status and existing diffs,
then start Step 2. Step 1 added only this specification and its maintainer-index
link. No runtime, configuration schema, generated reference, workflow, or research
project was changed. The planning files may still be uncommitted; preserve them.
