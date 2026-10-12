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

import make_graph
from commands import RECURSIVE_GOALS, RESERVED_PREFIX
from core import (CONFIG, GENERATED_TREES, MODULES, WorkbenchError, document_paths, has_module, integrations, local_path, module_config, module_names,
                  path_identity, path_name, read_json)

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


def check_export(project, export, backend=None):
    if export is None:
        return
    if not isinstance(export, dict):
        raise WorkbenchError("bibliography.export must be an object or null")
    unknown_keys(export, {"path", "required", "format"}, "bibliography.export")
    local_path(project, export.get("path"))
    if not isinstance(export.get("required", True), bool):
        raise WorkbenchError("bibliography.export.required must be boolean")
    if export.get("format") not in ("bibtex", "biblatex"):
        raise WorkbenchError("bibliography.export.format must be bibtex or biblatex")
    if backend == "biber" and export["format"] != "biblatex":
        raise WorkbenchError("Biber export should use Better BibLaTeX")


def check_bibliography(project, bib):
    if not isinstance(bib, dict):
        raise WorkbenchError("bibliography must be an object")
    unknown_keys(bib, {"backend", "files", "export"}, "bibliography configuration")
    if bib.get("backend", "none") not in ("none", "bibtex", "biber"):
        raise WorkbenchError("bibliography.backend must be none, bibtex, or biber")
    if not isinstance(bib.get("files", []), list):
        raise WorkbenchError("bibliography.files must be a list")
    for name in bib.get("files", []):
        local_path(project, name)
    check_export(project, bib.get("export"), bib.get("backend"))


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


def check_ci(ci):
    if not isinstance(ci, dict):
        raise WorkbenchError("ci must be an object")
    unknown_keys(ci, {"enabled", "pdf_artifact", "texlive_version"}, "ci configuration")
    if not all(isinstance(ci.get(k, True), bool) for k in ("enabled", "pdf_artifact")):
        raise WorkbenchError("CI toggles (enabled, pdf_artifact) must be true or false")
    if not re.fullmatch(r"20\d{2}", str(ci.get("texlive_version", "2026"))):
        raise WorkbenchError("ci.texlive_version must be a four-digit TeX Live year")


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
                             hint="create the .tex source first, or select an existing project-relative root with --root")
    if config.get("engine") not in ("pdflatex", "lualatex", "xelatex"):
        raise WorkbenchError("engine must be pdflatex, lualatex, or xelatex")
    # Whitespace is safe in subprocess argv, but latexmk/TeX cannot reliably
    # handle every special filename. Refuse rather than silently misbuild.
    if re.search(r"[\s%#{}\\]", config["root"]):
        raise WorkbenchError("Root document path must not contain whitespace or TeX-special characters")
    check_bibliography(project, config.get("bibliography", {}))
    check_lint(project, config.get("lint", {}))
    check_ci(config.get("ci", {}))
    if config.get("output_dir") is not None:
        local_path(project, config["output_dir"])
    document_paths(project, config["root"], config.get("output_dir"))
    cmd = config.get("build_command")
    if cmd is not None and (not isinstance(cmd, list) or not cmd or not all(isinstance(a, str) and a for a in cmd)):
        raise WorkbenchError("build_command must be a nonempty argv list, not shell text")
    check_validation(project, config.get("validation", {}))
    return config


def validate_common(project, view):
    # Shared project policy does not require a TeX document.
    check_bibliography(project, view.get("bibliography", {}))
    check_ci(view.get("ci", {}))
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


class SharedSettings(FrozenDict):
    """What a project shares with every document: the bibliography, the validation declarations and CI. A project without
    LaTeX has only this, so the bibliography checks take it; a document view is one too."""
    __slots__ = ()

    @property
    def bibliography(self):
        return self.get("bibliography", {})

    @property
    def validation(self):
        return self.get("validation", {})

    @property
    def ci(self):
        return self.get("ci", {})


class DocumentView(SharedSettings):
    """One declared document, resolved: what the LaTeX backend needs to build, verify and lint it. Its JSON is exactly
    what a build record stores as "configuration" (``Document.configuration``)."""
    __slots__ = ()

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
    if not has_module(config, "latex"):
        return ()
    values = config["modules"]["latex"]
    base = {**copy.deepcopy(DEFAULTS), **copy.deepcopy(values.get("defaults", {}))}
    default = values.get("default_document")
    result = []
    for name, overrides in values.get("documents", {}).items():
        settings = {**copy.deepcopy(base), **copy.deepcopy(overrides)}
        settings["lint"] = {**DEFAULTS["lint"], **base.get("lint", {}), **overrides.get("lint", {})}
        if settings.get("output_dir") is None:
            settings["output_dir"] = f".latex-ai/artifacts/documents/{name}/build"
        settings["lint"].setdefault("baseline", f".latex-ai/lint-baselines/{name}.json")
        bib = module_config(config, "bibliography") if has_module(config, "bibliography") else {"files": [], "export": None}
        bib["files"] = list(dict.fromkeys([*bib.get("files", []), *settings.pop("bibliography_files", [])]))
        bib["backend"] = settings.pop("backend")
        inputs = settings["inputs"]
        validation = copy.deepcopy(config.get("validation", {}))
        validation["manuscript_inputs"] = [*validation.get("manuscript_inputs", []), *inputs]
        view = {"name": name, **settings, "bibliography": bib,
                "ci": integrations(config)["ci"], "validation": validation}
        result.append(Document(name, json.dumps(view, sort_keys=True), default=name == default))
    return tuple(sorted(result, key=lambda document: (not document.default, document.name)))


def resolve(config, name=None):
    targets = specifications(config)
    if not targets:
        raise WorkbenchError("Module is disabled: latex")
    selected = name or next((target.name for target in targets if target.default), None)
    for target in targets:
        if target.name == selected:
            return target
    raise WorkbenchError(f"Unknown document: {selected!r}", hint="Declared documents: " + ", ".join(t.name for t in targets))


def document_settings(config, document=None):
    """A project configuration's document (the default one unless named) as a read-only view; a project without LaTeX
    has only the settings it shares. Resolve once, where the configuration is held: the backends take the result."""
    if "schema_version" not in config:
        raise TypeError("document_settings resolves a project configuration; this is already resolved, so use it as it is")
    if config.get("schema_version") != 3:
        raise WorkbenchError("Workbench 3 supports only project configuration schema 3")
    if has_module(config, "latex"):
        return resolve(config, document).view
    if document:
        raise WorkbenchError("Module is disabled: latex")
    return SharedSettings({"bibliography": module_config(config, "bibliography") if has_module(config, "bibliography") else {},
                           "validation": config.get("validation", {}), "ci": integrations(config)["ci"]})


def required_tools(config):
    tools = ["make", *[tool for name in module_names(config) for tool in MODULES[name]["tools"]]]
    if has_module(config, "latex"):
        for target in specifications(config):
            tex = target.view
            tools.extend(["latexmk", tex["engine"]])
            if tex.get("lint", {}).get("enabled", True):
                tools.append("chktex")
            backend = tex.get("bibliography", {}).get("backend", "none")
            if backend != "none":
                tools.append(backend)
    return list(dict.fromkeys(tools))


def validate_latex(project, values, config, enabled=True, planned_sources=None):
    if not isinstance(values, dict):
        raise WorkbenchError("The latex module configuration must be an object")
    unknown_keys(values, {"default_document", "defaults", "documents"}, "latex module")
    defaults = values.get("defaults", {})
    targets = values.get("documents")
    if not isinstance(defaults, dict):
        raise WorkbenchError("latex.defaults must be an object")
    unknown_keys(defaults, set(DEFAULTS) - {"build_command", "inputs", "bibliography_files"}, "document defaults")  # roots, commands and inputs belong to documents
    if defaults.get("engine", "pdflatex") not in ("pdflatex", "lualatex", "xelatex"):
        raise WorkbenchError("Invalid default document engine")
    if defaults.get("backend", "none") not in ("none", "bibtex", "biber"):
        raise WorkbenchError("Invalid default bibliography backend")
    if defaults.get("output_dir") is not None:
        local_path(project, defaults["output_dir"])
    if not isinstance(targets, dict) or not targets:
        raise WorkbenchError("latex.documents must be a nonempty object")
    if not isinstance(values.get("default_document"), str) or values["default_document"] not in targets:
        raise WorkbenchError("latex.default_document must name a declared document")
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
        command = fields.get("build_command")
        if isinstance(command, list) and command and isinstance(command[0], str) and Path(command[0]).name in {"make", "gmake"}:
            if any(isinstance(argument, str) and (argument in RECURSIVE_GOALS or argument.startswith(RESERVED_PREFIX)) for argument in command[1:]):
                raise WorkbenchError(f"Recursive build_command for document {name}; use the project's raw build target")
        check_validation(project, {"manuscript_inputs": fields.get("inputs", [])})
        if not isinstance(fields.get("bibliography_files", []), list):
            raise WorkbenchError(f"bibliography_files must be a list: {name}")
        for filename in fields.get("bibliography_files", []):
            local_path(project, filename)
    active = {**config, "modules": {**config.get("modules", {}), "latex": values}}
    validate_common(project, {"bibliography": module_config(config, "bibliography") if has_module(config, "bibliography") else {},
                              "ci": integrations(config)["ci"], "validation": config.get("validation", {})})
    roots, outputs = set(), set()
    exports = {path_identity(project, f".latex-ai/artifacts/documents/{name}/document.pdf") for name in targets}
    for target in specifications(active):
        view = target.view
        root = local_path(project, view["root"])
        if root.suffix != ".tex" or re.search(r"[\s%#{}\\]", view["root"]):
            raise WorkbenchError(f"Invalid TeX root: {view['root']}")
        identity = path_identity(project, view["root"])
        output = local_path(project, view["output_dir"]) / root.stem
        output_ids = {path_identity(project, output.relative_to(project).as_posix() + suffix) for suffix in (".pdf", ".log", ".aux", ".fls")}
        if identity in roots or output_ids & outputs:
            raise WorkbenchError(f"Document root or output collision: {target.name}")
        if output_ids & exports:
            raise WorkbenchError(f"Document build overlaps an exported PDF: {target.name}")
        roots.add(identity)
        outputs.update(output_ids)
        clean = view
        if enabled:
            validate_document_settings(project, clean, planned_sources)
        else:
            # Saved disabled roots may have been removed; validate structure without requiring a toolchain/root.
            validate_document_settings(project, clean, {path_name(project, view["root"]): None})
    if enabled:
        validate_make_ownership(project, targets, values["default_document"])
    return values


def validate_make_ownership(project, targets, default=None):
    """Reject known recursive/shared adopted graphs instead of running them twice."""
    adopted = {}
    for name, fields in targets.items():
        command = fields.get("build_command")
        if command and len(command) == 2 and Path(command[0]).name in {"make", "gmake"} and re.fullmatch(r"[A-Za-z][\w.-]*", command[1]):
            adopted[name] = command[1]
    if not adopted:
        return
    text = re.sub(r"# BEGIN LATEX AI WORKBENCH.*?# END LATEX AI WORKBENCH", "", make_graph.makefile_text(project), flags=re.S)
    graph = make_graph.read(text, project)
    edges, unresolved = {}, set()
    for rule in graph.rules:
        if not rule.literal:
            continue
        dependencies = {word for word in rule.prerequisites.split() if make_graph.LITERAL.fullmatch(word)}
        for name in rule.targets:
            edges.setdefault(name, set()).update(dependencies)
            if rule.unresolved:
                unresolved.add(name)
    seen = {}
    forbidden = RECURSIVE_GOALS
    def closure_for(goal):
        todo, closure = [goal], set()
        while todo:
            node = todo.pop()
            if node not in closure:
                closure.add(node)
                todo.extend(edges.get(node, ()))
        return closure

    # The adapter adds the default phase to check. An existing raw prerequisite
    # for another adopted document would also run outside its ownership phase.
    additional = {goal for name, goal in adopted.items() if name != default}
    # Parent goals also execute check: `all: check note` has the same conflict.
    # Dot-prefixed Make metadata declarations (notably .PHONY) are not parents
    # that the generated adapter executes. Computed parents cannot be resolved
    # safely without evaluating project Make code, so require explicit ownership.
    public = {name for name in edges if re.fullmatch(r"[A-Za-z][\w.-]*", name)}
    full_checks = [closure_for(name) for name in public if "check" in closure_for(name)]
    if additional and (any(additional & nodes for nodes in full_checks) or unresolved & public or graph.unresolved):
        raise WorkbenchError("Existing check has shared or unresolved ownership of additional adopted documents",
                             hint="provide an explicit project adapter that serializes document ownership before registering these builds")
    for name, goal in adopted.items():
        closure = closure_for(goal)
        if closure & forbidden:
            raise WorkbenchError(f"Recursive adopted build for {name}; use a raw target without workbench build/check dependencies")
        if len(adopted) > 1 and (closure & unresolved or goal not in edges or graph.unresolved):
            raise WorkbenchError(f"Cannot establish separate Make target ownership for {name}",
                                 hint="multiple adopted documents with computed/implicit prerequisites require an explicit project adapter")
        owned = closure & edges.keys()
        for previous, nodes in seen.items():
            shared = owned & nodes
            if shared:
                raise WorkbenchError(f"Adopted document builds {previous} and {name} share Make targets: {', '.join(sorted(shared))}",
                                     hint="provide an explicit project adapter with separate target ownership before registering both document builds")
        seen[name] = owned


def validate_config(project, config, planned_sources=None):
    if not isinstance(config, dict):
        raise WorkbenchError("Configuration must be a JSON object")
    if config.get("schema_version") != 3:
        raise WorkbenchError(f"Workbench 3 supports only project configuration schema 3 (this file declares {config.get('schema_version')!r})",
                             hint="older configurations are not migrated and your authored files are untouched: write a schema-3 "
                                  f"{CONFIG} (format: docs/configuration.md in the workbench package; `latex-ai-init init` writes one for a new project)")
    unknown_keys(config, {"schema_version", "modules", "disabled_modules", "integrations", "validation"}, "core configuration")
    modules = config.get("modules")
    if not isinstance(modules, dict):
        raise WorkbenchError("modules must be an object")
    unknown_keys(modules, MODULES, "", noun="module")
    disabled = config.get("disabled_modules", {})
    if not isinstance(disabled, dict):
        raise WorkbenchError("disabled_modules must be an object")
    unknown_keys(disabled, MODULES, "saved disabled", noun="module")
    if set(disabled) & modules.keys():
        raise WorkbenchError(f"Module is both enabled and saved as disabled: {', '.join(sorted(set(disabled) & modules.keys()))}")
    for name, values in {**disabled, **modules}.items():
        if name == "latex":
            validate_latex(project, values, config, enabled=name in modules, planned_sources=planned_sources)
            continue
        if not isinstance(values, dict):
            raise WorkbenchError(f"The {name} module configuration must be an object")
        unknown_keys(values, MODULES[name]["defaults"], f"{name} module")
        missing = set(MODULES[name]["requires"]) - modules.keys()
        if name in modules and missing:
            raise WorkbenchError(f"{name} requires enabled module(s): {', '.join(sorted(missing))}")
        effective = {**copy.deepcopy(MODULES[name]["defaults"]), **values}
        if name == "notes":
            base = local_path(project, effective["path"])
            for key in ("index", "session_state"):
                entry = local_path(project, (Path(effective["path"]) / effective[key]).as_posix()) if isinstance(effective[key], str) else None
                if entry is None or not entry.is_relative_to(base) or entry == base or ".." in Path(effective[key]).parts or Path(effective[key]).is_absolute():
                    raise WorkbenchError(f"Invalid notes.{key} path: {effective[key]!r}", hint="use a file name inside the notes directory")
        if name == "markdown":
            patterns = effective["files"]
            if not isinstance(patterns, list) or not patterns:
                raise WorkbenchError("markdown.files must be a nonempty list of project-relative paths/globs")
            for pattern in patterns:
                if not project_pattern(pattern):
                    raise WorkbenchError(f"Invalid Markdown input pattern: {pattern!r}", hint="use a project-relative glob without '..'")
                local_path(project, pattern)
                if not Path(pattern).parts or Path(pattern).parts[0] in GENERATED_TREES:
                    raise WorkbenchError("Markdown inputs cannot be generated/infrastructure trees")
        for key in ("path", "manifest"):
            if key in effective:
                local_path(project, effective[key])
                parts = Path(effective[key]).parts
                if not parts or local_path(project, effective[key]) == project.resolve() or ".." in parts or parts[0] in {".git", ".latex-ai", ".vscode", ".github", ".codex", ".claude"} or effective[key] in {CONFIG, "AGENTS.md", "CLAUDE.md", "Makefile", "makefile", "GNUmakefile", ".gitignore"}:
                    raise WorkbenchError(f"Reserved module path: {effective[key]}")
                if key == "manifest" and Path(effective[key]).suffix != ".json":
                    raise WorkbenchError("Module manifests must use .json paths")
    manifests = [path_identity(project, module_config(config, name)["manifest"]) for name in ("numerics", "figures", "claims") if name in modules]
    if len(manifests) != len(set(manifests)):
        raise WorkbenchError("Module manifests must use distinct paths")
    adapters = config.get("integrations", {})
    if not isinstance(adapters, dict):
        raise WorkbenchError("integrations must be an object")
    unknown_keys(adapters, {"editor", "ci"}, "integrations")
    if not isinstance(adapters.get("editor", False), bool):
        raise WorkbenchError("integrations.editor must be true or false")
    validate_common(project, {"bibliography": module_config(config, "bibliography") if has_module(config, "bibliography") else {},
                              "ci": integrations(config)["ci"], "validation": config.get("validation", {})})
    ci = integrations(config)["ci"]
    if ci.get("pdf_artifact", False) and not has_module(config, "latex") and "latex" not in disabled:
        raise WorkbenchError("PDF CI artifact requires the latex module")
    return config


def load_config(project):
    return validate_config(project, read_json(project / CONFIG, CONFIG))


STATES = {
    "current": "verified build matches its sources",
    "stale": "sources or build settings changed since its verified build",
    "failed": "its last build failed or was interrupted",
    "running": "a build is in progress",
    "missing": "not built yet",
}
