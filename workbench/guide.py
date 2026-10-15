"""Orientation commands: ``help`` lists what this project can do, ``status`` says where it stands.

Both are read-only: nothing is built, run, written or changed in Git. What they list comes from
the project's own Makefile and configuration, so a command that is not installed is never offered.
This module is also the one place that knows how a workbench command is named in a given Makefile.
"""
import re
from pathlib import Path

from commands import COMMANDS  # the registry derives every name shown to readers
from core import MAKEFILES, MODULES, VERSION, WorkbenchError, document_paths, has_module
from schema import STATES, specifications


def enabled(command, config):
    """Whether this configuration turns the command on."""
    return not command.needs or any(has_module(config, name) for name in command.needs)


PURPOSE = {
    "latex": "build and check a LaTeX manuscript", "bibliography": "check bibliography files and keys",
}
CHECKED = ("files", "policy", "unit", "portability", "manuscript", "bibliography")


RULE = re.compile(r"^([^\s#:=$%][^:=#$%]*?)\s*::?(?![:=])", re.M)  # a rule line: its targets, before the colon
CONDITIONALS = {"ifeq", "ifneq", "ifdef", "ifndef", "else", "endif"}
WRAPPER = re.compile(r"^[+@-]*\s*(?:\$\(PYTHON\)|python(?:3(?:\.\d+)?)?)\s+(?:-[A-Za-z]+\s+)*\.latex-ai/workbench\.py\s+check\s*$")


def active_makefile(project):
    """Name of the file GNU Make reads in this directory, or None.

    Actual directory entries are compared first: on a case-insensitive filesystem ``makefile`` and
    ``Makefile`` are one file, and the spelling on disk is the one that was written.
    """
    try:
        present = {path.name for path in project.iterdir()}
    except OSError:
        return None
    return next((name for name in MAKEFILES if name in present), None) or next((name for name in MAKEFILES if (project / name).is_file()), None)


def makefile_text(project):
    name = active_makefile(project)
    try:
        return (project / name).read_text(encoding="utf-8") if name else ""
    except (OSError, ValueError):
        return ""


def make_targets(text):
    """The targets a Makefile text names on rule lines. Nothing is expanded or included."""
    return {name for match in RULE.finditer(text) for name in match.group(1).split()}


def old_adapter(project):
    """Whether the Makefile still carries the build adapter of Workbench 4.3 and before, which this release cannot run."""
    return "latex-ai-build-prepare" in makefile_text(project)


def project_check_rule(project):
    """Whether the Makefile gives ``check`` anything beyond what the installer wrote: prerequisites, an inline recipe, a recipe
    other than the workbench's own, a second rule that adds any of those, or an include or eval that might define one. ``validate`` then runs
    ``make check`` rather than select documents, so that the project's own check is never skipped. When in doubt, True."""
    text = makefile_text(project)
    if ".RECIPEPREFIX" in text or re.search(r"^\s*-?s?include\s", text, re.M) or "$(eval" in text or "${eval" in text or re.search(r"^[^\s#:=]*\$[^:=#]*::?(?![:=])", text, re.M):
        return True  # a target or an include that is computed may be check
    lines = text.replace("\\\n", " ").splitlines()
    for index, line in enumerate(lines):
        match = RULE.match(line)
        if not match or "check" not in match.group(1).split():
            continue
        prerequisites, *inline = line[match.end():].split("#", 1)[0].split(";", 1)
        if match.group(1).split() != ["check"] or prerequisites.strip() or inline:
            return True
        for follow in lines[index + 1:]:
            if follow.startswith("\t"):
                if not WRAPPER.fullmatch(follow[1:].split("#", 1)[0].strip()):
                    return True
            elif follow.strip() and not follow.lstrip().startswith("#") and follow.split()[0] not in CONDITIONALS:
                break  # a conditional does not end a rule's recipe in GNU Make; anything else does
    return False


def usable_name(text, short, reserved, targets=None):
    """The Make name that reaches the workbench command, or None when this Makefile lacks it."""
    targets = make_targets(text) if targets is None else targets
    if reserved is None:
        return short if short in targets else None
    if reserved not in targets:
        return None  # a bare `short` here would not be ours
    return short if re.search(rf"^{re.escape(short)}\s*:\s*{re.escape(reserved)}\s*$", text, re.M) else reserved


def available(project, config=None):
    """Each command's usable Make name here (None when it is not available)."""
    text = makefile_text(project)
    targets = make_targets(text)
    return {command.short: None if config is not None and not enabled(command, config)
            else usable_name(text, command.short, command.reserved, targets) for command in COMMANDS}


def command_name(project, short):
    """The Make name of one command in this project, or None when its Makefile lacks it."""
    reserved = next(command.reserved for command in COMMANDS if command.short == short)
    return usable_name(makefile_text(project), short, reserved)


def enabled_modules(config):
    return [name for name in MODULES if config is not None and has_module(config, name)]


def installer(arguments):
    """An installer command for a hint. A project does not record where the package lives, so the
    path is the placeholder the documentation uses throughout."""
    return f"python3 /path/to/workbench/latex-ai-init {arguments}"


ENABLE = 'add it to "modules" in .latex-ai.json (docs/modules.md in the workbench package says how)'


def module_disabled(config, name):
    return WorkbenchError(f"Module is disabled: {name}", hint="to turn it on, " + ENABLE)


def document_targets(project, config):
    """What to type to build one document: its own Make target where the Makefile has one, else the long way."""
    text = makefile_text(project)
    documents = specifications(config)
    # A matching name alone may be cleanup, another workbench command, or a project-owned recipe.
    own = [document.name for document in documents if re.search(
        rf"^{re.escape(document.name)}:\n\t@\$\(PYTHON\) \.latex-ai/workbench\.py build --document {re.escape(document.name)}\s*$", text, re.M)]
    other = [document.name for document in documents if document.name not in own]
    build = command_name(project, "build") or "latex-ai-build"
    sentences = []
    if own:
        sentences.append(", ".join(f"make {name}" for name in own) + ": each builds that document.")
    if own or len(documents) > 1:
        sentences += [f"{name} has no target of its own: make {build} DOC={name}" for name in other]
    return sentences


def help_text(project, config, problem):
    names = available(project, config)
    enabled = enabled_modules(config)
    lines = [f"LaTeX AI Workbench {VERSION}: commands for this project" + (f" (enabled: {', '.join(enabled)})" if enabled else "")]
    if problem:
        lines += ["", f"Configuration problem: {problem[0]}",
                  f"  To fix it: {problem[1]}", "  Until then only help, status, the guide and the issue report work."]
    start = [f"make {names[short]}{extra}" for short, extra in (("status", ""), ("guide", " (a short manual)")) if names[short]]
    if start:
        lines[1:1] = ["", "Start here: " + ", then ".join(start)]
    groups = {}  # a group is listed once, where its first command is
    for command in COMMANDS:
        if names[command.short]:
            groups.setdefault(command.group, []).append(command)
    for title, commands in groups.items():
        lines += ["", title]
        for command in commands:
            short = command.short
            usage = command.usage if config or not command.usage.startswith("DOC") else ""
            line = f"make {names[short]}" + (f" {usage}" if usage else "")
            lines.append(f"  {line:<34}{command.description}")
    disabled = [name for name in MODULES if name not in enabled and config is not None]
    if disabled:
        lines += ["", "Not enabled here: " + "; ".join(f"{name} ({PURPOSE[name]})" for name in disabled),
                  "  To turn one on, " + ENABLE + "."]
    if config and has_module(config, "latex"):
        lines += ["", "Documents: " + ", ".join(document.name + (" (default)" if document.default else "") for document in specifications(config)),
                  "  make check checks all documents; build/export without DOC uses the default."]
        lines += ["  " + sentence for sentence in document_targets(project, config)]
    lines += ["", "Nothing here changes Git. Written guide: docs/quickstart.md in the workbench package (the folder the installer was run from)."]
    if names["guide"]:
        lines.append(f"A short manual for this project: make {names['guide']}")
    return "\n".join(lines)


STATE_WORDS = {"missing": "not built yet"}  # in the Documents line only: "is missing" read as a missing file; the table below keeps the state's name


def pdf_folders(config):
    """Where the builds put their PDFs: the usual folder with NAME, the one folder a single document sets, or each document's own."""
    targets = specifications(config)
    usual = ".latex-ai/artifacts/documents/{}/build"
    if all(target.view["output_dir"] == usual.format(target.name) for target in targets):
        return usual.format("NAME") + "/"
    if len(targets) == 1:
        return targets[0].view["output_dir"] + "/"
    return "; ".join(f"{target.name}: {target.view['output_dir']}/" for target in targets)


def failed_log(project, config, name):
    """Where the compiler's log of a document is, project-relative, when there is one to read."""
    for target in specifications(config):
        if target.name == name:
            stem = document_paths(project, target.view["root"], target.view["output_dir"])[2]
            log = Path(str(stem) + ".log")
            return log.relative_to(project.resolve()).as_posix() if log.is_file() and log.is_relative_to(project.resolve()) else None
    return None


def manual_text(project, config, problem, documents=None):
    """The short manual: how to work in this project, written with the command names that work in it."""
    names = available(project, config)

    def line(short, text, usage=""):
        return [f"  make {names[short]}{(' ' + usage) if usage else ''}", f"      {text}"] if names.get(short) else []
    lines = [f"LaTeX AI Workbench {VERSION}: manual for {project.name}", ""]
    if problem:
        lines += [f"Configuration problem: {problem[0]}", f"  To fix it: {problem[1]}", "  Until then only help, status, this manual and the issue report work.", ""]
    else:
        lines.append("Modules: " + (", ".join(enabled_modules(config)) or "none (core only)"))
    if documents:
        lines.append("Documents: " + "; ".join(f"{d['id']} = {d['root']}{' (default)' if d.get('default') else ''}: {STATE_WORDS.get(d['state'], d['state'])}" for d in documents))
    lines += ["", "The everyday loop",
              *line("status", "where things stand, and what to do next"),
              "  Edit your files.",
              *line("validation-plan", "which checks your change needs (nothing runs; without Git, all of them)"),
              *line("validate", "run only those checks"),
              *line("check", "the full check, before you share the work (build, references, citations and, if on, lint)")]
    if names.get("snapshot") or names.get("snapshots"):
        lines += ["", "Before a risky change (an upgrade, a large edit, an agent let loose on the files)",
                  *line("snapshot", "keep a copy of every file, uncommitted ones too, outside the project (needs Git installed; the project need not use it)", 'SNAPSHOT_NOTE="why"'),
                  *line("snapshots", "list the copies, with the commands that restore from one (write a file's path where it says FILE; that overwrites the file)")]
    if config is not None and has_module(config, "latex"):
        lines += ["", "One document (DOC=NAME; without it, the default document)",
                  *line("build", f"build the PDF (into {pdf_folders(config)})", "DOC=NAME"),
                  *line("all", "build every document, one after another; it stops at the first one that fails"),
                  *[f"  {sentence}" for sentence in document_targets(project, config)],
                  *line("document-check", "build, check and lint one document", "DOC=NAME"),
                  *line("pdf-artifact", "copy the current PDF to .latex-ai/artifacts/documents/NAME/document.pdf", "DOC=NAME"),
                  *line("lint-baseline", "accept today's ChkTeX style warnings so that only new ones fail; your decision, never for an ERROR", "DOC=NAME"),
                  "", "What a document's state means (not whether its checks passed)"] + [f"  {state:<8}{meaning}" for state, meaning in STATES.items()]
    lines += ["", "When something goes wrong",
              "  A line starting ERROR: is an ordinary failure (an undefined reference or citation is one):",
              "  read the file or tool it names, and its Hint, if it has one.",
              "  INTERNAL ERROR means a defect in the workbench, not in your work:"]
    lines += [f"      make {names['issue']} ISSUE_NOTE=\"what you saw, what you expected\"" if names.get("issue") else "      write down what you saw and what you expected",
              "      writes a local report; nothing is sent anywhere."]
    lines += ["", "Working with AI agents",
              "  They read AGENTS.md and edit your files. They ask before committing, pushing or anything that rewrites or discards work,",
              "  and never push to the default branch (main or master) or merge a pull request.",
              "  They do not edit .latex-ai/ (the workbench's own files) or switch a check off to get a green result.",
              "", "More: make " + (names["help"] or "help") + " lists every command.",
              "To update this project, follow docs/upgrading.md in a newer workbench folder (the one you installed from)."]
    differ = [(short, actual) for short, actual in names.items() if actual and actual != short]
    if differ:
        lines += ["", "Names: your Makefile keeps its own target for " + ", ".join(f"`{short}`" for short, _ in differ) +
                  "; the workbench's commands are " + ", ".join(f"`make {actual}`" for _, actual in differ) + "."]
    return "\n".join(lines)


def status_text(project, config, problem, installed, git, plan, plan_error, documents=None):
    names = available(project, config)
    lines = [f"LaTeX AI Workbench {VERSION}: status of {project.name}", ""]
    next_steps, validate_step, last_steps, waiting = [], [], [], []

    def row(label, value):
        lines.append(f"  {label:<11}{value}")

    if "record" in installed:
        row("Workbench", f"installation record .latex-ai/installation.json is {installed['record']}")
        next_steps.append("restore .latex-ai/installation.json from version control, or write it again with: " + installer("runtime . --force"))
    else:
        files, changed = installed.get("files", {}), installed.get("differing", [])
        if installed.get("version_matches"):
            row("Workbench", f"{installed['runtime_version']} installed, matches its record; {len(changed)} managed file(s) changed locally")
        else:
            row("Workbench", f"runtime {installed.get('runtime_version')} but its record says {installed.get('record_version')}; {len(changed)} managed file(s) changed locally")
            next_steps.append(installer("diff . --diff") + "   (how the project differs from this release; docs/upgrading.md says what to do)")
        for name in changed[:5]:
            lines.append(f"               {name}: {files[name]}")
        if len(changed) > 5:
            lines.append(f"               and {len(changed) - 5} more")
        if changed and installed.get("version_matches"):
            next_steps.append(installer("diff . --diff") + "   (shows what differs from the files that were installed)")
    if old_adapter(project):
        row("Makefile", "wraps its build in an adapter that this release no longer has; the build and check fail until the project is migrated")
        next_steps.insert(0, "migrate the project to the workbench's own Makefile: docs/migrating.md in the workbench package says how")
    if problem:
        row("Config", f"Configuration problem: {problem[0]}")
        next_steps.insert(0, problem[1])
    else:
        row("Modules", ", ".join(enabled_modules(config)) or "none (core only)")
    if git and git.get("branch"):
        row("Git", f"branch {git['branch']} at {git['head']}, {git['uncommitted_files']} uncommitted file(s)")
    else:
        row("Git", "not a Git repository (or no commits yet)")
    if problem:
        pass
    elif plan_error:
        row("Changes", f"could not be determined: {plan_error}")
    elif not plan["paths"] and plan["fallback"]:
        row("Changes", "cannot tell what changed without Git history to compare with")
        if names["check"]:
            last_steps.append(f"make {names['check']}   (without Git history every check applies)")
    elif not plan["paths"]:
        row("Changes", "none since the last commit")
    else:
        selected = ", ".join(key for key in CHECKED if plan[key]) or "none"
        row("Changes", f"{len(plan['paths'])} file(s); the checks they need: {selected}")
        if names["validate"]:
            validate_step.append(f"make {names['validate']}" + ("   (builds the affected documents and runs the checks these changes need)" if plan["manuscript"] else ""))
    if documents:
        # Receipt state is independent of Git: a failed build stays pending after its sources are restored.
        counts = {}
        for document in documents:
            counts[document["state"]] = counts.get(document["state"], 0) + 1
        row("Documents", ", ".join(f"{count} {state}" for state, count in counts.items()))
        selected = set(plan["documents"]) if plan and not plan_error and validate_step else set()
        missing = []
        for document in documents:
            state = document["state"]
            lines.append(f"               {document['id']}: {state} ({STATES.get(state, state)}; {document['root']}, {document['engine']})")
            lines += [f"                 {reason}" for reason in document.get("reasons", ())]
            if state == "failed":
                log = failed_log(project, config, document["id"])
                if log:
                    lines.append(f"                 read its log: {log}")
            if state == "running" and document.get("ownership"):
                ownership = document["ownership"]
                lines.append(f"                 owner PID {ownership['owner_pid']} ({'alive' if ownership['owner_alive'] else 'ended'}); "
                             f"live compiler groups: {', '.join(map(str, ownership['compiler_groups'])) or 'none'}")
                waiting.append("wait for this build, or inspect its processes as described in docs/troubleshooting.md in the workbench package")
            if state == "missing":
                missing.append(document["id"])
            elif state in {"failed", "stale"} and document["id"] not in selected:
                command = names.get("document-check")
                step = f"make {command} DOC={document['id']}" if command else f"make {names['check']}" if names["check"] else None
                if step:
                    validate_step.append(step + f"   ({STATES[state]})")
        check = f"make {names['check']}" if names["check"] else None
        if missing and check and not any(step.split("   ")[0] == check for step in last_steps):
            last_steps.append(f"{check}   (no build yet: {', '.join(missing)})")
    lines.append("")
    builds = validate_step + last_steps
    if waiting:  # a second build is refused while one runs, so the wait comes first and the rest follows it
        builds = [step + "   (after the running build ends)" for step in builds]
    next_steps = waiting + next_steps + builds
    if next_steps:
        lines.append("Next:")
        lines += [f"  {step}" for step in dict.fromkeys(next_steps)]
    elif plan_error:
        lines.append("Nothing can be suggested until the problem reported above is fixed.")
    else:
        lines.append("Nothing pending." + (f" `make {names['check']}` runs the full check." if names["check"] else ""))
    return "\n".join(lines)
