---
name: latex-ai-workbench
description: Bootstrap, review, update, edit, and review projects using the local modular LaTeX AI Workbench. Use for its manuscript workflows; follow enabled modules, canonical Make commands and project policy. Preserve human approval for Git mutations.
---

# LaTeX AI Workbench operating skill

Use the workbench as deterministic infrastructure for the project's enabled modules. Start
with the selected project's AGENTS policy; CLAUDE delegates to it. Read the
project config and Makefile to learn enabled modules, paths, commands and conventions. Do not
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

For notes, documentation, policy or unrelated code, choose validation by changed
files. Ordinary non-LaTeX files belong alongside the manuscript; editing them
does not require a manuscript build. Preview with `make validation-plan`, then
use `make validate` and any task-specific code/format tests. Check the reported
selection against actual dependencies. Included Markdown/code, figures/data,
build configuration and uncertain inputs need manuscript checks. Policy changes
also need semantic review; structural validation cannot prove safe permissions.
For committed review changes use `LATEX_AI_BASE=<verified revision>`; for a full
manuscript check use `make check`. Read the package's
[validation guide](../../docs/validation.md) for comparison behavior.

## Named documents and modules

For schema-3 named documents, read [TeX notes](../../docs/tex-notes.md). `make check` covers every declared
document. Use `make latex-ai-document-check DOC=NAME` for one document and
`make latex-ai-pdf-artifact DOC=NAME` for its verified export. Included TeX
fragments are checked through their consuming document. Preserve handwritten
sources; a project's own build steps are Make targets or scripts that `build_command` names.

For module selection/disable and adapter choices,
read [modules](../../docs/modules.md). Use the project's declared paths and tool environment; LaTeX is optional.

Preview change-aware checks. Notes-only changes do not need a manuscript build.
`make check` runs full manuscript checks only when LaTeX is enabled. Review units,
tolerances and assumptions yourself; input hashes and green checks do not prove
scientific validity. Preserve sources when disabling modules.

## Manuscript editing workflow (LaTeX enabled)

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
5. For manuscript edits, run `make check` from the project root. For other edits,
   use the change-aware validation above. Diagnose observed output. Separate
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
Use Better BibTeX, keep the export updated,
sort by citation key and avoid automatic Git push. Do not invent a collection
or export another project's sources. The user controls GUI applications.

## Safety invariants

- AGENTS is canonical semantic policy. Avoid a second independent rule set in
  CLAUDE, editor prompts or this skill.
- Make commands are canonical; the editor invokes them instead of replicating
  TeX command logic. Preserve the project's own build steps.
  This skill writes commands by their short names. Where the project gave such a name a
  recipe of its own, the workbench command is the
  `latex-ai-` form; `make latex-ai-help` lists the names that apply in a project.
- Git reads are allowed. Staging, commits, pushes/pulls, integration, branch
  changes, stashes, resets/restores/cleaning and worktree changes require the
  owner's explicit approval. Existing session authorization remains valid for
  its stated operation and scope; do not ask twice or assume a broader grant.
- Do not weaken local Codex/Claude guardrails. Prefix rules supplement semantic
  policy; they do not protect against all alternative command forms.
- A suspected workbench defect (`INTERNAL ERROR`, a verdict that contradicts
  its inputs or a check that skips what it should cover) is reported, not repaired in passing:
  distrust that verdict for the task, never edit `.latex-ai/` or weaken a check, capture
  evidence with `make latex-ai-issue ISSUE_NOTE="..."`, and tell the user. Ordinary failures such as a
  stale report or a failing scientific check are not defects.
- Safe file edits and validation proceed autonomously. Pause for a consequential
  ambiguity, GUI action, destructive operation, privileged/system change or
  action outside the authorized filesystem, naming the concrete blocker.
