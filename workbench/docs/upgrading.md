# Audit and release upgrades

## Workbench 3 boundary

Workbench 3 is the supported development line. Earlier experimental releases
are retired from support; they receive no compatibility patches or backports.
Historical tags, release notes, and verification records remain available to
explain past decisions. Removing published versions is not necessary to simplify
the current runtime.

Workbench 3 accepts project configuration schema 3 only. Schema-1/2 readers,
migration flags, v0 adoption, and old manuscript receipt/export paths have been
removed. There is no automatic conversion of older installations. Preserve authored
sources and archives; create a reviewed schema-3 configuration for any experimental
old project before using this release. Do not delete an installation manifest or
recovery journal to bypass ownership checks.

Within the supported model, upgrades retain project configuration and enabled
modules. Named document receipts and exported PDFs have one layout. Unsupported
or malformed receipts require rebuilding; they never certify a PDF. Current
installation journals have an independently
versioned format; their schema numbers are not project configuration versions.

Current document receipts use format 3, which certifies recorder-context handling
and protected first-build dependency discovery. Previous receipts are invalidated,
including ones whose recorder has been removed. Rebuilding writes the current
format; there is no receipt conversion path.

Distribution maintainers can use `make -C workbench upgrade-reference`, then
`make -C workbench audit-reference` and `make -C workbench test`. These update the
reference through the installer and verify parity; they perform no Git mutations.

Keep `.latex-ai.json`, installed `.latex-ai/*.py`, `.latex-ai/installation.json`,
Makefile, policies, editor configuration and CI in version control. The manifest
stores installed and upstream text baselines; it is required for safe merges
and is not a cache. Ignore `.latex-ai/backups/` and `.latex-ai/artifacts/`.

## Updating an installed project

1. Inspect Git branch/status/diff, policy, config, current manifest version and
   the new package release. Preserve uncommitted changes.
2. Run the new package's `upgrade PROJECT --dry-run --diff` and assess the plan.
3. Reconcile reported conflicts deliberately; the tool has no overwrite switch.
4. Run the same upgrade command without dry-run. Existing changed files receive
   timestamped, project-local backups before writes. If a planned file has
   changed concurrently, the operation stops; completed writes are rolled back
   only if they still contain the installer's own bytes.
5. Run `make doctor`, `make check`, then audit with the new package. Inspect the
   diff and status. Approval for Git mutations is a separate final action.

Repeated init/upgrade produces no further writes when the installation is
current. Audit and dry-run only read. Upgrades refuse unsupported schemas and
downgrades. There is no network updater: release retrieval and Git changes are
under human control.

## Pinned workflow actions

Every action the generated workflow uses is pinned to a commit, with its tag in a comment
(`uses: actions/checkout@<commit> # v7`). A tag is resolved again on every CI run, so a moved or hijacked tag would change
what runs with your checkout and token in reach; a commit cannot move. The workbench carries the pins, so a new release
brings new ones: an upgrade changes the `uses:` lines of `.github/workflows/latex-ai.yml` and nothing else in it. An action
the workbench has no pin for is refused when the workflow is generated. Your own workflows are not touched.

## Ownership and conflicts

New runtime, policy, Make and workflow files are managed as whole files. In the
Makefile, `AGENTS.md`, `CLAUDE.md` and `.gitignore` of a project that had none,
the installed text is the managed part: lines you add above or below it are
yours, are kept on every upgrade and are not reported as changes. A change
inside the installed text is not merged and blocks the upgrade. To resolve it,
run the upgrade with `--dry-run --diff`, which prints your change against the
installed text; undo it or move it outside that text, and run the upgrade
again. Runtime, guardrail and workflow files are installed whole and are not
meant to be edited at all: restore them from version control. Do not delete
manifest entries to force an overwrite. An unchanged upstream/current file can
remain unchanged without conflict.

Existing Makefile/AGENTS/CLAUDE/ignore content is retained outside clearly
marked workbench blocks. Upgrades replace only their block, and local edits
inside the block cause a conflict. Existing policies remain canonical.

VS Code JSON uses three-way merging by dictionary key and task/tool/recipe
identifier. Unrelated additions and preferences survive. Concurrent edits to
the same managed property conflict. New package defaults do not override
unchanged project preferences. Formatting may become standard JSON during
initial merging; JSONC is deliberately left untouched.

Existing agent permission files are never weakened or silently replaced.
Different policies require manual reconciliation, preserving stricter rules.
Unknown/deleted installed files and malformed managed blocks stop the plan.
Previously managed files no longer in the desired set are retained and reported,
not deleted. Disabling installed managed CI generates a disabled job on upgrade;
unrelated workflows remain governed by their own project policy.

Deleting a managed block intentionally stops an upgrade; it will not be
reintroduced silently. The active GNU Make filename is retained, including
`GNUmakefile` and lowercase `makefile`. A new file that shadows the installed
Makefile is a conflict. On macOS the installer tracks the actual filename
spelling instead of treating case-insensitive aliases as different Makefiles.

Backups are plain files, not automatic restore commands. Before any recovery,
inspect current changes and compare the relevant backup. Recover a specific
file only with the owner's explicit authorization when it would discard work.
Do not run `git restore`, `reset` or `clean` as upgrade recovery.

What changed in each release, and how releases are cut, is in the [maintainers' release notes](maintainers/releases.md).


## Interrupted installations

The installer serializes installation writers and journals each multi-file change
before replacing any managed file. The installation manifest is written last.
Handled failures attempt rollback; abrupt process death leaves
`.latex-ai/transaction.json`. Audit, init, configure and upgrade refuse to
continue while this journal exists.

Inspect the journal, then restore the previous installation with:

```sh
python3 /path/to/workbench/latex-ai-init recover /path/to/project
```

Recovery checks every destination before restoring anything. Files edited after
the interrupted operation are preserved and reported for manual reconciliation.
Do not delete the journal to bypass that check. Recovery itself can be resumed
if interrupted. Existing backups remain available. This mechanism covers process
interruption; it does not promise atomic multi-file storage across hardware or
filesystem failure. Audit and dry-run never perform recovery implicitly.
