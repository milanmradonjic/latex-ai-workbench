# Bootstrap, review and update

## Bootstrap an existing project

Confirm the exact project scope. Read its status/branch/diff, AGENTS, CLAUDE,
Makefile or alternate build scripts, latexmk rc, editor files, agent permissions,
workflows, TeX roots/inputs and bibliography declarations. Do not scan unrelated
research repositories as discovery shortcuts. Preserve dirty files.

Locate the entire reusable workbench package, with `latex-ai-init`, templates
and runtime together. A local CLI invocation is:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run --diff
```

Before `init`, prepare `.latex-ai.json` explicitly using [configuration](../../../docs/configuration.md).
Use schema 4 with at least one named document, its root, and an explicit default.
Inspect local files to choose settings; the installer does not infer them. Multiple
documents remain supported. Declare bibliography files, custom argv build commands,
output directories, lint settings, and editor preference in the configuration.
Choose snapshots once during setup and record `"snapshots": false` by default.
For a project already using Git, keep that default unless the user wants a
separate working-copy backup. Set `true` only for an explicit opt-in; do not
create timers or ask again during ordinary edits and upgrades.
Do not ask the owner to resolve ordinary choices evident from the authorized project.

`init` refuses an installation record and any conflicting generated destination.
It never adopts or merges Makefiles, editor files, or policies. Preserve local
content and stricter guardrails when resolving conflicts explicitly. Set
`integrations.editor` to false to keep editor setup outside installation.
A custom command must produce the configured PDF/log and must not call a generated
build/check target recursively. Setup writes no workflow and changes no Git state.

When the dry run shows no conflict, apply it with the same command minus dry-run.
Do not request approval for harmless authorized file changes. Setup does not
stage files or run builds. Run `make doctor`, then `make check`, inspect diff
and status. Report real validation and any incomplete GUI
configuration. Create synthetic portability fixtures within an authorized
test directory instead of modifying a research project.

## Review an installed project

Review against the actual package and the project's installation record, not remembered state.
Confirm root/backend/config agree with source and output layout. Inspect any
local adapters and rc overrides. `latex-ai-init diff PROJECT --diff` is structural and read-only:
it lists runtime files that differ from this release and project files that differ from what a
new project would get. Run canonical validation separately when the task includes execution.

Check canonical semantic policy, delegation, editor Make invocation, intact
Git approval rules, tracked bibliography inputs, ignored build outputs and
record/runtime consistency (`make status`). Distinguish:

- missing workbench component or required input;
- unsupported or ambiguous convention;
- intentional local customization;
- a runtime file edited locally;
- build/citation/reference failure;
- optional setup or human action still pending.

Do not claim that structural compliance proves scientific correctness, GUI
extension behavior, authentication or successful remote CI. Scope findings to
observed files and command results.

## Update

A project is updated by following this recipe, and an update never ends without a diff and a check for the owner to read. The installer does not merge, audit or recover: it creates a project
(`init`), shows how a project differs from a release (`diff`) and refreshes the runtime files it vendored (`runtime`). Everything else is text you read and edit, with a diff to check it.
Only schema-4 projects are supported; an older schema is refused with a hint, and nothing is converted. Locate the new release's folder (the one with `latex-ai-init`, the templates and the runtime
together) first; it is called `/path/to/new-workbench` below.

1. **Consider recovery.** Use the project's Git history as the usual recovery
   mechanism. Ordinary edits and upgrades do not require a snapshot or a new
   commit. If a large change warrants a checkpoint, obtain approval for a Git
   commit under the project's policy. `make snapshot` is an optional alternative
   only when `"snapshots": true` was selected ([snapshots](../../../docs/snapshots.md)).
   Preserve existing uncommitted work; Git integration alone does not save it.
2. **Read what changed.** The project's stamp is the version in `.latex-ai/installation.json`: `make status` shows it against the vendored runtime's, and `make doctor` prints it, with the runtime
   files edited or missing. Read the [release notes](../../../docs/maintainers/releases.md) for every release after that version, up to the new one: they name the generated files that changed and the settings
   that were removed. A removed setting is refused by name, with a hint.
3. **See the difference.** From the new release's folder, `python3 /path/to/new-workbench/latex-ai-init diff /path/to/project --diff` lists the runtime files that differ (`RUNTIME differs` or
   `missing`) and the other files (policy, Makefile, editor settings) that differ from what a new project would get. It writes nothing; it exits 1 when a runtime file differs. In its unified diffs a `-` line is the project's and a `+` line is what the release would write, so the project's own
   content shows as a deletion: take over only the additions you want. (A project can ask for the same from inside: `make doctor LATEX_AI_TEMPLATE=/path/to/new-workbench`.) If the release notes list a setting that the new release refuses, `diff` and `runtime` stop at it,
   because they read `.latex-ai.json`: make the edit of step 6 first.
4. **Refresh the runtime.** `python3 /path/to/new-workbench/latex-ai-init runtime /path/to/project --dry-run`, then without `--dry-run`. It replaces `.latex-ai/*.py` (a file the release adds, `snapshot.py` for one, is new and untracked until the owner commits it), backs the old files up under
   `.latex-ai/backups/`, and rewrites the record. A runtime file that was edited, or that the record does not know, is refused; restore it from version control. `--force` replaces it, and that is the
   owner's call, not a way past a refusal (the runtime is not meant to be edited: report a defect with `make issue` instead).
5. **Read, then edit, the files that are yours.** `AGENTS.md`, `CLAUDE.md`, the Makefile, `.gitignore`, `.vscode/` and the guardrails (`.claude/`, `.codex/`) belong to the project. Take over what
   the release notes name and the diff shows as new (a new command's lines in the Makefile, a line of policy); never weaken a permission or a Git guardrail, keep the stricter rule when two differ, and do not paste over local content.
6. **Edit `.latex-ai.json` by hand** where the release notes say a setting changed. Keep named documents and optional bibliography/editor settings explicit.
7. **Check.** `make doctor LATEX_AI_TEMPLATE=/path/to/new-workbench`: the stamp now matches the template and no runtime file differs, and whatever generated file still differs is the project's own
   and was kept on purpose. Then `make check`, then `git diff`. Report what changed, what was kept and why, and what did not run. Commits and pushes are the owner's separate step.

Never delete the installation record to bypass a check. Backups are recovery evidence, not permission to discard newer work; recovery that replaces user changes needs approval and a specific
file/version choice.

Updating the package itself requires versioning its release and regression
testing observed failures. Only schema-4 projects are supported. Unsupported configurations must fail
before writes; do not add old-release conversion paths.
