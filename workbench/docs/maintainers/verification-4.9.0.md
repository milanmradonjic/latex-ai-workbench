# Version 4.9.0 verification

This records step 3.7 of [the plan after 4.4.0](plan-after-4.4.0.md): `make doctor` reports the project's version stamp and, given the folder of a release, that release's own `latex-ai-init diff`; and the update recipe an
agent follows is in the skill file (`skills/latex-ai-workbench/references/installation.md`, "Update"), with `docs/upgrading.md` as the short guide that points to it. The design question, whether the doctor should know the
template at all, was put to the owner, who chose the version where it does (`LATEX_AI_TEMPLATE`, run through the release's own installer).
Built on 4.8.1 (`73f6538`). Tested on 2026-10-15 on Linux (x86_64, GNU Make 4.3, Git 2.43.0, Python 3.13.16, 3.12.13 and 3.11.17) with TeX Live 2023 from Debian.
The hosted results are at the end of this record (added by the record that follows it).

| Check | Result |
|---|---|
| `tests/test_scope_4_9_0.py` against 4.8.1 | 12 of its 15 tests fail: no stamp in the doctor's output, no `--template`, no `LATEX_AI_TEMPLATE`, no template line, no installer error handling. The three that pass are the control that the doctor writes nothing into the project and the two that read the recipe, which were copied in with the new `references/installation.md` and `docs/upgrading.md` |
| The same after the change | All 15 pass. The older `tests/test_scope_4_3_0.py` test of the recipe now reads the skill file's "Update" instead of `docs/upgrading.md` |
| What the new tests cover | The stamp of a project that matches; an edited runtime file, a missing one and a record of another version, each named, with the doctor still passing; a record that cannot be read, named and not fatal; the stamp printed before a missing tool stops the doctor (run with an empty `PATH`); the line that says how to compare when no template is given; the template's version and "runtime files are identical"; `--template`, the variable and `make doctor LATEX_AI_TEMPLATE=...` doing the same; a runtime file and a generated file that differ, listed, and the doctor still passing; an older project shown against the template; a folder that is not a workbench refused with a hint; an installer that exits 2 reported with its own message and not swallowed; the template folder left byte for byte as it was (the doctor runs the installer with bytecode writing off, which the test does not do for it); nothing written into the project; the recipe's seven steps present and in order, each with the words it needs; `upgrading.md` at most 45 lines and pointing at the recipe |
| Thirteen mutations | All 13 caught, each by tests named for it: the record's version shown as the runtime's; a differing version not said to differ; edited files not listed; an unreadable record crashing the doctor; a folder that is not a workbench accepted; a runtime that differs made an error (exit 1 refused); an installer that refuses (exit 2) not made an error; the installer's report not shown; the variable not read; the option ignored; the line that says how to compare removed; the stamp not printed; the stamp not printed when a tool is missing. Two things the first runs showed: one mutation (a folder that is not a workbench accepted) survived because the missing script raised the same error, so the test now asserts the message "is not a workbench folder"; and a mutation that removed `-B` from the installer's command survived because the installer sets `sys.dont_write_bytecode` itself, so the redundant `-B` was removed from the code and that mutation dropped. The last two entries of the script were once the same text under two labels; the second now keeps the stamp out only when a tool is missing, and is caught by the test of the stamp before a missing tool |
| `make -C workbench test` | 523 tests (the 508 of 4.8.1 and the 15 new), 2 skipped (the unreadable-folder test, since this runs as root, and the test that needs GNU Make 3.81, which is not here), OK on 3.13.16, 3.12.13 and 3.11.17 |
| `make -C workbench portability` | All 51 scenarios pass |
| 4.8.1 and this tree, identical projects, each installed and run by its own release | 232 comparisons, 0 differences, none skipped as noise: the eight projects of the earlier comparisons. Masked, because they are the change: the version, the doctor's own output (the stamp and the template line), and the doctor's line in `help` and the manual. Every receipt, every policy and editor file and every other action's output is identical |
| The generated-files guard | Unchanged: the Makefile did not change (Make passes `LATEX_AI_TEMPLATE=...` given on its command line to the recipe, so the doctor needs no new Makefile line). The reference's Makefile needed no edit |
| `make -C workbench upgrade-reference`, then `audit-reference` | The refresh changed `commands.py`, `core.py`, `diagnostics.py` and `workbench.py` in the reference's `.latex-ai/`, and the audit then reports the runtime identical |
| Size | The package is 4,396 lines (4,365 before; `cat workbench/*.py`): `diagnostics.py` 198, `runtime.py` 818. `bootstrap.py` is still 579, under its ceiling of 580. The tests are 7,801 lines (7,637) |

## An agent other than the author followed the recipe

The step's acceptance is that an agent other than its author follows the recipe on a copy, and that its diff and `make check` are recorded. A fresh agent was given a copy of a real project made by 4.6.0, the folder of 4.9.0 as the template,
and only the skill file's "Update" section (not the release notes: its instructions barred `docs/maintainers`, which was my mistake as a brief, found by what it reported, and is the first finding below). It took a snapshot first, then:

- **The diff it ended with**, against the project as installed by 4.6.0: 9 files changed, 207 insertions, 67 deletions. The runtime files are the new release's; the Makefile gained 11 lines and lost none (`export SNAPSHOT_NOTE` and the two snapshot commands, the 11 lines that
  the notes of 4.7.0 say a project from 4.6 or before is missing); `AGENTS.md`, `.gitignore`, `.latex-ai.json`, `CLAUDE.md`, `.claude`, `.codex` and `.vscode` are unmodified, so no policy was taken from the release.
- **`make check`** passed (exit 0) on the updated copy.
- **`make doctor LATEX_AI_TEMPLATE=...`** then printed `records 4.9.0; the vendored runtime is 4.9.0`, all runtime files unmodified, and showed as differing only files the recipe says to read and keep: the project's `AGENTS.md`, its `.gitignore`, and its own `figures` rule in the Makefile.

What it found, and what changed in the recipe because of it (each is now in the skill file; the recipe test holds the seven steps, in order, and the commands each must name, and does not hold the wording of these corrections):

1. **The first pass did not read the release notes**, and guessed at step 5 that the snapshot targets of the Makefile were "new and wanted". A second pass over the notes of 4.7.0 to 4.9.0 found that it had missed nothing: the 4.7.0 entry says the eleven lines are exactly what a project from 4.6 or before is missing, no entry names a `.latex-ai.json` setting that changed, and 4.8.0, 4.8.1 and 4.9.0 say the Makefile and editor files are unchanged. The recipe now names `docs/maintainers/releases.md` as the file to read, and says that "since" means every release after the version in the project's stamp.
2. **A false claim:** the recipe said `make doctor` prints the stamp, which a project from before 4.9 cannot do (its `make doctor` is the old one). It now says to read `.latex-ai/installation.json` by hand, or use `make status`, for such a project.
3. **Step 1 (the snapshot)** assumed a `make snapshot` rule; a project from before 4.7 has none. The recipe now gives `python3 /path/to/workbench/runtime.py snapshot --project ...` for that case.
4. **The direction of `--diff`** was not stated; the recipe now says that `-` is the project's line and `+` the release's.
5. **A runtime file the release adds** (`snapshot.py` for a project from before 4.7) shows as untracked in `git status` after the refresh, which the recipe did not say; step 4 now says to expect it and that the owner commits it.
6. **The record it was told to read was not there:** the notes of 4.9.0 link `verification-4.9.0.md`, and the agent, run before this file was written, reported the folder holding no such file. This file answers that; the link was not wrong, the order of my work was.

Not claimed: that a cold reader opens `releases.md` unprompted. The agent read it only because the second pass told it to. It also reported that the span to read, "since" in step 2, had to be inferred from the stamp; step 2 now says it is every release after the stamp's version.

## Found on the way

- **The doctor runs the release's installer rather than repeating its rule.** The alternative (comparing the project with the template inside the doctor) would have put a second copy of the rule for what "differs" in the project's runtime, and the two would drift. A release that cannot read the project says so with its own message; an exit of 0 or 1 is a report.
- **No Makefile line changed.** The variable is named like `LATEX_AI_BASE`, and Make passes a variable given on its command line to the recipe, so `make doctor LATEX_AI_TEMPLATE=/path` reaches the program as an environment variable. Nothing in the generated Makefile, and so nothing in the guard, moved.
- **A project from before 4.9 cannot print its own stamp,** because its `make doctor` is the old one. The recipe reads the record by hand for it, or asks `make status`; the new doctor is what the template's folder gives it after step 4.
- **The doctor leaves the template as it found it.** Python writes `__pycache__` beside the program it runs unless told not to; the installer sets `sys.dont_write_bytecode` itself, and a test copies the package and asserts that no file appears in it.

## Hosted verification

All six required checks passed on the pull request ([#14](https://github.com/milanmradonjic/latex-ai-workbench/pull/14): [`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38698397762) in 2m37s with TeX Live 2026; the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38698397607), 1m58s to 2m18s each), and again on the merge commit `ff41ee8` on `main` ([`validate`](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38700041807); the [five Python versions](https://github.com/milanmradonjic/latex-ai-workbench/actions/runs/38700041836)).

## Not verified

- **A template older than 4.5 or newer than 4.9.** Only releases whose installer accepts `diff PROJECT` were run (4.9.0 itself, and the fake installers of the tests); an installer of another kind would be an error with its own message, which is the test with the exit code 2, not a real release.
- **A project of another shape than the one the agent used.** One project from 4.6.0 was followed end to end; the differential runs eight projects, but only through the commands, not through the recipe.
- **macOS and Windows,** and a template folder on a network file system.

## Open items

Next in [the plan after 4.4.0](plan-after-4.4.0.md): step 3.8, the tests regrouped by component. The gates (Git guardrails, changed-file routing, the manual) are still the owner's, as are the two launchd agents of 4.8.0.
