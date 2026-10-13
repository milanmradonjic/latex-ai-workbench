# Bootstrap, audit and upgrade

## Bootstrap an existing project

Confirm the exact project scope. Read its status/branch/diff, AGENTS, CLAUDE,
Makefile or alternate build scripts, latexmk rc, editor files, agent permissions,
workflows, TeX roots/inputs and bibliography declarations. Do not scan unrelated
research repositories as discovery shortcuts. Preserve dirty files.

Locate the entire reusable workbench package, with `latex-ai-init`, templates
and runtime together. A local CLI invocation is:

```sh
python3 /path/to/workbench/latex-ai-init audit /path/to/project --json
```

Audit missing components and conflicts; an absent installation returns 1.
Select a profile or modules and enable the editor adapter only
when needed; read [module setup](../../../docs/modules.md). Projects without a manuscript
do not need a TeX root. Profiles choose initial configuration only.
For handwritten TeX notes, register independent roots
with `configure --document ID --root PATH`. Preview first. Read
[TeX notes](../../../docs/tex-notes.md) for named output ownership, mixed formats
and adopted Make restrictions. Only project configuration schema 3 is supported.
Explicit configure operations use the same dry-run, conflict and
backup safeguards. Ambiguous root/engine detection returns 2 and requires explicit choices after
inspection. Select `--root` for multiple manuscripts, `--engine` for fontspec
or custom build files, and `--backend` for nonstandard bibliography declarations.
Do not ask the owner to resolve ordinary choices evident from local files.

Run `init PROJECT --dry-run --diff` with the chosen options. For an existing
Makefile whose build target is not `build`, supply `--build-command` as a JSON
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
and status and run audit again. Report real validation and any incomplete GUI
configuration. Create synthetic portability fixtures within an authorized
test directory instead of modifying a research project.

## Repository audit

Audit against the actual package and installed manifest, not remembered state.
Confirm root/backend/config agree with source and output layout. Inspect any
local adapters and rc overrides. Run canonical validation separately when the
task includes execution; CLI audit itself is structural and read-only.

Check canonical semantic policy, delegation, editor Make invocation, intact
Git approval rules, tracked bibliography inputs, ignored build outputs and
manifest/runtime consistency. Distinguish:

- missing workbench component or required input;
- unsupported or ambiguous convention;
- intentional local customization;
- conflicting managed-file change;
- build/citation/reference failure;
- optional setup or human action still pending.

Do not claim that structural compliance proves scientific correctness, GUI
extension behavior, authentication or successful remote CI. Scope findings to
observed files and command results.

## Upgrade

Inspect the installed release and the new package. Run new-package
`upgrade PROJECT --dry-run --diff`; project config stays human-owned. Full-file
runtime/template changes and edits inside managed blocks can conflict. JSON
uses three-way merges. Local content outside managed text blocks is preserved.
No automatic downgrade, deletion or forced overwrite is available.

Resolve a conflict with an explicit, focused edit after understanding both
versions. Do not delete the manifest to bypass ownership. Apply the safe plan,
then validate, audit and inspect the diff. Timestamped backups are recovery
evidence, not permission to discard newer work. Recovery that replaces user
changes needs approval and a specific file/version choice.

Updating the package itself requires versioning its release and regression
testing observed failures. Only schema-3 projects are supported. Unsupported configurations must fail
before writes; do not add old-release conversion paths.
