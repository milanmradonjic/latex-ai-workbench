# Version 4.10.2: code audit and repairs

Audited the current public repository on 15 October 2026. The clean local `main`
and remote `HEAD` both pointed to `89a7f3a50e3175b79e2c7eeda99796ec29f9b7f9`
(4.10.1). Repairs are on `audit/4.10.2-code-audit`.

## Scope and findings

Read all production Python modules, the command registry, installer and runtime
boundaries, output recovery, process ownership, snapshot retention, configuration,
generated templates, and CI definitions. Inspected relevant regression tests and
documentation, ran the complete suite and real-compiler scenarios, and added
adversarial probes using disposable synthetic projects.

| Finding | Observed on 4.10.1 | Repair and regression evidence |
|---|---|---|
| F1, P1: PDF export can overwrite authored files | A symlink or hard link from `artifacts/documents/paper/document.pdf` to `main.tex` makes `artifact` exit successfully after replacing the source with PDF bytes. Redirecting its parent directory also allows overwriting an authored figure. | Refuse linked export destinations and redirected parents. `ExportSafetyAudit.test_export_refuses_a_symlink_to_source`, `test_export_refuses_a_hard_link_to_source`, and `test_export_refuses_a_redirected_parent_directory` preserve the sentinel source bytes. |
| F2, P2: export can publish partial or unverified bytes | An I/O failure partway through `shutil.copyfile` destroys the previous usable export. A PDF changed during copying is also published successfully despite no matching verified receipt. | Copy to a temporary sibling, recheck receipt freshness and the copied PDF's digest, then replace the destination. Preserve its mode and remove failed temporary files. `ExportSafetyAudit.test_failed_export_preserves_the_previous_complete_pdf` injects a partial write and I/O error; `test_a_pdf_changed_during_copy_is_not_published_as_verified` changes the compiler output inside the copy operation. |
| F3, P2: doctor checks the wrong build tools | A missing custom executable is never checked; native tools on PATH yield “All required tools found.” Conversely, a working custom builder requires `latexmk` and `pdflatex` unnecessarily. | Check the custom command's first executable, or the native tools for a native build. Keep enabled lint and bibliography requirements. The two `ConfigurationAudit.test_doctor_*` tests cover missing and available custom builders. Hidden tools inside scripts still need the owner's checks. |
| F4, P2: malformed configuration becomes an internal fault | A non-object `modules.bibliography` produces exit 70 when `latex` is written first, but an ordinary input error when it is written second. Document resolution expands the bibliography before its shape has been checked. | Validate every module's object shape before resolving any document. `ConfigurationAudit.test_malformed_bibliography_is_an_input_error_in_either_module_order` checks six invalid values in both orders. A further 104 field/value probes produce no unexpected exception. |
| F5, P2: document build guidance can invoke cleanup | A document named `clean` is offered `make clean` as its build command. Any unrelated same-named target is also assumed to build that document, and the fallback assumes `build` is still the workbench alias. | Recognize the generated document recipe, and use the usable build command for the fallback. Both `DocumentTargetSafety` tests cover the cleanup collision, an unrelated recipe, and a project-owned `build`. |
| F6, P2: regression fixtures write into the user's home | Two manual tests invoke `snapshot` with the real HOME; the sandbox caught attempts to create `/Users/user/.snapshots`. LuaLaTeX tests likewise use a real, unwritable font cache. | Every `ProjectCase` subprocess receives a temporary home and TeX cache. The two existing manual snapshot tests now pass without leaving their fixture. The recipe-prefix fixture also selects a capable `gmake` when macOS's Make 3.81 cannot parse that fixture's Make 3.82 syntax. |
| O1: unnecessarily large transient allocations | Hashing an input reads its entire content into memory; verifying a PDF header also reads the entire PDF. | Hash in 1 MiB chunks and read only the five PDF-header bytes. `DigestMemoryAudit` checks the SHA-256 and subsequent content changes, with less than 3 MiB traced peak allocation for an 8 MiB input. |

The configuration reference also still claimed that `init` merges existing editor
JSON, which 4.4 removed. The bibliography guide implied configured custom builds
did not receive the before/after export check, although they do. Both descriptions
now match the implementation. The root README points to this record.

## Reproduction and validation

The eleven new tests were run against a disposable copy of the distribution with
production `core.py`, `schema.py`, `latex.py`, and `guide.py` restored from the
audited commit. Every test fails there: 16 failures counting malformed-value
subcases. All eleven pass with the repairs. Existing generated-file fixtures were
left unchanged.

The first full run, inside the filesystem sandbox, ran 546 tests and reported six
failures and two skips. Two failures exposed the real-home fixture writes; two
LuaLaTeX failures reported no writable font cache; one fixture used `.RECIPEPREFIX`
with macOS's GNU Make 3.81; and one process-identity test could not execute `ps`
inside the sandbox. No production process check was disabled to conceal that
restriction. The final suite runs outside the sandbox with temporary fixture
homes and caches.

The first run after the repairs reached all 556 tests, with one failure: the
existing digest-cache test counted calls to `Path.read_bytes`, which streaming
hashes no longer use. It now counts file opens and still requires exactly one
read of an unchanged input and a different hash after a same-size edit. This
instrumentation works with both the original and streaming implementations;
the cache requirement was not relaxed. A duplicate full run accidentally
started through incorrect Make argument forwarding was stopped and is not
counted as validation evidence.

| Check | Result |
|---|---|
| Eleven new regressions against original code | All fail, 16 failure reports including subcases |
| Eleven new regressions plus the existing cache check against repairs | All 12 pass |
| `make -C workbench check` on the final tree | Pass: 557 tests, 555 pass and 2 platform skips; all 51 real-compiler portability scenarios pass |
| Reference `make check` | Pass: real pdfLaTeX, bibliography, text integrity, log validation, and ChkTeX |
| `make -C workbench upgrade-reference`, then `audit-reference` | Pass: runtime files identical at 4.10.2; project-owned AGENTS differences reported separately |
| Generated Makefile/editor guard | Pass, unchanged stored fixtures |
| Runtime `validate --files-only` | Pass: text/syntax, policy structure and local Markdown links |
| `git diff --check` | Pass |
| Hosted Python 3.10–3.14 and TeX Live checks | Separate evidence on the pull request's Checks tab; this record reports local verification |

Local platform: macOS arm64, Python 3.14.8, GNU Make 3.81 (4.4.1 for the
recipe-prefix fixture), TeX Live 2026, latexmk 4.88. Compiler portability also
passed all 51 scenarios before the repairs.
The two final skips are the Linux `/proc` zombie test and a non-UTF-8 project-path
test that this filesystem cannot represent. The GNU Make 3.81 compatibility test,
LuaLaTeX, XeLaTeX, Biber, and macOS PID-reuse checks ran and passed.

## Review and limits

This audit is single-agent, as the owner requested. The independent second-model
review required for changes to `latex.py` by [the maintainer rules](README.md#working-on-the-workbench-itself)
has not been performed: the owner's current instructions prohibit code-review
subagents. The pull request remains a draft with that requirement visible.
Self-review and regression evidence do not substitute for it.

Windows, launchd scheduling, network-file-system locks and actual agent permission
engines were not exercised locally. The suite tests guardrail definitions, which
are not a sandbox for arbitrary shell or programmatic Git use. Custom-command
dependencies assembled dynamically still require explicit declarations, as the
configuration reference already documents. No exhaustive absence-of-defects or
scientific-validity claim follows from these checks.

Configuration and receipt schemas, generated Makefile/editor templates, permission
rules, snapshot retention, manuscript and bibliography are unchanged. Existing
projects receive the repairs through the documented runtime refresh; no migration
is needed. The owner still reviews and merges the pull request and updates their
main checkout afterwards.
