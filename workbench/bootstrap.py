"""Create a workbench project, or refresh its runtime. No Git mutations or network calls.

``init`` writes the files a new project needs. It never changes a file the project has: one that differs from what it would write
is a conflict. Configuration must be prepared explicitly before installation.
``diff`` shows how a project differs from what ``init`` would write now. ``runtime`` refreshes the vendored runtime files.
There is no upgrade, audit or recovery: a project is updated by following docs/upgrading.md.
"""
import argparse
import difflib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import posixpath
import shlex
import shutil
import sys

sys.dont_write_bytecode = True
import guide
from commands import RECIPE_ARGUMENTS, COMMANDS
from core import (CONFIG, MAKEFILES, VERSION, WorkbenchError, atomic_write, effective_config, git_output,
                  integrations, line_buffered, local_path, runtime_sources)
from diagnostics import recorded_digests, sha256_text
from latex import bibliography_check
from schema import document_settings, load_config, specifications, validate_config

PACKAGE = Path(__file__).resolve().parent
STATE = ".latex-ai/installation.json"  # what init and runtime wrote: the version, and a digest of each runtime file
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


def initial_config(project):
    """Installation consumes explicit configuration; it never derives settings from source files."""
    if read(project, STATE) is not None:
        raise WorkbenchError("This project already has the workbench installed",
                             hint="use `latex-ai-init runtime .` to refresh runtime files or `latex-ai-init diff .` to inspect differences")
    if read(project, CONFIG) is None:
        raise WorkbenchError(f"Installation requires an explicit {CONFIG}",
                             hint=f"prepare {CONFIG} using examples/minimal/.latex-ai.json in the workbench package, declaring each document root")
    return load_config(project)


def make_targets():
    """One fixed Make recipe per public registry entry; values enter through the environment."""
    result = ["export ISSUE_NOTE ISSUE_COMMAND SNAPSHOT_NOTE DOC"]
    for command in COMMANDS:
        result.extend([f".PHONY: {command.short}", f"{command.short}:",
                       f"\t@$(PYTHON) .latex-ai/workbench.py {command.action}{RECIPE_ARGUMENTS[command.selects]}"])
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
    pdfs = ["/" + compiled_pdf(document.view, project).removeprefix("./") for document in specifications(config)]
    if pdfs:
        files[".gitignore"] = (PACKAGE / "templates/.gitignore").read_text() + "\n".join(pdfs) + "\n.latex-ai/backups/\n"
    files["Makefile"] += make_targets()
    if adapter["editor"]:
        files[".vscode/settings.json"] = (PACKAGE / "templates/.vscode/settings.json").read_text(encoding="utf-8")
        settings = json.loads(files[".vscode/settings.json"])
        targets = specifications(config)
        settings.pop("latex-workshop.latex.outDir", None)
        out_dir, _ = viewer_out_dir([target.view for target in targets])
        if out_dir:
            settings["latex-workshop.latex.outDir"] = out_dir
        settings["latex-workshop.latex.autoBuild.run"] = "never"
        settings["latex-workshop.latex.tools"] = [{"name": "make-" + document.name, "command": "make",
            "args": ["-C", "%WORKSPACE_FOLDER%", "build", "DOC=" + document.name]} for document in targets]
        settings["latex-workshop.latex.recipes"] = [{"name": "Build " + document.name, "tools": ["make-" + document.name]} for document in targets]
        settings["latex-workshop.latex.recipe.default"] = "Build " + targets[0].name
        tasks = [{"label": "Workbench: Check all", "type": "process", "command": "make", "args": ["check"],
                  "options": {"cwd": "${workspaceFolder}"}, "problemMatcher": []}]
        for document in targets:
            for label, command in (("Build", "build"), ("Check", "document-check"), ("Export PDF", "pdf-artifact")):
                tasks.append({"label": label + ": " + document.name, "type": "process", "command": "make",
                              "args": [command, "DOC=" + document.name], "options": {"cwd": "${workspaceFolder}"}, "problemMatcher": []})
        files[".vscode/tasks.json"] = encoded({"version": "2.0.0", "tasks": tasks})
        files[".vscode/settings.json"] = encoded(settings)
    return files


MOVE_ASIDE = "use a fresh project directory or resolve the conflicting file explicitly before init"


def plan(project, config):
    """What `init` would write: (updates, conflicts, notes). A file that is absent is created; one that is already what init writes is
    left as it is; one that differs is a conflict. Nothing of the project's is merged into or overwritten."""
    wanted = desired_files(config, project)
    present = {path.name for path in project.iterdir()}  # actual names: on macOS, exists("makefile") also matches "Makefile"
    updates, conflicts, notes = [], [], []
    if integrations(config)["editor"]:
        reason = viewer_out_dir([target.view for target in specifications(config)])[1]
        if reason:
            notes.append(reason)
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


def closing_lines(args, report):
    """The plain-language end of the text output: what happened, and what to do next."""
    if report["conflicts"]:
        return ["", "Nothing was changed. Resolve the CONFLICT lines above, then run this command again."]
    if args.dry_run:
        return ["", "Dry run: nothing was changed. Run the same command without --dry-run to apply it (--diff shows the exact changes)."]
    if not report["applied"] or not report["changes"]:
        return []
    created = sum(item["path"] != STATE for item in report["changes"])
    lines = ["", f"Done: {created} file(s) added. No file you already had was changed.", "", "Next:"]
    steps = [("doctor", "confirm the required tools are installed"), ("help", "see the commands"),
             ("status", "see where the project stands"), ("check", "run the full check")]
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="LaTeX AI Workbench: create a project, preserve local files, never mutate Git")
    parser.add_argument("mode", choices=["init", "diff", "runtime"], help="init: create a project; diff: how a project differs from this release; runtime: refresh its runtime files")
    parser.add_argument("project", nargs="?", type=Path, default=Path.cwd())
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
        allowed = {"init": {"dry_run", "diff", "json"}, "diff": {"diff"}, "runtime": {"dry_run", "force"}}
        refused = ["--" + name.replace("_", "-") for name in ("dry_run", "diff", "force", "json")
                   if getattr(args, name) and name not in allowed[args.mode]]
        if refused:
            raise WorkbenchError(f"`{args.mode}` does not take {', '.join(refused)}",
                                 hint="init: --dry-run, --diff, --json; diff: --diff; runtime: --dry-run, --force")
        if args.mode != "init":
            return do_diff(project, args) if args.mode == "diff" else do_runtime(project, args)
        git = git_snapshot(project)
        config = initial_config(project)
        updates, conflicts, notes = plan(project, config)
        try:
            for document in specifications(config):
                bibliography_check(project, document.view)
        except WorkbenchError as error:
            conflicts.append("Bibliography: " + str(error))
        export = config.get("bibliography", {}).get("export")
        if export and not local_path(project, export["path"]).exists() and not export.get("required", True):
            notes.append(f"Optional bibliography export pending: {export['path']}")
        if git["better_bibtex_auto_push"] and git["better_bibtex_auto_push"].lower() in {"true", "yes", "1", "on"}:
            conflicts.append("Better BibTeX automatic Git push is enabled; manual Git approval policy is not satisfied")
        backup = None
        if not conflicts and not args.dry_run:
            backup = apply(project, updates)
        tex = document_settings(config)
        report = {"version": VERSION, "project": str(project), "git": git, "config": config, "document": tex,
                  "changes": [{"path": u["path"], "action": "create" if u["before"] is None else "update"} for u in updates],
                  "conflicts": conflicts, "notes": notes, "backup": backup, "applied": not conflicts and not args.dry_run}
        if args.json:
            print(encoded(report), end="")
        else:
            print(f"LaTeX AI Workbench {VERSION}: {args.mode} {project}")
            print(git["status"] or "No Git repository (no Git initialization performed)")
            print("Documents: " + ", ".join(document.name for document in specifications(config)))
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
            for line in closing_lines(args, report):
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
            print(encoded({"error": str(error), "hint": advice, "git": locals().get("git")}), end="")
        else:
            print("ERROR: " + str(error), file=sys.stderr)
            if advice:
                print("Hint: " + advice, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
