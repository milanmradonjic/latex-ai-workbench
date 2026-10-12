# Project bibliography

`zotero.bib` is the Better BibTeX auto-export of the owner's Zotero collection
`LaTeX AI Workbench test`. Automatic updating was verified by adding a second
existing reference and observing the file update from one entry to two. Do
not create placeholder entries or hand-edit this generated bibliography.

The export is required and declared in `.latex-ai.json`. Validation fails if
it is absent, empty or structurally invalid. The current manuscript has no
citations, so its backend remains `none`; when citations are introduced, select
the actual backend and add the source's bibliography commands. Track this
`.bib` input in Git with explicit approval; builds and CI use repository
contents without contacting Zotero. Both current entries passed an isolated
offline BibTeX build; their metadata was not edited or independently verified.

See [the reusable integration guide](../workbench/docs/bibliography.md).
