---
name: latex-ai-workbench
description: Bootstrap, review, update, edit, and review projects using the local LaTeX AI Workbench. Use for its manuscript workflows; follow declared documents, canonical Make commands and project policy. Preserve human approval for Git mutations.
---

# LaTeX AI Workbench operating skill

Use the workbench as deterministic infrastructure for the project's declared LaTeX documents. Start
with the selected project's AGENTS policy; CLAUDE delegates to it. Read the
project config and Makefile to learn declared documents, paths, commands and conventions. Do not
copy an example's root name or bibliography style into an unrelated manuscript.

This skill gives procedure, not authority. Respect the user's project scope,
application boundary and existing approvals. It does not authorize access to
other research projects, sending prompts to another chat/model, configuring
desktop applications, or changing Git state.

## Route by task

- For setup, review or update, read [installation procedures](references/installation.md).
- For independent or cross-model review, worktree coordination, or preparing
  human approval, read [review procedures](references/review.md).
- For normal manuscript edits, follow the workflow below. Load the other
  references only when needed.

Normally run `make validate` directly: it explains and executes its selection.
Use `make validation-plan` first only when the preview will affect a decision.
Ordinary Markdown, JSON, Python and notes
receive file checks; test calculations and unrelated code separately. TeX,
bibliography, figures, configured builders and build settings select `make check`
for every document. Policy changes also require semantic review.

Directories named exactly `archive`, at any depth, hold historical material and
get file checks regardless of extension; a path `.latex-ai.json` names stays active.
`.diff` and `.patch` get text-integrity checks. Copy or move historical files out
before making them active inputs.
Routing does not inspect manuscript dependencies. Build freshness and export
still use full dependency tracking and receipts. Transfer research results
explicitly into TeX or figure files; do not turn document checks into automatic
numerical or figure-regeneration pipelines. Preserve the project's declared
custom builder contract.

For committed reviews use `LATEX_AI_BASE=<verified revision>`; missing history
or a failed/interrupted build selects the complete project. Package tests and
compiler portability are explicit maintainer Make/CI commands. See the
[validation guide](../../docs/validation.md).

## Named documents

For schema-4 named documents, read [TeX notes](../../docs/tex-notes.md). `make check` covers every declared
document. Use `make document-check DOC=NAME` for one document and
`make pdf-artifact DOC=NAME` for its verified export. Included TeX
fragments are checked through their consuming document. Preserve handwritten
sources; a project's own build steps are Make targets or scripts that `build_command` names.

Use declared paths and the project's tool environment. Every project has LaTeX
documents; ordinary documentation and code can coexist with them. `make check`
checks all documents. Input hashes and green checks do not prove scientific validity.

## Manuscript editing workflow

1. Inspect branch, status and current diff before changing files. Distinguish
   existing user changes from your work. Do not reset, restore or clean them.
   Read the root and relevant input files, macros and local notation. Inspect
   the canonical validation path without rewriting it.
2. Determine the requested scientific and structural scope. Preserve macros,
   equation numbering, citation keys, labels, bibliography style and prose
   conventions unless the task actually requires a change. For an uncertain
   scientific claim, identify what evidence or assumption is missing; do not
   fill the gap with plausible invented data or literature.
3. Make a focused edit. Match surrounding math delimiters, fraction notation,
   macro use, line breaks and spacing. Avoid whole-file formatting. If a label
   or macro must change, trace consumers across the active manuscript first.
4. Check scientific reasoning at the appropriate depth: definitions and domain,
   assumptions, dimensions/units, signs, limiting cases, normalization and
   consistency between equations, text and figures. Deterministic build success
   is evidence of valid typesetting, not correct science.
5. During a manuscript editing batch, use `make build DOC=name` when a PDF
   preview is needed. Run `make validate` from the project root when the
   requested batch is complete, before delivery or Git handoff; a single editing
   request ends at delivery. Intermediate previews do not complete validation.
   Capture complete compiler output in a generated log, retain the exit status,
   and return a concise result with relevant warnings and failure context.
   Reuse session context and inspect the relevant source range and diff for small
   follow-up edits. Diagnose observed output. Separate
   syntax/build failures, undefined references/citations, duplicate keys/labels,
   stale rerun requests, and advisory typesetting warnings. Fix introduced
   problems; report pre-existing issues without silently broadening the task.
   Do not weaken lint or permission settings to obtain a green result.
6. Inspect `git diff --check`, the final diff and status. Report changed source,
   validation results, relevant warnings and unresolved assumptions. Human
   approval comes after a concrete, reviewable change is ready.

Use a second model when its independent assessment can improve confidence in
consequential science, structure or integration. Ordinary typos do not need a
writer/reviewer ceremony. Either Codex or Claude can write or review; use the
user's existing subscription-authenticated workflow and preserve credentials.

## Bibliography judgment

Determine whether each `.bib` is authored or generated. Read config's export
declaration and the bibliography guide supplied with the package when available.
Do not edit generated Zotero exports or repair metadata with an LLM. Obtain a
human-confirmed source correction and stable re-export. Preserve cited keys;
changing a key requires updating actual citations deliberately.

Build from local repository contents. Do not call Zotero or remote exporters
as part of Make/CI. Required exports must exist and contain entries. Use
`make bib-check` for file/key readiness and `make check` for compiler/backend
validation. For macro-generated paths, declare known files in config rather
than treating static discovery as a full TeX interpreter.

When manual Zotero configuration is required, stop and name one exact action,
application, value/path and result to report. First establish whether Better
BibTeX is installed/enabled; then obtain the target collection before an export.
Use Better BibTeX (a biber paper lists its `.bib` under `bibliography.files` and has no `export`), keep the export updated,
sort by citation key and avoid automatic Git push. Do not invent a collection
or export another project's sources. The user controls GUI applications.

## Safety invariants

- AGENTS is canonical semantic policy. Avoid a second independent rule set in
  CLAUDE, editor prompts or this skill.
- Make commands are canonical; the editor invokes them instead of replicating
  TeX command logic. Preserve the project's own build steps.
  Commands have fixed names: `make build DOC=name` and `make all` select documents.
  There are no reserved aliases; local overrides are an explicit project customization.
- Git reads are allowed. Staging, commits, pushes/pulls, integration, branch
  changes, stashes, resets/restores/cleaning and worktree changes require the
  owner's explicit approval. Existing session authorization remains valid for
  its stated operation and scope; do not ask twice or assume a broader grant.
- Do not weaken local Codex/Claude guardrails. Prefix rules supplement semantic
  policy; they do not protect against all alternative command forms.
- A suspected workbench defect (`INTERNAL ERROR`, a verdict that contradicts
  its inputs or a check that skips what it should cover) is reported, not repaired in passing:
  distrust that verdict for the task, never edit `.latex-ai/` or weaken a check, capture
  evidence with `make issue ISSUE_NOTE="..."`, and tell the user. Ordinary failures such as a
  stale report or a failing scientific check are not defects.
- Safe file edits and validation proceed autonomously. Pause for a consequential
  ambiguity, GUI action, destructive operation, privileged/system change or
  action outside the authorized filesystem, naming the concrete blocker.
