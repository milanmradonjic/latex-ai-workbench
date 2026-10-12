# TeX notes and named document targets

Status: implemented in workbench 2.7.0; validation is recorded in
[the verification note](verification-2.7.md), including the distinction between
local and hosted evidence.
Baseline: workbench 2.6.0, including the completed architecture fixes.

## Implementation decisions

The six phases below are implemented. Legacy backend views retain their old
paths and schema-1-to-2 migration contract; schema 3 resolves immutable document
specifications rather than rewriting existing configuration at dispatch.
Disabled schema-3 LaTeX settings still vendor the lightweight document validator
so a fresh disabled installation can validate retained definitions without TeX.

The adopted default uses the existing outer Make graph. Additional documents
run sequentially after it. Separate literal adopted graphs are supported;
multiple graphs with shared, computed or implicit ownership are rejected with
an adapter hint. Arbitrary shared Make graphs are not generalized in this
release. Existing full-check goals and parents that reach additional adopted
targets also require an adapter. Full `make check` ignores `DOC` selection; document-specific commands
use it. Generated editor settings select explicit named tasks and disable
automatic builds on save, while preserving local customizations.

The full lint/backend portability matrix and Python-version CI require the
complete hosted environment. Local compiler evidence does not substitute for
those checks; the reference's checks and permission guardrails remain intact.

## Intended behavior

A project can contain a paper, several independently compiled TeX notes, TeX
fragments, and Markdown notes. Each declared TeX document has its own build
configuration, dependencies, verified receipt, diagnostics, and PDF export.
Shared sources select every document that consumes them. A TeX fragment belongs
to its consuming documents; its extension alone never makes it a build target.

The notes module organizes project-owned source notes and session state. It
does not decide how they are compiled. LaTeX and Markdown retain their existing
backend responsibilities. A TeX notebook does not require Pandoc, and plain
notes do not require a TeX installation.

## Configuration contract

Introduce schema 3 for named documents and configurable note entry points.
Continue accepting schema 1 and schema 2 without rewriting their configuration.
Normalize all supported schemas into one runtime representation. An old LaTeX
root becomes the document `manuscript`, retaining its existing paths and commands.
The existing explicit migration operation gains a reviewed schema-3 migration;
ordinary upgrade does not migrate configuration or enable additional modules.

An illustrative new project:

```json
{
  "schema_version": 3,
  "modules": {
    "latex": {
      "default_document": "paper",
      "defaults": {
        "engine": "pdflatex",
        "backend": "none",
        "lint": {"enabled": true, "args": []}
      },
      "documents": {
        "paper": {"root": "main.tex"},
        "derivation": {"root": "notes/derivation.tex", "engine": "lualatex"},
        "notebook": {"root": "notes/notebook.tex"}
      }
    },
    "notes": {
      "path": "notes",
      "index": "index.md",
      "session_state": "session-state.tex"
    }
  }
}
```

The example config refers to existing source files. A note entry point can be
Markdown, TeX, or another text format; this is separate from whether it is a
declared compilable document. `index` and `session_state` resolve relative to
`notes.path`, remain inside that directory, and default to the existing Markdown
filenames. Checks validate their existence and path boundaries. Backend checks
apply only when the corresponding module/input or document is declared.

Each document supports `root`, `engine`, `backend`, `lint`, `output_dir`,
`build_command`, and explicit extra input paths/globs. Module defaults apply
before per-document overrides; lint settings merge field by field, with no
shared mutable configuration. Roots and build commands are target-specific.
Source bibliography declarations remain authoritative; project-level export
readiness and duplicate-key checks remain shared. Explicit supplemental
bibliography inputs, where needed, are scoped to their document.

Document IDs use a restricted stable slug syntax, independent of file names.
Reject unknown fields, invalid defaults, duplicate canonical roots, recursive
commands, and overlapping output stems, including symlink aliases. Disabling
LaTeX retains document definitions and source/artifact files. Disabled targets
are not built or required to have usable toolchains.

## Command contract

| Command | Behavior |
|---|---|
| `make latex-ai-documents` | List document IDs, roots, engines and validity state; read-only |
| `make latex-ai-build DOC=derivation` | Build one named document and establish its receipt |
| `make latex-ai-document-check DOC=derivation` | Build, verify and lint one named document |
| `make latex-ai-pdf-artifact DOC=derivation` | Export that document only after verifying its current receipt |
| `make latex-ai-lint DOC=derivation` | Lint one document through a reserved workbench target |
| `make latex-ai-clean DOC=derivation` | Apply existing cleanup rules to one document; invalidate its receipt |
| `make check` | Check every declared document and each enabled shared module |
| `make latex-ai-plan` | Report affected document IDs and reasons without executing commands |
| `make latex-ai-validate` | Check the documents and other modules selected by changed inputs |

Direct runtime commands accept `--document ID`. Build, lint, verify, export and
clean use `default_document` when the selector is omitted. Full project checks
cover all documents; a targeted document check covers only the selected document
and its bibliography/build requirements. It does not silently run scientific
tasks. Invalid selectors fail before modifying receipts or launching commands.

The installer exports `DOC` into recipe environments and passes its value as a
quoted argv argument. It never interpolates the value into shell source or
uses it as a filesystem path without validating it. Existing project target
names and recipes remain authoritative; reserved workbench targets provide
unambiguous access to the new operations.

## Implementation sequence

### 1. Establish the document model and compatibility boundary

Primary files: `core.py`, new `documents.py`, `bootstrap.py`, module tests.

- Implement immutable document specifications, default resolution, canonical
  identities, and the schema-3 validators/normalizer.
- Keep `latex_config()` as a compatibility adapter that resolves one selected
  document into the existing backend view. Backends receive a resolved target;
  they do not independently choose defaults.
- Normalize schema-1/2 roots in memory. Preserve old explicit migration
  behavior through documented version handling and provide schema-3 dry-run
  diffs. Carry disabled configurations and local settings through migration.
- Compute required tools as the union across enabled documents. Targeted
  operations require only the selected document's tools.
- Vendor the new document module when LaTeX is enabled; verify notes-only and
  numerics-only installed projects remain independent of it.

Acceptance: existing configurations still execute with their previous behavior;
new configurations can resolve two different engines; collisions and malformed
selectors fail before any project mutation.

### 2. Isolate builds, receipts, artifacts and lint policy

Primary files: `latex.py`, `documents.py`, build/receipt regressions.

- Pass resolved document identity through compilation, bibliography checks,
  linting, verification, export, and cleanup.
- For new named targets, use
  `.latex-ai/artifacts/documents/<id>/build/` as the default compiler output
  directory, with a sibling `build-receipt.json` and exported `document.pdf`.
  Respect explicitly configured existing output locations after collision checks.
- Include target identity and its effective configuration in receipt comparison.
  Discover inputs using existing literal traversal, explicit declarations, and
  that target's compiler recorder file. A document configuration change must not
  invalidate unrelated receipts unless shared inputs changed.
- Preserve failure invalidation, input mutation detection, output regeneration,
  owner PID/start-time checks, and stale export rejection. Failed note builds
  cannot revive or overwrite another document's receipt or export.
- Keep the project-wide build exclusion contract for the first release, including
  adopted Make phase ownership. Serialize document builds; unknown custom
  recipes can modify shared files even when configured output directories differ.
  Maintain a project-wide active-build record across prepare/finish processes,
  separate from individual receipts. Ownership covers the complete build, not
  just the short calls that update a receipt; abandoned ownership is diagnosed
  using the existing PID/start-time rules.
- Preserve legacy build/receipt locations for schema-1/2 installations and the
  default-document `manuscript.pdf` compatibility export. Existing receipts are
  reused only if their complete recorded identity/configuration still matches;
  otherwise require a new verified build.
- Add target-specific lint baseline paths. Preserve the legacy project baseline
  for old configurations and migrated legacy targets. Writing or refreshing a
  baseline remains an explicit owner decision.
- Invalidate the selected receipt before cleanup, including cleanup failures.
  Retain the existing restriction on cleanup of custom builds.

Acceptance: two `main.tex` files in different note directories produce independent
outputs; a failed or stale note cannot affect a valid paper; repeated unchanged
builds retain incrementality; concurrent commands cannot cross-associate receipts.

### 3. Add format-independent notes and explicit setup

Primary files: `research.py`, `bootstrap.py`, templates, examples.

- Replace hard-coded Markdown filenames in inspection and seed ownership with
  configured index/session-state paths. Retain Markdown defaults for all existing
  notebook installations and preserve their contents during upgrade.
- Add an explicit `tex-notebook` setup profile. In a fresh directory, it seeds
  `notes/index.tex` as a standalone notebook and `notes/session-state.tex` as an
  included fragment, then declares only the notebook root as a document.
- Support explicitly adding a document with
  `configure --document ID --root PATH`, with optional per-target engine/backend
  and build-command choices. Add an explicit default-document selection option.
- Discovery reports multiple standalone roots as candidates; it never enrolls
  every `.tex` file automatically. A legacy `--root` still selects one root.
- Seed supported Markdown/TeX entry points only when explicitly requested and
  missing. Other text formats must already exist. Existing source files remain
  project-owned and are never overwritten or deleted by disable/upgrade.
- Validate planned fresh-profile sources without writing to the project during
  audit/dry-run; installation applies configuration and sources transactionally.
- Add TeX-only and mixed-note examples, including a fragment and shared macros.

Acceptance: a fresh TeX notebook works without Pandoc; a mixed index/session
format works; edited existing notes survive configure, upgrade and disable;
dry-run creates no project files and executes no compiler.

### 4. Route validation and expose per-document results

Primary files: `runtime.py`, `documents.py`, `guide.py`, `diagnostics.py`.

- Build a dependency index keyed by document ID using canonical path identities.
  Share the existing path utilities; retain research `TaskGraph` for scientific
  tasks rather than representing document builds as experiments.
- Add selected document IDs and per-target reasons to validation-plan JSON.
  Retain the `manuscript` boolean as an aggregate compatibility signal.
- Editing a known document input selects all its consumers. Shared macros,
  figures, bibliographies and deleted dependencies select every affected target.
  Shared build policy, unknown TeX/resources, macro-generated inputs, or missing
  comparison/dependency information conservatively select all document targets
  and explain the fallback. An unrelated Markdown note does not select TeX unless
  it is a declared or observed input.
- Ensure selective execution consumes the exact plan rather than calling an
  unqualified full check that would build every root. Shared module checks run
  once, and scientific task execution remains explicit.
- Add document-aware status/help/issue reports and structured command results.
  Aggregate checks return nonzero if any document fails and identify every
  failing document; no aggregate success is printed on partial failure.
- Keep inspection read-only and report stale/missing/running receipts without
  repairing state or rebuilding as a consequence of inspection.

Acceptance: editing one note selects only that note; shared macros select their
consumers; deleted/uncertain inputs cannot escape checking; failed document IDs
are visible in human and JSON reports.

### 5. Integrate canonical Make, CI and editor commands

Primary files: `adapters.py`, `guide.py`, `bootstrap.py`, Make/editor templates.

- Extend the shared command table with document listing/checking and a reserved
  lint target; generate selector-aware recipes and matching guidance from it.
- Preserve single-root adopted Make behavior and its one-compiler/incrementality
  guarantees. Route additional documents through separate canonical wrappers;
  never infer their custom build command from the project's existing `build` target.
- For multi-document adopted projects, extend `check` with all registered
  documents while retaining existing recipes. Generalize prepare/finish hooks
  by target identity and preserve the existing GNU Make 4.3+ requirement.
  Generate an explicit sequence between document completion phases so parallel
  Make cannot launch a second document while the first has active ownership.
  Shared raw Make prerequisites must still execute once in a single Make graph;
  ambiguous overlapping custom build ownership requires an explicit adaptation.
- Have CI consume the selected IDs from the same plan, invoke canonical Make
  targets, and collect/upload separately named PDFs only for documents that
  passed verification. Run project-level research/Markdown checks once. Missing
  comparison history produces full coverage. Explicit full checks build all roots.
- Generate named editor tasks that call these Make commands. Preserve existing
  editor settings and avoid imposing one global output directory on targets with
  different layouts. Keep existing single-root editor behavior unchanged.
- Extend ignored output paths for every target, including disabled definitions,
  without ignoring source notes or tracked installation state.

Acceptance: terminal, editor tasks and CI select the same documents; an adopted
paper is compiled once under parallel Make; two exported PDFs never overwrite
one another; custom recipes and existing aliases remain intact.

### 6. Verify migration, user workflows and release readiness

Primary files: tests, `tests/portability.py`, user/maintainer docs and operating skill.

- Retain the existing regression suite (210 tests at this baseline). Add
  behavior-focused regressions for selection, per-target failures, configuration
  isolation, collision rejection, receipt isolation, and migration/rollback.
- Cover notes-only, single TeX notebook, paper plus multiple TeX notes, mixed
  Markdown/TeX notes, shared resources, included fragments, identical stems,
  custom/adopted Make targets, and disabled/re-enabled LaTeX.
- Exercise real pdfLaTeX, LuaLaTeX and XeLaTeX builds; BibTeX/Biber; fresh checkout
  selection; changed/deleted inputs; relocation; source changes during builds;
  repeated incremental builds; and parallel adopted Make invocations.
- Run independent code review before release. Use inexpensive blind validation
  agents for installed user workflows, supplying the published instructions and
  expected goals rather than implementation details.
- Update module/configuration, installation/migration, daily-use, validation,
  notes examples, skill guidance, release notes and verification evidence.
- Audit and check the unchanged reference manuscript through its current
  schema-2 configuration, and run compatibility CI on Python 3.10–3.14 plus the
  existing full TeX environment. Demonstrate that no manuscript/bibliography
  content or permission policy changes were required.

Completion requires both backward compatibility and the new multi-document
workflows to pass. Publish only after the implementation and verification evidence
are concrete and reviewable, within the owner's authorization for that work.

## Scope boundary

This increment adds handwritten TeX notes, explicit document targets, and shared
organization of mixed-format notes. It does not add a TeX parser, automatic
Markdown-to-TeX conversion, executable notebook cells, cross-document references,
or automatic regeneration of scientific outputs. Document-level parallel build
scheduling can follow later once custom-build ownership is explicit and tested.
