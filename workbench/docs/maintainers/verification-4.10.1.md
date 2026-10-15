# Version 4.10.1 verification

This records the patch that fixes three of the findings the two readers of the manual left outside its wording, listed in [the 4.9.1 record](verification-4.9.1.md): the missing Hint on an undefined reference, a TeX message cut by the log's own wrapping,
and a failed document's log, which `status` did not name. The owner asked for these three after an assessment of each reader finding that found none of them a defect and these three the ones that meet the most common failure of a LaTeX paper.
Built on 4.10.0 (`8f22d5f`). Tested on 2026-10-15 on Linux (x86_64, GNU Make 4.3, Git 2.43.0, Python 3.13.16, 3.12.13 and 3.11.17) with TeX Live 2023 from Debian.
The hosted results are not yet in this record; they are added by the record that follows it.

| Check | Result |
|---|---|
| The new tests against 4.10.0 | 5 tests, in two classes (`ReadTheLog` in `tests/test_receipts.py`, `FailedDocumentLog` in `tests/test_guide.py`). Three fail: an undefined reference gives no Hint line at all; a message TeX wrapped is printed cut at `ended by \end{docume`; `status` does not name the log of a failed document. Two pass as controls: a short message is not joined with the line after it, and a log that is not there is not named |
| The same after the change | All 5 pass |
| What the tests hold the change to | The Hint of the integrity error names the log (`outputs/main.log`) and what to run (`document-check`), by a build whose log holds an undefined reference. The wrapped message is checked with the stand-in `latexmk` of the test (a script on the `PATH` that writes a log of exactly the 79-character first line TeX would write, then the rest, and fails), whole in the error and not joined with the `l.8` context line after it. `status` is checked before the build (no log line), after a failing build (`read its log: outputs/main.log`), after the build is repaired (none again) and with the log deleted (none) |
| Ten mutations | All 10 caught by a test named for it: the integrity error without its Hint; the wrapped message not joined; every line joined; the wrap width 80 and not 79; a Hint that forgets the log, or one that forgets what to run; `status` never naming the log, naming it for a document that has not failed, naming one that is not there, or naming it with an absolute path |
| `make -C workbench test` | 546 tests (the 541 of 4.10.0 and the 5 new), 2 skipped (the unreadable-folder test, since this runs as root, and the test that needs GNU Make 3.81), OK on 3.13.16, 3.12.13 and 3.11.17 |
| `make -C workbench portability` | All 51 scenarios pass |
| 4.10.0 and this tree, identical projects, each installed and run by its own release | 232 comparisons, 0 differences, none masked beyond the version. None of the eight projects reaches an undefined reference or a failed document with a log, which is the only place the output changes; the new tests carry that evidence |
| The generated-files guard | Unchanged: the Makefile and the editor files did not change |
| `make -C workbench upgrade-reference`, then `audit-reference` | The refresh changed `core.py`, `guide.py` and `latex.py` in the reference's `.latex-ai/`, and the audit then reports the runtime identical |
| Size | The package is 4,445 lines (4,413; `cat workbench/*.py`): `latex.py` and `guide.py` grew by 41 lines between them. `bootstrap.py` is still 579. The tests are 9,195 lines without `test_support.py` (9,085) |

## What changed

- **The Hint.** `verify` raised "Unresolved manuscript integrity errors" with no Hint, the only build failure that had none. It now gives the sentence a compiler error already gave: `the full log is outputs/main.log; correct the source, then run make document-check DOC=NAME` (`make check` where the document has no name). The sentence is one function, `read_the_log`, used by both.
- **The wrapped message.** TeX wraps its log at 79 characters (`max_print_line`), and `compiler_error` printed the first error line as it stood. It now joins the continuation while a line is exactly 79 characters long. The reader's real build had cut the message at `\end{docume`, which is where the first line ended.
- **`status`.** A failed document gets a line `read its log: PATH` when its log is there (project-relative). The path is found with `core.document_paths`, the rule the build uses, so `guide.py` imports nothing from `latex.py` and the layering of the modules is unchanged.

## Found on the way

- **A failing custom build gives no TeX error.** The first version of the tests used the test project's stand-in builder (`build_command`) that exits 1; its failure is the generic "Command failed with exit status 1", which reads no log. The TeX-error path is only the default `latexmk`, so the two tests of the wrapped message put a stand-in `latexmk` on the `PATH`. The first run against 4.10.0 showed it: the test failed for the wrong reason until the fixture was right.
- **The cut-off was TeX's, not an arbitrary limit.** The reader reported it as "about 80 characters"; it is exactly TeX's own wrapping, which is why joining the next line is the whole fix.

## Not changed

The rest of the readers' findings stay as listed in [the 4.9.1 record](verification-4.9.1.md): `status` offering `make validate` again after a failed validate (it is the right command once the source is fixed, and now the log is named), the check names "files" and "manuscript" (keys of the plan's JSON), a `slides.tex` edit routed as a manuscript input, `make lint` printing nothing when clean, and a line telling the owner to commit.

## Not verified

- **A TeX configured with another `max_print_line`.** The join fires on exactly 79 characters; a distribution that wraps elsewhere would keep the cut message, and a message of exactly 79 characters that TeX did not wrap would be joined with the next log line. Neither was run. The real build behind the reader's report was TeX Live's default.
- **A real TeX for the new tests.** The wrapped-message tests use a stand-in `latexmk` that writes the log; the existing test of a real compiler error (`test_compiler_failure_names_the_tex_error`) still runs with the real tools where they exist.
- **Hosted results.** The pull request is the first run of this version's workflows.
- **macOS and Windows.**

## Open items

None of the plan: its steps are done. Open for the owner: gate G3 (his own reading of the manual, and how project notes grow) and setting up the two launchd agents of 4.8.0.
