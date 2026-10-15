# Simplification after 4.10.2

Status: implemented and independently checked for 5.0.0, 15 October 2026. See [verification](verification-5.0.0.md).

The owner approved planning these three reductions: require LaTeX projects, make
installation explicit, and standardize commands and guidance. There are no real
projects using this or earlier releases, so migration and backward compatibility
are not requirements. Earlier scope decisions remain historical evidence; this
plan supersedes their decisions only in the areas named here.

## Scope and invariants

- Every configured project has at least one named LaTeX document and one explicit
  default document. Multiple documents and shared output directories remain supported.
- Bibliography checking remains optional within a LaTeX project, including shared
  files, per-document selections, and Zotero/Better BibTeX export checks.
- Keep native pdflatex/BibTeX builds and explicit custom argv build commands.
- Keep receipts, dependency discovery, locks, process recovery, atomic export,
  lint baselines, snapshots, editor integration, and the vendored runtime.
- Keep changed-file classification, per-document validation selection, ignore
  safeguards, and conservative fallback behavior. Coarser validation was the
  fourth implementation step and is outside this plan.
- Make remains the canonical interface. AGENTS.md remains the canonical agent policy.
- Do not refactor immutable document containers, redesign receipts, remove fixed
  engine/export-format fields, or change the custom-build contract in this work.
- No migration command, old-schema reader, compatibility alias, or automatic
  conversion of prior installations. Historical verification records stay intact.

## Intended interface

Use a new configuration schema (schema 4) with project-level `documents`,
`default_document`, optional `bibliography`, `validation`, and `integrations`.
Remove the `modules` wrapper and module enable/disable semantics. Preserve the
meaning of document settings and shared bibliography defaults; missing optional
bibliography settings mean no additional bibliography boundary/export checks.
Document resolution must still produce the settings the retained build code needs.

Installation reads an explicitly prepared `.latex-ai.json`. A small documented
example is the starting point for an agent or owner; a separate configuration
wizard is unnecessary. `init` validates this file and the declared roots before
planning any writes. Missing or invalid configuration produces a specific error
and points to the example. It never guesses roots, bibliography files, a default
document, or another engine from source contents. Custom commands remain JSON argv.
Editor preference is declared in configuration rather than competing setup flags.

Use one fixed public Make vocabulary:

| Purpose | Command |
|---|---|
| Build default or selected document | `make build [DOC=name]`; bare `make` builds the default |
| Build every document | `make all` |
| Check the complete project | `make check` |
| Check one document | `make document-check DOC=name` |
| Lint selected/default document | `make lint [DOC=name]` |
| Inspect documents and project | `make documents`, `make status`, `make doctor` |
| Select validation | `make validation-plan`, `make validate` |
| Bibliography and PDF export | `make bib-check [DOC=name]`, `make pdf-artifact [DOC=name]` |
| Help and local support report | `make help`, `make guide`, `make issue` |
| Existing maintenance actions | `make clean`, `make lint-baseline`, `make snapshot`, `make snapshots` |

Remove generated `make NAME` document targets, `latex-ai-*` duplicates,
`document-lint`, and the `modules` action. Do not remove unrelated runtime-only
actions such as receipt verification. Keep one registry for CLI dispatch,
generated recipes, and help. Fixed help may list configured documents and paths;
it does not discover command names by interpreting Make recipes.

The installer remains create-only: it refuses conflicting existing Makefiles
rather than adopting them or silently omitting commands. Owners can later add
their own targets; redefining a documented workbench target is an explicit local
customization. Guidance describes the supported template interface and does not
claim to verify arbitrary Makefile edits.

## Implementation sequence

### 1. Require LaTeX projects and remove module modes

Change configuration validation and resolution first, followed by runtime dispatch,
doctor/status/help, installer rendering, templates, and test fixtures. Remove the
module registry and gating, standalone bibliography/core-only branches, and the
shared-settings path that exists only for projects without documents. Replace
module reports with document/project information where needed.

Acceptance:

- Missing/empty documents, an unknown default, and unsupported schema/module
  configuration fail as ordinary configuration errors before build or install writes.
- A two-document fixture builds/checks each document and the whole project.
- Shared output folders and shared/per-document bibliography selections still work.
- A project without bibliography checks remains a valid LaTeX project.
- Help, status, and issue capture still explain malformed/missing configuration.

### 2. Replace installer inference with explicit configuration

Remove recursive project inventory used for configuration guesses, source-based
engine/backend detection, and the configuration-selection flags they serve.
Remove obsolete report fields and hints. Keep direct checks of declared paths,
tool requirements, generated-file conflicts, and editor files being installed.
Retain `init`, preview/diff behavior, and runtime refresh; these operate on the
new explicit configuration and do not convert old installations.

Acceptance:

- Identical configuration produces the same planned installation even when extra
  undeclared TeX/Bib files are present.
- Missing declared roots and malformed custom argv fail without partial installation.
- A declared custom builder is accepted without source guessing; doctor checks its
  executable rather than requiring the native toolchain unnecessarily.
- Preview, create-only refusal, interrupted-init completion, idempotence, and
  runtime refresh retain their existing safety properties.
- Explicit multi-document configuration installs correctly; no single-root-only
  setup shortcut becomes the effective supported path.

### 3. Standardize Make recipes and guidance

Simplify the registry to one Make name per public command and render fixed recipes.
Remove alias collision selection and generated document-name targets. Rewrite help,
guide, status hints, installer closing advice, and diagnostics to use that vocabulary.
Update editor tasks, agent instructions, package skill, snapshots documentation,
workflows, and maintained examples that invoke renamed commands.

Remove Make parsing used only to choose guidance names. Retain the narrow parsing
needed for custom `check` preservation in validation and for recursive custom-build
protection. In particular, keep `project_check_rule` behavior: selecting documents
must not bypass additional checks in a customized project Makefile. This step does
not authorize simplifying the validation planner.

Acceptance:

- Every command printed in help, status, or setup advice exists in a fresh install.
- `DOC` selection works for build, lint, check, bibliography, and export; unknown
  names fail clearly. `make check` still checks all documents.
- No duplicate reserved aliases or automatic document-name recipes are generated.
- Projects with extra custom `check` work still receive complete validation.
- Guidance never recommends a cleanup/custom target because its name matches a document.
- Existing command-argument quoting and environment-variable safety remain covered.

## Integration, validation, and delivery

Keep the final configuration, installer, command registry, rendered fixtures, and
reference installation together in one implementation commit: they form one
interface and their tests must agree. Record independent-review findings and any
repairs separately. Use one regular PR for the three reductions, separate from
the merged 4.10.2 audit PR. Do not merge or rewrite the audit branch.

For each stage, run the affected tests through the package Make interface. Replace
tests whose behavior is deliberately removed with rejection tests; retain safety
coverage and meaningful assertions for the surviving features. Do not preserve
whole obsolete mode suites merely to keep the old test count.

At integration:

1. Run `make -C workbench check` (unit regressions and real-TeX portability).
2. Regenerate the reference runtime through the package target, never by editing
   `.latex-ai/` directly. Update the reference configuration, Makefile, policy, and
   editor files to the new contract as maintained source.
3. Run the generated-file/reference guards, reference `make check`, and explicit
   two-document/shared-output and custom-builder smoke cases.
4. Check current templates, docs, skill instructions, and workflows for removed
   module/configuration/command vocabulary. Exclude historical records from rewriting.
5. Confirm the hosted Python matrix and TeX validation pass with required job names
   unchanged. Record local passes, skips, and hosted results separately.

Record the behavior removals and new interface in release notes and a verification
record. Select a release version according to repository release policy; the schema
and command changes must be explicit. No migration guide or compatibility layer is
part of the deliverable. If work unexpectedly requires changing locking, receipt,
or process semantics, stop that expansion and scope it separately.

Completion means a LaTeX-only tool with explicit configuration and one documented
command interface, while the retained validation and build protections still pass.
