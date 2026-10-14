# Version 4.5.1 verification

This records the release that makes `init` stop at a paper that needs lualatex, xelatex or biber and say what to declare instead. It follows [4.5.0](verification-4.5.0.md), which left such a
paper to fail at its first build, and was asked for by the owner.
Tested on 2026-10-14 on Linux (x86_64, GNU Make 4.3, Python 3.13.16, 3.12.13 and 3.11.17) with TeX Live 2023 from Debian: `latexmk`, `chktex`, `bibtex`, and for the first time
LuaHBTeX 1.17.0 (`lualatex`), XeTeX 3.141592653-2.6-0.999995 (`xelatex`), Biber 2.19 and `biblatex`. The hosted results follow in the next record.

| Check | Result |
|---|---|
| `tests/test_scope_4_5_1.py` against 4.5.0 | 6 of its 9 tests fail: `init` succeeds as pdflatex on a source with a `% !TeX program` comment, `\directlua`, `luacode`, `xeCJK`, `fontspec` or biblatex (8 cases), `--modules latex` does not stop it either, and the four tests that follow the hint with real tools cannot, since there is no hint (lualatex, xelatex, biber, and lualatex in a subfolder). The other three pin what must not change and pass on both: a `--build-command` takes the guard away; a source that only mentions another toolchain (a pdflatex magic comment, `fontspec` in a comment, biblatex processed by BibTeX, plain BibTeX) is not refused; a project with its own configuration is not second-guessed |
| The same after the change | All 9 pass. The four real-tool tests run the command the hint prints, through `init` and then `check`: the paper builds, the receipt is current, and the tool left its mark (LuaHBTeX or XeTeX in the log, Biber in the `.blg`) beside the source |
| Eleven mutations | Each is caught by the test named for it: the guard gone; a build command no longer taking it away; the magic comment not read; a magic comment for xelatex or XeTeX given lualatex's flag; biblatex given an engine flag; biblatex processed by BibTeX refused; comments searched too; `fontspec` no longer a sign; the hint without `-cd`, or naming no file. The first run missed three: `-recorder`, which turned out to be redundant (`latexmk` records its inputs itself, so the hint no longer carries it), and `-cd` and the root's path, which no test needed until one built a paper in a subfolder |
| `make -C workbench test` | 382 tests (373 before, 9 new), 1 skipped, OK on 3.13.16, 3.12.13 and 3.11.17 |
| `make -C workbench portability` | All 51 scenarios pass |
| 4.5.0 and this tree, identical projects, each installed and run by its own release | 232 comparisons, 0 differences, none skipped as noise: the eight projects of the 4.5.0 comparison (four built with a real `latexmk`), none of which needs another toolchain. The guard is in the installer, so no runtime action changes |
| `make -C workbench upgrade-reference`, then `audit-reference` | The refresh changed `core.py` (the version) and the record; the audit then reports the runtime identical |
| Size | The package is 3,963 lines (3,936 before): the guard is 27 lines of `bootstrap.py`: a table of three signs, a function that adds the magic comment and biblatex, and the refusal. The tests are 6,121 lines (5,996) |

## Found on the way

- **A hint is code.** The printed command is the whole fix, so it is tested by following it rather than by comparing its text, and the first version of the tests missed two of its parts until a paper in a subfolder was built.
- **The 4.5.0 detection test changed meaning.** It now gives `init` a `--build-command` for sources that name another toolchain, so that it still shows `init` writing `pdflatex` and no backend for them, which is the no-inference it was written to pin.
- **The signs err toward stopping.** A source that merely contains `{fontspec}` in verbatim text is refused until it is given a `--build-command`; the refusal says how, in one command.

## Hosted verification

All six required checks passed on the pull request ([#9](https://github.com/milanmradonjic/latex-ai-workbench/pull/9): [`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38579127811) in 1m46s with TeX Live 2026; the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38579128064), 1m06s to 1m29s each), and again on the merge commit `ee069c2` on `main` ([`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38583858226); the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38583858166)).

## Not verified

- **Hosted runs of this pull request**, with TeX Live 2026 in the `validate` job. The four tests that follow the hint with real tools run only where TeX is installed: the hosted Python jobs have none, so they skip there, and the `validate` job runs `portability`, not the unit tests. So the advice is proved here, not hosted; a `portability` scenario would move it there, at the price of requiring `lualatex`, `xelatex` and `biber` in that job.
- **How often the signs misjudge a real paper.** They were written from what 4.4.2 looked for, and tested on constructed sources, not on a corpus.
- **Other platforms and versions locally.** macOS, Windows, and Python 3.10 and 3.14.

## Open items

Next in [the plan after 4.4.0](plan-after-4.4.0.md): step 3.5, per-document targets, which changes the generated Makefile on purpose. The gates (Git guardrails, changed-file routing, the manual) are still the owner's.
