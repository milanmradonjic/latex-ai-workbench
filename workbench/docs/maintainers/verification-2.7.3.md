# Version 2.7.3 verification

This follow-up repairs the hosted failure of published 2.7.2 commit
`5bf75cc06c5cfc228b9f52d8fc83c1bb3fd9d9af`.

## Reproduced failure and cause

Both workflows failed on the same regression:
`test_review_oneshell_and_chosen_shell_keep_receipt_ownership`.
The LaTeX AI Workbench run 38110552792 stopped at unit tests, before bibliography
or TeX-container validation. Python compatibility run 38110552778 failed on all
five supported versions. Retrieved job logs show one failure and fourteen
compiler-dependent skips: the adopted recipe launcher reported
`Syntax error: Unterminated quoted string`.

The launcher placed `-c 'exec "$@"'` inside `.SHELLFLAGS`. GNU Make 4.3 splits
these flags on whitespace in its `.ONESHELL` path, treating the quoted command
as multiple arguments. Local GNU Make 4.4.1 accepted it, so the earlier local
suite did not establish this compatibility. The existing regression failed
first in hosted jobs; it has not been weakened or skipped.

## Repair

The generated adapter still uses a single `/bin/sh` executable and overridden
target shell settings. It now passes `.latex-ai/recipe-shell.sh` as the shell
script, followed by runtime arguments and the expanded recipe. The script
executes `"$@"`, preserving the recipe as one argument without nested quoting
inside Make flags. The existing gated process launch and ownership publication
remain responsible for compiler lifecycle. The installer owns the script and
includes it only when LaTeX is enabled; it requires no executable mode bit.

The regression now exercises eight combinations: ordinary/`.ONESHELL` recipes,
`/bin/sh`/`/bin/bash`, and `-c`/`-ec`, with spaces in fixture project paths.

## Validation

Local validation on 2026-10-11, with GNU Make 4.4.1:

| Check | Outcome |
|---|---|
| `make -C workbench test` | 289 passed, no skips, 97.049 s. |
| Expanded launcher regression | All eight combinations passed. |
| Temporary compiler-only portability | 81/81 passed with real pdfLaTeX, LuaLaTeX, XeLaTeX and BibTeX. Fixture lint is explicitly disabled; this does not replace full ChkTeX/Biber coverage. |
| Independent read-only review | No findings. Fresh real-pdfLaTeX fixtures passed ordinary/`.ONESHELL` Bash flags including `-eu -o pipefail`, automatic variables, piped stdin, nested pipe-jobserver Make, parallel overlap and incremental reuse. Installed scripts match source and work with mode 0644. |
| Reference upgrade and audit | Installer-only regeneration; audit has no changes or conflicts. |
| File/policy checks and `git diff --check` | Passed. |

Evidence is retained under `/workspace/latex-ai-audit-3/ci-followup/`, including
the original hosted failure extract, full regression log, compiler-only report
and independent `review/report.md`. The upstream
[GNU Make 4.3 launcher](https://github.com/mirror/make/blob/4.3/src/job.c)
was inspected: its `.ONESHELL` branch tokenizes shell flags with
`find_next_token`, confirming the quoted-flag incompatibility.

This record is prepared before publication. The corrected exact-commit hosted
runs must succeed before treating the hosted failure as closed. Local ChkTeX
and Biber are still missing; full TeX Live 2026 portability and reference lint
must be checked in the hosted TeX action. Broader platform limits remain as
recorded in the [2.7.2 verification](verification-2.7.2.md).
