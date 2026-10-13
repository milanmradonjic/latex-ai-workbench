"""Orientation commands: ``help`` lists what this project can do, ``status`` says where it stands.

Both are read-only: nothing is built, run, written or changed in Git. What they list comes from
the project's own Makefile and configuration, so a command that is not installed is never offered.
This module is also the one place that knows how a workbench command is named in a given Makefile.
"""
import re

from commands import COMMANDS  # the registry derives every name shown to readers
from core import MODULES, VERSION, WorkbenchError, has_module
import make_graph
from make_graph import MAKEFILES, active_makefile, makefile_text  # read the project's Makefile
from schema import STATES, specifications

# Check and lint retain the project's conventions. Build also has a reserved
# wrapper so an adopted recipe participates in the artifact validity contract.
UNLISTED = frozenset({"latex-ai-build-prepare"})  # internal transaction hook, never a user command


def enabled(command, config):
    """Whether this configuration turns the command on."""
    return not command.needs or any(has_module(config, name) for name in command.needs)


PURPOSE = {
    "latex": "build and check a LaTeX manuscript", "bibliography": "check bibliography files and keys",
}
CHECKED = ("files", "policy", "unit", "portability", "manuscript", "bibliography")


def included_texts(project, text, seen=None):
    """Texts of the makefiles this one includes by literal name, inside the project. A target defined
    there is as much the project's own as one in the file itself."""
    return make_graph.read(text, project, managed=False).sources[1:]


def project_check_rule(project):
    """Whether the project's own Makefile text (outside the workbench block, including makefiles it
    includes) gives ``check`` prerequisites or a recipe of its own, beyond the installed template's."""
    graph = make_graph.read(makefile_text(project), project)
    if graph.unresolved:
        return True  # a computed target/include may define check; do not skip it
    managed = {"latex-ai-core-check", "latex-ai-check-passed", "latex-ai-other-documents", "latex-ai-named-check"}
    wrapper = re.compile(r"^[+@-]*\s*(?:\$\(PYTHON\)|python(?:3(?:\.\d+)?)?)\s+(?:-[A-Za-z]+\s+)*\.latex-ai/workbench\.py\s+check\s*$")
    for rule in graph.rules:
        if "check" not in rule.targets:
            continue
        prerequisites = [word for word in rule.prerequisites.split() if word != "|"]
        if any(word not in managed for word in prerequisites):
            return True
        for command in rule.recipes:
            command = make_graph.partition(command, '#')[0].strip()
            if command and not wrapper.fullmatch(command):
                return True
    return False


def make_targets(text, project=None):
    """Targets a Makefile text defines; with a project, also those of the files it includes."""
    return make_graph.read(text, project, managed=False).targets


def usable_name(text, short, reserved, targets=None, project=None):
    """The Make name that reaches the workbench command, or None when this Makefile lacks it."""
    targets = make_targets(text, project) if targets is None else targets
    if reserved is None:
        return short if short in targets else None
    if reserved not in targets:
        return None  # a bare `short` here would be the project's own target, not ours
    return short if re.search(rf"^{re.escape(short)}\s*:\s*{re.escape(reserved)}\s*$", text, re.M) else reserved


def shadowed(text, project=None):
    """(short, reserved) pairs where the Makefile keeps its own target under the short name."""
    targets = make_targets(text, project)
    return [(command.short, command.reserved) for command in COMMANDS if command.reserved and command.reserved in targets
            and command.short in targets and usable_name(text, command.short, command.reserved, targets) == command.reserved]


def available(project, config=None):
    """Each command's usable Make name here (None when it is not available)."""
    text = makefile_text(project)
    targets = make_targets(text, project)
    return {command.short: None if config is not None and not enabled(command, config)
            else usable_name(text, command.short, command.reserved, targets) for command in COMMANDS}


def command_name(project, short):
    """The Make name of one command in this project, or None when its Makefile lacks it."""
    reserved = next(command.reserved for command in COMMANDS if command.short == short)
    return usable_name(makefile_text(project), short, reserved, project=project)


def enabled_modules(config):
    return [name for name in MODULES if config is not None and has_module(config, name)]


def installer(arguments):
    """An installer command for a hint. A project does not record where the package lives, so the
    path is the placeholder the documentation uses throughout."""
    return f"python3 /path/to/workbench/latex-ai-init {arguments}"


def enable_command(config, name="NAME"):
    return installer(f"configure . --enable {name}")


def module_disabled(config, name):
    return WorkbenchError(f"Module is disabled: {name}", hint="turn it on with: " + enable_command(config, name))


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
                  "  Turn one on with: " + enable_command(config)]
    if config and has_module(config, "latex"):
        lines += ["", "Documents: " + ", ".join(document.name + (" (default)" if document.default else "") for document in specifications(config)),
                  "  make check checks all documents; build/export without DOC uses the default."]
    lines += ["", "Nothing here changes Git. Written guide: docs/quickstart.md in the workbench package (the folder the installer was run from)."]
    if names["guide"]:
        lines.append(f"A short manual for this project: make {names['guide']}")
    return "\n".join(lines)


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
        lines.append("Documents: " + "; ".join(f"{d['id']}{' (default)' if d.get('default') else ''} is {d['state']}" for d in documents))
    lines += ["", "The everyday loop",
              *line("status", "where things stand, and what to do next"),
              "  Edit your files.",
              *line("validation-plan", "which checks your change needs (nothing runs)"),
              *line("validate", "run only those checks"),
              *line("check", "the full check, before you share the work")]
    if config is not None and has_module(config, "latex"):
        lines += ["", "One document (DOC=NAME; without it, the default document)",
                  *line("build", "build the PDF and record that it matches its sources", "DOC=NAME"),
                  *line("document-check", "build, verify and lint one document", "DOC=NAME"),
                  *line("pdf-artifact", "copy the verified PDF to .latex-ai/artifacts/documents/NAME/document.pdf", "DOC=NAME"),
                  *line("lint-baseline", "accept today's ChkTeX warnings; only new ones fail (the owner's decision)", "DOC=NAME"),
                  "", "What a document's state means"] + [f"  {state:<8}{meaning}" for state, meaning in STATES.items()]
    lines += ["", "When something goes wrong",
              "  A line starting ERROR: is an ordinary failure: read the file or tool it names, and its Hint.",
              "  INTERNAL ERROR means a defect in the workbench, not in your work:"]
    lines += [f"      make {names['issue']} ISSUE_NOTE=\"what you saw, what you expected\"" if names.get("issue") else "      write down what you saw and what you expected",
              "      writes a local report; nothing is sent anywhere."]
    lines += ["", "Working with AI agents",
              "  They read AGENTS.md. They ask before any Git change, never push to the default branch and never merge a pull request.",
              "  They do not edit .latex-ai/ (the workbench's own files) or switch a check off to get a green result.",
              "", "More: make " + (names["help"] or "help") + " lists every command; docs/quickstart.md in the workbench package explains installing and upgrading."]
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

    if "manifest" in installed:
        row("Workbench", f"installation record .latex-ai/installation.json is {installed['manifest']}")
        next_steps.append("restore .latex-ai/installation.json from version control, or see what is installed with: " + installer("audit ."))
    else:
        files, changed = installed.get("files", {}), installed.get("differing", [])
        if installed.get("version_matches"):
            row("Workbench", f"{installed['runtime_version']} installed, matches its manifest; {len(changed)} managed file(s) changed locally")
        else:
            row("Workbench", f"runtime {installed.get('runtime_version')} but manifest {installed.get('manifest_version')}; {len(changed)} managed file(s) changed locally")
            next_steps.append(installer("upgrade . --dry-run --diff") + "   (then without --dry-run)")
        for name in changed[:5]:
            lines.append(f"               {name}: {files[name]}")
        if len(changed) > 5:
            lines.append(f"               and {len(changed) - 5} more")
        if changed and installed.get("version_matches"):
            next_steps.append(installer("audit .") + "   (shows what differs from the files that were installed)")
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
            last_steps.append(f"{check}   (no verified build yet: {', '.join(missing)})")
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
