# Synthetic Markdown notebook

This is a toolchain fixture, not research evidence. Its bibliography entry and
diagram are explicitly synthetic. Copy this directory into a new project,
initialize it with the workbench CLI, and use `make md-check` or `make md-render`.
Pandoc 2.17+ must be on PATH for those commands; TeX is unnecessary.

The example covers linked notes, an explicit heading identifier, equations,
citations from a local bibliography, a local SVG and a displayed Python snippet.
That snippet is never executed. HTML goes to
`.latex-ai/artifacts/markdown/notes/index.html`; no source file is rewritten.
