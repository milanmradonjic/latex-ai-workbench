# Repository purpose

Read `.latex-ai.json` for enabled modules, paths, project commands and validation
choices. Schema 3 is the only supported project configuration. It describes optional
modules, named TeX documents, and configurable note entry points. This file is the canonical
semantic policy; `CLAUDE.md` delegates here.

# Editing principles

- Treat LaTeX source as authoritative. Prefer minimal, reviewable changes.
- Preserve notation, macros, labels, references, citation keys, equation
  numbering, and document structure unless the requested task requires changes.
- Preserve local LaTeX style: math delimiters, fraction notation, spacing,
  equivalent syntactic forms, and existing macros.
- Do not reformat or rewrite unrelated material.
- Never invent references, bibliography metadata, numerical results, data,
  or literature claims. Resolve metadata problems at their source with a human.
- For scientific edits check definitions, assumptions, units, signs, limiting
  cases, and consistency with surrounding equations and prose.
- Do not edit generated build files. Do not hand-edit a bibliography declared
  as a Zotero/Better BibTeX export; fix the source record and export again.

# Canonical validation

Use the project Makefile from the repository root:

    make check               # enabled modules; full manuscript checks when LaTeX is enabled
    make latex-ai-build      # configured build with a verified receipt
    make latex-ai-documents  # declared documents and build validity
    make latex-ai-document-check DOC=name  # check one named document
    make lint                # configured static checks
    make latex-ai-bib-check  # bibliography boundary/key/export checks
    make latex-ai-doctor     # tools required by enabled modules
    make latex-ai-plan       # preview checks selected by changed files
    make latex-ai-validate   # run the selected checks
    make latex-ai-help       # this project's commands, by the names that work here
    make latex-ai-status     # where the project stands and what to do next

Every command except `check` and `lint` is named in this file by its `latex-ai-`
form, which always reaches the workbench. The shorter everyday names (`doctor`, `validate`
and so on) are aliases only where this project's Makefile had no target of that name;
where it had one, its own recipe was kept. `make latex-ai-help` shows which names apply here.

Choose validation according to what changed. Ordinary documentation, notes and
unrelated files belong in this repository and do not require a manuscript build.
`make latex-ai-validate` checks changed files, runs workbench tests when relevant, and
invokes `make check` for manuscript inputs, potential figures, build/configuration
changes or uncertain inputs (with schema-3 named documents: the affected documents'
checks, or `make check` when the project's Makefile has its own check rule). Policy changes need structure checks and semantic
review; unrelated code also needs its own relevant tests. A Markdown or code
file consumed by LaTeX is a manuscript input. `make latex-ai-plan` explains
the selection; missing comparison history conservatively selects full checks.
Use `LATEX_AI_BASE=<revision> make latex-ai-validate` to include already committed changes.
`make check` performs full document validation when the LaTeX module is enabled;
schema 3 checks every declared root. Document build/export commands accept
`DOC=name`; without it they use the default. Included TeX fragments are inputs
to their consuming documents, not independent build targets.
`make latex-ai-modules` reports the enabled modules. A project's own build command may
still regenerate files it depends on; that is part of the build. The workbench does not
establish scientific validity: inspect assumptions, units and tolerances yourself.

After edits inspect `git diff` and `git status`, and report selected validation,
results, relevant warnings, and unresolved issues. Diagnose
failures before modifying source; fix errors introduced by the task. Do not
silence failures by disabling checks without an explicit design decision.
A document's configured lint baseline lists the style warnings the owner accepted;
the check fails only on new ones, and a line you edit counts as new. Creating or
refreshing that baseline (`make latex-ai-lint-baseline`) is the owner's decision,
like changing the lint settings: ask first, and never do it to get a passing check.
The compiler and BibTeX/Biber are authoritative for TeX expansion and
bibliography semantics. Static inspection is not a replacement for them.

Clean build files (`make latex-ai-clean`, where the workbench provides it) only when
stale build state is suspected or explicitly asked for. It is not a routine validation step. CI and editor integrations must call
the same Make commands; CI builds exclusively from repository contents.

# Git safety

- Inspect branch, status, and diff before editing; preserve user changes.
- Git mutations require explicit user approval, including staging, committing,
  initializing/cloning repositories, writing Git configuration,
  pushing, pulling, merging, rebasing, resetting, restoring, cleaning, stashing,
  branch changes/deletion, worktree creation/removal, and history rewriting.
- Changes reach the default branch (`main` or `master`) only through a pull request
  from a topic branch; never push, merge or fast-forward to it directly. Agents open
  pull requests; only the owner merges them, on the hosting service or from their own
  terminal. When asked to merge, give the pull request's link instead. The agent rules
  refuse pushes to the default branch and merging pull requests.
- Do not weaken agent permission rules. They supplement this policy; they do
  not guarantee protection against every shell or programmatic Git invocation.
- Keep changes within the requested project and task. Do not infer permission
  to edit other projects, configure applications, or publish results.

# Suspected workbench defects

The workbench is shared infrastructure. Its failures are not yours to hide, nor to repair in passing.

- Ordinary outcomes are not defects: a failing lint check, a missing citation. Fix the work, not the checker.
- Treat as a suspected defect: `INTERNAL ERROR` output (the workbench exits 70, which `make`
  reports as `Error 70` while exiting 2 itself, so go by the label); a "current" or
  "success" result that contradicts the declared inputs or outputs; a check that passes or
  skips something it should cover; a command changing state outside its scope (Git, files);
  non-deterministic results; behaviour that contradicts the documentation.
- Then do not rely on that verdict for the current task. Do not edit `.latex-ai/`, weaken or
  disable a check, or treat a failing check as passed. Use only a documented workaround.
  Capture evidence with `make latex-ai-issue ISSUE_NOTE="observed ... expected ..."` (a local report;
  nothing is sent anywhere), and tell the user what happened, what it affects and what you
  verified independently.
- Repairs belong in the workbench distribution, with a regression test that fails first and
  an independent review, and need the user's approval like any other change.

# Writer/reviewer workflow

Either Codex or Claude may write or review. The workbench package (it is not part
of this project; the owner knows where it is kept) holds an optional playbook,
`skills/latex-ai-workbench/`, for bootstrap, review and upgrade tasks. Review correctness, scientific reasoning, compilation, citations,
local style, and scope separately; mark preference-only suggestions clearly.
Do not require a second model for trivial edits. Present changes and validation
results for human approval before any Git mutation.

# Response style

Default to concise, technically precise responses. Lead with the result and
report important decisions, validation, and unresolved issues. Increase depth
for scientific or mathematical reasoning. These preferences do not impose terse
prose on manuscript text or documentation.
