# Version 3.4.1 verification

This records the repair of the missing `latex-workshop.latex.outDir` in the generated VS Code settings, tested on
2026-10-12 on macOS (Darwin 25.5, Python 3.14.8, GNU Make 4.4.1 from Homebrew with `gnubin` first on `PATH`, TeX Live
with latexmk 4.88). It is stacked on 3.4.0, which was still an open pull request. The hosted results for the pull request head and
for the merge commit follow the local ones.

| Check | Result |
|---|---|
| The reported project, read without changing it (a test project of two documents, kept outside this repository) | Two documents, `revision/main.tex` and `revision/supplementary.tex`, both with `output_dir` `revision/build`; the generated `.vscode/settings.json` has tools and recipes but no `latex-workshop.latex.outDir` |
| `tests/test_repairs_3_4_1.py` against 3.4.0 | 9 of 10 fail: the seven cases of the rule error (there was no `viewer_out_dir`); an installed project with the reported layout has no `outDir` (`KeyError`); documents that build in different places give no explanation. The tenth, a project built beside its sources, passes before and after, as a guard against adding a key where none is needed |
| The same tests after the change | All 10 pass. The rule is checked for: built beside the root; the reported layout (`%DIR%/build`); the single-document default layout; different folders each with the same subfolder; one shared folder outside the documents'; the root `.`; spelling of the path (`./revision/./build/`); and documents that disagree |
| The generated-files guard | Failed first, on the three fixtures that have a document, the editor files and an output folder of their own; after regenerating, exactly one line was added in each (`"latex-workshop.latex.outDir": "%DIR%/.latex-ai/artifacts/documents/manuscript/build"`). Every other stored copy is untouched, among them the multi-document fixture, which has no common value |
| `latex-ai-init upgrade --dry-run --diff` on the reported project | `.vscode/settings.json` gains `"latex-workshop.latex.outDir": "%DIR%/build"` and nothing else in the editor files; the project was not modified |
| Previous version installed in a scratch copy of that layout, then upgraded: untouched settings | Gain `%DIR%/build` |
| The same, with the user's own preferences (`editor.tabSize`, the PDF viewer) | The key is added; both preferences are kept |
| The same, with the identical value already set by hand | Upgrade succeeds, the file is as it was |
| The same, with a different value set by hand | `CONFLICT: .vscode/settings.json: Upgrade conflicts with local changes at latex-workshop.latex.outDir`, nothing changed, the hand-set value stays |
| `make -C workbench test` | 405 passed, 1 skipped (`test_a10_zombie_owner_is_not_running` needs `/proc`, which macOS lacks) |
| `make -C workbench portability` | 87 of 87 |
| `make latex-ai-bib-check`, `make check`, `audit` in the reference | Pass; the import graph still has no cycle |

## Hosted verification

All three pull-request workflows passed for the exact head `4766058579b46d4d4af2df404c4f33d60116086d` before integration; the same three also passed on the
branch push.

| Workflow | Result |
|---|---|
| Workbench Python compatibility | Python 3.10–3.14 each ran 405 tests successfully, with 21 expected skips: 20 requiring TeX and one requiring the actual macOS Make 3.81 parser |
| Schema-3 acceptance | Named-document PDF and export selection checks passed |
| LaTeX AI Workbench | The 405-test suite (21 expected skips) and 87/87 compiler portability checks passed |

The same three workflows then passed on the squash-merge commit `03df127` itself on `main`:
Python compatibility (Python 3.10–3.14, 405 tests each), Schema-3 acceptance
and LaTeX AI Workbench (405 tests, 87/87 portability checks). No hosted timing comparison is claimed.

## Field check

The owner upgraded the reported project (installed from an in-progress build of 3.4.0, so only `core.py`, `guide.py` and
`.vscode/settings.json` differed) to 3.4.1 and reported that **View PDF worked**. Compared with the backup the upgrade
made, its settings gained only `"latex-workshop.latex.outDir": "%DIR%/build"`. The upgrade itself ran no build, but
`revision/build/main.pdf` is dated after it (17:40, the upgrade 17:37), so something rebuilt it afterwards; what was not
recorded. The second `main.pdf` the owner noticed was an empty file at `revision/main.pdf`, dated before the upgrade and at the path the
viewer used to look; the owner removed it. What created it was not verified.

## Not verified

- **LaTeX Workshop itself, beyond one report.** VS Code was not run here. The owner reported that View PDF worked on the
  upgraded project; which of its two documents was tried, and the VS Code and extension versions, were not recorded. The
  rule rests otherwise on the extension's documented semantics (`outDir` is where it looks for the PDF; a relative value
  starts at the root file's folder; the placeholders expand per root file).
- **Windows.** The extension also has `%DIR_W32%`; only the POSIX form is generated.
- **Python 3.10–3.13 on macOS.** The local suite used Python 3.14.8; the matrix above ran those versions on Linux.
- **GNU Make 3.81.** The suite and portability ran on GNU Make 4.4.1.

## Open items

- **Documents that build in different places** still cannot be aligned with the viewer by one setting. This includes
  several documents left on the default per-document folders (`.latex-ai/artifacts/documents/<name>/build`), the common
  case; setup says so, and giving them the same `output_dir` fixes it. Changing the default layout would be a larger
  decision. The extension's own auto-detection reads `-outdir=` from the arguments of the last tool it ran; passing
  that through the Make tool is a possible route, but it relies on behaviour the documentation does not promise and was
  not tried.
