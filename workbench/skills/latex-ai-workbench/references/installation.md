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

`init` is for a project that has no `.latex-ai/installation.json`; it refuses one that has it
(see Update below). Select a profile or modules and enable the editor adapter only
when needed; read [module setup](../../../docs/modules.md). Projects without a manuscript
do not need a TeX root. Profiles choose initial configuration only.
For handwritten TeX notes, add independent roots under `modules.latex.documents` in
`.latex-ai.json` by hand. Read [TeX notes](../../../docs/tex-notes.md) for named output ownership,
mixed formats and adopted Make restrictions. Only project configuration schema 3 is supported.
Ambiguous root/engine detection returns 2 and requires explicit choices after
inspection. Select `--root` for multiple manuscripts, `--engine` for fontspec
or custom build files, and `--backend` for nonstandard bibliography declarations.
Do not ask the owner to resolve ordinary choices evident from local files.

For an existing Makefile whose build target is not `build`, supply `--build-command` as a JSON
argv list invoking its actual safe target. Check where its PDF/log are written;
config `output_dir` must match. Never delegate a runtime build to itself.

Assess each planned addition/merge. Prefer retaining a local Make recipe over
replacing it. Treat malformed JSON, colliding task names, differing agent
permissions and unsupported syntax as conflicts to explain, not excuses to
overwrite. Strict JSON editor merges preserve unrelated settings. Use
`--skip-editor` for JSONC when the user does not need immediate GUI integration;
document the manual integration still pending. The workbench writes no
workflow; never remove one the project has without authorization.

After evaluating a safe plan, apply it with the same command minus dry-run.
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

Follow [the update recipe](../../../docs/upgrading.md): be able to undo, read the release notes,
`diff`, `runtime`, then read and edit the project's own files by hand, then `make doctor`
and `make check`. `latex-ai-init runtime` refuses a runtime file that was edited unless
`--force` is given; that is the owner's call, not a way past a refusal. Never delete the
installation record to bypass a check. Backups are recovery evidence, not permission to
discard newer work; recovery that replaces user changes needs approval and a specific
file/version choice.

Updating the package itself requires versioning its release and regression
testing observed failures. Only schema-3 projects are supported. Unsupported configurations must fail
before writes; do not add old-release conversion paths.
