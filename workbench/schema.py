"""Project configuration: the schema and its validation, and the declared LaTeX documents resolved from it.

This sits directly above ``core`` and depends on nothing else of the workbench but the Makefile reader, so every
module that needs a validated configuration or a document (``runtime``, ``guide``, ``latex``, the installer) can
import it without a cycle. ``core`` cannot: it must stay below this module.
"""
from dataclasses import dataclass
import copy
import json
from pathlib import Path, PurePosixPath
import re

from commands import RECURSIVE_GOALS
from core import (BACKENDS, CONFIG, ENGINES, EXPORT_FORMATS, WorkbenchError, document_paths, integrations, local_path, make_goals,
                  path_identity, path_name, read_json, OUTPUT_SUFFIXES)

DEFAULTS = {"engine": "pdflatex", "backend": "none", "lint": {"enabled": True, "args": []},
            "output_dir": None, "build_command": None, "inputs": [], "bibliography_files": []}

FIELDS = {"root", *DEFAULTS}

ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")


def unknown_keys(values, allowed, where, noun="field"):
    """Refuse configuration entries the schema does not know, naming them so a typo is found at once."""
    extra = sorted(map(str, set(values) - set(allowed)))
    if extra:
        label = " ".join(word for word in (where, noun) if word)
        raise WorkbenchError(f"Unknown {label}{'s' if len(extra) > 1 else ''}: {', '.join(extra)}",
                             hint=f"supported: {', '.join(sorted(map(str, allowed)))}")


ENGINE_HINT = "remove the engine setting (pdflatex is the default); a document that needs another engine declares a build_command (docs/configuration.md)"
BACKEND_HINT = "a document that needs biber declares a build_command (docs/configuration.md); otherwise use none or bibtex"
FORMAT_HINT = "export with Zotero's Better BibTeX; a biber paper lists its .bib file under bibliography.files and leaves export null (docs/bibliography.md)"


def check_choice(value, allowed, what, hint):
    """Refuse a setting the workbench does not offer, by name, and say what to do instead."""
    if value not in allowed:
        shown = "is missing" if value is None else f"{value!r} is not supported"
        raise WorkbenchError(f"{what} {shown}; choose {' or '.join(allowed)}", hint=hint)


def check_export(project, export):
    if export is None:
        return
    if not isinstance(export, dict):
        raise WorkbenchError("bibliography.export must be an object or null")
    unknown_keys(export, {"path", "required", "format"}, "bibliography.export")
    local_path(project, export.get("path"))
    if not isinstance(export.get("required", True), bool):
        raise WorkbenchError("bibliography.export.required must be boolean")
    check_choice(export.get("format"), EXPORT_FORMATS, "bibliography.export.format", FORMAT_HINT)


def check_bibliography(project, bib):
    if not isinstance(bib, dict):
        raise WorkbenchError("bibliography must be an object")
    unknown_keys(bib, {"backend", "files", "export"}, "bibliography configuration")
    check_choice(bib.get("backend", "none"), BACKENDS, "bibliography backend", BACKEND_HINT)
    if not isinstance(bib.get("files", []), list):
        raise WorkbenchError("bibliography.files must be a list")
    for name in bib.get("files", []):
        local_path(project, name)
    check_export(project, bib.get("export"))


def check_lint(project, lint, where="lint"):
    if not isinstance(lint, dict):
        raise WorkbenchError(f"{where} must be an object")
    unknown_keys(lint, {"enabled", "args", "baseline"}, where)
    if not isinstance(lint.get("enabled", True), bool):
        raise WorkbenchError(f"{where}.enabled must be true or false")
    if not isinstance(lint.get("args", []), list) or not all(isinstance(a, str) for a in lint.get("args", [])):
        raise WorkbenchError(f"{where}.args must be a list of arguments")
    if "baseline" in lint:
        local_path(project, lint["baseline"])


def project_pattern(pattern):
    """A glob that stays inside the project: relative, without '..' and without control characters."""
    return (isinstance(pattern, str) and bool(pattern) and not Path(pattern).is_absolute()
            and ".." not in Path(pattern).parts and not any(c in pattern for c in "\n\r\0"))


def check_validation(project, validation):
    """Project validation declarations, independent of document selection."""
    if not isinstance(validation, dict):
        raise WorkbenchError("validation must be an object")
    unknown_keys(validation, {"manuscript_inputs", "ignore", "package"}, "validation")
    for key, label, example in (("manuscript_inputs", "manuscript input", "data/*.csv"), ("ignore", "ignore", "docs/**")):
        patterns = validation.get(key, [])
        if not isinstance(patterns, list):
            raise WorkbenchError(f"validation.{key} must be a list of project-relative glob patterns")
        for pattern in patterns:
            if not project_pattern(pattern):
                raise WorkbenchError(f"Invalid {label} pattern in validation.{key}: {pattern!r}",
                                     hint=f"use a project-relative glob without '..', for example \"{example}\"")
    package = validation.get("package")
    if package is not None:
        # The path is placed in generated shell and YAML, so keep to characters that need no escaping
        # beyond quoting, and never the project root (routing prefixes are directory-relative).
        if (not isinstance(package, str) or not re.fullmatch(r"[A-Za-z0-9._/ -]+", package) or package != package.strip()
                or package.startswith("-") or ".." in Path(package).parts):
            raise WorkbenchError("validation.package must be null or a project-relative directory using letters, digits, space and . _ - /")
        local_path(project, package)
        if Path(package).parts in ((), (".",)) or PurePosixPath(package).as_posix() == ".":
            raise WorkbenchError("validation.package must be a subdirectory, not the project root")


def validate_document_settings(project, config, planned_sources=None):
    if not isinstance(config, dict):
        raise WorkbenchError("Configuration must be a JSON object")
    if not isinstance(config.get("name"), str):
        raise WorkbenchError("Resolved document needs a name")
    if "root" not in config:
        raise WorkbenchError("Configuration needs a root TeX document")
    root = local_path(project, config["root"])
    if root.suffix != ".tex" or not (root.is_file() or path_name(project, config["root"]) in (planned_sources or {})):
        raise WorkbenchError(f"Root TeX document does not exist: {root}",
                             hint="create the .tex source first, or declare an existing project-relative root in .latex-ai.json")
    check_choice(config.get("engine"), ENGINES, "engine", ENGINE_HINT)
    # Whitespace is safe in subprocess argv, but latexmk/TeX cannot reliably
    # handle every special filename. Refuse rather than silently misbuild.
    if re.search(r"[\s%#{}\\]", config["root"]):
        raise WorkbenchError("Root document path must not contain whitespace or TeX-special characters")
    check_bibliography(project, config.get("bibliography", {}))
    check_lint(project, config.get("lint", {}))
    if config.get("output_dir") is not None:
        local_path(project, config["output_dir"])
    document_paths(project, config["root"], config.get("output_dir"))
    cmd = config.get("build_command")
    if cmd is not None and (not isinstance(cmd, list) or not cmd or not all(isinstance(a, str) and a for a in cmd)):
        raise WorkbenchError("build_command must be a nonempty argv list, not shell text")
    check_validation(project, config.get("validation", {}))
    return config


def validate_common(project, view):
    # Shared bibliography and validation declarations are checked before resolving documents.
    check_bibliography(project, view.get("bibliography", {}))
    check_validation(project, view.get("validation", {}))


def _refuse(self, *arguments, **keywords):
    raise TypeError(f"a resolved view is read-only; take a copy with to_json() to change one ({type(self).__name__})")


def _freeze(value):
    if isinstance(value, dict):
        return FrozenDict(value)
    if isinstance(value, list):
        return FrozenList(value)
    return value


def _thaw(value):
    if isinstance(value, dict):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_thaw(item) for item in value]
    return value


class FrozenList(list):
    """A list that refuses to change. It compares and serializes as the list it holds, so a view stays what JSON made of it."""
    __slots__ = ()
    __setitem__ = __delitem__ = __iadd__ = __imul__ = append = extend = insert = remove = pop = clear = sort = reverse = _refuse

    def __init__(self, items=()):
        super().__init__(_freeze(item) for item in items)

    def __copy__(self):
        return _thaw(self)

    def __deepcopy__(self, memo):
        return _thaw(self)

    def __reduce__(self):
        return (list, (_thaw(self),))


class FrozenDict(dict):
    """A dict that refuses to change, at every depth. Equality, ``json.dumps`` and ``{**d}`` behave as for a dict;
    ``to_json()`` and ``copy.deepcopy`` give plain data the caller may change."""
    __slots__ = ()
    __setitem__ = __delitem__ = __ior__ = clear = pop = popitem = setdefault = update = _refuse

    def __init__(self, *arguments, **keywords):
        super().__init__({key: _freeze(item) for key, item in dict(*arguments, **keywords).items()})

    def to_json(self):
        return _thaw(self)

    __copy__ = to_json

    def __deepcopy__(self, memo):
        return _thaw(self)

    def __reduce__(self):
        return (dict, (_thaw(self),))


class DocumentView(FrozenDict):
    """Immutable resolved settings for one declared LaTeX document."""
    __slots__ = ()

    @property
    def bibliography(self):
        return self["bibliography"]

    @property
    def validation(self):
        return self["validation"]

    @property
    def name(self):
        return self["name"]

    @property
    def root(self):
        return self["root"]

    @property
    def engine(self):
        return self["engine"]

    @property
    def output_dir(self):
        return self["output_dir"]

    @property
    def build_command(self):
        return self.get("build_command")

    @property
    def lint(self):
        return self.get("lint", {})

    @property
    def inputs(self):
        return self.get("inputs", [])


@dataclass(frozen=True)
class Document:
    name: str
    configuration: str
    default: bool = False

    @property
    def view(self):
        """The backend configuration of this document: read-only, so no caller can change another target's."""
        return DocumentView(json.loads(self.configuration))


def specifications(config):
    values = config
    base = {**copy.deepcopy(DEFAULTS), **copy.deepcopy(values.get("defaults", {}))}
    default = values.get("default_document")
    result = []
    for name, overrides in values.get("documents", {}).items():
        settings = {**copy.deepcopy(base), **copy.deepcopy(overrides)}
        settings["lint"] = {**DEFAULTS["lint"], **base.get("lint", {}), **overrides.get("lint", {})}
        if settings.get("output_dir") is None:
            settings["output_dir"] = f".latex-ai/artifacts/documents/{name}/build"
        settings["lint"].setdefault("baseline", f".latex-ai/lint-baselines/{name}.json")
        bib = {"files": [], "export": None, **copy.deepcopy(config.get("bibliography", {}))}
        bib["files"] = list(dict.fromkeys([*bib.get("files", []), *settings.pop("bibliography_files", [])]))
        bib["backend"] = settings.pop("backend")
        inputs = settings["inputs"]
        validation = copy.deepcopy(config.get("validation", {}))
        validation["manuscript_inputs"] = [*validation.get("manuscript_inputs", []), *inputs]
        view = {"name": name, **settings, "bibliography": bib, "validation": validation}
        result.append(Document(name, json.dumps(view, sort_keys=True), default=name == default))
    return tuple(sorted(result, key=lambda document: (not document.default, document.name)))


def resolve(config, name=None):
    targets = specifications(config)
    if not targets:
        raise WorkbenchError("Project needs at least one LaTeX document")
    selected = name or next((target.name for target in targets if target.default), None)
    for target in targets:
        if target.name == selected:
            return target
    raise WorkbenchError(f"Unknown document: {selected!r}", hint="Declared documents: " + ", ".join(t.name for t in targets))


def document_settings(config, document=None):
    """Resolve project configuration once; backends accept only its immutable document view."""
    if "schema_version" not in config:
        raise TypeError("document_settings resolves a project configuration; use an existing view as it is")
    if config["schema_version"] != 4:
        raise WorkbenchError("Workbench 5 supports only project configuration schema 4")
    return resolve(config, document).view


def required_tools(config):
    tools = ["make"]
    for target in specifications(config):
        tex = target.view
        command = tex.get("build_command")
        tools.extend([command[0]] if command else ["latexmk", "pdflatex"])
        if tex.get("lint", {}).get("enabled", True):
            tools.append("chktex")
        backend = tex.get("bibliography", {}).get("backend", "none")
        if backend != "none":
            tools.append(backend)
    return list(dict.fromkeys(tools))


def validate_documents(project, config, planned_sources=None):
    values = config
    defaults = values.get("defaults", {})
    targets = values.get("documents")
    if not isinstance(defaults, dict):
        raise WorkbenchError("defaults must be an object")
    unknown_keys(defaults, set(DEFAULTS) - {"build_command", "inputs", "bibliography_files"}, "document defaults")  # roots, commands and inputs belong to documents
    check_choice(defaults.get("engine", "pdflatex"), ENGINES, "default document engine", ENGINE_HINT)
    check_choice(defaults.get("backend", "none"), BACKENDS, "default bibliography backend", BACKEND_HINT)
    if defaults.get("output_dir") is not None:
        local_path(project, defaults["output_dir"])
    if not isinstance(targets, dict) or not targets:
        raise WorkbenchError("documents must be a nonempty object")
    if not isinstance(values.get("default_document"), str) or values["default_document"] not in targets:
        raise WorkbenchError("default_document must name a declared document")
    for name, fields in targets.items():
        if not isinstance(name, str) or not ID.fullmatch(name):
            raise WorkbenchError(f"Invalid document ID: {name!r}")
        if not isinstance(fields, dict):
            raise WorkbenchError(f"Document {name} must be an object")
        unknown_keys(fields, FIELDS, f"document {name}")
        if "root" not in fields:
            raise WorkbenchError(f"Document {name} needs a root TeX file", hint=f'for example "{name}": {{"root": "main.tex"}}')
        for where, lint in (("defaults.lint", defaults.get("lint", {})), (f"documents.{name}.lint", fields.get("lint", {}))):
            check_lint(project, lint, where)
        if any(goal in RECURSIVE_GOALS for goal in make_goals(fields.get("build_command"))):
            raise WorkbenchError(f"Recursive build_command for document {name}; use the project's raw build target")
        check_validation(project, {"manuscript_inputs": fields.get("inputs", [])})
        if not isinstance(fields.get("bibliography_files", []), list):
            raise WorkbenchError(f"bibliography_files must be a list: {name}")
        for filename in fields.get("bibliography_files", []):
            local_path(project, filename)
    validate_common(project, {"bibliography": config.get("bibliography", {}),
                              "validation": config.get("validation", {})})
    roots, outputs = set(), set()
    exports = {path_identity(project, f".latex-ai/artifacts/documents/{name}/document.pdf") for name in targets}
    root_ids = {path_identity(project, fields['root']) for fields in targets.values()}
    for target in specifications(config):
        view = target.view
        root = local_path(project, view["root"])
        if root.suffix != ".tex" or re.search(r"[\s%#{}\\]", view["root"]):
            raise WorkbenchError(f"Invalid TeX root: {view['root']}")
        identity = path_identity(project, view["root"])
        output = local_path(project, view["output_dir"]) / root.stem
        output_ids = {path_identity(project, output.relative_to(project).as_posix() + suffix) for suffix in OUTPUT_SUFFIXES}
        if identity in roots or output_ids & (outputs | root_ids):
            raise WorkbenchError(f"Document root or output collision: {target.name}")
        if output_ids & exports:
            raise WorkbenchError(f"Document build overlaps an exported PDF: {target.name}")
        roots.add(identity)
        outputs.update(output_ids)
        validate_document_settings(project, view, planned_sources)
    return values


def validate_config(project, config, planned_sources=None):
    if not isinstance(config, dict):
        raise WorkbenchError("Configuration must be a JSON object")
    if config.get("schema_version") != 4:
        raise WorkbenchError(f"Workbench 5 supports only project configuration schema 4 (this file declares {config.get('schema_version')!r})",
                             hint=f"prepare {CONFIG} using examples/minimal/.latex-ai.json in the workbench package")
    unknown_keys(config, {"schema_version", "default_document", "defaults", "documents", "bibliography", "integrations", "validation"}, "project configuration")
    bibliography = config.get("bibliography", {})
    if not isinstance(bibliography, dict):
        raise WorkbenchError("bibliography must be an object")
    unknown_keys(bibliography, {"files", "export"}, "shared bibliography")
    validate_documents(project, config, planned_sources)
    adapters = config.get("integrations", {})
    if not isinstance(adapters, dict):
        raise WorkbenchError("integrations must be an object")
    unknown_keys(adapters, {"editor"}, "integrations")
    if not isinstance(adapters.get("editor", False), bool):
        raise WorkbenchError("integrations.editor must be true or false")
    return config


def load_config(project):
    return validate_config(project, read_json(project / CONFIG, CONFIG))


STATES = {
    "current": "built from these exact files without a LaTeX error",
    "stale": "files or build settings changed since it was built",
    "failed": "its last build failed or was interrupted",
    "running": "a build is in progress",
    "missing": "not built yet",
}
