# Two documents that cite each other

This synthetic example is an article and its supplement. Each reads the other's
`.aux` file through `xr-hyper` (`\externaldocument`), so a label that moves in one
document changes the references in the other. One `latexmk` run of each is not
enough; the build has to repeat until both documents have read the other's
current state.

Workbench has no such build of its own. The configuration therefore declares a
`build_command` for each document, and [`build_documents.py`](build_documents.py)
is a project-owned adapter that does the settling. It follows the
[coupled-roots contract](../../docs/configuration.md#build-receipts-and-recovery):

- builds the selected document and its companion incrementally, in the shared
  `build/` folder, and keeps `-synctex=1` for the editor;
- records which companion `.aux` each document last consumed, and rebuilds a
  document that `latexmk` skipped although the companion's `.aux` changed;
- stops after `MAX_ROUNDS` (6) rounds and reports non-convergence;
- bootstraps an `.aux` that a failed TeX run left missing or truncated;
- regenerates missing outputs, and regenerates the selected document once when
  Workbench sets `LATEX_AI_BUILD_FORCE=1` and nothing else rebuilt it;
- rejects a build during which a source changed, and drops its cache on any
  failure. The cache is not a build receipt: Workbench decides validity itself.

Copy this directory into a fresh project, then run:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/project
cd /path/to/project
make all
make check
```

To adapt it to your own documents, edit the constants at the top of
`build_documents.py` (`DOCUMENTS`, the folder of the `.tex` files, the output
folder and the input patterns) and the matching entries in `.latex-ai.json`.
Both documents must declare both sources, the adapter and any shared resources
under `inputs`, so that an edit to any of them makes a build stale. Use the same
output folder for both and name it in each `\externaldocument{build/NAME}`.

The adapter has its own tests, which need no TeX installation apart from the one
test that exercises the real bibliography backend:

```sh
python3 -m unittest discover -p 'test_*.py'
```

It handles exactly two coupled documents. More than two, or a different coupling
than `xr-hyper`, needs a different adapter.
