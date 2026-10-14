# Project configuration

Workbench 4 supports **configuration schema 3 only**, for projects with or without
TeX. `.latex-ai.json` is project-owned UTF-8 JSON. Unknown fields and older schemas
fail clearly; there is no automatic migration. After deliberate configuration
changes, `latex-ai-init diff . --diff` shows what the generated Makefile and editor files would now contain; an agent
applies what is wanted by hand ([updating](upgrading.md)).

## One paper, or several documents

```json
{
  "schema_version": 3,
  "modules": {
    "latex": {
      "default_document": "paper",
      "defaults": {"engine": "pdflatex", "lint": {"enabled": true}},
      "documents": {
        "paper": {"root": "paper.tex", "backend": "bibtex"},
        "derivation": {"root": "notes/derivation.tex"}
      }
    },
    "bibliography": {"files": ["bibliography/references.bib"], "export": null}
  },
  "integrations": {
    "editor": false
  }
}
```

Each document needs a root and a stable ID. `default_document` names the target
selected by build/export without `DOC`. `make check` checks every document.
A fragment included by a root is an input, not another compilation target.
Projects without TeX simply omit `modules.latex`; see [modules](modules.md).

| Setting | Meaning |
|---|---|
| `latex.documents.<id>.root` | Project-relative `.tex` root; it must exist. |
| `engine` | `pdflatex`, the only engine. For another, declare a `build_command`. |
| `backend` | `none` (default) or `bibtex`; source and configuration must agree. |
| `lint` | `enabled: true`, `args: []`, optional project-relative `baseline`. |
| `output_dir` | Defaults to `.latex-ai/artifacts/documents/<id>/build`; override for custom layouts. |
| `build_command` | Optional nonempty argv list, run at the project root; no shell expansion. It is also how a document is built with another engine (lualatex, xelatex) or another bibliography program (biber): the workbench itself builds with pdflatex and BibTeX. |
| `inputs` | Additional project-relative paths/globs; each must match a file when building. |
| `bibliography_files` | Per-document `.bib` inputs, added to the shared bibliography. |
| `latex.defaults` | Shared engine/backend/lint/output defaults. Roots, commands, and inputs belong to documents. |
| `bibliography.files` | Shared `.bib` inputs, including paths assembled through macros. |
| `bibliography.export` | `null`, or `{path, required, format}` for a local Zotero export. |
| `integrations.editor` | Opt into generated editor tasks. |
| `validation.manuscript_inputs` | Extra project-relative globs for shared indirect dependencies. |
| `validation.ignore` | Project-relative globs, for example `docs/**`, for paths that are never routed to the manuscript build. See [validation](validation.md). |
| `validation.package` | Distribution directory for its own tests; default `workbench`, `null` disables package routing. |

`export.required: true` rejects missing or empty exports. The format is `bibtex`, for
Zotero's Better BibTeX. Builds use local files and
never contact Zotero. Backend settings do not rewrite TeX packages or citation styles.

Paths must remain inside the project, including through symlinks. Root filenames
cannot contain whitespace or TeX-special characters. Distinct documents cannot
alias roots, compiler outputs, or exports. latexmk uses `-cd`, so TeX input paths
resolve from the root's directory; configuration paths resolve from the project.
Normal latexmk rc files remain active. Custom commands must write the configured
stem's PDF and log; nonstandard job naming needs explicit adaptation.

Custom commands run from the project root unless their own script changes it.
Recorder `INPUT` paths resolve from the recorder's `PWD`, not from the TeX root.
New recorder inputs discovered during any build trigger one forced rebuild
with the complete observed input set hashed before and after. This avoids
certifying an input first observed only after compilation; a further change
fails the attempt. Declare hidden inputs to avoid that extra discovery pass.
Absolute system inputs outside the project are not fingerprinted.

Installer previews and JSON reports include the selected document's resolved
engine, bibliography backend, output directory, and lint policy. `--no-lint`
affects that document; new documents inherit `modules.latex.defaults` otherwise.
`bib-check` without `DOC` checks all document bibliographies, and with `DOC` only
that document; its successful output names the actual files checked.

## Accepting existing style warnings

ChkTeX is enabled by default. `make latex-ai-lint-baseline DOC=paper` records
existing warnings at `.latex-ai/lint-baselines/paper.json`, unless `lint.baseline`
declares another path. Keep it in version control. Creating or refreshing the
baseline is the owner's decision. Warning identity includes the source line;
editing that line makes its warning new. Accepted warnings are not globally
disabled. `lint.args` and `.chktexrc` control deliberate checker policy.

For a deliberate compiler-only project, set `latex.defaults.lint.enabled` to
`false`; document settings override that shared default. The installer's
`--no-lint` option changes the configured document, so a subsequently registered
note still uses the shared defaults. Missing ChkTeX is otherwise a failed check,
not an automatic reason to turn lint off.

## Build receipts and recovery

Each document has `.latex-ai/artifacts/documents/<id>/build-receipt.json`.
The current receipt format stores build identity directly: root, engine, output
location, command, bibliography declarations, and input/output fingerprints.
Lint and default selection do not change PDF identity. A first build must
write both PDF and log. Incremental reuse needs a matching verified receipt;
old or malformed receipts certify nothing. Failure or interruption invalidates
the attempt even if the source is later restored. Export requires a current receipt.

When a custom command leaves existing outputs without a valid receipt, the
Workbench moves them aside and runs the command once more. Per-attempt intent
journals under `.latex-ai/artifacts/unverified/<id>/` preserve originals.
Missing originals are restored on failure without overwriting replacements.
The next owned build recovers interrupted moves. This supports process recovery,
not guarantees against lost storage or hardware failure.

Dependencies include literal TeX resources, compiler recorder inputs, declared
globs, bibliography, command scripts, latexmk configuration, and the Makefile
when the build command is a `make` goal. Makefiles are hashed in full; an
included Makefile is not followed. Declare includes and hidden dependencies in `inputs`.
Receipts cannot prove that arbitrary custom commands invoke a compiler or that
their results are scientifically correct.

## Make and editor boundaries

`init` writes the Makefile and never reads or merges another one; a project's own targets go after what it wrote
([migrating](migrating.md)). The generated Makefile asks nothing of the GNU Make version.

Editor setup creates named Make tasks/recipes, disables automatic builds on
save, and prevents magic comments from bypassing Make. `init` merges into existing JSON settings by key;
JSONC requires `--skip-editor` and deliberate manual integration.

LaTeX Workshop finds a document's PDF through `latex-workshop.latex.outDir`: one setting whose placeholders expand
per root file. Setup sets it to the first value that gives every document its real output directory:
`%DIR%/<folder>` when each document builds into the same folder beside its own root (`revision/main.tex` built into
`revision/build/` gives `%DIR%/build`); `%WORKSPACE_FOLDER%/<folder>` when all documents share one folder; nothing
when each is built beside its root, where the viewer already looks. Documents that build in different places
cannot share one value. Setup then leaves the setting unset and says so, and the viewer looks beside each root
file. Give those documents the same `output_dir` to let **View PDF** find them; the default folders differ by
document name, so several documents with no `output_dir` are in this case.

See [TeX notes](tex-notes.md), [validation](validation.md), and
[updating](upgrading.md) for the update recipe.
