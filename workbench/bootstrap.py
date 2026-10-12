"""Safe setup, audit and upgrade planning. No Git mutations or network calls."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shlex
import sys

sys.dont_write_bytecode = True
from core import CONFIG, GENERATED_TREES, VERSION, WorkbenchError, local_path, git_output, make_has_extra_prereqs, ADOPTED_MAKE, read_tex
import make_graph
from schema import document_settings, load_config, specifications, validate_config
from latex import bibliography_check, source_tree, tex_without_comments
from core import MODULES, PROFILES, has_module, line_buffered, module_config, integrations, effective_config, runtime_sources
from diagnostics import EXTENDABLE, MANIFEST_SCHEMA, current_record, extends, file_record, is_installed, managed_text
import copy
import contextlib
import io
import guide
from guide import MAKEFILES, make_targets
from adapters import core_makefile, integration_text, make_adapter, merge_block, module_make_targets, workflow
from installation import apply, installation_lock, pending_transaction, read, recover

PACKAGE = Path(__file__).resolve().parent
from installation import STATE
EXCLUDED = GENERATED_TREES | {"workbench", "build", "out"}  # the installer also leaves out the distribution and build folders
STRATEGIES = {"full", "block", "json", "seed"}
COPIED = ((".latex-ai/", "workbench runtime"), (".claude/", "agent guardrails that prompt before Git changes"),
          (".codex/", "agent guardrails that prompt before Git changes"))


def encoded(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_snapshot(project):
    def command(*args):
        return git_output(project, *args)
    return {"branch": command("branch", "--show-current"),
            "status": command("status", "--short", "--branch"),
            "better_bibtex_auto_push": command("config", "--get", "zotero.betterbibtex.push")}


def discover(project):
    tex, bib, helper, workflows = [], [], [], []
    for directory, folders, files in os.walk(project, followlinks=False):
        folders[:] = sorted(d for d in folders if d not in EXCLUDED and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink():
                continue
            relative = path.relative_to(project).as_posix()
            if name.endswith(".tex"):
                tex.append(relative)
            if name.endswith(".bib"):
                bib.append(relative)
            if name in {"Makefile", "GNUmakefile", "makefile", ".latexmkrc", "latexmkrc"} or name.endswith((".sh", ".py")):
                helper.append(relative)
            if relative.startswith(".github/workflows/"):
                workflows.append(relative)
    roots = [name for name in tex if re.search(r"\\documentclass(?:\[[^\]]*\])?\s*\{", tex_without_comments(read_tex(project / name)))]
    return {"tex_files": tex, "root_candidates": roots, "bib_files": bib, "build_files": helper,
            "workflows": workflows, "editor_files": [p for p in (".vscode/settings.json", ".vscode/tasks.json") if (project / p).exists()],
            "agent_files": [p for p in ("AGENTS.md", "CLAUDE.md", ".claude/settings.json", ".codex/rules/git-safety.rules") if (project / p).exists()]}


def build_command_argument(text):
    """--build-command is an argument vector written as a JSON array, never shell text."""
    try:
        value = json.loads(text)
    except ValueError:
        value = None
    if not isinstance(value, list) or not value or not all(isinstance(argument, str) and argument for argument in value):
        raise WorkbenchError(f"--build-command must be a JSON array of strings, not {text!r}",
                             hint='for example --build-command \'["make", "pdf"]\' (quote it so the shell keeps the brackets and quotes)')
    return value


def detect_config(project, inventory, args):
    old = read(project, CONFIG)
    if old is not None:
        config = load_config(project)
        if args.profile is not None or args.modules is not None or args.editor or args.ci:
            raise WorkbenchError("Profiles/adapters select initial defaults only; edit installed configuration explicitly",
                                 hint="this project is already installed: `upgrade` refreshes it, and `configure --enable NAME` or `--disable NAME` changes "
                                      "its modules. --profile, --modules, --editor and --ci only choose the starting set of a new install")
        if args.document or args.default_document:
            if args.mode != "configure":
                raise WorkbenchError("Document changes require configure mode")
            if not has_module(config, "latex"):
                raise WorkbenchError("Enable the latex module before adding a document")
            values = config["modules"]["latex"]
            if args.document:
                fields = values["documents"].setdefault(args.document, {})
                for key in ("root", "engine", "backend"):
                    if getattr(args, key) is not None:
                        fields[key] = getattr(args, key)
                if args.build_command is not None:
                    fields["build_command"] = build_command_argument(args.build_command)
                if args.no_lint:
                    fields["lint"] = {**fields.get("lint", {}), "enabled": False}
            if args.default_document:
                values["default_document"] = args.default_document
            return validate_config(project, config)
        tex = document_settings(config)
        selections = [(args.root, tex.get("root")), (args.engine, tex.get("engine")),
                      (args.backend, tex.get("bibliography", {}).get("backend", "none")),
                      (build_command_argument(args.build_command) if args.build_command else None, tex.get("build_command"))]
        adapter = integrations(config)
        if any(chosen is not None and chosen != current for chosen, current in selections) or (
            args.no_lint and tex.get("lint", {}).get("enabled", True) or args.no_ci and adapter["ci"].get("enabled", False) or
            args.no_artifact and adapter["ci"].get("pdf_artifact", False)):
            raise WorkbenchError("Project choices differ; edit .latex-ai.json explicitly instead of overriding installed configuration")
        if args.mode == "configure":
            saved = config.setdefault("disabled_modules", {})
            for name in args.disable:
                if name in config["modules"]:
                    saved[name] = config["modules"].pop(name)
            for name in args.enable:
                default = ({"default_document": "manuscript", "documents": {"manuscript": {"root": args.root or "main.tex"}}}
                           if name == "latex" else copy.deepcopy(MODULES[name]["defaults"]))
                config["modules"].setdefault(name, saved.pop(name, default))
            if not saved:
                config.pop("disabled_modules", None)
        return validate_config(project, config)
    if args.mode == "configure":
        raise WorkbenchError("Not installed; use init first")
    if args.document or args.default_document:
        raise WorkbenchError("Document configuration options require an installed project; use configure")
    if args.profile == "tex-notebook":
        if args.root or args.build_command:
            raise WorkbenchError("The tex-notebook profile seeds notes/index.tex; register existing roots with configure or the writing profile")
        config = {"schema_version": 3, "modules": {
            "latex": {"default_document": "notebook", "documents": {"notebook": {
                "root": "notes/index.tex", "engine": args.engine or "pdflatex", "backend": args.backend or "none",
                "lint": {"enabled": not args.no_lint, "args": []}}}},
            "notes": {"path": "notes", "index": "index.tex", "session_state": "session-state.tex"}},
            "integrations": {"editor": args.editor and not args.skip_editor, "ci": {
                "enabled": args.ci and not args.no_ci, "pdf_artifact": not args.no_artifact, "texlive_version": "2026"}}}
        return validate_config(project, config, planned_sources=note_seeds(config))
    if args.profile is not None or args.modules is not None:
        names = PROFILES[args.profile] if args.profile is not None else [n.strip() for n in args.modules.split(",") if n.strip()]
        if set(names) - MODULES.keys():
            raise WorkbenchError("Unknown module(s): " + ", ".join(sorted(set(names) - MODULES.keys())))
        config = {"schema_version": 3, "modules": {n: copy.deepcopy(MODULES[n]["defaults"]) for n in names},
                  "integrations": {"editor": args.editor and not args.skip_editor,
                                   "ci": {"enabled": args.ci and not args.no_ci, "pdf_artifact": "latex" in names and not args.no_artifact,
                                          "texlive_version": "2026"}}}
        if "latex" not in names:
            if args.root or args.engine or args.backend or args.build_command or args.no_lint:
                raise WorkbenchError("TeX options require the latex module")
            return validate_config(project, config)
        detected_args = copy.copy(args)
        detected_args.profile = detected_args.modules = None
        detected = detect_config(project, inventory, detected_args)
        config["modules"]["latex"] = module_config(detected, "latex")
        if has_module(detected, "bibliography"):
            # A source-declared bibliography is a real required capability.
            config["modules"]["bibliography"] = module_config(detected, "bibliography")
        return validate_config(project, config)
    roots = inventory["root_candidates"]
    selected = args.root or (roots[0] if len(roots) == 1 else None)
    if not selected:
        raise WorkbenchError("Root is ambiguous or absent; select --root PATH. Candidates: " + (", ".join(roots) or "none found"),
                             hint=f"name the manuscript's main file, for example --root {roots[0]}" if roots else
                             "a manuscript needs its main .tex file (with \\documentclass) to exist: create it, or name it with --root. "
                             "A project without a manuscript takes a profile without LaTeX: --profile notebook, numerical or core")
    root = local_path(project, selected)
    if not root.is_file():
        raise WorkbenchError(f"Root not found: {selected}")
    sources = source_tree(project, root)
    text = "\n".join(s for _, s in sources)
    raw = read_tex(root)
    magic = re.search(r"^\s*%\s*!TeX\s+(?:program|TS-program)\s*=\s*(\w+)", raw, re.M | re.I)
    engine = args.engine or (magic[1].lower() if magic else None)
    if not engine and re.search(r"\\(?:directlua|usepackage(?:\[[^\]]*\])?\{luacode\})", text):
        engine = "lualatex"
    if not engine and re.search(r"\\(?:XeTeX|setCJKmainfont)|\{xeCJK\}", text):
        engine = "xelatex"
    if not engine and inventory["build_files"]:
        engine, source = build_engine(project, inventory["build_files"])
        if engine:
            inventory["engine_source"] = source  # reported as a note, so the choice can be checked in the dry run
    if not engine and ("fontspec" in text or inventory["build_files"]):
        reason = "it loads fontspec" if "fontspec" in text else "it has build files of its own (" + ", ".join(inventory["build_files"][:3]) + ") that do not name one engine"
        makefile = guide.makefile_text(project)
        own_build = "" if not makefile or "build" in make_targets(makefile, project) else (
            "; its Makefile has no `build` target, so also name the command that builds the PDF, for example --build-command '[\"make\", \"pdf\"]'")
        raise WorkbenchError("Engine/build conventions need confirmation; inspect build files and supply --engine",
                             hint=f"the engine is not guessed for this project because {reason}: add --engine pdflatex, --engine lualatex or --engine xelatex{own_build}")
    engine = engine or "pdflatex"
    biblatex = re.search(r"\\usepackage(?:\[([^\]]*)\])?\{biblatex\}", text)
    backend = args.backend or ("bibtex" if biblatex and re.search(r"backend\s*=\s*bibtex", biblatex[1] or "")
                               else "biber" if biblatex or "\\addbibresource" in text
                               else "bibtex" if "\\bibliography{" in text else "none")
    files = []
    for match in re.finditer(r"\\(?:bibliography|addbibresource)(?:\[[^\]]*\])?\s*\{([^{}\\]+)\}", text):
        for value in match[1].split(","):
            value = value.strip()
            if not value.endswith(".bib"):
                value += ".bib"
            path = local_path(project, str((root.parent / value).relative_to(project)))
            files.append(path.relative_to(project).as_posix())
    command = build_command_argument(args.build_command) if args.build_command else None
    if command is None and "build" in make_targets(guide.makefile_text(project), project):
        command = ["make", "build"]
    modules = {"latex": {"default_document": "manuscript", "documents": {"manuscript": {
        "root": selected, "engine": engine, "backend": backend,
        "lint": {"enabled": not args.no_lint, "args": []}, "build_command": command,
        "output_dir": root.parent.relative_to(project).as_posix() if command else None}}}}
    if files or backend != "none":
        modules["bibliography"] = {"files": sorted(set(files)), "export": None}
    return validate_config(project, {"schema_version": 3, "modules": modules,
        "integrations": {"editor": not args.skip_editor, "ci": {"enabled": not args.no_ci,
            "pdf_artifact": not args.no_artifact, "texlive_version": "2026"}}})


ENGINE_SIGNS = (("lualatex", r"lualatex|-pdflua(?![a-z])|-lualatex(?![a-z])"), ("xelatex", r"xelatex|-pdfxe(?![a-z])|-xelatex(?![a-z])"),
                ("pdflatex", r"pdflatex|latexmk\b[^\n]*\s-pdf(?![a-z])"))


def build_engine(project, build_files):
    """The engine the project's own build names (a Makefile, latexmkrc or shell script), with the file it was
    read from. Reading the project's convention is not guessing; two different engines are left to the user."""
    found = {}
    for name in build_files:
        if Path(name).name in {*MAKEFILES, ".latexmkrc", "latexmkrc"} or name.endswith(".sh"):
            try:
                text = "\n".join(line.split("#", 1)[0] for line in (project / name).read_text(encoding="utf-8").splitlines())
            except (OSError, ValueError):
                continue
            for engine, pattern in ENGINE_SIGNS:
                if re.search(pattern, text):
                    found.setdefault(engine, name)
    return next(iter(found.items())) if len(found) == 1 else (None, None)


def replay(args, verb, project):
    """The command that applies what this run previewed: the same choices, under another mode."""
    words = ["python3", str(PACKAGE / "latex-ai-init"), verb, str(project)]
    for name in ("profile", "modules", "root", "engine", "backend", "build_command"):
        if getattr(args, name) is not None:
            words += ["--" + name.replace("_", "-"), getattr(args, name)]
    words += ["--" + name.replace("_", "-") for name in ("editor", "ci", "no_lint", "no_ci", "no_artifact", "skip_editor") if getattr(args, name)]
    return shlex.join(words)


def closing_lines(args, project, report, makefile):
    """The plain-language end of the text output: what happened, and what to do next."""
    files = [item for item in report["changes"] if item["path"] != STATE]
    record_only = bool(report["changes"]) and not files  # the manifest follows edits to files it shares with the project
    if report["conflicts"]:
        return ["", "Nothing was changed. Resolve the CONFLICT lines above, then run this command again."]
    if args.mode == "audit":
        if not report["changes"]:
            return ["", "Audit only: nothing was changed; the installation is current."]
        command = replay(args, "upgrade" if (project / STATE).is_file() else "init", project)
        if record_only:
            return ["", f"Audit only: nothing was changed. Only the installation record ({STATE}) would be refreshed, to follow "
                        f"your edits to files it shares with you (Makefile, policy, editor settings); apply with: {command}"]
        return ["", f"Audit only: nothing was changed. {len(files)} file(s) would be added or updated; apply with: {command}"]
    if args.dry_run:
        return ["", "Dry run: nothing was changed. Run the same command without --dry-run to apply it (--diff shows the exact changes)."]
    if not report["applied"] or not report["changes"]:
        return []
    if record_only:
        return ["", f"Done: the installation record ({STATE}) now follows your edits to the files it shares with you; no other file was changed."]
    created = sum(item["action"] == "create" for item in files)
    lines = ["", f"Done: {created} file(s) added, {len(files) - created} updated. Files you already had were kept; "
                 f"anything replaced is backed up under {report['backup'] or '.latex-ai/backups'}.", "", "Next:"]
    steps = [(guide.usable_name(makefile, short, reserved), meaning) for short, reserved, meaning in (
        ("doctor", "latex-ai-doctor", "confirm the required tools are installed"), ("help", "latex-ai-help", "see the commands this project has"),
        ("status", "latex-ai-status", "see where the project stands and what to run first"), ("check", None, "run the full check"))]
    width = max([len(name) for name, _ in steps if name] or [0])
    return lines + [f"  make {name:<{width}}  # {meaning}" for name, meaning in steps if name]


def initial_json_merge(current, desired):
    result = dict(current)
    for key, value in desired.items():
        if key not in result:
            result[key] = value
        elif key in {"latex-workshop.latex.recipe.default", "latex-workshop.latex.build.enableMagicComments", "latex-workshop.latex.outDir"} and result[key] != value:
            raise WorkbenchError(f"Editor setting {key} conflicts with canonical Make/output configuration; use --skip-editor to preserve it")
        elif isinstance(value, dict) and isinstance(result[key], dict):
            result[key] = initial_json_merge(result[key], value)
        elif isinstance(value, list) and key in {"tasks", "latex-workshop.latex.tools", "latex-workshop.latex.recipes"}:
            identity = "label" if key == "tasks" else "name"
            if not isinstance(result[key], list) or any(not isinstance(item, dict) for item in result[key]):
                raise WorkbenchError(f"Invalid {key} array")
            existing = {item.get(identity): item for item in result[key]}
            additions = []
            for item in value:
                if item[identity] in existing and existing[item[identity]] != item:
                    raise WorkbenchError(f"Conflicting editor {identity}: {item[identity]}; use --skip-editor to preserve editor files")
                if item[identity] not in existing:
                    additions.append(item)
            result[key] = result[key] + additions
        # Ordinary editor preferences belong to the project; retain them.
    return result


def three_way(base, local, new):
    if local == base:
        return new
    if new == base or local == new:
        return local
    if all(isinstance(v, list) for v in (base, local, new)):
        combined = base + local + new
        identity = next((k for k in ("label", "name") if combined and all(isinstance(i, dict) and k in i for i in combined)), None)
        if identity:
            maps = [{i[identity]: i for i in seq} for seq in (base, local, new)]
            if any(len(m) != len(seq) for m, seq in zip(maps, (base, local, new))):
                raise WorkbenchError("Duplicate editor item identifiers")
            merged = three_way(*maps)
            order = list(dict.fromkeys(i[identity] for i in local + new))
            return [merged[k] for k in order if k in merged]
    if all(isinstance(v, dict) for v in (base, local, new)):
        result = {}
        absent = object()
        for key in dict.fromkeys(list(local) + list(new) + list(base)):
            b, l, n = base.get(key, absent), local.get(key, absent), new.get(key, absent)
            if l == b:
                value = n
            elif n == b or l == n:
                value = l
            elif all(isinstance(v, dict) for v in (b, l, n)) or all(isinstance(v, list) for v in (b, l, n)):
                value = three_way(b, l, n)
            else:
                raise WorkbenchError(f"Upgrade conflicts with local changes at {key}")
            if value is not absent:
                result[key] = value
        return result
    raise WorkbenchError("Upgrade conflicts with local changes")


def seed_paths(config):
    paths = {module_config(config, name)["manifest"] for name in ("numerics", "figures", "claims") if has_module(config, name)}
    if has_module(config, "notes"):
        values = module_config(config, "notes")
        paths.update((Path(values["path"]) / values[key]).as_posix() for key in ("index", "session_state"))
    return paths


def note_seeds(config):
    if not has_module(config, "notes"):
        return {}
    values = module_config(config, "notes")
    result = {}
    for key in ("index", "session_state"):
        path = (Path(values["path"]) / values[key]).as_posix()
        suffix = Path(path).suffix.lower()
        if suffix == ".md":
            relative = os.path.relpath(Path(values["path"]) / values["session_state"], Path(path).parent).replace(os.sep, "/")
            result[path] = ("# Research notes\n\nRecord ideas, derivations and decisions here.\n\n[Session state](" + relative + ")\n"
                            if key == "index" else "# Session state\n\n## Current question\n\n## Established results and assumptions\n\n## Open issues\n\n## Next action\n")
        elif suffix == ".tex":
            if key == "index":
                relative = os.path.relpath(Path(values["path"]) / values["session_state"], Path(path).parent).replace(os.sep, "/")
                body = "\\input{" + relative + "}\n" if Path(relative).suffix == ".tex" else "\\section*{Session state}\n% See " + relative + "\n"
                result[path] = "\\documentclass{article}\n\\usepackage{amsmath}\n\\begin{document}\n\\section*{Research notes}\n" + body + "\\end{document}\n"
            else:
                result[path] = "\\section*{Current question}\n\n\\section*{Established results and assumptions}\n\n\\section*{Open issues}\n\n\\section*{Next action}\n"
    return result


# Seeded into a new task manifest beside the (empty) task list: the format, where the user will look for it.
EXAMPLE_TASK = {
    "numerics": {"note": "Not a task. Copy the object under \"task\" into \"tasks\" under a name of your choice, fit it to your project, and run it "
                         "with: make run TASK=<name>. The full format is under \"Task manifests\" in docs/research.md of the workbench package.",
                 "task": {"description": "What this run computes", "command": ["python3", "analysis/run.py", "configs/run.json"],
                          "inputs": ["analysis/run.py", "configs/run.json"], "outputs": ["results/run.json"],
                          "checks": [{"command": ["python3", "analysis/check.py"], "cost": "cheap"}]}},
    "figures": {"note": "Not a task. Copy the object under \"task\" into \"tasks\" under a name of your choice, fit it to your project, and build it "
                        "with: make figure TASK=<name>. A figure that reads a declared result becomes stale when that result does.",
                "task": {"description": "What this figure shows", "command": ["python3", "analysis/plot.py"],
                         "inputs": ["analysis/plot.py", "results/run.json"], "outputs": ["figures/result.pdf"]}},
}


def compiled_pdf(tex, project=None):
    root = local_path(project, tex["root"]) if project is not None else Path(tex["root"])
    output = (local_path(project, tex["output_dir"]) if project is not None else Path(tex["output_dir"])) if tex.get("output_dir") else root.parent
    pdf = output / (root.stem + ".pdf")
    return pdf.relative_to(project).as_posix() if project is not None else pdf.as_posix()


def viewer_out_dir(documents):
    """The ``latex-workshop.latex.outDir`` that points LaTeX Workshop's View PDF at where every document is built.

    One string serves every document: its placeholders expand per root file, and a relative value starts at the root's
    folder. The first template that gives each document its real output directory wins. ``(None, None)`` means each is
    built beside its root, where the viewer already looks; ``(None, reason)`` that no single value fits them all, so
    none is set (a value right for some documents would send the viewer to the wrong place for the others)."""
    places = [(document["name"], PurePosixPath(document["root"]).parent, PurePosixPath(posixpath.normpath(document["output_dir"])))
              for document in documents]
    if all(output == root for _, root, output in places):
        return None, None
    inside = [output.relative_to(root) for _, root, output in places if output != root and output.is_relative_to(root)]
    if len(inside) == len(places) and len(set(inside)) == 1:
        return "%DIR%/" + inside[0].as_posix(), None
    shared = {output for _, _, output in places}
    if len(shared) == 1:
        only = next(iter(shared))
        return ("%WORKSPACE_FOLDER%" if only == PurePosixPath(".") else "%WORKSPACE_FOLDER%/" + only.as_posix()), None
    where = "; ".join(f"{name} builds into {output.as_posix()}" for name, _, output in places)
    return None, ("LaTeX Workshop's View PDF can follow only one output folder pattern, and these documents build in different "
                  f"places ({where}), so the generated settings leave latex-workshop.latex.outDir unset and the viewer looks beside each "
                  "root file. Give the documents the same output_dir, or the same folder name beside each root, to let it find their PDFs.")


def desired_files(config, project=None):
    config = effective_config(config)
    files = {}
    for name in ["AGENTS.md", "CLAUDE.md", "Makefile", ".gitignore", ".claude/settings.json", ".codex/rules/git-safety.rules"]:
        files[name] = (PACKAGE / "templates" / name).read_text(encoding="utf-8")
    for source, target in runtime_sources(config).items():
        files[".latex-ai/" + target] = (PACKAGE / source).read_text(encoding="utf-8")
    files[".gitignore"] = ".DS_Store\n__pycache__/\n.latex-ai/backups/\n.latex-ai/artifacts/\n"
    adapter = integrations(config)
    if not has_module(config, "latex"):
        files["Makefile"] = core_makefile(config)
    retained = config
    if not has_module(config, "latex") and config.get("disabled_modules", {}).get("latex"):
        retained = {**config, "modules": {**config["modules"], "latex": config["disabled_modules"]["latex"]}}
    pdfs = ["/" + compiled_pdf(document.view, project).removeprefix("./") for document in specifications(retained)]
    if pdfs:
        files[".gitignore"] = (PACKAGE / "templates/.gitignore").read_text() + "\n".join(pdfs) + "\n.latex-ai/backups/\n"
    files["Makefile"] += module_make_targets(config, make_graph.read(files["Makefile"]).targets)  # the short names the template already defines
    if adapter["editor"]:
        if has_module(config, "latex"):
            files[".vscode/settings.json"] = (PACKAGE / "templates/.vscode/settings.json").read_text(encoding="utf-8")
            settings = json.loads(files[".vscode/settings.json"])
            targets = specifications(config)
            settings.pop("latex-workshop.latex.outDir", None)
            out_dir, _ = viewer_out_dir([target.view for target in targets])
            if out_dir:
                settings["latex-workshop.latex.outDir"] = out_dir
            settings["latex-workshop.latex.autoBuild.run"] = "never"
            settings["latex-workshop.latex.tools"] = [{"name": "make-" + document.name, "command": "make",
                "args": ["-C", "%WORKSPACE_FOLDER%", "latex-ai-build", "DOC=" + document.name]} for document in targets]
            settings["latex-workshop.latex.recipes"] = [{"name": "Build " + document.name, "tools": ["make-" + document.name]} for document in targets]
            settings["latex-workshop.latex.recipe.default"] = "Build " + targets[0].name
            tasks = [{"label": "Workbench: Check all", "type": "process", "command": "make", "args": ["check"],
                      "options": {"cwd": "${workspaceFolder}"}, "problemMatcher": []}]
            for document in targets:
                for label, command in (("Build", "latex-ai-build"), ("Check", "latex-ai-document-check"), ("Export PDF", "latex-ai-pdf-artifact")):
                    tasks.append({"label": label + ": " + document.name, "type": "process", "command": "make",
                                  "args": [command, "DOC=" + document.name], "options": {"cwd": "${workspaceFolder}"}, "problemMatcher": []})
            files[".vscode/tasks.json"] = encoded({"version": "2.0.0", "tasks": tasks})
            files[".vscode/settings.json"] = encoded(settings)
        else:
            files[".vscode/tasks.json"] = encoded({"version": "2.0.0", "tasks": [{"label": "Workbench: Check", "type": "process", "command": "make", "args": ["check"], "options": {"cwd": "${workspaceFolder}"}, "problemMatcher": []}]})
    for name in ("numerics", "figures", "claims"):
        if has_module(config, name):
            path = module_config(config, name)["manifest"]
            files[path] = encoded({"schema_version": 1, "claims": []} if name == "claims" else {"schema_version": 1, "tasks": {}, "example": EXAMPLE_TASK[name]})
    files.update(note_seeds(config))
    if adapter["ci"].get("enabled", False):
        files[".github/workflows/latex-ai.yml"] = workflow(config)
    return files


def plan(project, config, args):
    state_text = read(project, STATE)
    damaged = WorkbenchError(f"Damaged installation record: {STATE}", hint="restore it from version control or from a backup under "
                             ".latex-ai/backups/; it holds the baselines that make upgrades safe, so it is never guessed")
    try:
        state = json.loads(state_text) if state_text else {"schema_version": 1, "version": None, "files": {}}
    except ValueError:
        raise damaged
    if not isinstance(state, dict):
        raise damaged
    if state.get("schema_version") not in (1, MANIFEST_SCHEMA):
        raise WorkbenchError("Unsupported installation manifest schema")
    if args.mode == "upgrade" and not state_text:
        raise WorkbenchError("Not installed; use init first")
    oldfiles = state.get("files")
    if not isinstance(oldfiles, dict) or any(not isinstance(record, dict) or record.get("strategy") not in STRATEGIES for record in oldfiles.values()):
        raise damaged
    try:
        newer = bool(state.get("version")) and tuple(map(int, state["version"].split("."))) > tuple(map(int, VERSION.split(".")))
    except (AttributeError, ValueError):
        raise damaged
    if newer:
        raise WorkbenchError("Refusing downgrade from a newer workbench installation")
    wanted = desired_files(config, project)
    # Use actual directory names: on macOS, exists("makefile") can also match
    # "Makefile", which must retain its registered spelling for upgrades.
    project_names = {path.name for path in project.iterdir()}
    active_makefile = next((name for name in MAKEFILES if name in project_names), "Makefile")
    if active_makefile not in project_names and any((project / name).exists() for name in MAKEFILES):
        raise WorkbenchError("Unsupported Makefile filename casing; reconcile explicitly before setup")
    managed_makefiles = [name for name in MAKEFILES if name in oldfiles]
    if managed_makefiles and managed_makefiles != [active_makefile]:
        raise WorkbenchError(f"Active {active_makefile} differs from managed {managed_makefiles}; reconcile Makefile selection explicitly")
    if active_makefile != "Makefile":
        wanted[active_makefile] = wanted.pop("Makefile")
    # Retain the reference's existing CI filename on every subsequent run.
    if ".github/workflows/latex.yml" in oldfiles and ".github/workflows/latex-ai.yml" in wanted:
        wanted[".github/workflows/latex.yml"] = wanted.pop(".github/workflows/latex-ai.yml")
    if not integrations(config)["ci"].get("enabled", False):
        for name in oldfiles:
            if name.startswith(".github/workflows/"):
                wanted[name] = workflow(config)
    if args.skip_editor:
        wanted = {p: t for p, t in wanted.items() if not p.startswith(".vscode/")}
    updates, conflicts, notes, records, local = [], [], [], dict(oldfiles), []  # local: edits that block, for --diff
    if has_module(config, "latex") and integrations(config)["editor"] and not args.skip_editor:
        reason = viewer_out_dir([target.view for target in specifications(config)])[1]
        if reason:
            notes.append(reason)
    config_before = read(project, CONFIG)
    if config_before is None or args.mode == "configure":
        if config_before is None or json.loads(config_before) != config:
            updates.append({"path": CONFIG, "before": config_before, "after": encoded(config)})
    seeds = seed_paths(config)
    if has_module(config, "notes"):
        values = module_config(config, "notes")
        for key in ("index", "session_state"):
            path = (Path(values["path"]) / values[key]).as_posix()
            if path not in wanted and not local_path(project, path).is_file():
                conflicts.append(f"Missing notes entry point: {path}; create it before installation (seed templates support .md and .tex)")
    if not has_module(config, "latex") and ".vscode/settings.json" in oldfiles:
        wanted[".vscode/settings.json"] = encoded({"latex-workshop.latex.autoBuild.run": "never"})
    for name, upstream in wanted.items():
        try:
            if name.startswith(".vscode/"):
                upstream = encoded(json.loads(upstream))
            current = read(project, name)
            record = oldfiles.get(name)
            strategy = record["strategy"] if record else "seed" if name in seeds else "full"
            if strategy == "seed" and (current is not None or record):
                # Research notes/manifests belong to the project after creation:
                # never overwritten, and never recreated if the project deleted them.
                if current is None:
                    notes.append(f"Project-owned {name} was deleted locally; not recreated")
                records[name] = file_record(name, "seed", current, upstream)
                continue
            if not record and name.startswith(".vscode/"):
                strategy = "json"
            proposed = upstream
            if current is None:
                if record:
                    raise WorkbenchError("Previously installed file was deleted locally; reconcile explicitly")
            elif record:
                base = record.get("installed")
                if strategy == "block":
                    content = make_adapter(current, config, project) if name in MAKEFILES else integration_text(name, upstream)
                    proposed = merge_block(current, content, base)
                    upstream = content
                elif strategy == "json":
                    proposed = encoded(three_way(json.loads(record.get("upstream", base)), json.loads(current), json.loads(upstream)))
                elif current == upstream:
                    proposed = current
                elif extends(name, record, current):
                    # The installed text is intact: what the project wrote above or below it stays where it is.
                    proposed = current.replace(managed_text(record), upstream, 1)
                elif not is_installed(record, current):
                    # A digest-only record cannot show what was installed: show the change against this release's text.
                    shown = managed_text(record)
                    local.append({"path": name, "before": upstream if shown is None else shown, "after": current,
                                  "label": f"workbench {VERSION}" if shown is None else "as installed"})
                    raise WorkbenchError(
                        "Locally modified managed file: your copy differs inside the text the workbench installed. Lines added above or below that text are "
                        "kept on upgrade, a change inside it is not merged; undo it or move it outside, then run this again (--diff shows the change)"
                        if name in EXTENDABLE else
                        "Locally modified managed file: this file is installed whole and is not meant to be edited; restore it from version control, "
                        "then run this again (--diff shows the change)")
            elif name in MAKEFILES:
                strategy = "block"
                upstream = make_adapter(current, config, project)
                proposed = merge_block(current, upstream)
            elif name in {"AGENTS.md", "CLAUDE.md", ".gitignore"}:
                strategy = "block"
                upstream = integration_text(name, upstream)
                proposed = merge_block(current, upstream)
            elif name.startswith(".vscode/"):
                strategy = "json"
                try:
                    proposed = encoded(initial_json_merge(json.loads(current), json.loads(upstream)))
                except json.JSONDecodeError:
                    raise WorkbenchError("JSONC/comments unsupported for automatic editing; use --skip-editor and integrate manually")
            elif name.startswith((".claude/", ".codex/")):
                if current != upstream:
                    raise WorkbenchError("Existing agent guardrail differs; preserved. Reconcile with supplied template manually")
            elif name.startswith(".github/"):
                if current != upstream:
                    raise WorkbenchError("Workflow filename already used; preserve and reconcile manually")
            elif current != upstream:
                raise WorkbenchError("Unmanaged runtime file already exists")
            if current != proposed:
                updates.append({"path": name, "before": current, "after": proposed})
            records[name] = file_record(name, strategy, proposed, upstream)
        except (WorkbenchError, ValueError, KeyError) as error:
            conflicts.append(f"{name}: {error}")
    # Keep custom policy and ignore blocks stable on subsequent upgrades.
    for name, record in list(records.items()):
        if name not in wanted:
            notes.append(f"Previously managed {name} retained; no automatic deletion")
    manifest = encoded({"schema_version": MANIFEST_SCHEMA, "version": VERSION,
                        "files": {name: current_record(name, record) for name, record in records.items()}})
    if manifest != state_text and not conflicts:
        updates.append({"path": STATE, "before": state_text, "after": manifest})
    return updates, conflicts, notes, local


def main(argv=None):
    parser = argparse.ArgumentParser(description="LaTeX AI Workbench: inspect first, preserve local files, never mutate Git")
    parser.add_argument("mode", nargs="?", choices=["audit", "init", "upgrade", "configure", "recover"], default="audit")
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--profile", choices=sorted(PROFILES))
    selection.add_argument("--modules", help="Exact comma-separated initial module selection; empty selects core only")
    parser.add_argument("--editor", action="store_true", help="Opt into project-local editor adapter for a new modular project")
    parser.add_argument("--ci", action="store_true", help="Opt into CI for a new modular project")
    parser.add_argument("--document", help="configure: add or update a named LaTeX document")
    parser.add_argument("--default-document", help="configure: select the default named document")
    parser.add_argument("--enable", action="append", choices=sorted(MODULES), default=[])
    parser.add_argument("--disable", action="append", choices=sorted(MODULES), default=[])
    parser.add_argument("--root")
    parser.add_argument("--engine", choices=["pdflatex", "lualatex", "xelatex"])
    parser.add_argument("--backend", choices=["none", "bibtex", "biber"])
    parser.add_argument("--build-command", help="JSON argv for an existing build, e.g. '[\"make\",\"pdf\"]'")
    parser.add_argument("--no-lint", action="store_true", help="Disable lint for the selected document; other documents inherit their shared defaults")
    parser.add_argument("--no-ci", action="store_true")
    parser.add_argument("--no-artifact", action="store_true")
    parser.add_argument("--skip-editor", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_intermixed_args(argv)
    line_buffered()
    try:
        if (args.document or args.default_document) and (args.enable or args.disable or args.no_ci or args.no_artifact):
            raise WorkbenchError("Configure documents and module/CI choices in separate reviewed operations")
        if (args.enable or args.disable) and args.mode != "configure":
            raise WorkbenchError("--enable/--disable require configure mode")
        if set(args.enable) & set(args.disable):
            raise WorkbenchError("Cannot enable and disable the same module")
        project = args.project.resolve()
        if not project.is_dir():
            raise WorkbenchError(f"Project directory does not exist: {project}",
                                 hint="name the project's folder, not a file inside it" if project.is_file() else f"create it first: mkdir -p {shlex.quote(str(project))}")
        if args.mode == "recover":
            if args.dry_run:
                raise WorkbenchError("Recovery is explicit; inspect .latex-ai/transaction.json before running it")
            with installation_lock(project):
                restored = recover(project)
            print("Previous installation restored" if restored else "No unfinished installation transaction")
            return 0
        pending_transaction(project)
        inventory = discover(project)
        git = git_snapshot(project)
        config = detect_config(project, inventory, args)
        updates, conflicts, notes, local = plan(project, config, args)
        if inventory.get("engine_source"):
            notes.append(f"engine {document_settings(config)['engine']} read from {inventory['engine_source']}; pass --engine to choose another")
        if args.mode != "upgrade" and args.profile is None and args.modules is None:
            # The default for a paper is the fullest: say what comes with it besides the checks, and how to decline.
            created = [update["path"] for update in updates if update["before"] is None]
            if any(path.startswith(".vscode/") for path in created):
                notes.append("the default for a paper adds VS Code settings and tasks (.vscode/); --skip-editor leaves them out")
            if any(path.startswith(".github/workflows/") for path in created):
                notes.append("the default for a paper adds a GitHub Actions workflow (.github/workflows/); --no-ci leaves it out")
        try:
            if has_module(config, "latex") or has_module(config, "bibliography"):
                bibliography_check(project, document_settings(config))
        except WorkbenchError as error:
            conflicts.append("Bibliography: " + str(error))
        if config.get("modules") is not None:
            import research
            for name in ("numerics", "figures", "claims"):
                if has_module(config, name) and local_path(project, module_config(config, name)["manifest"]).is_file():
                    try:
                        if name == "claims":
                            with contextlib.redirect_stdout(io.StringIO()):
                                research.check_claims(project, config)
                        else:
                            research.tasks(project, config, name)
                    except (WorkbenchError, ValueError, KeyError, TypeError) as error:
                        conflicts.append(f"{name} manifest: {error}")
        # The Makefile as it will be: the planned text of whichever name is active, else the one on disk.
        final_makefile = next((u["after"] for u in updates if u["path"] in MAKEFILES), None) or guide.makefile_text(project)
        for short, reserved in guide.shadowed(final_makefile, project):
            notes.append(f"kept your Makefile target `{short}`; the workbench command is `make {reserved}`")
        if "latex-ai-build-prepare" in final_makefile and make_has_extra_prereqs() is False:
            notes.append(f"the adopted Make build needs {ADOPTED_MAKE} (with .EXTRA_PREREQS), and the `make` on PATH is older: "
                         "your own targets keep working, but the workbench's build and check refuse until a newer GNU Make "
                         "comes first on PATH (on macOS, for example, Homebrew's `make`, installed as gmake with a gnubin directory)")
        export = module_config(config, "bibliography").get("export")
        if export and not local_path(project, export["path"]).exists() and not export.get("required", True):
            notes.append(f"Optional bibliography export pending: {export['path']}")
        if git["better_bibtex_auto_push"] and git["better_bibtex_auto_push"].lower() in {"true", "yes", "1", "on"}:
            conflicts.append("Better BibTeX automatic Git push is enabled; manual Git approval policy is not satisfied")
        backup = None
        if not conflicts and args.mode != "audit" and not args.dry_run:
            backup = apply(project, updates)
        tex = document_settings(config, args.document) if has_module(config, "latex") else None
        report = {"version": VERSION, "project": str(project), "git": git, "inventory": inventory, "config": config, "document": tex,
                  "changes": [{"path": u["path"], "action": "create" if u["before"] is None else "update"} for u in updates],
                  "conflicts": conflicts, "notes": notes, "backup": backup,
                  "applied": not conflicts and args.mode != "audit" and not args.dry_run}
        if args.json:
            print(encoded(report), end="")
        else:
            print(f"LaTeX AI Workbench {VERSION}: {args.mode} {project}")
            print(git["status"] or "No Git repository (no Git initialization performed)")
            print("Modules: " + (", ".join(name for name in MODULES if has_module(config, name)) or "core only"))
            if tex:
                print(f"Document {tex['name']}: root {tex['root']}; engine: {tex['engine']}; bibliography: {tex['bibliography']['backend']}; "
                      f"output: {tex['output_dir']}; lint: {'enabled' if tex['lint']['enabled'] else 'disabled'}")
                if args.mode == "configure":
                    print("NOTE: Other documents inherit shared defaults; --no-lint applies only to this document")
            for item in report["changes"]:
                print(f"{item['action'].upper()}: {item['path']}")
            for note in notes:
                print("NOTE: " + note)
            for conflict in conflicts:
                print("CONFLICT: " + conflict)
            if backup:
                print("Backups: " + backup)
            print("No changes applied" if not report["applied"] else "Applied" if updates else "Already current; no changes")
        if args.diff:
            for update in updates:
                if update["path"] == STATE:
                    continue
                copied = next((kind for prefix, kind in COPIED if update["path"].startswith(prefix)), None)
                if update["before"] is None and copied:
                    # The package's own code and rule lists, copied unchanged: thousands of lines nobody reviews in a preview.
                    print(f"new file: {update['path']} ({len(update['after'].splitlines())} lines of {copied}, copied unchanged from the package)")
                    continue
                print("".join(difflib.unified_diff((update["before"] or "").splitlines(True), update["after"].splitlines(True),
                                                fromfile=update["path"], tofile=update["path"])), end="")
            for change in local:
                print("".join(difflib.unified_diff(change["before"].splitlines(True), change["after"].splitlines(True),
                                                fromfile=f"{change['path']} ({change['label']})", tofile=change["path"] + " (yours)")), end="")
        if not args.json:  # last, so that the summary is what remains on screen after a long diff
            for line in closing_lines(args, project, report, final_makefile):
                print(line)
        return 2 if conflicts else 1 if args.mode == "audit" and updates else 0
    except Exception as error:
        if not isinstance(error, (WorkbenchError, OSError, ValueError)):
            # Nothing the project's files can cause: a defect in the installer itself.
            message = f"INTERNAL ERROR: {type(error).__name__}: {error}"
            hint = "This looks like a defect in the workbench, not a problem with the project; report it with the command and this output."
            if args.json:
                print(encoded({"internal_error": message, "hint": hint}), end="")
            else:
                print(message + "\n" + hint, file=sys.stderr)
            return 70
        advice = getattr(error, "hint", None)
        if args.json:
            print(encoded({"error": str(error), "hint": advice, "inventory": locals().get("inventory"), "git": locals().get("git")}), end="")
        else:
            print("ERROR: " + str(error), file=sys.stderr)
            if advice:
                print("Hint: " + advice, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
