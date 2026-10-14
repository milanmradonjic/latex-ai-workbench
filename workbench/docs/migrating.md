# Migrating an existing project

`init` creates a project. It never changes a file the project has: a file that differs from what `init` would write is a conflict, and nothing
is written until none is left. An existing project (one with its own Makefile, `AGENTS.md`, editor settings or an older workbench) is brought
over by an agent following this recipe: the workbench's files go in, and the project's own content is carried across by hand, with a diff to check it.
The recipe was tried on a real paper with two coupled documents, its own build script and an older workbench installed; it took about ten steps.

1. **Take a snapshot you can return to.** The project is committed in Git, or the whole folder is copied. A project without Git has no undo, so
   `git init` and a first commit (the owner's step) or a copy comes first. Do not migrate without one.
2. **Read what the project has.** The Makefile (which targets build the PDF, which make figures, which test), build scripts, `latexmkrc`,
   `AGENTS.md` (which sections are the project's own and which the workbench's older text), `.vscode/`, `.gitignore`, `.github/workflows/`, and
   `.latex-ai.json` if an older workbench wrote one.
3. **Decide the build.** A paper that builds with `latexmk -pdf` (pdflatex, with BibTeX if it has a bibliography) needs no `build_command`. One that needs lualatex,
   xelatex or biber, or that builds some other way, sets `build_command` (an argv list) to the project's
   script or to `make TARGET` for a target of its own Makefile, with `output_dir` where the PDF and log appear and `inputs` for what the compiler
   cannot see. Never name `build`, `check`, `validate` or a `latex-ai-` goal: that would call itself.
4. **Clear out an older workbench's generated files.** Remove `.latex-ai/` (keep `.latex-ai/lint-baselines/` if the owner accepted one), the Makefile when it holds
   only workbench targets, the generated entries of `.vscode/`, and the generated policy text of `AGENTS.md` (keep the project's own sections). In
   `.latex-ai.json` delete `integrations.ci` and `disabled_modules`, which no longer exist, and any `engine` other than `pdflatex`, `backend: biber` or export `format: biblatex`
   (workbench 4.5 refuses them; step 3 says what to declare instead). A Makefile that still has a block between
   `# BEGIN LATEX AI WORKBENCH` and `# END LATEX AI WORKBENCH`, or the target `latex-ai-build-prepare`, belongs to the adapter of 4.3 and before: take the
   block out and keep the project's own rules above it.
5. **Find the conflicts.** `latex-ai-init init PROJECT --dry-run` lists every file that exists and differs. Move each aside, outside the project.
6. **Run `init`** (`--root` or `--build-command` where step 3 needs them; a `.latex-ai.json` the project already has is used as it is).
7. **Carry the project's content back, after what `init` wrote.** Its own Make targets after the Makefile (a figure or data step is a plain
   target; `make figures` runs it); its own `AGENTS.md` sections after the policy; its `.gitignore` lines; its editor preferences into
   `.vscode/settings.json`. For `.claude/` and `.codex/` keep the stricter rule where two differ, and never weaken a Git guardrail.
8. **Replace a workflow an older release wrote.** It calls actions that no longer exist (`plan --github-output`). Write the project's own, or remove
   it with the owner's say; the workbench writes none.
9. **Lint.** An existing paper usually has ChkTeX warnings, and `make check` fails on them. Accepting them as a baseline
   (`make lint-baseline DOC=NAME`) is the owner's decision; never silence a warning kind to get past the check.
10. **Verify.** `make doctor`, `make check`, `make status`, then `git diff` (or compare with the copy). Report what changed and what was not run. The commit is the owner's.

`latex-ai-init diff PROJECT --diff` afterwards shows what still differs from what a new project would get; for the policy, Makefile and editor files that is the
project's own content, which is expected. Updating later is [another recipe](upgrading.md).
