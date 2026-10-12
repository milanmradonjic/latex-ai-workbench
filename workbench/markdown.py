"""Optional Pandoc Markdown checks and explicit local HTML export.

Pandoc owns parsing, heading identifiers, math and citation syntax. This backend
only checks project references and maps local links into generated HTML.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from core import GENERATED_TREES, WorkbenchError, atomic_write, damaged_text, has_module, local_path, module_config
from schema import document_settings

OUTPUT = ".latex-ai/artifacts/markdown"
READER = "markdown-raw_html-raw_tex-raw_attribute"


def documents(project, config):
    paths = set()
    for pattern in module_config(config, "markdown")["files"]:
        matches = list(project.glob(pattern))
        if not matches and not any(c in pattern for c in "*?["):
            raise WorkbenchError(f"Missing Markdown source: {pattern}")
        for path in matches:
            name = path.relative_to(project)
            if set(name.parts) & GENERATED_TREES:
                continue
            resolved = local_path(project, name.as_posix())
            if not resolved.is_file() or path.suffix.lower() not in {".md", ".markdown"}:
                raise WorkbenchError(f"Markdown input must be a .md/.markdown file: {name}")
            paths.add(path)
    if not paths:
        raise WorkbenchError("No Markdown sources match markdown.files")
    return sorted(paths)


def pandoc(project, arguments, text):
    executable = shutil.which("pandoc")
    if not executable:
        raise WorkbenchError("Markdown module requires Pandoc 2.17+ on PATH; other modules do not require it")
    result = subprocess.run([executable, "--sandbox", *arguments], cwd=project,
                            input=text, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise WorkbenchError("Pandoc failed: " + result.stderr.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.stdout


def nodes(value):
    if isinstance(value, dict):
        if "t" in value:
            yield value
        for item in value.values():
            yield from nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from nodes(item)


def identifiers(ast, name):
    found = set()
    for node in nodes(ast):
        content = node.get("c")
        if not isinstance(content, list) or not content:
            continue
        attr = content[1] if node["t"] == "Header" else content[0]
        if not (isinstance(attr, list) and len(attr) == 3 and isinstance(attr[0], str)
                and isinstance(attr[1], list) and isinstance(attr[2], list)):
            continue
        identifier = attr[0]
        if identifier:
            if identifier in found:
                raise WorkbenchError(f"Duplicate Markdown identifier in {name}: {identifier}")
            found.add(identifier)
    return found


def local_reference(project, source, target):
    url = urlsplit(target)
    if url.scheme or url.netloc:
        return None  # External links are never fetched or checked.
    path = unquote(url.path)
    if path.startswith("/"):
        raise WorkbenchError(f"Use a relative local Markdown link in {source.relative_to(project)}: {target}")
    linked = source.parent / path if path else source
    # Keep the lexical project path for output mapping, but validate symlinks.
    name = Path(os.path.relpath(linked, project)).as_posix()
    resolved = local_path(project, name)
    if not resolved.exists():
        raise WorkbenchError(f"Broken local Markdown link in {source.relative_to(project)}: {target}")
    return project / name, url


def inspect(project, config):
    sources = documents(project, config)
    cache = {}

    def parse(path):
        if path not in cache:
            text = path.read_text(encoding="utf-8-sig")
            if damaged_text(text):
                raise WorkbenchError(f"NUL or merge conflict marker in {path.relative_to(project)}")
            ast = json.loads(pandoc(project, ["--from=" + READER, "--to=json"], text))
            cache[path] = (ast, identifiers(ast, path.relative_to(project)))
        return cache[path]

    bibliographies, keys = [], set()
    if has_module(config, "bibliography"):
        import latex
        bibliographies = list(latex.bibliography_check(project, document_settings(config)))
        for path in bibliographies:
            keys.update(latex.bib_keys(path.read_text(encoding="utf-8-sig"), path.relative_to(project)))
    for source in sources:
        ast, _ = parse(source)
        for node in nodes(ast):
            if node["t"] in {"Link", "Image"}:
                reference = local_reference(project, source, node["c"][-1][0])
                if reference:
                    linked, url = reference
                    if url.fragment and linked.suffix.lower() in {".md", ".markdown"}:
                        if unquote(url.fragment) not in parse(linked)[1]:
                            raise WorkbenchError(f"Broken Markdown anchor in {source.relative_to(project)}: {node['c'][-1][0]}")
            elif node["t"] == "Cite":
                for citation in node["c"][0]:
                    key = citation["citationId"]
                    # A bare @name reads as a mention unless the project declares a bibliography;
                    # bracketed [@key] is always deliberate citation syntax.
                    bare = citation.get("citationMode", {}).get("t") == "AuthorInText"
                    if key not in keys and (has_module(config, "bibliography") or not bare):
                        raise WorkbenchError(f"Unknown Markdown citation in {source.relative_to(project)}: {key}; "
                                             f"declare its local .bib in modules.bibliography (write \\@{key} for a literal at sign)")
    return sources, {path: cache[path][0] for path in sources}, bibliographies


def check(project, config):
    sources, _, _ = inspect(project, config)
    print(f"Markdown checks passed ({len(sources)} documents; local links, Markdown anchors and citation keys)")


def destination(project, path):
    # Generated writes cannot follow even an in-project symlink.
    local_path(project, path.relative_to(project).as_posix())
    cursor = path
    while cursor != project:
        if cursor.is_symlink():
            raise WorkbenchError(f"Refusing symlink Markdown output: {path.relative_to(project)}")
        cursor = cursor.parent
    if path.exists() and not path.is_file():
        raise WorkbenchError(f"Expected generated file: {path.relative_to(project)}")


def render(project, config):
    sources, asts, bibliographies = inspect(project, config)
    output = project / OUTPUT
    outputs = {source: output / source.relative_to(project).with_suffix(".html") for source in sources}
    if len(set(outputs.values())) != len(outputs):
        raise WorkbenchError("Markdown sources collide at a generated HTML path")
    # New Pandoc names this option --math-method; older supported releases use
    # --mathml. Select by advertised capability, without a version-specific map.
    math_option = "--math-method=mathml" if "--math-method" in pandoc(project, ["--help"], "") else "--mathml"
    writes = {}
    for source in sources:
        ast = copy.deepcopy(asts[source])
        # Arbitrary front matter is research metadata, not renderer configuration.
        ast["meta"] = {key: value for key, value in ast.get("meta", {}).items() if key in {"title", "author", "date", "lang"}}
        for node in nodes(ast):
            if node["t"] not in {"Link", "Image"}:
                continue
            reference = local_reference(project, source, node["c"][-1][0])
            if not reference:
                if node["t"] == "Image":
                    raise WorkbenchError("HTML export requires local images: " + node["c"][-1][0])
                continue
            linked, url = reference
            if node["t"] == "Image":
                target = output / ".resources" / linked.relative_to(project)
                writes[target] = linked.read_bytes()
            else:
                target = outputs.get(linked, linked)
            relative = quote(Path(os.path.relpath(target, outputs[source].parent)).as_posix(), safe="/")
            node["c"][-1][0] = urlunsplit(("", "", relative, url.query, url.fragment))
        arguments = ["--from=json", "--to=html5", "--standalone", math_option,
                     "--metadata=pagetitle:" + source.stem]
        if bibliographies:
            arguments.append("--citeproc")
            arguments.extend("--bibliography=" + str(path) for path in bibliographies)
        writes[outputs[source]] = pandoc(project, arguments, json.dumps(ast, ensure_ascii=False)).encode("utf-8")
    # Resolve every destination before changing anything. Keep old generated
    # exports on disk; render/upgrade/disable never delete project artifacts.
    for path in writes:
        destination(project, path)
    for path, data in writes.items():
        atomic_write(path, data)
    for source, path in outputs.items():
        print(f"HTML: {source.relative_to(project)} -> {path.relative_to(project)}")
