# Optional Markdown checks and HTML export

The `markdown` module adds one dependency, **Pandoc 2.17+ on PATH**. It uses
Pandoc's Markdown reader and JSON syntax tree for both checking and rendering.
There is no separate Markdown parser, formatter, Node toolchain, site framework,
or executable notebook layer. Notes remain ordinary project-owned files.

Enable this module only in projects that need it. The `notebook` profile still
creates plain notes without requiring Pandoc. No other module requires Pandoc.
The reference manuscript keeps Markdown disabled. See the
[synthetic notebook](../examples/markdown/README.md) for a complete example.

## Configuration and commands

In schema 3, an enabled module has this default configuration:

```json
"markdown": {"files": ["notes/**/*.md"]}
```

`files` is a nonempty list of project-relative paths or glob patterns. Recursive
globs include files directly in the named directory. Supply paths explicitly
when notes use another directory or when checking documentation:

```json
"markdown": {"files": ["journal/**/*.md", "README.md", "docs/**/*.md"]}
```

Matched sources must be `.md` or `.markdown` files. Generated/runtime/Git/env
trees are excluded even from broad globs. Explicit missing sources, an empty
document selection and paths escaping the project fail. Notes and bibliography
are independent optional modules; Markdown does not create notes or require TeX.

Use the normal installer `configure --enable markdown --dry-run --diff` to
review enabling it, then apply that configuration operation. Existing settings
can be edited explicitly and refreshed with an upgrade dry-run. The installer
does not install tools or run Pandoc. `make doctor` reports the required binary.

| Command | Behavior |
|---|---|
| `make md-check` | Read-only check of all declared Markdown sources |
| `make md-render` | Check those sources, then explicitly write local HTML |
| `make validation-plan` | Preview changed-file selection without invoking Pandoc |
| `make validate` | Check declared Markdown after project changes; never render |
| `make check` | Include Markdown in the full enabled-module check |

When local Make targets already use these names, their recipes remain intact;
the workbench provides `latex-ai-md-check` and `latex-ai-md-render` aliases.

## What is checked

The reader supports Pandoc Markdown, including ordinary/reference-style links,
local images, automatic or explicit heading identifiers, math and citations.
Code blocks and inline code remain literal code. Link to a heading or give it
an explicit identifier:

```markdown
[label](other.md#model)
## Model {#model}
```

Wiki-link dialects are outside this initial module; Pandoc's identifier rules
define the anchor names.

Checks reject missing local targets, broken fragments into Markdown documents,
duplicate explicit identifiers, text conflict markers and unknown citation keys.
Links resolve relative to the source note, with URL escapes decoded. Local
paths must stay inside the project; use relative links. External links are
retained without network requests. Fragments into non-Markdown files and remote
link availability are not checked. Unresolved reference-style syntax that the
Markdown reader treats as plain text is also plain text here.

For `[@key]` citations, enable `bibliography` and declare the actual local `.bib`
files/export in its settings. Pandoc reads a bare `@name` as an in-text citation
too, so with a bibliography declared an unknown `@name` is an error: write `\@name`
(or use code) for a literal at sign. Without the bibliography module a bare `@name`
is just a mention, while bracketed `[@key]`/`[-@key]` always has to resolve. The existing bibliography checker validates
boundaries, duplicate keys and required exports; Pandoc citeproc formats HTML
references from the same files. No second bibliography configuration is added.
Generated Zotero exports retain their existing editing restrictions. These
checks establish key/file readiness, not literature accuracy or scientific truth.

An explicit validation after any project change checks the declared document
set, including incoming links after a target is deleted or renamed. This small
conservative check avoids a maintained link graph or save watcher. It does not
select scientific execution or TeX by itself. Markdown actually consumed by
TeX still selects manuscript validation through the existing dependency rules.

## Generated HTML ownership

For `notes/model.md`, output is
`.latex-ai/artifacts/markdown/notes/model.html`. This generated tree is ignored
by the installed project. Sources, bibliography and handwritten TeX are never
rewritten. Math uses native MathML, with no CDN or JavaScript renderer. Citation
formatting uses Pandoc's default style; custom publication styling is deferred.

Links between declared Markdown documents point to their HTML counterparts.
Local images are copied under `.resources/` with project-relative paths. Other
local links remain relative references to the project's original files; keep
the generated tree with the project when moving it. External hyperlinks remain
links. HTML export rejects remote images, so rendering performs no remote
resource fetch. It does not inline or execute code, filters, raw HTML or raw TeX.

Only `title`, `author`, `date` and `lang` front matter pass to the HTML writer;
other metadata remains in the note and cannot configure the renderer. Raw HTML,
raw TeX and raw attribute extensions are disabled; TeX math is still supported.
This deliberate dialect works for research notes without template/filter hooks.

Check/render failure before writing leaves prior exports intact. Rendering
replaces generated files for the current document set; it does not remove older
exports. Disabling, upgrading or re-enabling preserves notes and generated
artifacts. Source paths that map to the same HTML filename are rejected.

Saving any file invokes no new workbench command. CI provisions Pandoc only
when Markdown checks or distribution regressions are selected, then invokes
`make md-check`. A LaTeX project's full CI check also provisions it inside the
TeX container when the module is enabled. CI never invokes `md-render` or
publishes a notebook/site.

PDF/Word export, automatic TeX generation, search indexing, schema-enforced note
metadata and static websites can be added when a concrete project requires
them. They are deliberately outside this first increment. The current module
has one reader, one writer and one additional binary.

Reader/writer behavior follows the [Pandoc manual](https://pandoc.org/MANUAL.html).
