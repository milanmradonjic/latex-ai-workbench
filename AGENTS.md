# Repository purpose

Read `.latex-ai.json` for named LaTeX documents, paths, project commands and validation
choices. Schema 4 is the only supported project configuration. Every project needs
at least one LaTeX document; bibliography checks and editor integration are optional. This file is the canonical
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

    make check               # full checks for every declared document
    make build      # configured build with a verified receipt
    make documents  # declared documents and build validity
    make document-check DOC=name  # check one named document
    make lint                # configured static checks
    make bib-check  # bibliography boundary/key/export checks
    make doctor     # tools required by declared document settings
    make validation-plan       # preview checks selected by changed files
    make validate   # run the selected checks
    make help       # the fixed command interface
    make status     # where the project stands and what to do next

Make commands have fixed names from the generated template. `make build DOC=name`
builds one document; bare `make` builds the default and `make all` builds every document.
Local overrides of documented commands are the project's responsibility.

Choose validation according to what changed. Ordinary documentation, notes and
unrelated files belong in this repository and do not require a manuscript build.
`make validate` checks changed files, runs workbench tests when relevant, and
invokes `make check` for manuscript inputs, potential figures, build/configuration
changes or uncertain inputs (with schema-4 named documents: the affected documents'
checks, or `make check` when the project's Makefile has its own check rule). Policy changes need structure checks and semantic
review; unrelated code also needs its own relevant tests. A Markdown or code
file consumed by LaTeX is a manuscript input. `make validation-plan` explains
the selection; missing comparison history conservatively selects full checks.
Use `LATEX_AI_BASE=<revision> make validate` to include already committed changes.
`make check` performs full document validation;
schema 4 checks every declared root. Document build/export commands accept
`DOC=name`; without it they use the default. Included TeX fragments are inputs
to their consuming documents, not independent build targets.
A project's own build command may
still regenerate files it depends on; that is part of the build. The workbench does not
establish scientific validity: inspect assumptions, units and tolerances yourself.

After edits inspect `git diff` and `git status`, and report selected validation,
results, relevant warnings, and unresolved issues. Diagnose
failures before modifying source; fix errors introduced by the task. Do not
silence failures by disabling checks without an explicit design decision.
A document's configured lint baseline lists the style warnings the owner accepted;
the check fails only on new ones, and a line you edit counts as new. Creating or
refreshing that baseline (`make lint-baseline`) is the owner's decision,
like changing the lint settings: ask first, and never do it to get a passing check.
The compiler and BibTeX are authoritative for TeX expansion and
bibliography semantics. Static inspection is not a replacement for them.

Clean build files (`make clean`, where the workbench provides it) only when
stale build state is suspected or explicitly asked for. It is not a routine validation step. Editor integrations and any hosted checks must call
the same Make commands, and build exclusively from repository contents.

# Git safety

- Inspect branch, status, and diff before editing; preserve user changes.
- Git mutations that write history, branches or the working tree require explicit user approval, including committing,
  initializing/cloning repositories, writing Git configuration,
  pushing, pulling, merging, rebasing, resetting, restoring, cleaning, stashing,
  branch changes/deletion, worktree creation/removal, and history rewriting.
  Staging (`git add`) and `git fetch` change none of those and need no approval of their own; the commit or merge that follows does.
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
  Capture evidence with `make issue ISSUE_NOTE="observed ... expected ..."` (a local report;
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

# Git guidance for the owner

This section belongs to this project, not to the workbench; upgrades keep it.

The owner is new to Git. Whenever a Git step is due, whether one the owner takes
(reviewing or merging a pull request, pulling, resolving a conflict, pushing from their
own terminal) or one that needs their approval (committing, pushing, creating a branch),
advise them at that point, before relying on the step:

- **What and why.** Name the step, say in plain words why it is needed now, and explain
  any Git term the first time it appears (branch, commit, pull request, merge, conflict).
- **How.** Give the exact way to do it: the GitHub page, button and option to choose, or
  the command to run, from which folder and on which branch.
- **Effect.** Say what it changes, whether it can be undone, and how.
- **First check.** Say what to check before doing it: for a merge, that CI is green
  and the diff has been read.

Never take an owner's step yourself to spare them the trouble. When a task ends, list
any Git steps still waiting for the owner, in the order they should be done. In a workbench
session (below) the agent's own commits, pushes and pull requests are pre-approved: report
them in that list afterwards, in the same terms, instead of asking first.

# Two kinds of session: manuscript and workbench

This section belongs to this project, not to the workbench; upgrades keep it.

This repository holds a manuscript project and, in `workbench/`, the package that supplies its
tooling. A session is one of two kinds, and only the owner chooses which.

- **Manuscript session (the default).** The task is the manuscript, the notes, the bibliography,
  the figures or the project's configuration. The workbench is shared infrastructure here: do not
  edit `workbench/` or `.latex-ai/`. When something looks like a defect, follow "Suspected
  workbench defects" above: report it and carry on.
- **Workbench session.** The task is to change the workbench itself: a step of
  `workbench/docs/maintainers/plan-after-4.4.0.md`, a release, a repair. It begins only when the
  owner says so in the task ("this is a workbench session", or the plan's session prompt). The
  maintainers' rules in `workbench/docs/maintainers/README.md` ("Working on the workbench itself")
  then apply, including fixing a small defect in the pull request already open. Change `workbench/`
  and what the installer regenerates from it (`make -C workbench upgrade-reference`); never the
  manuscript, and never `.latex-ai/` by hand.

**Git in a workbench session.** Starting one is also the owner's approval, for its task, to create
its topic branches, commit, push those branches and open their pull requests, without asking each
time; this is the explicit approval "Git safety" asks for, and the pull request is where the changes
are presented for review. Report each of these afterwards: what it did, why, and how to undo it. Still
the owner's, every time: merging, updating the owner's clone (`git switch main`,
`git pull`), any push to `main`, anything that rewrites or discards work (reset, restore, clean,
stash, rebase, amending a pushed commit, deleting local branches, history rewriting), writing Git
configuration, changing the agents' permission rules, and anything outside the session's task. In a
manuscript session every Git mutation needs approval, as "Git safety" says.

**Opening the pull request.** The owner has asked that an agent open the pull request itself as soon as it has pushed a topic
branch with finished work, without asking first, and report its link, what the checks showed and what could not be verified. This
holds in both kinds of session: it follows a push that was already approved (in a manuscript session, the push still needs approval
each time). If a pull request for the branch exists, push to it; never open a second one for the same change. Merging stays the
owner's, as above: give the owner the command, `gh pr merge NUMBER --auto --merge --delete-branch` while the required checks are still running (it
merges once they pass, and a red one holds it), or the same without `--auto` once they have passed.

The kind never changes by itself. A manuscript session that finds a workbench defect stays a
manuscript session: report it and ask. A workbench session that finds a problem in the manuscript
reports it and leaves it. The Git rules above apply to both kinds.
