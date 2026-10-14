# Bibliography and Zotero / Better BibTeX

The build chain is:

    Zotero collection → Better BibTeX auto-export → project .bib → latexmk → BibTeX → PDF/log validation

Zotero supplies metadata; the project stores a deterministic text snapshot. CI
and local builds use that snapshot, with no Zotero process, network endpoint,
database connection, API key, or editor plugin required.

## File ownership and version control

Use `bibliography/zotero.bib` for one targeted collection's generated export.
Declare it in `.latex-ai.json`. Track the `.bib` file, as it is a build input
even though generated. Keep separate, intentional manual entries in
`bibliography/local.bib` when a project needs them. Validate duplicate keys
across both files. Do not edit the generated export by hand: re-exporting will
overwrite those changes. Corrections belong in Zotero and require human review.

Do not version Zotero's database, storage directory, attachments, private
annotations, application preferences or export cache. Avoid absolute attachment
paths in the export. Keep essential bibliographic fields, DOI/URL and source
provenance. Avoid blind global field filtering that could alter unrelated
projects; export options are controlled manually by the user.

`.bbl`, `.blg`, `.bcf`, `.run.xml`, `.aux`, compiler logs and generated PDFs are
normally ignored. Preserve any publisher-specific requirement to submit/track
`.bbl`; revise ignore conventions deliberately for that project. Source figure
PDFs remain trackable because the workbench ignores only the configured output
PDF, not every `*.pdf`.

## Manual setup checkpoints

An agent stops at each required GUI step and requests only that step, naming
the application, action, exact value/path and result to report. The following
is the reusable procedure; do not issue it as a batch of GUI requests.

1. **Check the plugin.** In Zotero, open **Tools → Plugins**. Report whether
   **Better BibTeX** is installed and enabled, and its displayed version. If
   absent, use the [official installation procedure](https://retorque.re/zotero-better-bibtex/installation/)
   in a subsequent step; plugin installation remains under human control.
2. **Choose the collection.** Use a paper-specific collection containing only
   intended sources. Do not guess a research collection or export the entire
   personal library without the owner's choice.
3. **Set up export.** In Zotero, right-click the chosen collection and select
   **Export Collection…**. Use format **Better BibTeX**. Enable **Keep updated**, leave
   notes/files exports off, and save to the exact project path, for this
   reference `bibliography/zotero.bib` in the repository root.
   [Better BibTeX documents this automatic export registration](https://retorque.re/zotero-better-bibtex/exporting/auto/).
4. **Check deterministic options.** In Zotero Settings/Preferences → Better
   BibTeX → Export, confirm **Sort TeX/CSL output** is **citation key**. The
   exporter documents this as its version-control-friendly default. Preserve
   existing key conventions; do not refresh all keys or change the key formula
   in an established manuscript. Once keys are cited, pin them through Zotero's
   normal Better BibTeX controls when needed.
   [Export options](https://retorque.re/zotero-better-bibtex/preferences/export/),
   [citation key guidance](https://retorque.re/zotero-better-bibtex/citing/).
5. **Confirm update behavior.** In Better BibTeX → Automatic exports, confirm
   the target path and **On Change** or **When Idle**, matching the owner's
   preference. Let any scheduled export finish before building. Ask for the
   file's appearance, then inspect it with CLI tools and `make bib-check`.

Better BibTeX also offers automatic Git operations. **Do not enable them.** Its
[Git support](https://retorque.re/zotero-better-bibtex/exporting/auto/#git-support)
performs pull/stage/commit/push, which conflicts with human approval for each
Git mutation. Bootstrap reports an enabled `zotero.betterbibtex.push` setting
as a blocking conflict; it never changes Git configuration automatically.

These sources were checked on 2026-10-08; GUI wording may vary with the installed
Zotero version. The user reports what they see; an agent does not control the UI.

## Enabling real bibliography use

The reference uses backend `none` because its manuscript has no citation or
bibliography commands. Its `bibliography/zotero.bib` export is now present,
required and declared in `bibliography.files`. The owner created the collection
and exported existing real references; adding a second reference updated the
file automatically. Both entries passed a separate offline BibTeX build. No
bibliography metadata or manuscript citation was fabricated for integration.

For another project's first export, inspect its real entries without inventing
or repairing metadata. Set `export.required` true when the snapshot should be
required by validation. Add it to `bibliography.files`, set the backend to `bibtex`,
and use the existing document's citation style. A manuscript written for biblatex and Biber is outside
what the workbench builds itself: it declares a `build_command` ([configuration](configuration.md)), lists its `.bib` file under `bibliography.files`, and leaves `export` null,
since the only export format is Better BibTeX's.

Existing source uses a bibliography style plus
`\bibliography{bibliography/zotero}`. Add real citations only for claims supported by
the source and requested by the manuscript task, then run `make check` and inspect the `.bib` diff.

## Deterministic validation and limits

`make bib-check` checks known local bibliography files for UTF-8 decoding,
NUL/merge-conflict markers, unterminated entries, invalid/duplicate keys (compared
case-insensitively when the backend is BibTeX, as BibTeX does; case-variant keys
stay distinct when it is `none`), and
missing or empty required exports. Literal resources in the root/input files
are included. Explicit config paths cover resources hidden by macros. These
boundary checks do not fully parse BibTeX expressions or validate research
metadata. BibTeX does the actual backend validation during compilation.

`make check` builds, then rejects unresolved citations/references, duplicate
labels, bibliography/backend failures and persistent rerun requests. It prints
other package/typesetting warnings for review. It does not statically demand
that every citation-looking token is a key, so macro definitions, examples and
custom citation commands do not create noisy regex key-check failures.
When the configured backend is `none`, old `.blg` files are ignored; current
compiler warnings are still checked. Config and source must agree about the
active backend.

Default runtime builds hash bibliography files before and after compilation.
An intervening auto-export makes that build fail so it can be rerun on a stable
snapshot. Existing direct Makefile build recipes retain their own execution;
the final integrity target checks their resulting files, but cannot detect a
mid-build export race. Avoid editing Zotero during those custom builds or adapt
the recipe to invoke the configured runtime build.

Offline validation cannot establish whether a `.bib` matches the latest Zotero
library state or whether metadata is true. Missing required fields, inaccurate
DOIs and title capitalization must be assessed through backend warnings and
human/source review. Do not use LLM guesses as repairs. Never pull bibliography
from localhost during the build, and never depend on Zotero being reachable in CI.
