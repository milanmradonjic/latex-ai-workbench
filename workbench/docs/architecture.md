# How the Workbench works

The project keeps its own runtime in `.latex-ai/`. The distribution supplies the
installer and templates; ordinary checks do not depend on its original location.
Python and Make provide the core. Optional modules require their own tools.

## Four boundaries

1. **Authored work:** TeX, notes, bibliography exports and data belong to the
   project. The installer preserves them.
2. **Configuration:** `.latex-ai.json` declares enabled modules and named
   documents. Profiles choose initial settings; upgrades do not apply profiles again.
3. **Execution:** Make is the canonical interface. Editor tasks and CI invoke
   those commands. Builds compile documents; planning never builds.
4. **Evidence:** receipts describe what happened under declared
   dependencies. They do not establish scientific validity.

## Three kinds of state

| State | Location | Purpose |
|---|---|---|
| Installation ownership | `.latex-ai/installation.json` | Records what was installed (a digest for files installed whole, the text of merged and extendable files) and merge baselines; needed for safe updates. |
| Operation locks | `.latex-ai/artifacts/locks/` | Empty lock files that serialize builds and installs for every user of the project. |
| Document receipts | `.latex-ai/artifacts/documents/<id>/build-receipt.json` | Establish whether compiler outputs match current declared inputs and build identity. |

The installation manifest is not a disposable cache. A PDF existing on disk is
not enough for verified export.

Build status reports live owner
and compiler identities from the same process checks used to block competing builds.

## Daily loop

Use `make status` to see missing, stale, failed, running, or current documents.
Edit authored files, preview `make latex-ai-plan`, and run `make validate`.
Use `make build DOC=name` for explicit compilation and `make check` for all
documents and enabled checks. If a project already owns a short target name,
`make latex-ai-help` identifies its reserved Workbench counterpart.

Included TeX fragments are checked through consuming documents. Independent
notes have their own root, document ID, receipt, and PDF.

Commands expose their resolved context: installer previews show the selected
document's engine, backend, lint and output directory; bibliography results name
the documents/files checked. An installed runtime is bound to its own project.
Compiler-recorded inputs use the recorder's working directory. A build
that first discovers an input recompiles once with that input protected by hashes.

See [configuration](configuration.md) for declarations and
[troubleshooting](troubleshooting.md) for recovery.
