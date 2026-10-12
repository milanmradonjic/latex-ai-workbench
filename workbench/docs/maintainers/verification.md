# Verification checkpoint — 2026-10-09

The reference at `<repository root>` was initially clean on
`main`, with canonical Make/editor/agent/CI infrastructure. Its baseline
`make check` passed. The original gaps were parameterization, reusable
setup/audit/upgrades, bibliography integration and compiler-log integrity checks.

## Completed

- Dependency-free Python workbench package, reusable templates, JSON config,
  project-local runtime and installation manifest.
- Audit/dry-run, conflict reporting, backups, idempotent setup, safe merge and
  upgrade behavior; no Git mutation or network operation in the installer.
- Configurable root/engine/backend/output, canonical Make commands and editor/CI
  routing. Existing reference permission files remain byte-identical.
- Verified, required Zotero export and deterministic bibliography checks,
  compiler-log citation/reference/label checks and PDF collection.
- Setup, daily work, writer/reviewer, worktree approval, bibliography and upgrade
  guides plus the reusable agent skill.

## Observed validation

The reference is installed at workbench version **2.1.0**, schema 2, with only
LaTeX and bibliography enabled. The core, LaTeX and optional research backends
are separate project-local files. Schema 1 remains supported; migration was
explicitly reviewed through the installer dry-run and applied with backups.
Root, engine, backend, export requirements and build choices are preserved.

Optional modules/profiles support notes-only and numerical projects without TeX.
Explicit numeric/figure runs capture source/config/data and output snapshots,
checks, environment and status. Read-only freshness propagates stale producer
status. Notes-only edits do not invoke scientific checks. Disabling retains
artifacts and module settings; re-enabling restores them. Editor/CI adapters
follow enabled modules. The synthetic example demonstrates the research loop;
no research modules or synthetic scientific results were added to the reference.

| Check | Result |
|---|---|
| Reference `make doctor` | Required Python/Make/latexmk/pdfLaTeX/ChkTeX found |
| Reference `make check` | Passed; PDF current; integrity checks passed |
| Reference `make validate` | Passed through selected file/policy, package regression/portability and manuscript checks |
| Documentation-only validation | Passed without a build or PDF change; broken local link correctly failed |
| Change discovery/selection | Covered staged/unstaged/untracked/deleted paths, missing history, included Markdown/code, recorder/custom inputs and additional input globs |
| VS Code `LaTeX: Check` task | Owner reported canonical `make check` and passing integrity checks on 2026-10-09 |
| LaTeX Workshop build command | Owner reported `Canonical make build`, `make -C <workspace> build` and successful `BUILD_DONE` on 2026-10-09 |
| Reference `make bib-check` | Passed with two real exported entries |
| Reference `make pdf-artifact` | Collected configured PDF successfully |
| Reference audit | Release 2.1 current; no changes/conflicts; required export present |
| Repeated reference init with original options | No planned changes |
| Unit/regression tests | 93 passed with isolated Pandoc 3.12.1, including 15 Markdown installation/integration cases |
| Synthetic portability suite | 54 checks passed, including three TeX engines/backends, notes-only, numeric/figure loop, staleness, relocation, disable/retention and mixed schema-2 project |
| Runtime/manifest consistency and Python syntax | Verified |
| Git diff whitespace check | Passed |
| Manuscript, Zotero export, editor files and Codex/Claude Git guardrails | SHA-256 unchanged; build settings semantically preserved |
| Documentation links | Verified |
| Skill metadata and workflow YAML | Checked with Ruby standard-library YAML and structural assertions |

The bundled skill-creator Python validator could not run because its optional
PyYAML module is absent from the available Python runtimes. No dependency was
installed. YAML frontmatter, required fields, naming, allowed metadata,
description limits, placeholders and reference links were checked separately.

Synthetic artifacts and complete logs are retained at
`<projects folder>/latex-ai-portability-rcnh0roy/`; `report.json`
records results. Tests cover pdfLaTeX/BibTeX, LuaLaTeX/Biber/multiple inputs,
XeLaTeX/nested roots/different outputs, existing Make/editor/workflow files,
an existing `GNUmakefile`,
undefined citations/references, duplicate labels/keys and truncated exports.
That synthetic suite uses explicitly marked fixture entries. The later Zotero
integration check uses copies of the owner's actual export, without editing
metadata or adding citations to the reference manuscript.

## Zotero integration verified

The owner reports Better BibTeX 9.0.71 installed/enabled in Zotero 10.0.6. They
created `LaTeX AI Workbench test` and exported existing references using Better
BibTeX with Keep updated. The destination is
`<repository root>/bibliography/zotero.bib`.

After a second existing reference was added to the collection, the export
changed from one entry to two, sorted by citation key. Bibliography structure
and the reference manuscript checks passed. An isolated offline BibTeX build
with both entries also passed; its files and logs are retained at
`<projects folder>/latex-ai-zotero-smoke-wmqtosj6/`, including
`two-entry-validation.json` and `two-entry-validation.txt`.

The project now requires the exported snapshot in `.latex-ai.json`. Its
manuscript still contains no citations and uses backend `none`; the actual
BibTeX processing was tested in the isolated fixture. Zotero metadata was
not silently repaired or independently checked against publication sources.

## Remaining human checkpoints

No further Zotero setup is required for this reference's current export. The
owner retains control of the collection, metadata and all GUI applications.

Hosted GitHub Actions passed for the prior 1.0.1 publication, commit `d5842e5`:
30 regressions, manuscript integrity and the PDF upload were verified in
run 37896171117.
The owner approved publication of the current implementation. Commit `7ead797`
published both 1.1.0 and the modular 2.0.0 implementation. Its first hosted run
37906302643
exposed installer option ordering on Ubuntu's Python 3.12. Version 2.0.1 uses
the standard library's intermixed argument parser and adds a regression for
both option placements. The repair was published as `cdcd22e` and passed
hosted run 37907031281:
78 regressions, compiler/research portability, manuscript integrity and PDF upload.
The subsequent 2.1 Markdown increment was committed as `da47602`, pushed on the
owner's instruction and passed
hosted run 37909866649.
All 93 regressions ran without skips using Ubuntu's Pandoc 3.1.3; 54 portability
checks, manuscript integrity and PDF upload also passed. The owner
previously verified both the VS Code check task and the LaTeX Workshop build command.
Zotero export behavior was verified through the owner's manual actions and
resulting file changes. Local implementation and editor verification are complete.

The 2.0.0 implementation was committed and pushed on the owner's instruction.
No pulls, branch/worktree changes, host package installations or GUI automation
were performed. The protected research project and old agent worktrees were not
modified. Setup backups are ignored under `.latex-ai/backups/`.

Full canonical validation output is retained in
`/private/tmp/workbench-2-validation.log`; final unit output is in
`/private/tmp/workbench-2-unit-final.log`. The reference-preservation hash/settings
snapshot is `/private/tmp/workbench-2-reference-before.json`. Backups for the
schema/runtime migration are timestamped under the reference `.latex-ai/backups/`.
These temporary logs are local evidence; the retained synthetic `report.json`
and this checkpoint record the durable verification summary.

## Markdown increment verified locally

Version 2.1 adds one optional Pandoc backend for read-only local link/Markdown
anchor/citation checks and explicit HTML export. It does not change any profile
selection or add a watcher, formatter, site framework or code execution layer.
The reference's Markdown module stays disabled, so its required tools and
manuscript/bibliography/editor settings remain unchanged.

The official Pandoc 3.12.1 macOS arm64 archive was downloaded into an isolated
test directory under `Projects/` and verified against the release's SHA-256:
`c2146cf33a583f3ac93eccddf1bb662371d5cfcce1aad1c87ad860cca1435d46`.
No host package was installed and no global PATH or GUI application was changed.
Tests receive that binary's directory only in their process environment.

The synthetic notebook smoke project and logs are retained at
`<projects folder>/latex-ai-markdown-smoke-3dq9t8pl/`.
Its `verification.json` records successful initialization, doctor, full check,
notes-only validation, HTML export and audit. Generated HTML was inspected
structurally for equations, citation entries, relative links and copied images;
no GUI preview was performed. All scientific and bibliography fixture content
is explicitly synthetic. Regression cases cover code remaining literal,
failure-before-write behavior, escaping paths/symlinks, duplicate anchors,
encoded links, source retention, disable/re-enable and project relocation.

Final change-aware validation with the isolated binary is logged in
`/private/tmp/workbench-md-validation.log`; its 54 portability checks and logs
are retained at `<projects folder>/latex-ai-portability-7a32fjkg/`.
Without Pandoc, only its nine real
integration cases are explicitly skipped; core/installation tests still run.
The managed CI provisioned Pandoc and verified this increment in the hosted run
above. The reference keeps Markdown disabled; the real Markdown backend tests
ran through the package regression suite.

## Complete synthetic research pilot

The new project `<projects folder>/latex-ai-research-pilot-ct3hzjvq/`
combines notes, Markdown, numerics, figures, provenance, freshness and LaTeX.
Bibliography, claims, editor and CI integrations are disabled. Its environment
uses the existing Python/Matplotlib installations and the isolated Pandoc binary;
it introduces no global installation or application configuration.

`verification/pilot.json` records the explicit task/validation commands and
their expected outcomes. The scalar decay rate changed from 1.5 to 2 per second.
Configured-output checks compare the actual recorded samples and parameter
snapshot with the analytic solution and exercise zero-rate/convergence cases.
Matplotlib generated SVG/PDF/PNG figures from those samples. Notes and the
handwritten manuscript were updated from the observed values, not fabricated.
The final manuscript and plot were inspected visually from PNG files, and the
compiled PDF text was checked against the current sampled error.

Notes-only validation preserved scientific output/PDF hashes. Changing the
parameter marked both numeric and figure tasks stale; freshness and validation
left outputs and run records unchanged. Running numerics alone left the figure
stale. Explicit figure execution and manuscript updates restored passing full
checks and current freshness. Four successful run records retain verified input
and output snapshots, including both parameter values. An initial manuscript
draft failed ChkTeX's caption/label whitespace check; the source was corrected
and lint remained enabled. Its failed log is retained in the pilot.

The practical follow-up is the [research loop guide](../research-loop.md). These
documentation updates were committed locally on the owner's instruction; the
published runtime implementation is unchanged. Validation of the synthetic model
establishes this tested workflow and its specified numerical checks, not
applicability to a physical system.

## Audit remediation — release 2.1.1

An independent audit of 2.1.0 found eight defects; all are fixed in 2.1.1 with
a regression test each (the new tests fail on the 2.1.0 code, except two
guards that check legitimate reruns are not rejected). Locally reproduced:
105 regressions (the 93 original plus 12 new; nine Pandoc cases skip without Pandoc)
on Python 3.14 and 3.11 with Pandoc 3.12.1 and on 3.9.6 without it, 54
portability checks, and the reference `make check`. The reference was upgraded to
2.1.1 with a timestamped backup; only the installed runtime files and manifest
changed, and its manuscript, bibliography, Makefile, policies, editor, CI and
guardrail files are byte-identical. Commit `9a5e6e2` was pushed on the owner's
instruction and passed hosted run 37922995007:
the planner selected package regressions, portability and manuscript checks; all
105 regressions ran with no skips and no failures (Ubuntu's Pandoc 3.1.3), 54
portability checks passed in the TeX Live container, the manuscript integrity
check passed and the PDF artifact (40,840 bytes, ID 11612104531) uploaded. This is
hosted evidence for the pushed 2.1.1 state only.

### Release 2.1.2

Runs stopped by Ctrl-C or SIGTERM are now recorded as `interrupted` with a finish
time rather than left `running` (a process killed outright still cannot update its
record). It adds one regression that sends both signals to a real run and fails on
the 2.1.1 code. Locally reproduced: 106 regressions on Python 3.14 and 3.11 with
Pandoc 3.12.1 and on 3.9.6 without it (nine Pandoc cases skip), 54 portability
checks and the reference `make check`. The reference was upgraded to 2.1.2: only the
installed `core.py` (version string) and the manifest changed. Commit `d2e24be` was
pushed on the owner's instruction and passed
hosted run 37923801039:
all 106 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3), including
the interruption test, 54 portability checks passed in the TeX Live container, the
manuscript integrity check passed and the PDF artifact (40,842 bytes, ID
11613815206) uploaded.
The documentation-only commit `85e6783` that recorded this ran only the file
checks (run 37924197154):
its Markdown, regression, TeX and PDF-upload steps were skipped.

### Release 2.1.3

The structural duplicate-key check now follows the backend: with BibTeX, keys that
differ only by case are duplicates (BibTeX reports "Repeated entry" and the build
failed with only a generic `latexmk` status); Biber, which accepts them with a
case-mismatch warning, and unprocessed exports keep them distinct. Exact duplicates
stay errors everywhere. One regression covers all three backends and fails on 2.1.2.
Locally reproduced: 107 regressions on Python 3.14 and 3.11 with Pandoc 3.12.1 and on
3.9.6 without it (nine Pandoc cases skip), 54 portability checks and the reference
`make check`. The reference was upgraded to 2.1.3: only the installed `core.py`,
`latex.py` and the manifest changed. Commit `11e9459` was pushed on the owner's
instruction and passed
hosted run 37924556766:
all 107 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3), including
the backend-dependent duplicate-key test, 54 portability checks passed in the TeX
Live container, the manuscript integrity check passed and the PDF artifact (40,840
bytes, ID 11613491759) uploaded.

### Release 2.1.4

Three smaller audit items. (1) Read-only Git queries could rewrite `.git/index`: with
stale file stats the 2.1.3 installer `audit` did, and `git diff` in change discovery
still does under `GIT_OPTIONAL_LOCKS=0`, which it ignores. All queries now run with that
setting and the diff runs against a throwaway copy of the index; a real-repository
test shows the index byte-identical afterwards and fails on 2.1.3. (2) `make doctor`
named whichever `python3` was first on PATH (a different interpreter in the failing
case) and now names the one running. (3) A bare `@name` in Markdown notes is a citation
only when the bibliography module is declared, with the `\@name` escape documented;
bracketed citations always resolve. Locally reproduced: 111 regressions on Python 3.14
and 3.11 with Pandoc 3.12.1 and on 3.9.6 without it (ten Pandoc cases skip), 54
portability checks and the reference `make check`; the reference was upgraded to 2.1.4
(installed runtime, core and manifest only) and its own index did not change. Commit
`ebc1785` was pushed on the owner's instruction and passed
hosted run 37926028189:
all 111 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3), including the
real-repository stale-index test on the runner's own Git and the Markdown mention
test, 54 portability checks passed in the TeX Live container, the manuscript
integrity check passed and the PDF artifact (40,841 bytes, ID 11614301459) uploaded.

### Release 2.1.5

The agent permission guardrails now cover the Git operations `AGENTS.md` names that
they missed: worktree creation/removal, branch rename/copy/force/re-target,
`cherry-pick`, `revert`, `am`, `rm`, `mv`, `tag`, `update-ref`, `filter-branch`,
`remote set-url` and neighbours (33 additional prompt rules in each agent's file,
generated from one list). Checked with Codex's own rule evaluator
(`codex execpolicy check`, local only, not part of the suite): all 33 added
operations plus the existing ones prompt, and 18 read-only commands (`status`, `diff`,
`log`, `show`, `fetch`, `worktree list`, `remote -v` and others) do not. A regression
that parses both files without needing Codex checks that they agree, cover every
operation the policy names and leave inspection prompt-free; it fails on 2.1.4. The
README now lists what prefix rules cannot see (`git branch NAME`, `git config`
writes, `-C`/`-c`/`--git-dir`, aliases, programmatic Git). Locally reproduced: 112
regressions on Python 3.14 and 3.11 with Pandoc 3.12.1 and on 3.9.6 without it (ten
Pandoc cases skip), 54 portability checks and the reference `make check`. The
reference was upgraded to 2.1.5: its two guardrail files gain the new prompts, and
nothing was removed. Commit `217fadb` was pushed on the owner's instruction and passed
hosted run 37927891001:
all 112 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3), including the
guardrail consistency test, 54 portability checks passed in the TeX Live container, the
manuscript integrity check passed and the PDF artifact (40,840 bytes, ID 11615476393)
uploaded. The hosted run does not exercise Codex's rule evaluator; that check was local.

### Release 2.1.6

The installed runtime no longer assumes this repository's layout. Routing of the
distribution's own helpers, tests and templates, the `make -C` test commands and the
generated CI workflow now use `validation.package`, or else `workbench/` when it holds
both a `Makefile` and the distribution's `latex-ai-init`. On 2.1.5 an unrelated
directory called `workbench` with a Makefile selected `unit`, `portability` and
`manuscript` checks (demonstrated on a fixture, where the resulting `make -C workbench`
would have run that project's own Makefile); 2.1.6 selects nothing for it. The two
diverging copies of the `validation` checks in the core are now one shared function. Two
regressions cover detection, relocation, disabling, rejection of unsafe values and the
workflow/commands; both fail on 2.1.5. This reference's own routing was re-checked after
the upgrade (docs select nothing, package tests select unit, runtime and templates select
the full set, skills select policy) and is unchanged. Locally reproduced: 114 regressions
on Python 3.14 and 3.11 with Pandoc 3.12.1 and on 3.9.6 without it (ten Pandoc cases
skip), 54 portability checks and the reference `make check`. The reference was upgraded
to 2.1.6 (installed runtime, core and manifest only). Commit `25d2528` was pushed on the
owner's instruction and passed
hosted run 37928516896:
all 114 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3), including both
package-detection tests, 54 portability checks passed in the TeX Live container, the
manuscript integrity check passed and the PDF artifact (40,840 bytes, ID 11615900352)
uploaded.

### Audit remediation index

| Audit finding | Fixed in |
|---|---|
| Stale declared output recorded as a successful run | 2.1.1 (refined rule, shared current-ness function) |
| Consumed text files undetected without a local recorder file | 2.1.1 |
| Deleted claim evidence passed `validate` | 2.1.1 |
| Lone `=======` treated as a merge conflict | 2.1.1 |
| `venv/` walked by the no-TeX full check | 2.1.1 |
| `make run TASK=...` interpreted shell syntax | 2.1.1 |
| Deleted seed notes/manifests blocked upgrades | 2.1.1 |
| Script run directly as `command[0]` not tracked | 2.1.1 |
| Interrupted runs left `running` | 2.1.2 |
| Case-variant duplicate keys passed `bib-check` under BibTeX | 2.1.3 |
| Git queries could rewrite `.git/index`; `doctor` named the wrong interpreter; `@name` mentions rejected | 2.1.4 |
| Guardrails missed Git operations named by the policy | 2.1.5 |
| Runtime assumed this repository's `workbench/` layout | 2.1.6 |

Hosted CI evidence for every release above is recorded in its section. This index was
first written as if the audit were closed; an independent review of 2.1.1 to 2.1.6 found
that too broad, and the sections for 2.1.7 and 2.1.8 record what it found and how each
point was resolved.

### Release 2.1.7

Response to an independent review of 2.1.1 to 2.1.6, which showed that the run contract
was stated more strongly than it holds: a `touch` after an input change was recorded as
a successful regeneration and reported current, and two concurrent runs of one task
rejected each other's still-current output (both reproduced here before changing
anything). 2.1.7 states the real contract in `research.md` (file identity proves a write,
not attribution, and `touch`, `chmod` and concurrent writers satisfy it), records and
prints a warning when an output has the previous bytes although the inputs or definition
changed, makes the decay example's check compare its result with the current parameters
so a stale or touched result fails, and refuses a second concurrent run of the same task
through an advisory temp-directory lock. Four regressions cover these and fail on 2.1.6
(the touch run exits 0, no warning exists, both concurrent runs fail). The adjudicator's
two scenarios were re-run against the fixed code: without a content check the touch is
still accepted, now with a warning and a documented limit; the overlapping run is refused
and freshness stays current. One portability expectation changed, because the stricter
example check now fails `validate` after a parameter change before the freshness report.
Locally reproduced: 118 regressions on Python 3.14 and 3.11 with Pandoc 3.12.1 and on
3.9.6 without it (ten Pandoc cases skip), 54 portability checks and the reference `make
check`; the reference was upgraded to 2.1.7 (installed core and manifest only). Commit
`e215fb6` was pushed on the owner's instruction and passed
hosted run 37932974588:
all 118 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3), including the four
new ones (the concurrency test ran on the runner's own scheduler), 54 portability checks passed
in the TeX Live container, the manuscript integrity check passed and the PDF artifact (40,841
bytes, ID 11617376619) uploaded.

### Independent review of 2.1.1 to 2.1.6 and its resolution

The original author reviewed the remediation adversarially (report retained at
`<projects folder>/latex-ai-adjudication-g34qjeo9/REPORT.md`). It reproduced 114
regressions and 54 portability checks and judged 2.1.2 and 2.1.3 sound, 2.1.1, 2.1.4 and
2.1.5 sound with limitations and the configurable package path of 2.1.6 not sound. Every
claimed gap was reproduced again here in fresh fixtures before anything was changed. One
proposed direction could not be followed: isolating the shared index does not stop Git
touching it, because every command that loads a split index (`ls-files`, `status`,
`diff-index`) freshens its mtime, so that point became a documentation correction. Anthropic's
permissions documentation was also checked (rules evaluate deny, then ask, then allow; `:*`
equals a trailing ` *`; Bash ask and deny rules are explicitly not a security boundary).

| Review finding | Resolved in |
|---|---|
| A metadata-only `touch` recorded as a regeneration and reported current | 2.1.7: contract stated, same-bytes warning, attribution check in the example |
| Concurrent runs of one cached task rejected each other | 2.1.7: advisory lock |
| Consumed TeX file names containing spaces missed without a recorder file | 2.1.8 |
| Package path with a space broke generated CI; package `.` routed nothing | 2.1.8: quotable subdirectories only, shell-quoted in CI |
| Environment whose marker file Git ignores was checked as project source | 2.1.8: markers found on disk |
| `git fetch` mutates state yet was ungated | 2.1.8: gated with `git remote update` |
| Split index: shared-index mtime changes | 2.1.8: documented as unavoidable; contents tested byte-identical |
| Overbroad wording, stale "(local only)" headings, tests that failed only for a missing API | 2.1.8 |

### Release 2.1.8

The remaining review items as one patch (see the table above); additionally the redundant
`git diff` and `git status` allow entries are removed, since Claude Code already runs read-only
forms of `git` unasked and an explicit `git diff:*` allow would also permit `git diff
--output=PATH` (this relies on that documentation, not on an end-to-end prompt test). Seven
new or changed regression cases cover the spaced names, the real generated CI commands (they are run
through `sh -c`, not string-matched), the unsafe package values, an ignored marker in a real
repository, a split index, and the flipped `fetch` expectation. Four fail on 2.1.7 for behavioural
reasons (the spaced names, the CI commands and package values, the ignored marker, the guardrails);
the split-index test is a guard that passes on both; two older tests were only reordered to lead
with behaviour and also pass on 2.1.7. The adjudicator's own
probe script was re-run against the fixed code: the spaced name routes, the generated command
`make -C 'tools/kit space' test` succeeds, the ignored-marker environment is no longer listed, and
the only remaining Git metadata change is the split index's shared-index mtime. Locally reproduced:
121 regressions on Python 3.14 and 3.11 with Pandoc 3.12.1 and on 3.9.6 without it (ten Pandoc cases
skip), 54 portability checks and the reference `make check`; the reference was upgraded to 2.1.8
(installed runtime, core, manifest and both guardrail files). Commit `c183198` was pushed on the
owner's instruction and passed
hosted run 37934439819:
all 121 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3), including the real-
repository tests (ignored marker, split index) on the runner's own Git (its log reports 2.55.0), the
generated-CI-command test and the guardrail test; 54 portability checks passed in the TeX Live
container, the manuscript integrity check passed and the PDF artifact (40,840 bytes, ID 11618036641)
uploaded.

### Release 2.2.0

A way to flag workbench defects as they are met, agreed after weighing a proposal for agents to
flag them by instruction alone. By my count about two thirds of the roughly twenty-two defects
fixed in 2.1.1 to 2.1.8 were silent (a check skipped or a wrong result accepted) and only about a
third announced themselves, so the capability is mechanical first and an instruction second.
(1) Unexpected exceptions in the runtime and installer are labelled `INTERNAL ERROR` with exit
status 70, apart from `ERROR` diagnostics (1; installer 2); the traceback is kept in the OS temp
directory, so read-only commands stay read-only. (2) `make issue` writes one local, ignored
report (version, installed files against the manifest, configuration, plan, run records, tool
versions, Git state, recent faults), works with a broken configuration, never includes
environment variables and sends nothing. (3) `AGENTS.md` says what counts as a suspected defect and
forbids editing `.latex-ai/` or weakening a check to get past it; repairs go through the
distribution with a failing test first and independent review.

Narrowing the label exposed malformed hand-edited data that crashed instead of being diagnosed, so
it was fuzzed first: every key of the configuration, task manifests, claims and a run record was
deleted or replaced by seven wrong values. Of about 860 research-side mutations 11 escaped as raw
exceptions (an unhashable claim `status` or check `cost`, a damaged run record), and a schema-1
configuration produced ten more (a missing `root` or export `path`, unhashable `engine`, `backend`
or export `format`, and a missing `ci` section in the workflow generator). All are now diagnostics;
re-running the fuzz found no internal fault in about 570 configuration mutations over three project
shapes (schema 1, schema 2, and schema 2 with CI and editor adapters) nor in the research sweep.
Two regressions encode this (the research sweep runs in the suite; the legacy cases fail on 2.1.8
with the original exceptions), plus tests for the exit-code split with a provoked fault, the report
(contents, a canary environment variable absent, a locally modified managed file named, a broken
configuration), the Make target with hostile text, the installer's classification and the policy
text. A real installed project was driven through the flow: a simulated defect exited 70 with the
instructions, an ordinary stale result exited 1, and `make issue` captured the fault and the run
records. This does not catch a plausible wrong result that passes every check; attribution checks
remain the answer to that. Locally reproduced: 128 regressions on Python 3.14 and 3.11 with Pandoc
3.12.1 and on 3.9.6 without it (ten Pandoc cases skip), 54 portability checks and the reference
`make check`; the reference was upgraded to 2.2.0 (runtime, core, the new `diagnostics.py`, the
policy, the Makefile and the manifest). Commit `9cf3495` was pushed on the owner's instruction
and passed
hosted run 37938049039:
all 128 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3), including every new
test above, 54 portability checks passed in the TeX Live container, the manuscript integrity
check passed and the PDF artifact (40,841 bytes, ID 11619212115) uploaded.

### Release 2.2.1

The 2.2.0 defect-flagging policy was tried on sub-agents. Eight defect classes were planted in the
distribution (a bare `=======` flagged as a conflict marker, a `pyenv.cfg` typo that makes a venv
get scanned, a `KeyError` on an optional task key, an untouched output accepted as fresh, claims
evidence read from the wrong configuration, file names with spaces hidden from the dependency scan,
freshness comparing recorded inputs with themselves, and a JSON syntax error swallowed), each given
to one agent on 2.2.0 and one on 2.1.8, with three defect-free controls per condition; a first
round with defects planted by editing installed files served as a pilot and its flaws (the manifest
comparison exposed the plants, overt plants, one defect never exposed) were corrected in the
second. Over both rounds (15 exposed defects per condition, one agent per cell, one grader, the
same model) agents on 2.2.0 flagged 15 of 15 and wrote a formal `make issue` report in 14, repaired
or worked around nothing; agents on 2.1.8 flagged 12 of 15, wrote no report, edited `.latex-ai/` in
two runs and rewrote the user's valid content to satisfy a wrong checker in two. The difference in
flagging is not significant (one-sided Fisher p = 0.11, or 0.24 if r74 is counted as flagged: its
report called the freshness and success verdicts false but blamed the project's scripts, not the
planted workbench line). It is a small exploratory trial in which the policy, the report command,
the fault label and the release differ together, so it does not isolate the policy's effect (see
the 2.2.2 correction). All 12 controls were free of false flags, and the runs left no recorded
history or index change (subjects were told not to run state-changing Git commands, so this says
little about the policy). The blinding was formal only (2.2.0 agents quote the policy and leave
report files) and one scenario carried a project-side bug that is a legitimate alternative
explanation for its symptom. Results and harness are kept in the audit directory.

The trial found two faults in 2.2.0. (1) `make issue` computes the validation plan, so when the
defect was in shared code that the plan uses (a `KeyError` in task expansion) the command crashed
with the same fault and captured nothing, while its own message said to run it; reproduced on the
trial fixture. It now collects the plan, configuration and each evidence section separately and
records a failure as that section's content, so the rest of the report is still written (two
regressions: a fault planted in the installed `research.py`, driven through the real command and
checked against the fault just seen; and each diagnostics section, and configuration loading,
failing in turn). Both fail on 2.2.0. (2) The policy and docs named "exit status 70" as the signal,
but `make` prints `Error 70` for the recipe and exits 2 itself, so a caller checking `make`'s
status would not see it; the policy now points to the `INTERNAL ERROR` label and the README states
the `make` behaviour. Locally reproduced: 130 regressions on Python 3.14, 3.11 and 3.9.6 (ten
Pandoc cases skip here, as Pandoc is not installed in this environment), 54 portability checks
and the reference `make check`; the reference was upgraded to 2.2.1 (runtime, core,
`diagnostics.py`, policy and manifest). A first attempt to run the three interpreters in parallel
failed one test on each: background shell jobs inherit an ignored SIGINT, which the interrupt test
needs; run in the foreground they pass. Commit `e947c8a` was pushed on the
owner's instruction and passed
hosted run 37950334812:
all 130 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3 and Git 2.55.0), including
both new `issue` tests, 54 portability checks passed in the TeX Live container, the manuscript
integrity check passed and the PDF artifact (40,841 bytes, ID 11626375948) uploaded. The run
carries a runner notice that `ubuntu-latest` migrates to Ubuntu 26 on 19 October 2026; the first
run after that date should be read for changes in Pandoc, Git or the TeX Live container.

### Release 2.2.2

An independent adjudication of 2.2.1 (a separate agent, reading the code, rerunning the suites and
re-grading the round-two reports before seeing the author's grades) confirmed the report fix on a
copy of the exact failing fixture, both new tests failing on 2.2.0 and passing on 2.2.1, 130 tests
on Python 3.14, 3.11 and 3.9.6 and 54 portability checks, and found no regression. Its one defect
is fixed here: the installer keeps a project's own `issue` Make target and installs only
`latex-ai-issue`, but the policy, the short policy added to existing `AGENTS.md` files, the
internal-fault message, the skill and the README all told readers to run `make issue`, which in
such a project ran the project's recipe, exited 0 and wrote no report (reproduced by the
adjudicator; present since 2.2.0). They now name `make latex-ai-issue`. One regression builds
a project with its own `issue` recipe, reads the command out of the policy template, runs it and
checks that a report is written and the project's recipe is not, that `make issue` still reaches
the project's recipe, and that the runtime message, full policy, short policy and skill name the
same command and none of them the bare alias; it fails on 2.2.1 with the project's recipe having
run. Two older assertions were updated to the new name. Locally reproduced: 131 regressions on
Python 3.14 with the isolated Pandoc 3.12.1 on `PATH` (no skips) and on 3.11 and 3.9.6 without it
(ten Pandoc cases skip), 54 portability checks and the reference `make check`; the reference was
upgraded to 2.2.2 (runtime, core, policy and manifest).

Corrections to the 2.2.1 record, from the same adjudication. (1) Pandoc: the isolated 3.12.1
used for the earlier local runs is
`<projects folder>/latex-ai-markdown-tools/pandoc-3.12.1-arm64/bin/pandoc` (archive
SHA-256 `c2146cf33a583f3ac93eccddf1bb662371d5cfcce1aad1c87ad860cca1435d46`); it is not on the
ordinary `PATH`, which is why ten cases skipped, and it is not an installed system tool. (2) The
trial's conclusion above is descriptive only. Counts by round: pilot, 2.2.0 flagged 7 of 7 with
7 reports and no repair or workaround, 2.1.8 flagged 6 of 7 with one repair and one workaround;
corrected round, 2.2.0 flagged 8 of 8 with 7 reports (r63's capture failed), 2.1.8 flagged 6 of 8
(7 if r74 is counted) with one repair and one workaround. "Flagged" is rubric-sensitive: counting
a warning that a verdict is false as a flag gives 13 of 15 for 2.1.8. Zero reports under 2.1.8 is
partly a capability difference, since it has no report command. The policy's examples of a
suspected defect match the planted classes, and the S1 fixture carries a real project-side bug.
Nothing here shows what the policy alone does, or a general rate. (3) The adjudicator's remaining
notes are not addressed by this release: `issue` still cannot run if the runtime cannot import or
the report directory is unwritable, and its post-write summary assumes the usual shape of each
section; neither reproduces the original failure, and both are left until real use meets them. Commit `815fd7e` was pushed on the owner's
instruction and passed
hosted run 37955577228:
all 131 regressions ran with no skips or failures (Ubuntu's Pandoc 3.1.3), including the new
adoption test, 54 portability checks passed in the TeX Live container, the manuscript integrity
check passed and the PDF artifact (40,840 bytes, ID 11626949855) uploaded.

### Release 2.3.0

Ease of use, in three parts agreed after asking what a first-time user meets: (1) `make help`
and `make status`; (2) the installer's closing summary, a note when a project's own target keeps a
workbench alias's name, and `Hint:` lines on the most common expected errors; (3) the user
documentation reorganised around a short README, a quickstart and an "I want to…" page, with the
maintainer material moved under `docs/maintainers/`. Each part has regressions written first:
`help` and `status` (what each lists for a core and a research project, the usable name where
the project has its own `help` and `issue`, a broken configuration, a read-only `status` before
and after runs and a parameter change, Git and locally modified installed files, and a test that
every Make target the installer generates for each of the five profiles is described by `help`);
the installer's summary for audit, dry run, apply and an up-to-date upgrade, and the kept-target
notes; and the hints (a missing installation, a disabled module, a missing or unknown task, stale
outputs, a missing tool). All relative links in the Markdown under `workbench/` were checked
after the move, the only unresolved one being an illustrative example inside `markdown.md` that
was already there. Nothing was tried on people: whether the new output is clearer is the author's
judgement, not a measurement. Locally reproduced: 140 regressions on Python 3.14 with the
isolated Pandoc 3.12.1 on `PATH` and on 3.11 and 3.9.6 without it (ten Pandoc cases skip), 54
portability checks and the reference `make check`; the reference was upgraded to 2.3.0 (runtime,
core, LaTeX backend, the new `guide.py`, policy, Makefile and manifest). The release went to GitHub as
three commits (`883021b` help and status, `ada7b9a` installer summary and hints, `99e735e`
documentation) pushed together, with a fourth after a failure. Hosted run
37958566111 on `99e735e`
failed one new test: `make test` sets `MAKEFLAGS`, so the Make child the help test ran printed
"Entering directory" and its exact-output comparison failed. Local runs had used `python -m
unittest` directly and never saw it; the helper now removes the inherited Make variables, the suite
is verified as CI runs it (`make -C workbench test`), and that is how it should be run before a push.
The fix, `6957b60`, passed hosted run 37958860184:
all 140 regressions with no skips or failures (Ubuntu's Pandoc 3.1.3). Hosted coverage is
therefore partial: the first run stopped at the unit step and the second, which changed only a
test file, selected only unit tests, so none of these runs executed the portability checks or the
manuscript build against 2.3.0. Those ran locally on the final code (54 portability checks and the
reference `make check`; the fix changed only a test). Release 2.3.1 closed the gap.

### Release 2.3.1

Follows an independent adjudication of the 2.3.0 hosted record, which confirmed the coverage gap
described above and advised a way to run the full set of checks on demand, since another push of
the same code was the only means. Both generated workflows (LaTeX and core) now also start on
`workflow_dispatch`; ordinary pushes and pull requests stay change-aware. A manual run has no
previous revision, so `LATEX_AI_BASE` is the empty string and the planner's existing fallback ("no
usable comparison revision") selects full validation. One regression checks that both generated
workflows carry the trigger and the empty-base expression, and, in a real Git repository, that a
clean tree selects no paths while an empty base selects the manuscript and file checks with the
full-validation note. `docs/validation.md` explains how to start a run (Actions, Run workflow, or
`gh workflow run`). Locally, run through `make test` as CI runs it: 141 regressions on Python 3.14
with the isolated Pandoc 3.12.1 on `PATH` and on 3.11 and 3.9.6 without it (ten Pandoc cases skip),
54 portability checks and the reference `make check`; the reference was upgraded to 2.3.1 (its
workflow gains only the trigger line; action versions are untouched). Commit `3d4b2b6` was pushed on the owner's
instruction. Its own push, which selected everything because a workflow file is a control file,
passed hosted run 37982023165:
all 141 regressions with no skips or failures (Ubuntu's Pandoc 3.1.3), 54 portability checks in the
TeX Live container, the manuscript integrity check and the PDF artifact (40,841 bytes, ID
11641049456). The new trigger was then used once, `gh workflow run latex.yml --ref main`, and
hosted run 37982451732
(event `workflow_dispatch`, same commit) logged "full validation selected: No usable comparison
revision", selected files, policy, unit, portability, manuscript and bibliography, and passed the
same 141 regressions and 54 portability checks and uploaded the PDF (40,842 bytes, ID 11641074850).
Because that commit contains all of 2.3.0's code, this is the first hosted run of the portability
checks and manuscript build against it. Markdown and research steps were skipped in both runs,
as the reference enables neither module.

### Release 2.3.2

Follows a code review of releases 2.2.2 to 2.3.1 (`816fec8..ded4575`) run in the working session
at the owner's request. It reported fifteen findings, thirteen reproduced in scratch projects
before any fix; nearly all were in the 2.3.0 orientation and summary work, and the 2.3.1 trigger
itself came out clean. The owner asked for all of them to be fixed. The release notes list the
changes; in short:

| Finding | Resolution |
|---|---|
| `make help` empty where a `GNUmakefile` sits beside a `Makefile` | one `active_makefile` in `guide.py`, in GNU Make's own order, shared with the installer |
| Policy told agents bare `make help` / `make status` | policy and short policy name `make latex-ai-help` / `make latex-ai-status` and explain the kept-target rule |
| Status counted seed files and editor settings as changed installation files | only whole files the installer owns are compared; seeds are `project-owned` |
| Installer summary ignored `GNUmakefile` / `makefile` | the planned text of whichever name is active is used |
| A project's own `doctor` / `clean` shown as the workbench's | `doctor`, `bib-check`, `pdf-artifact`, `clean` gain reserved names; `build` / `lint` are listed only with a manuscript |
| Enable hint failed on schema 1 | the hint adds `--migrate-config` there and shows the installer by path |
| Audit's apply command dropped its options | the command is rebuilt from the parsed options, with the installer's real path, shell-quoted |
| Audit said "current" beside exit status 1 | a record-only change is described as such, on audit and on apply |
| Quickstart's first command failed on an empty folder | installer errors print `Hint:`; the root error points to the profiles; the quickstart shows the command |
| Status gave `INTERNAL ERROR` for a damaged `installation.json` | status diagnoses it; the installer reports `ERROR:` with a hint (exit 2) |
| "Nothing pending" when that was not known | said only when known; no Git history suggests the full check, a changed installed file an audit |
| Makefile `TASK` guard hid the better message | guard removed; the runtime answers, naming the declared tasks under the name that works |
| Help and status showed a raw `FileNotFoundError` without a config | the same plain message and next step as every other command |
| Generated CI called short Make names a project may own | workflows call only `check` and reserved names |
| New status test needed Git without a skip guard | guarded, and it no longer needs `git init -b` |

Each fix has a regression test that was seen to fail first (fifteen new tests; four existing
ones adjusted). Locally, through `make test` as CI runs it: 156 regressions on Python 3.14, 3.11
and 3.9.6 with the isolated Pandoc 3.12.1 on `PATH` (no skips), 54 portability checks and the
reference `make check`; the reference was upgraded to 2.3.2 (Makefile, policy, runtime files and
workflow; action versions untouched) and audits as current. Commit `373f4a8` was pushed under the
owner's standing instruction for release work.

**The first hosted run failed, and why.** Hosted run 37987900963
stopped at the package tests: 155 of 156 passed and one new test,
`test_status_only_says_nothing_is_pending_when_that_is_known`, failed. The generated workflow
exports `LATEX_AI_BASE` for the whole job, so the package's own test step inherits it; `make status`
in a throwaway fixture then compared against a commit that fixture does not have, fell back to
"every file changed" and suggested `make validate` where the test expected "Nothing pending". It is
a defect of the test helper, not of the release: the same helper already stripped `MAKEFLAGS` after
the equivalent 2.3.0 failure. It was reproduced locally by exporting the variable, the helper now
strips it too, and the suite was rerun with the variable set to a foreign revision, set empty (a
manual run) and unset, on all three interpreters (156 pass each). Lesson recorded: `make -C
workbench test` locally is not the whole of CI's environment; before a push, also run it once
with `LATEX_AI_BASE` exported.

Commit `1a1144e` (the helper fix) passed hosted run 37988789389:
156 regressions, no failures. That push changed one test file, so it selected only file checks and
the package tests, and the failed first run had stopped before the TeX steps. The manual trigger
added in 2.3.1 was therefore used, `gh workflow run latex.yml --ref main`:
hosted run 37988913818
(event `workflow_dispatch`, commit `1a1144e`) logged "full validation selected: No usable
comparison revision", selected files, policy, unit, portability, manuscript and bibliography, and
passed all 156 regressions, 54 portability checks in the TeX Live container and the manuscript
integrity check, and uploaded the PDF (40,842 bytes, ID 11644605969). The PDF was collected with
`make latex-ai-pdf-artifact`, so the reserved names the workflow now calls are exercised on the
hosted runner. Markdown and research steps were skipped, as the reference enables neither module.

Not done: the fresh-user trial planned after 2.3.0 has still not been run, so the usability of
`make help`, `make status` and the installer summary rests on these tests and on the review, not on
observation of new users or agents.

### Release 2.3.3

Follows the user trial of 2.3.2 that the 2.3.2 record listed as not done. The session agent ran it
itself, without fresh agents: ten journeys through the user documents with the commands as printed
(150 commands in 14 throwaway projects, with real TeX builds) and a sweep of every command the
documents, the examples, the agent policy and the skill show (27 Make targets, 8 installer options
and 2 direct runtime commands, all present). Because the tester wrote the code under test, it was
a scripted walkthrough and not a blind test. It reported thirteen findings: four where a user was
blocked or misled and nine smaller ones. The report, transcripts and scripts are in
`<projects folder>/latex-ai-user-trial-6nKb09Zh/` (`REPORT.md`, `logs/`, `scripts/`).
The owner asked for all of them to be fixed.

| Finding (friction) | Resolution |
|---|---|
| ChkTeX warnings failed the first check before the build, hiding TeX errors, with no hint (2) | the full check builds and verifies first, then lints; a lint failure carries a hint naming `.chktexrc`, `lint.args` and `lint.enabled` |
| A JSON syntax error did not name its file (2) | one reader for project JSON files names the file; file checks do the same for ordinary data files |
| An added Makefile target blocked every later upgrade of a fresh project (2) | in a Makefile, `AGENTS.md`, `CLAUDE.md` or `.gitignore` installed whole, lines above or below the installed text are the project's and survive upgrades; a change inside still blocks, saying so, and `--diff` prints it |
| The look-first preview printed 2,281 lines with the summary on line 23 (2) | new runtime and guardrail files are listed by name and size (428 lines for the same paper); the summary is printed last |
| Change-aware validation silently needs Git history (1) | the quickstart says so; the fallback note is in plain words |
| Through a pipe, `ERROR:` came before the lines explaining it (1) | output is line-buffered in the runtime and the installer |
| Research: the suggested first check fails; a failing task check gave a traceback and no hint (1) | `make status` is among the installer's next steps; the freshness report is printed first; a failing check names its task and the commands that refresh it; failures show the whole command; `run`/`figure` warn about and record a stale producer |
| Task-manifest errors were terse and unanchored (1) | they name the manifest and show the expected form; status and hints point to `docs/research.md` when nothing is declared |
| Targets in an included makefile were invisible to the installer (1) | literal `include` files are read when existing targets are collected |
| The full policy listed short names a project may own (1) | it names every command by its `latex-ai-` form except the shared `check`, `build` and `lint` |
| The default paper install added editor and CI files unannounced (1) | a note names both and the flags that decline them; the quickstart says it |
| Installer errors without hints (1) | hints for a missing folder, an undetermined engine (with `--build-command` when the Makefile has no `build` target) and a profile passed to an installed project |
| Small print (1) | quiet recipes; a final "passed" line; a doctor hint per missing tool; `bib-check` described as what it checks; uncommitted files counted as files |

Each fix has a regression test that was seen to fail first (thirteen new tests; two existing
ones adjusted). The situations the trial flagged were then rerun by hand against the fixed code:
the lint failure with its hint, the TeX error now reported, an upgrade from 2.2.2 with a target
added to the generated Makefile (merged, with status reporting no changed file), the 428-line
preview, and the stale-result messages. Locally, through `make test` as CI runs it: 169 regressions
on Python 3.14, 3.11 and 3.9.6 with the isolated Pandoc 3.12.1 on `PATH` (no skips), each also
with `LATEX_AI_BASE` exported as hosted CI sets it (the lesson of 2.3.2), and once with it empty;
54 portability checks and the reference `make check`. The reference was upgraded to 2.3.3
(Makefile, policy and runtime files; the workflow is unchanged) and audits as current. Commit
`f732c83` was pushed on the owner's instruction.

Its push selected every job, because installed runtime files are control files, and passed at the
first attempt: hosted run 37994243372
selected files, policy, unit, portability, manuscript and bibliography, passed all 169 regressions
with no skips or failures, the 54 portability checks in the TeX Live container and the manuscript
check (which now ends "Full check passed: latex, bibliography"), and uploaded the PDF (40,840
bytes, ID 11646856123). No manual run was needed. Markdown and research steps were skipped, as the
reference enables neither module.

Behaviour that changed beyond messages, for anyone upgrading: the order of the full check (build,
integrity, lint); `check` depending on the integrity target before `lint` in adapted Makefiles;
quiet recipes in every generated Makefile; whole-file Makefile, policy and ignore files accepting
additions around the installed text; and run records carrying an optional `stale_upstream` list.

Not done: a blind trial. The findings above are what breaks or misleads when the documents are
followed literally by someone who knows the system; what a newcomer or a fresh agent would fail to
guess is still untested.

### Blind trial of 2.3.3, and release 2.4.0

**The trial.** At the owner's request three fresh agents (Claude Haiku 5.5, one run each, about
407,000 tokens and 102 tool calls) tried release 2.3.3 without seeing its source, tests or these
records; their transcripts confirm that none was opened. The owner chose a stand-in project over a
real one: a multi-file paper with a BibTeX bibliography, its own Makefile, simulation and plot
scripts with existing results, notes and editor settings, built by the session agent with no
planted defects. One agent adopted the workbench from the documents, one brought the simulation and
figure under it and followed a parameter change through, and one worked as a coding agent in an
already-adopted copy with only the project's `AGENTS.md`. All three reached their goals without
help; the session agent reran the checks in each copy. No new blocking defect was found. Twelve
findings were graded; the one that mattered was that both newcomers got past the ChkTeX gate by
silencing warning kinds, one of them all five that appeared. The report, the three project copies
and the raw transcripts are in `<projects folder>/latex-ai-blind-trial-D1uNHKkp/`.
Limits: one run per cell, one model, one synthetic project built by someone who knows the system.

**The decision.** The owner left the choice of what to fix, and how, to the session agent, with
the earlier remark about simplifying what had grown by accretion in mind. Done:

| Change | Why |
|---|---|
| New installations are always written in schema 2, with unchanged defaults | one format; no migration step to turn a module on; schema 1 is still read |
| `guide.COMMANDS` carries each command's action and enabling modules, and the installer generates every reserved Make target from it | command names had been written in four places, which is where most findings of the last three rounds came from |
| Generated workflows hold only the steps of modules that are on | a step for a module that is off named a target the project lacks; one agent found it confusing |
| Lint baseline: `make latex-ai-lint-baseline` writes `.chktex-baseline.json`; only new warnings fail afterwards | adopt the gate on an existing paper without silencing the checker |
| Engine read from the project's own build files when they name exactly one | both adopters had to read their Makefile to answer the installer |
| Status order, "passed" lines, one line for run records, an example in new manifests, wording | the smaller graded findings |

Not done, on purpose: marked blocks for every installed file (it would rewrite every installed
project's files, and 2.3.3 already lets users add around the installed text); a quieter TeX log
(it risks hiding error context); registering existing results without a run (untested either way:
the stand-in's simulation reruns in milliseconds).

**Verification.** Seven new regression tests, each seen to fail first, and four portability checks
that drive the real ChkTeX through a warning, the baseline and a new warning. Nine older tests
that relied on a plain install writing schema 1 now build that format explicitly, so schema 1
stays covered, and one reads the root through the format-neutral view; two portability steps edit the configuration in its new place. Locally, through
`make test` as CI runs it: 176 regressions on Python 3.14, 3.11 and 3.9.6 with the isolated Pandoc
3.12.1 on `PATH` (no skips), with `LATEX_AI_BASE` unset, empty and set as hosted CI sets it; 58
portability checks; the reference `make check`. By hand: the adoption path on the trial's stand-in
project (engine read from its Makefile, 16 warnings accepted by the baseline, check passing, four
new warnings failing), and upgrades from release 2.2.2 of a fresh project with a target added to
its Makefile and of an adopted project (both pass their checks; the schema 1 configuration is left
as it is). The reference was upgraded to 2.4.0: Makefile, policy, runtime files, and a workflow
that loses the Markdown and research steps because it enables neither module.

Commit `b508bfb` was pushed under the owner's instruction to decide and fix. Its push selected
every job, because the workflow and the installed runtime files are control files, and passed at
the first attempt: hosted run 37999736060
ran all 176 regressions with no skips or failures, all 58 portability checks in the TeX Live
container (so the machine format used for the baseline works with TeX Live's ChkTeX as well as
MacTeX's), and the manuscript check, and uploaded the PDF (40,842 bytes, ID 11647994553).

Not covered: the research and Markdown steps of a generated workflow have still never run on a
hosted runner, since the reference enables neither module; the baseline has been used on one real
manuscript-like project only; and no person other than the session agent has tried the release.


## 2.5.0 architecture changes — local verification, 2026-10-10

Implemented against reference commit `0c31e3f7a6589f268f0b28ea38c095195ef35e16`.
The workspace is a byte-verified source snapshot retrieved through GitHub;
the shell network proxy was unavailable, so it is not a Git checkout.
These results describe local validation before publication; subsequent commits
and hosted runs are recorded separately.

- `make -C workbench test`: 191 tests passed, including 15 architecture
  regressions. Coverage includes path aliases, hard links, dependency routing,
  stale custom artifacts, a real pdfLaTeX custom/incremental build, installer
  process death, recovery preserving subsequent edits, lock contention,
  manifest ordering, profile/CI action parity and reference regeneration.
- Independent review of receipts, recovery, paths and atomic records found no
  concrete false-success or state-loss defect. Undiscoverable custom build inputs
  still require explicit declarations; this limit is documented.
- Installer upgrade regenerated the reference. Subsequent audit: version 2.5.0,
  zero pending changes, zero conflicts. Source and installed runtimes match.
- Changed-file syntax/policy/link checks passed. Generated workflow YAML parsed.
- Reference manuscript compilation and citation/reference verification passed.
  `make check` then failed because `chktex` is absent. Compiler portability also
  reached its first pdfLaTeX/BibTeX check and stopped at the same missing tool.
  `biber` is also absent. These checks remain incomplete; no lint setting or
  baseline was relaxed to obtain a passing result. Dependency installation was
  blocked by the unavailable network proxy.

Manuscript source, bibliography exports, agent policies and permission rules
were preserved. Build artifacts, transaction backups and local issue evidence
remain local. Remote CI and the full compiler/lint matrix still need validation
in an environment with the declared tools.


### Package installation retry

The owner requested installation without refreshing package lists. The existing
APT lists cannot locate `chktex` or `biber`, and no cached packages or existing
executables were found. No package-list update or package upgrade was performed
on this retry. System package directories are read-only in the managed workspace.
Local lint and the full compiler-portability matrix therefore remain incomplete;
the standard hosted workflow is the next verification route after publication.


### Hosted verification after publication

Architecture commit `8b2608c2b83637c5276a6fc60c088531ad13d63d` was committed and
pushed to `main` under the owner's instruction. Its
hosted run 38045363560
passed the file/policy checks, workbench regressions, all 58 compiler-portability
checks, the reference manuscript build and ChkTeX lint, and PDF collection.
The portability matrix included LuaLaTeX/Biber, pdfLaTeX/BibTeX, XeLaTeX,
custom Make builds, lint baseline rejection/acceptance, and negative integrity
checks. The manuscript artifact was uploaded (40,840 bytes, ID 11667398643).

The hosted regression suite ran 191 tests with one expected skip: the real
custom-compiler regression needs latexmk/pdfLaTeX on the host runner. That test
passed locally; the hosted compiler container separately validated custom Make
builds in the portability suite. The other 190 hosted regressions passed.
The published tree was checked against all 20 local changed-file blob hashes.
Local package installation remains unavailable, but the remaining full checks
have now passed in the hosted environment with the required TeX tools.
