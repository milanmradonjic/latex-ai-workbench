# How the Workbench works

The project keeps its own runtime in `.latex-ai/`. The distribution supplies the
installer and templates; ordinary checks do not depend on its original location.
Python and Make provide the interface; declared document builds require their configured tools.

## Four boundaries

1. **Authored work:** TeX, notes, bibliography exports and data belong to the
   project. The installer preserves them.
2. **Configuration:** `.latex-ai.json` explicitly declares named LaTeX documents and optional
   bibliography/editor settings. The installer validates these choices before writing.
3. **Execution:** Make is the canonical interface. Editor tasks and CI invoke
   those commands. Builds compile documents; planning never builds.
4. **Evidence:** receipts describe what happened under declared
   dependencies. They do not establish scientific validity.

## Three kinds of state

| State | Location | Purpose |
|---|---|---|
| Installation record | `.latex-ai/installation.json` | The release and a digest of each runtime file, so that a local edit shows and `runtime` can tell it from an older release's file. |
| Operation locks | `.latex-ai/artifacts/locks/` | Empty lock files that serialize builds for every user of the project. |
| Document receipts | `.latex-ai/artifacts/documents/<id>/build-receipt.json` | Establish whether compiler outputs match current declared inputs and build identity. |

The installation record is not a disposable cache. A PDF existing on disk is
not enough for verified export.

Build status reports live owner
and compiler identities from the same process checks used to block competing builds.

## Daily loop

Use `make status` to see missing, stale, failed, running, or current documents.
Edit authored files and run `make validate` when the requested batch is complete.
`make validation-plan` is an optional preview; validation prints its own plan.
Use `make build DOC=name` for explicit compilation and `make check` for all
documents and their checks. Public command names are fixed; document selection uses `DOC=name`.

Included TeX fragments are checked through consuming documents. Independent
notes have their own root, document ID, receipt, and PDF.

Commands expose their resolved context: installer previews show the selected
document's engine, backend, lint and output directory; bibliography results name
the documents/files checked. An installed runtime is bound to its own project.
Compiler-recorded inputs use the recorder's working directory. A build
that first discovers an input recompiles once with that input protected by hashes.

See [configuration](configuration.md) for declarations and
[troubleshooting](troubleshooting.md) for recovery.
