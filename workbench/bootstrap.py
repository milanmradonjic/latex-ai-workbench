"""Create a workbench project, or refresh its runtime. No Git mutations or network calls.

``init`` writes the files a new project needs. It never changes a file the project has: one that differs from what it would write
is a conflict, and an existing project is migrated by following docs/migrating.md, which an agent can do.
``diff`` shows how a project differs from what ``init`` would write now. ``runtime`` refreshes the vendored runtime files.
There is no upgrade, audit or recovery: a project is updated by following docs/upgrading.md.
"""
import argparse
import copy
import difflib
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import posixpath
import re
import shlex
import shutil
import sys

sys.dont_write_bytecode = True
import guide
from commands import RECIPE_ARGUMENTS
from core import (CONFIG, GENERATED_TREES, MAKEFILES, MODULES, VERSION, WorkbenchError, atomic_write, effective_config, git_output,
                  has_module, integrations, line_buffered, local_path, module_config, read_tex, runtime_sources)
from diagnostics import recorded_digests, sha256_text
from guide import make_targets
from latex import bibliography_check, source_tree, tex_without_comments
from schema import document_settings, load_config, specifications, validate_config

PACKAGE = Path(__file__).resolve().parent
STATE = ".latex-ai/installation.json"  # what init and runtime wrote: the version, and a digest of each runtime file
EXCLUDED = GENERATED_TREES | {"workbench", "build", "out"}  # the installer also leaves out the distribution and build folders
COPIED = ((".latex-ai/", "workbench runtime"), (".claude/", "agent guardrails that prompt before Git changes"),
          (".codex/", "agent guardrails that prompt before Git changes"))


def encoded(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def read(project, name):
    path = local_path(project, name)
    # A write destination must not be redirected even within the project.
    cursor = project / name
    while cursor != project:
        if cursor.is_symlink():
            raise WorkbenchError(f"Refusing symlink destination: {name}")
        cursor = cursor.parent
    if path.exists() and not path.is_file():
        raise WorkbenchError(f"Expected a file: {name}")
    return path.read_text(encoding="utf-8") if path.exists() else None


def publish(project, name, text):
    """Write installer text in the line endings the file already uses (an owner's CRLF file must not come back as LF)."""
    path = project / name
    if path.is_file():
        data = path.read_bytes()
        crlf = data.count(b"\r\n")
        if crlf > data.count(b"\n") - crlf:
            text = text.replace("\n", "\r\n")
    atomic_write(path, text)


def apply(project, updates):
    """Write the planned files; the original of every file that is replaced is kept under .latex-ai/backups/."""
    for update in updates:
        if read(project, update["path"]) != update["before"]:
            raise WorkbenchError(f"File changed after planning: {update['path']}; nothing applied")
    backup = project / ".latex-ai" / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for update in updates:
        if update["before"] is not None:
            read(project, str((backup / update["path"]).relative_to(project)))  # a backup must not be redirected by a symlink
    for update in updates:
        if update["before"] is not None:  # the original bytes, not their normalized reading
            destination = backup / update["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local_path(project, update["path"]), destination)
    for update in updates:
        publish(project, update["path"], update["after"])
    return str(backup.relative_to(project)) if backup.exists() else None


def git_snapshot(project):
    def command(*args):
        return git_output(project, *args)
    return {"branch": command("branch", "--show-current"),
            "status": command("status", "--short", "--branch"),
            "better_bibtex_auto_push": command("config", "--get", "zotero.betterbibtex.push")}


def discover(project):
    tex, bib = [], []
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
    roots = [name for name in tex if re.search(r"\\documentclass(?:\[[^\]]*\])?\s*\{", tex_without_comments(read_tex(project / name)))]
    return {"tex_files": tex, "root_candidates": roots, "bib_files": bib,
            "editor_files": [p for p in (".vscode/settings.json", ".vscode/tasks.json") if (project / p).exists()],
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
    """The configuration a new project starts from: its own `.latex-ai.json` if it has one, else a module list, else what
    the project's files say."""
    if read(project, STATE) is not None:
        raise WorkbenchError("This project already has the workbench installed",
                             hint="`init` creates projects. To refresh its runtime files run `latex-ai-init runtime .`; "
                                  "to see how it differs from what `init` would write now, `latex-ai-init diff .`; the rest is in docs/upgrading.md "
                                  "(and docs/migrating.md for a project that an older release adapted, or one to start over)")
    if read(project, CONFIG) is not None:
        config = load_config(project)
        if args.modules is not None or args.editor:
            raise WorkbenchError("The project has its own configuration; --modules and --editor only choose the starting set of a new project",
                                 hint=f"run init again without them (a project that an interrupted init began is finished that way); to change what it chose, edit {CONFIG}")
        tex = document_settings(config)
        selections = [(args.root, tex.get("root")),
                      (build_command_argument(args.build_command) if args.build_command else None, tex.get("build_command"))]
        if any(chosen is not None and chosen != current for chosen, current in selections) or (
                args.no_lint and tex.get("lint", {}).get("enabled", True)):
            raise WorkbenchError(f"Project choices differ; edit {CONFIG} explicitly instead of overriding it with options")
        return config
    if args.modules is not None:
        names = [n.strip() for n in args.modules.split(",") if n.strip()]
        if set(names) - MODULES.keys():
            raise WorkbenchError("Unknown module(s): " + ", ".join(sorted(set(names) - MODULES.keys())))
        config = {"schema_version": 3, "modules": {n: copy.deepcopy(MODULES[n]["defaults"]) for n in names},
                  "integrations": {"editor": args.editor and not args.skip_editor}}
        if "latex" not in names:
            if args.root or args.build_command or args.no_lint:
                raise WorkbenchError("TeX options require the latex module")
            return validate_config(project, config)
        detected_args = copy.copy(args)
        detected_args.modules = None
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
                             "A project without a manuscript takes no LaTeX module: --modules ''")
    root = local_path(project, selected)
    if not root.is_file():
        raise WorkbenchError(f"Root not found: {selected}")
    sources = source_tree(project, root)
    text = "\n".join(s for _, s in sources)
    backend = "bibtex" if "\\bibliography{" in text else "none"
    files = []
    for match in re.finditer(r"\\bibliography\s*\{([^{}\\]+)\}", text):
        for value in match[1].split(","):
            value = value.strip()
            if not value.endswith(".bib"):
                value += ".bib"
            path = local_path(project, str((root.parent / value).relative_to(project)))
            files.append(path.relative_to(project).as_posix())
    command = build_command_argument(args.build_command) if args.build_command else None
    modules = {"latex": {"default_document": "manuscript", "documents": {"manuscript": {
        "root": selected, "engine": "pdflatex", "backend": backend,
        "lint": {"enabled": not args.no_lint, "args": []}, "build_command": command,
        "output_dir": root.parent.relative_to(project).as_posix() if command else None}}}}
    if files or backend != "none":
        modules["bibliography"] = {"files": sorted(set(files)), "export": None}
    return validate_config(project, {"schema_version": 3, "modules": modules,
        "integrations": {"editor": not args.skip_editor}})



def core_makefile():
    return "# Project-local core checks.\nPYTHON ?= python3\n.DEFAULT_GOAL := check\n.PHONY: check\ncheck:\n\t@$(PYTHON) .latex-ai/workbench.py check\n"


def module_make_targets(config, existing=()):
    """Every command of the registry that this configuration enables, under its reserved ``latex-ai-`` name, plus the short alias
    unless the template defines that name itself. Guidance and hints can therefore always name a command that reaches the
    workbench, and no command is named in a second place."""
    commands = [command for command in guide.COMMANDS if command.reserved and guide.enabled(command, config)]
    # DOC reaches recipes through the environment ("$$DOC"), never as Make text
    # spliced into a shell line, so its value cannot be interpreted as shell syntax.
    result = ["export ISSUE_NOTE ISSUE_COMMAND",  # the same rule for the issue report's free text
              "export DOC"]  # the document selector
    for command in commands:
        result.extend([f".PHONY: {command.reserved}", f"{command.reserved}:"])
        result.append(f"\t@$(PYTHON) .latex-ai/workbench.py {command.action}{RECIPE_ARGUMENTS[command.selects]}")
        if command.short not in existing:
            result.extend([f".PHONY: {command.short}", f"{command.short}: {command.reserved}"])
    return "\n".join(result) + "\n"


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


def runtime_files(config):
    """The runtime files a project with this configuration vendors, as {".latex-ai/<name>": text}: the package's own code, copied unchanged."""
    return {".latex-ai/" + target: (PACKAGE / source).read_text(encoding="utf-8") for source, target in runtime_sources(effective_config(config)).items()}


def desired_files(config, project=None):
    config = effective_config(config)
    files = {}
    for name in ["AGENTS.md", "CLAUDE.md", "Makefile", ".gitignore", ".claude/settings.json", ".codex/rules/git-safety.rules"]:
        files[name] = (PACKAGE / "templates" / name).read_text(encoding="utf-8")
    files.update(runtime_files(config))
    files[".gitignore"] = ".DS_Store\n__pycache__/\n.latex-ai/backups/\n.latex-ai/artifacts/\n"
    adapter = integrations(config)
    if not has_module(config, "latex"):
        files["Makefile"] = core_makefile()
    pdfs = ["/" + compiled_pdf(document.view, project).removeprefix("./") for document in specifications(config)]
    if pdfs:
        files[".gitignore"] = (PACKAGE / "templates/.gitignore").read_text() + "\n".join(pdfs) + "\n.latex-ai/backups/\n"
    files["Makefile"] += module_make_targets(config, make_targets(files["Makefile"]))  # the short names the template already defines
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
    return files


MOVE_ASIDE = "move it aside, run init, then merge your content back (docs/migrating.md in the workbench package says how)"


def plan(project, config, args):
    """What `init` would write: (updates, conflicts, notes). A file that is absent is created; one that is already what init writes is
    left as it is; one that differs is a conflict. Nothing of the project's is merged into or overwritten."""
    wanted = desired_files(config, project)
    present = {path.name for path in project.iterdir()}  # actual names: on macOS, exists("makefile") also matches "Makefile"
    if args.skip_editor:
        wanted = {p: t for p, t in wanted.items() if not p.startswith(".vscode/")}
    updates, conflicts, notes = [], [], []
    if has_module(config, "latex") and integrations(config)["editor"] and not args.skip_editor:
        reason = viewer_out_dir([target.view for target in specifications(config)])[1]
        if reason:
            notes.append(reason)
    if read(project, CONFIG) is None:  # a configuration the project wrote itself is kept as it is
        updates.append({"path": CONFIG, "before": None, "after": encoded(config)})
    for other in (name for name in MAKEFILES if name in present and name != "Makefile"):
        conflicts.append(f"{other}: GNU Make reads it instead of the Makefile init writes; {MOVE_ASIDE}")
    for name, text in wanted.items():
        if name.startswith(".vscode/"):
            text = encoded(json.loads(text))
        try:
            current = read(project, name)
        except WorkbenchError as error:
            conflicts.append(f"{name}: {error}")
            continue
        if current is None:
            updates.append({"path": name, "before": None, "after": text})
        elif current != text:
            conflicts.append(f"{name}: already exists and is not what init writes; {MOVE_ASIDE}")
    if not conflicts:
        updates.append({"path": STATE, "before": read(project, STATE), "after": state_text({n: t for n, t in wanted.items() if n.startswith(".latex-ai/")})})
    return updates, conflicts, notes


def state_text(runtime):
    """The record init and runtime leave: the version, and a digest of every runtime file, so that a local edit shows."""
    return encoded({"schema_version": 3, "version": VERSION, "files": {name: sha256_text(text) for name, text in sorted(runtime.items())}})


def closing_lines(args, report, makefile):
    """The plain-language end of the text output: what happened, and what to do next."""
    if report["conflicts"]:
        return ["", "Nothing was changed. Resolve the CONFLICT lines above, then run this command again; migrating an existing project is described in docs/migrating.md."]
    if args.dry_run:
        return ["", "Dry run: nothing was changed. Run the same command without --dry-run to apply it (--diff shows the exact changes)."]
    if not report["applied"] or not report["changes"]:
        return []
    created = sum(item["path"] != STATE for item in report["changes"])
    lines = ["", f"Done: {created} file(s) added. No file you already had was changed.", "", "Next:"]
    steps = [(guide.usable_name(makefile, short, reserved), meaning) for short, reserved, meaning in (
        ("doctor", "latex-ai-doctor", "confirm the required tools are installed"), ("help", "latex-ai-help", "see the commands this project has"),
        ("status", "latex-ai-status", "see where the project stands and what to run first"), ("check", None, "run the full check"))]
    width = max([len(name) for name, _ in steps if name] or [0])
    return lines + [f"  make {name:<{width}}  # {meaning}" for name, meaning in steps if name]


def show(updates, local=()):
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


def runtime_differences(project, runtime):
    """(name, wanted text, current text or None) for each file of `runtime`, {name: text}, that the project does not hold as it is."""
    current = {name: read(project, name) for name in runtime}
    return [(name, text, current[name]) for name, text in runtime.items() if current[name] != text]


def do_diff(project, args):
    """Read-only: how the project differs from what `init` would write now. Exit status 1 when a runtime file differs."""
    config = load_config(project)
    wanted = desired_files(config, project)
    differing = runtime_differences(project, {name: text for name, text in wanted.items() if name.startswith(".latex-ai/")})
    for name, text, current in differing:
        print(f"RUNTIME {'missing' if current is None else 'differs'}: {name}")
    others = [(name, text, read(project, name)) for name, text in wanted.items() if not name.startswith(".latex-ai/")]
    for name, text, current in others:
        if current is None:
            print(f"MISSING: {name}")
        elif current != text:
            print(f"DIFFERS (a file you may have added to; read, do not overwrite): {name}")
            if args.diff:
                print("".join(difflib.unified_diff(current.splitlines(True), text.splitlines(True), fromfile=name + " (project)", tofile=name + " (template)")), end="")
    if args.diff:
        for name, text, current in differing:
            print("".join(difflib.unified_diff((current or "").splitlines(True), text.splitlines(True), fromfile=name + " (project)", tofile=name + " (this release)")), end="")
    print(f"Project runtime {recorded_version(project) or 'unrecorded'}; this release {VERSION}; "
          + ("runtime files are identical." if not differing else f"{len(differing)} runtime file(s) differ."))
    return 1 if differing else 0


def recorded_version(project):
    try:
        return json.loads((project / STATE).read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError):
        return None


def do_runtime(project, args):
    """Refresh the vendored runtime files, and the record of them. A file the project edited is never overwritten without --force."""
    if guide.old_adapter(project):
        raise WorkbenchError("This project's Makefile wraps its build in an adapter that Workbench 4.4 no longer has; refreshing the runtime would break it",
                             hint="migrate the project to the workbench's own Makefile first: docs/migrating.md in the workbench package says how")
    config = load_config(project)
    recorded = recorded_digests(project) or {}
    updates, conflicts = [], []
    wanted = runtime_files(config)
    for name, text in wanted.items():
        current = read(project, name)
        if current == text:
            continue
        if current is not None and not args.force and recorded.get(name) != sha256_text(current):
            conflicts.append(f"{name}: modified locally (or not written by the workbench); restore it from version control, or pass --force to replace it")
        updates.append({"path": name, "before": current, "after": text})
    state_before = read(project, STATE)
    state_after = state_text(wanted)
    if state_after != state_before:
        updates.append({"path": STATE, "before": state_before, "after": state_after})
    for update in updates:
        if update["path"] != STATE:
            print(f"{'CREATE' if update['before'] is None else 'UPDATE'}: {update['path']}")
    for conflict in conflicts:
        print("CONFLICT: " + conflict)
    if conflicts:
        print("Nothing was changed.")
        return 2
    if args.dry_run or not updates:
        print("Already current; no changes" if not updates else "Dry run: nothing was changed.")
        return 0
    backup = apply(project, updates)
    print(f"Runtime refreshed to {VERSION}." + (f" Replaced files are backed up under {backup}." if backup else ""))
    return 0


def init_only_flags(args):
    """The options only `init` reads that were given, so that `diff` and `runtime` refuse them rather than ignore them."""
    return ["--" + name.replace("_", "-") for name in ("modules", "editor", "root", "build_command", "no_lint", "skip_editor", "json")
            if getattr(args, name) not in (None, False)]


def main(argv=None):
    parser = argparse.ArgumentParser(description="LaTeX AI Workbench: create a project, preserve local files, never mutate Git")
    parser.add_argument("mode", choices=["init", "diff", "runtime"], help="init: create a project; diff: how a project differs from this release; runtime: refresh its runtime files")
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--modules", help="Exact comma-separated initial module selection; empty selects core only")
    parser.add_argument("--editor", action="store_true", help="Opt into project-local editor adapter for a new modular project")
    parser.add_argument("--root")
    parser.add_argument("--build-command", help="JSON argv for an existing build, e.g. '[\"make\",\"pdf\"]'")
    parser.add_argument("--no-lint", action="store_true", help="Disable lint for the document")
    parser.add_argument("--skip-editor", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--force", action="store_true", help="runtime: replace runtime files even where they were edited locally")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_intermixed_args(argv)
    line_buffered()
    try:
        project = args.project.resolve()
        if not project.is_dir():
            raise WorkbenchError(f"Project directory does not exist: {project}",
                                 hint="name the project's folder, not a file inside it" if project.is_file() else f"create it first: mkdir -p {shlex.quote(str(project))}")
        if args.mode != "init":
            refused = init_only_flags(args) + (["--force"] if args.force and args.mode != "runtime" else [])
            if refused:
                raise WorkbenchError(f"`{args.mode}` does not take {', '.join(refused)}",
                                     hint="`diff` takes --diff; `runtime` takes --dry-run and --force; the rest belong to `init`")
            return do_diff(project, args) if args.mode == "diff" else do_runtime(project, args)
        inventory = discover(project)
        git = git_snapshot(project)
        config = detect_config(project, inventory, args)
        updates, conflicts, notes = plan(project, config, args)
        if args.modules is None:
            # The default for a paper is the fullest: say what comes with it besides the checks, and how to decline.
            created = [update["path"] for update in updates if update["before"] is None]
            if any(path.startswith(".vscode/") for path in created):
                notes.append("the default for a paper adds VS Code settings and tasks (.vscode/); --skip-editor leaves them out")
        try:
            if has_module(config, "latex") or has_module(config, "bibliography"):
                bibliography_check(project, document_settings(config))
        except WorkbenchError as error:
            conflicts.append("Bibliography: " + str(error))
        # The Makefile as it will be: the planned text of whichever name is active, else the one on disk.
        final_makefile = next((u["after"] for u in updates if u["path"] in MAKEFILES), None) or guide.makefile_text(project)
        export = module_config(config, "bibliography").get("export")
        if export and not local_path(project, export["path"]).exists() and not export.get("required", True):
            notes.append(f"Optional bibliography export pending: {export['path']}")
        if git["better_bibtex_auto_push"] and git["better_bibtex_auto_push"].lower() in {"true", "yes", "1", "on"}:
            conflicts.append("Better BibTeX automatic Git push is enabled; manual Git approval policy is not satisfied")
        backup = None
        if not conflicts and not args.dry_run:
            backup = apply(project, updates)
        tex = document_settings(config) if has_module(config, "latex") else None
        report = {"version": VERSION, "project": str(project), "git": git, "inventory": inventory, "config": config, "document": tex,
                  "changes": [{"path": u["path"], "action": "create" if u["before"] is None else "update"} for u in updates],
                  "conflicts": conflicts, "notes": notes, "backup": backup, "applied": not conflicts and not args.dry_run}
        if args.json:
            print(encoded(report), end="")
        else:
            print(f"LaTeX AI Workbench {VERSION}: {args.mode} {project}")
            print(git["status"] or "No Git repository (no Git initialization performed)")
            print("Modules: " + (", ".join(name for name in MODULES if has_module(config, name)) or "core only"))
            if tex:
                print(f"Document {tex['name']}: root {tex['root']}; engine: {tex['engine']}; bibliography: {tex['bibliography']['backend']}; "
                      f"output: {tex['output_dir']}; lint: {'enabled' if tex['lint']['enabled'] else 'disabled'}")
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
            show(updates)
        if not args.json:  # last, so that the summary is what remains on screen after a long diff
            for line in closing_lines(args, report, final_makefile):
                print(line)
        return 2 if conflicts else 0
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
