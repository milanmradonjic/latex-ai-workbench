#!/usr/bin/env python3
"""Project-local workbench dispatcher. Run through the project Makefile."""
import argparse
import contextlib
import io
import ast
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.parse import unquote

sys.dont_write_bytecode = True
import commands
import diagnostics
import guide
import processes
from core import CONFIG, GENERATED_TREES, VERSION, MODULES, RUNTIME_FILES, WorkbenchError, atomic_write, damaged_text, git_read_env, input_identity, operation_lock, line_buffered, local_path, run, has_module, module_config, path_name, tracked_name, effective_config, module_names, validation_actions, validation_argv, VALIDATION_ACTIONS, CAPTURE_COMMANDS, read_tex
from schema import document_settings, load_config, required_tools, resolve, specifications


# Module-gated backend calls: latex.py is installed only with the latex module, so each is imported when called.
def output_paths(*args, **kwargs):
    import latex
    return latex.output_paths(*args, **kwargs)


def source_tree(*args, **kwargs):
    import latex
    return latex.source_tree(*args, **kwargs)


def tex_without_comments(*args, **kwargs):
    import latex
    return latex.tex_without_comments(*args, **kwargs)


def bib_keys(*args, **kwargs):
    import latex
    return latex.bib_keys(*args, **kwargs)


def bibliography_check(*args, **kwargs):
    import latex
    return latex.bibliography_check(*args, **kwargs)


def lint(*args, **kwargs):
    import latex
    return latex.lint(*args, **kwargs)


def build(*args, **kwargs):
    import latex
    return latex.build(*args, **kwargs)


def verify(*args, **kwargs):
    import latex
    return latex.verify(*args, **kwargs)


def artifact(*args, **kwargs):
    import latex
    return latex.artifact(*args, **kwargs)


def bibliography_checks(project, config, document=None):
    """Readiness of the shared bibliography and of each document's own declared files (or one document's)."""
    config = effective_config(config)
    if not has_module(config, "latex"):
        checked = bibliography_check(project, document_settings(config))
        return [{"document": None, "files": sorted(path.relative_to(project).as_posix() for path in checked)}]
    rows = []
    for target in ([resolve(config, document)] if document else specifications(config)):
        checked = bibliography_check(project, target.view)
        rows.append({"document": target.name, "files": sorted(path.relative_to(project).as_posix() for path in checked)})
    return rows


def document_checks(project, config, names=None):
    targets = [resolve(config, name) for name in names] if names is not None else specifications(config)
    rows, failures, hints = [], [], []
    for target in targets:
        print(f"Document {target.name}: {target.view['root']}")
        try:
            build(project, target.view)
            verify(project, target.view)
            lint(project, target.view)
        except EXPECTED as error:
            failures.append(f"{target.name}: {describe(error)}")
            rows.append({"id": target.name, "status": "failed", "error": describe(error)})
            print(f"Document {target.name} failed: {describe(error)}", file=sys.stderr)
            if getattr(error, "hint", None):
                hints.append((f"{target.name}: " if len(targets) > 1 else "") + error.hint)
        else:
            rows.append({"id": target.name, "status": "passed"})
    if failures:
        error = WorkbenchError("Document checks failed:\n" + "\n".join(failures), hint="; ".join(hints) or None)
        error.documents = rows
        raise error
    return rows


def full_check(project, config, documents=None):
    config = effective_config(config)
    results = []
    if has_module(config, "latex"):
        results = document_checks(project, config, documents)
    elif has_module(config, "bibliography"):
        bibliography_check(project, document_settings(config))
    # Include all ordinary files for a no-TeX full check; skip generated trees.
    if not has_module(config, "latex"):
        file_checks(project, {"paths": project_files(project), "policy": True, "full": True})
    print("Full check passed: " + (", ".join(name for name in MODULES if has_module(config, name)) or "core files and policy"))
    return results


def environment_root(path):
    """A Python virtual or conda environment, whatever it is named."""
    return (path / "pyvenv.cfg").is_file() or (path / "conda-meta").is_dir()


def project_files(project):
    """Ordinary files of a project for a full check.

    Git's view (tracked plus untracked and not ignored) honours .gitignore;
    without Git a walk is used. Both skip GENERATED_TREES and environments.
    """
    try:
        names = sorted(set(git_names(project, "ls-files", "-z") + git_names(project, "ls-files", "--others", "--exclude-standard", "-z")))
    except (OSError, WorkbenchError):
        names = None
    if names is not None:
        environments = {}

        def inside_environment(parts):
            # Look on disk, not in Git's listing: an ignored pyvenv.cfg never appears there.
            # Ancestors only (never the project root itself), each directory checked once.
            for end in range(1, len(parts)):
                if environments.setdefault(parts[:end], environment_root(project.joinpath(*parts[:end]))):
                    return True
            return False
        return [name for name in names
                if not set(PurePosixPath(name).parts[:-1]) & GENERATED_TREES
                and not inside_environment(PurePosixPath(name).parts)
                and not (project / name).is_symlink()]
    names = []
    for directory, folders, files in os.walk(project, followlinks=False):
        here = Path(directory)
        folders[:] = [n for n in folders if n not in GENERATED_TREES and not (here / n).is_symlink()
                      and not environment_root(here / n)]
        names.extend((here / n).relative_to(project).as_posix() for n in files if not (here / n).is_symlink())
    return names


def require(config, module):
    if not has_module(config, module):
        raise guide.module_disabled(config, module)

def git_names(project, *args, env=None):
    """NUL-separated names from a read-only Git query."""
    result = subprocess.run(["git", "-C", str(project), *args], capture_output=True, env=env or git_read_env())
    if result.returncode:
        raise WorkbenchError(result.stderr.decode(errors="replace").strip())
    return [os.fsdecode(name) for name in result.stdout.split(b"\0") if name]


def git_diff_names(project, *args):
    """``git diff --name-only`` against a throwaway copy of the index.

    ``git diff`` rewrites .git/index when file stat data is stale and, unlike
    ``git status``, ignores GIT_OPTIONAL_LOCKS. In the copy it can refresh freely,
    so the repository's own index is never touched.
    """
    located = subprocess.run(["git", "-C", str(project), "rev-parse", "--git-path", "index"], capture_output=True, env=git_read_env())
    if located.returncode:
        raise WorkbenchError(located.stderr.decode(errors="replace").strip())
    source = Path(os.fsdecode(located.stdout).strip())
    with tempfile.TemporaryDirectory(prefix="latex-ai-index-") as scratch:
        copy = Path(scratch) / "index"
        try:
            shutil.copyfile(source if source.is_absolute() else Path(project) / source, copy)
        except (OSError, ValueError) as error:
            raise WorkbenchError(f"Cannot read the Git index: {error}")
        return git_names(project, "diff", *args, env={**git_read_env(), "GIT_INDEX_FILE": str(copy)})


def changed_files(project, base=None):
    """Read Git only. Include staged, unstaged, untracked and deleted paths."""
    def git(*args):
        return git_names(project, *args)

    try:
        if base is not None and (not base or base.startswith("-") or re.fullmatch(r"0+", base)):
            raise WorkbenchError("No usable comparison revision")
        names = git_diff_names(project, "--relative", "--name-only", "--no-renames", "-z", base or "HEAD", "--")
        names += git("ls-files", "--others", "--exclude-standard", "-z")
        return sorted(set(names)), None
    except (OSError, WorkbenchError) as error:
        # Missing history must not silently turn a build change into docs-only.
        try:
            names = git("ls-files", "-z") + git("ls-files", "--others", "--exclude-standard", "-z")
        except (OSError, WorkbenchError):
            names = []
        return sorted(set(names)), f"Change discovery unavailable; full validation selected: {why_no_changes(error, base)}"


def why_no_changes(error, base):
    """The reason changes could not be listed, in the user's terms where the cause is a familiar one."""
    text = str(error)
    if isinstance(error, FileNotFoundError):
        return "Git is not installed (selecting checks by changed files needs it)"
    if "not a git repository" in text.lower():
        return "this folder is not a Git repository (selecting checks by changed files needs one, with at least one commit)"
    if base is None and ("HEAD" in text or ("Cannot read the Git index" in text and "No such file" in text)):
        return "this Git repository has no commit to compare with yet"
    return text


def manuscript_dependencies(project, config):
    if not has_module(config, "latex"):
        return set()
    import latex
    return latex.manuscript_dependencies(project, document_settings(config))


def package_dir(project, config):
    """Directory of the workbench distribution this project hosts, or None.

    ``validation.package`` names it (null turns package routing off). Without that setting
    ``workbench`` counts only when it carries the distribution's own entry point, so an
    unrelated directory of that name with a Makefile is not mistaken for it.
    """
    validation = config.get("validation", {})
    if "package" in validation:
        name = validation["package"]
        return PurePosixPath(name).as_posix() if name and (project / name / "Makefile").is_file() else None
    return "workbench" if (project / "workbench/Makefile").is_file() and (project / "workbench/latex-ai-init").is_file() else None


# What the planner routes by suffix. A suffix is named once: the data formats are in the manuscript table (a CSV may feed a
# figure) and, being text, in what the file checks read; none is in the table of ordinary documents.
DATA_SUFFIXES = frozenset({".csv", ".tsv"})
MANUSCRIPT_SUFFIXES = frozenset({".tex", ".bib", ".sty", ".cls", ".bst", ".bbx", ".cbx", ".lbx", ".tikz", ".png", ".jpg", ".jpeg",
                                 ".pdf", ".svg", ".eps", ".ps", ".webp", ".tif", ".tiff"}) | DATA_SUFFIXES
DOCUMENT_SUFFIXES = frozenset({".md", ".markdown", ".txt", ".rst", ".adoc", ".json", ".yaml", ".yml", ".toml", ".py"})
CHECKED_SUFFIXES = DOCUMENT_SUFFIXES | DATA_SUFFIXES | {".rules", ".tex", ".bib"}


def matches(name, patterns):
    """Whether a project-relative name matches any of the declared globs (``./docs/*`` and ``docs/*`` are the same)."""
    return any(fnmatch.fnmatchcase(name, Path(pattern).as_posix()) for pattern in patterns)


def validation_plan(project, config, paths=None, base=None):
    config = effective_config(config)
    validation = config.get("validation", {})
    fallback = None
    if paths is None:
        paths, fallback = changed_files(project, base)
    paths = sorted({tracked_name(project, name) for name in paths})
    dependencies = manuscript_dependencies(project, config)
    from_documents = {}
    if has_module(config, "latex"):
        from documents import dependency_index
        from_documents = dependency_index(project, config, paths)
        dependencies = set().union(*from_documents.values())
    dependency_ids = {input_identity(project, name) for name in dependencies}
    directory = package_dir(project, config)
    package = bool(directory)
    runtime_files = {f"{directory}/{name}" for name in RUNTIME_FILES} if package else set()
    templates, skills = (f"{directory}/templates/", f"{directory}/skills/") if package else ("\0", "\0")
    plan = {"paths": paths, "files": bool(paths), "policy": False, "package": directory,
            "unit": False, "portability": False, "manuscript": False,
            "fallback": fallback, "reasons": {}, "bibliography": False}
    for name in paths:
        suffix = Path(name).suffix.lower()
        control = (Path(name).name in {"Makefile", "makefile", "GNUmakefile", "latexmkrc", ".latexmkrc", ".chktexrc", ".chktex-baseline.json"}
                   or name == CONFIG or name.startswith((".latex-ai/", ".vscode/", templates))
                   or name in runtime_files)
        policy = (Path(name).name in {"AGENTS.md", "CLAUDE.md", "SKILL.md"}
                  or name.startswith((".claude/", ".codex/", skills)))
        declared = input_identity(project, name) in dependency_ids or matches(name, validation.get("manuscript_inputs", []))
        ignored = matches(name, validation.get("ignore", []))  # but never what the build reads or the owner declared: those come first
        if control:
            plan.update(manuscript=has_module(config, "latex"), unit=package, portability=package and has_module(config, "latex"), policy=True, bibliography=has_module(config, "bibliography"))
            reason = "build/configuration: full validation"
        elif declared or (not ignored and suffix in MANUSCRIPT_SUFFIXES):
            plan["manuscript"] = has_module(config, "latex")
            reason = "manuscript input or potential figure"
        elif policy:
            plan["policy"] = True
            reason = "agent policy: file/structure checks and semantic review"
        elif ignored:
            reason = "ignored by validation.ignore: file checks only"
        elif package and name.startswith(directory + "/") and suffix == ".py":
            plan["unit"] = package
            plan["portability"] |= has_module(config, "latex") and name == f"{directory}/tests/portability.py"
            reason = "workbench Python: regression tests"
        elif suffix in DOCUMENT_SUFFIXES or Path(name).name in {".gitignore", "LICENSE"}:
            reason = "ordinary documentation/data/code: file checks; use task-specific tests when relevant"
        else:
            plan["manuscript"] = has_module(config, "latex")
            reason = "unclassified input: conservative manuscript validation"
        plan["reasons"][name] = reason
    if has_module(config, "bibliography") or has_module(config, "latex"):
        bib = module_config(config, "bibliography") if has_module(config, "bibliography") else {}
        names = set(bib.get("files", []))
        if bib.get("export"):
            names.add(bib["export"]["path"])
        if has_module(config, "latex"):
            for target in specifications(config):  # a document's own declared bibliography files
                names.update(target.view.get("bibliography", {}).get("files", []))
        if {path_name(project, name) for name in names} & set(paths):
            plan["bibliography"] = True
    if fallback:
        plan.update(manuscript=has_module(config, "latex"), unit=package, portability=package and has_module(config, "latex"), policy=True, bibliography=has_module(config, "bibliography"))
    selected_documents = set()
    document_reasons = {}
    if has_module(config, "latex"):
        # A document whose last build failed stays selected until it builds, even when its
        # sources are back to the committed text and nothing appears changed.
        from documents import failed
        for name in failed(project, config):
            plan["manuscript"] = True
            selected_documents.add(name)
            document_reasons.setdefault(name, []).append("its last build failed or was interrupted")
    if plan["manuscript"]:
        identities = {name: {input_identity(project, value) for value in inputs} for name, inputs in from_documents.items()}
        for path in paths:
            if plan["reasons"][path] == "manuscript input or potential figure":
                affected = {name for name, inputs in identities.items() if input_identity(project, path) in inputs}
                if not affected:
                    affected = set(from_documents)
                selected_documents.update(affected)
                for name in affected:
                    document_reasons.setdefault(name, []).append(path)
        if fallback or any(reason in {"build/configuration: full validation", "unclassified input: conservative manuscript validation"} for reason in plan["reasons"].values()):
            selected_documents = set(from_documents)
            for name in selected_documents:
                document_reasons.setdefault(name, []).append("shared policy or uncertain inputs: full document coverage")
    plan["documents"] = sorted(selected_documents)
    plan["document_reasons"] = document_reasons
    plan["project_check"] = bool(plan["manuscript"] and guide.project_check_rule(project))
    plan["actions"] = validation_actions(plan)
    return plan


def broken_markdown_link(project, path, text):
    """The first local link of a Markdown file whose target is missing, as it is written (anchors and queries removed), or None.

    Links in code fences, to a URL or another scheme, absolute, or to an anchor of the same file are not local; one that leaves
    the project is not checked."""
    prose = re.sub(r"(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$", "", text)
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", prose):
        target = target.strip()
        target = target[1:target.find(">")] if target.startswith("<") else target.split()[0] if target else ""
        if not target or re.match(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|/|#)", target):
            continue
        target = unquote(target.split("#", 1)[0].split("?", 1)[0])
        linked = (path.parent / target).resolve()
        if linked.is_relative_to(project) and not linked.exists():
            return target
    return None


def file_checks(project, plan):
    for name in plan["paths"]:
        try:
            path = local_path(project, name)
        except WorkbenchError:
            continue  # a link that leaves the project: the plan tracks its content, but it is not project text
        extension = path.suffix.lower()
        if not path.is_file() or extension not in CHECKED_SUFFIXES:
            continue  # Deleted files still participate in routing.
        try:
            text = read_tex(path) if extension == ".tex" else path.read_text(encoding="utf-8-sig")  # TeX may declare an 8-bit encoding
        except ValueError as error:
            raise WorkbenchError(f"{name} is not UTF-8 text: {error}")
        if damaged_text(text):
            raise WorkbenchError(f"NUL or merge conflict marker in {name}")
        if extension == ".json":
            try:
                json.loads(text)
            except ValueError as error:
                raise WorkbenchError(f"{name} is not valid JSON: {error}")
        if extension in {".py", ".rules"}:
            ast.parse(text, filename=name)
        if extension in {".md", ".markdown"}:
            broken = broken_markdown_link(project, path, text)
            if broken is not None:
                raise WorkbenchError(f"Broken local Markdown link in {name}: {broken}")
    if plan["policy"]:
        for name in ("AGENTS.md", "CLAUDE.md"):
            if not local_path(project, name).is_file():
                raise WorkbenchError(f"Missing canonical policy/delegation file: {name}")
        if "AGENTS.md" not in (project / "CLAUDE.md").read_text():
            raise WorkbenchError("CLAUDE.md must delegate to AGENTS.md")
        print("Policy structure checked" + ("" if plan.get("full") else "; review policy/permission semantics in the diff"))
    print(("File checks passed for every project file" if plan.get("full") else "Changed-file checks passed") + " (JSON/Python syntax, text conflicts, local Markdown links)")


def validate_changes(project, plan, files_only=False):
    file_checks(project, plan)
    if files_only:
        return
    if os.environ.get("LATEX_AI_VALIDATE_ACTIVE") == str(project):
        raise WorkbenchError("Recursive validation: make check must not depend on make validate")
    env = {**os.environ, "LATEX_AI_VALIDATE_ACTIVE": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
    for action in validation_actions(plan):
        if action == "bibliography":
            bibliography_checks(project, load_config(project))
        elif action == "full" and has_module(load_config(project), "latex"):
            if plan.get("project_check"):
                # The project's own check rule may run anything; selecting documents would skip it.
                print("NOTE: this project's Makefile has its own check rule; running make check so that it is not skipped")
                run(validation_argv("full", plan["package"] or "workbench"), project, env)
                continue
            results, failures = [], []
            for name in plan.get("documents", []):
                try:
                    run(["make", "latex-ai-document-check", "DOC=" + name], project, env)
                except EXPECTED as error:
                    failures.append(f"{name}: {describe(error)}")
                    results.append({"id": name, "status": "failed", "error": describe(error)})
                else:
                    results.append({"id": name, "status": "passed"})
            if failures:
                error = WorkbenchError("Selected document checks failed:\n" + "\n".join(failures))
                error.documents = results
                raise error
        else:
            run(validation_argv(action, plan["package"] or "workbench"), project, env)
    if "full" not in validation_actions(plan):
        print("No manuscript build selected")


# Problems with the project's files, tools or input: reported as ERROR, exit status 1.
EXPECTED = (WorkbenchError, OSError, ValueError, SyntaxError)
INTERNAL_FAULT = 70  # EX_SOFTWARE: anything else is a defect in the workbench itself


def internal_fault(project, error):
    path = None
    try:
        path = diagnostics.record_fault(project, error, sys.argv[1:])
    except Exception:
        pass  # capturing evidence must never hide the fault
    print(f"INTERNAL ERROR: {type(error).__name__}: {error}", file=sys.stderr)
    print("This looks like a defect in the workbench, not a problem with your files or your work.", file=sys.stderr)
    print("Do not edit .latex-ai/ or work around the check. Capture a local report with `make latex-ai-issue`", file=sys.stderr)
    print("(or `python3 .latex-ai/workbench.py issue --note '...'`); nothing is sent anywhere.", file=sys.stderr)
    if path:
        print(f"Traceback kept at {path}", file=sys.stderr)
    return INTERNAL_FAULT


def issue(project, args):
    """Write a local report about a suspected workbench defect; works even when the configuration is broken."""
    config, config_error, plan = None, None, None
    try:
        config = load_config(project)
    except Exception as error:  # not only EXPECTED: the defect being reported may be in this very code
        config_error = f"{type(error).__name__}: {error}"
    if config is not None:
        try:
            plan = validation_plan(project, config, args.files, args.base)
        except Exception as error:
            plan = {"unavailable": f"{type(error).__name__}: {error}"}
    path, report = diagnostics.write_report(project, config, config_error, plan, args.note, args.failed_command)
    state, faults = report["installation"], report["recent_internal_faults"]
    modified = state.get("differing", [])
    print(f"Issue report written to {path.relative_to(project)}")
    print(f"Workbench {report['workbench_version']}; record {state.get('record_version')}; "
          f"{len(faults) if isinstance(faults, list) else 'unknown'} recent internal fault(s); files differing from the record: {', '.join(modified) or 'none'}")
    print("Local file; nothing is sent anywhere. Review it, then share it with whoever maintains the workbench.")
    return 0


def describe(error):
    return str(error) if isinstance(error, WorkbenchError) else f"{type(error).__name__}: {error}"


def missing_config(project):
    return WorkbenchError(f"No {CONFIG} in {project}: no workbench installed here",
                          hint="run it from the project root (the folder with .latex-ai.json), or install with: " + guide.installer("init ."))


def orientation_config(project):
    """(configuration, problem) for the read-only commands that must keep working when the configuration is
    broken or missing. The problem is (what is wrong, what to do about it)."""
    if not (project / CONFIG).is_file():
        error = missing_config(project)
        return None, (str(error), error.hint)
    try:
        return load_config(project), None
    except EXPECTED as error:
        return None, (describe(error), f"fix {CONFIG} (version control has the last good copy), or get a diagnosis with: " + guide.installer("diff ."))


def explain(project, args):
    """guide: the short manual, with this project's own documents and command names in it."""
    config, problem = orientation_config(project)
    rows = None
    if config is not None and has_module(config, "latex"):
        from documents import report
        try:
            rows = report(project, config)
        except EXPECTED:
            pass  # status reports a configuration that cannot be read; the guide still explains
    print(guide.manual_text(project, config, problem, rows))
    return 0


def orient(project, args):
    """help and status: read-only orientation that keeps working when the configuration is broken or missing."""
    config, problem = orientation_config(project)
    if args.action == "help":
        print(guide.help_text(project, config, problem))
        return 0
    plan = plan_error = None
    if config is not None:
        try:
            plan = validation_plan(project, config, args.files, args.base)
        except EXPECTED as error:
            plan_error = describe(error)
    installed, git = diagnostics.installation(project), diagnostics.git_state(project)
    args.result = {"configuration": effective_config(config) if config else None, "configuration_error": problem,
                   "installation": installed, "git": git, "validation_plan": plan, "plan_error": plan_error}
    rows = None
    if config is not None and has_module(config, "latex"):
        from documents import report
        try:
            rows = args.result["documents"] = report(project, config)
        except EXPECTED as error:
            plan_error = plan_error or describe(error)
    print(guide.status_text(project, config, problem, installed, git, plan, plan_error, rows))
    return 0


ACTIONS = commands.NAMES  # every action, from the registry


def main():
    if sys.argv[1:2] and sys.argv[1] in commands.REMOVED_ACTIONS:
        print(f"ERROR: {sys.argv[1]} belongs to the build adapter that Workbench 4.4 no longer has: this project's Makefile still calls it", file=sys.stderr)
        print("Hint: migrate the project to the workbench's own Makefile; docs/migrating.md in the workbench package says how", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("--document", help="Named LaTeX document; omitted uses the default for document operations")
    parser.add_argument("--note", default="", help="issue: what you observed and what you expected")
    parser.add_argument("--command", dest="failed_command", default="", help="issue: the command that misbehaved")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project root (default: current directory); an installed runtime belongs to its own project")
    parser.add_argument("--base", default=os.environ.get("LATEX_AI_BASE"), help="Git revision to compare; default HEAD plus local/untracked changes")
    parser.add_argument("--files", nargs="*", help="Explicit changed paths, including deleted paths")
    parser.add_argument("--json", action="store_true", help="Print structured results; plan/modules retain their native JSON formats")
    parser.add_argument("--files-only", action="store_true", help="Run lightweight file/policy checks only (a hook or a hosted job can run the rest separately)")
    args = parser.parse_args()
    project = args.project.resolve()
    line_buffered()
    if os.name == "posix":
        # Terminating the runtime unwinds normally: a running compiler group is stopped and the
        # build's receipt is marked failed, instead of both being abandoned.
        def interrupted(number, frame):
            raise processes.Interrupted(number)
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
    try:
        if args.json and not commands.BY_NAME[args.action].native_json:
            return structured_command(project, args)
        return dispatch(project, args)
    except processes.Interrupted as error:
        print(f"ERROR: {args.action} interrupted by {signal.Signals(error.number).name}", file=sys.stderr)
        return error.exit_status


def structured_command(project, args):
    """One JSON document per command, including child-process diagnostics."""
    stdout, stderr = io.StringIO(), io.StringIO()
    token = CAPTURE_COMMANDS.set(True)
    args.json = False
    interrupted = False
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = dispatch(project, args)
    except processes.Interrupted as error:
        status, interrupted = error.exit_status, True
        result = getattr(args, "result", None)
        args.result = {**(result if isinstance(result, dict) else {}), "signal": signal.Signals(error.number).name}
        stderr.write(f"{args.action} interrupted by {signal.Signals(error.number).name}\n")
    finally:
        CAPTURE_COMMANDS.reset(token)
    print(json.dumps({"schema_version": 1, "workbench_version": VERSION, "action": args.action,
                      "exit_status": status, "status": "interrupted" if interrupted else "success" if status == 0 else "internal-error" if status == INTERNAL_FAULT else "failed",
                      "result": getattr(args, "result", None), "stdout": stdout.getvalue(), "stderr": stderr.getvalue()}, indent=2))
    return status


# One handler per action, named by the registry (commands.py): do_<name>, with "-" written "_". A handler gets
# the project, the effective configuration (that of one document for the actions whose registry entry says
# `view`), the persisted configuration and the parsed arguments, and returns an exit status or None for success.
def do_issue(project, config, persisted, args):
    return issue(project, args)


def do_help(project, config, persisted, args):
    return orient(project, args)


do_status = do_help


def do_guide(project, config, persisted, args):
    return explain(project, args)



def selected_checks(project, config, args):
    """The checks the changed files select, reported as the plan; validate goes on to run them."""
    plan = validation_plan(project, config, args.files, args.base)
    args.result = plan
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        selected = ", ".join(key for key in ("files", "policy", "unit", "portability", "manuscript", "bibliography") if plan[key])
        print("Selected checks: " + (selected or "none (no changes; use make check for a full manuscript check)"))
        for name, reason in plan["reasons"].items():
            print(f"  {name}: {reason}")
        if plan["documents"]:
            print("Documents: " + ", ".join(plan["documents"]))
            for name in plan["documents"]:
                reasons = plan["document_reasons"].get(name, [])
                print(f"  {name}: " + "; ".join(reasons[:3]) + (f"; and {len(reasons) - 3} more" if len(reasons) > 3 else ""))
        if plan["fallback"]:
            print("NOTE: " + plan["fallback"])
        if os.environ.get("DOC"):
            print(f"NOTE: DOC={os.environ['DOC']} is ignored here: documents are selected from the changed files. "
                  f"To check one document use make {guide.command_name(project, 'document-check') or 'latex-ai-document-check'} DOC={os.environ['DOC']}")
    return plan


def do_plan(project, config, persisted, args):
    selected_checks(project, config, args)


def do_validate(project, config, persisted, args):
    validate_changes(project, selected_checks(project, config, args), args.files_only)


def do_modules(project, config, persisted, args):
    report = {name: {"enabled": has_module(config, name), "requires": spec["requires"], "configuration": module_config(config, name) if has_module(config, name) else None} for name, spec in MODULES.items()}
    print(json.dumps(report, indent=2))


def do_documents(project, config, persisted, args):
    from documents import report
    args.result = report(project, config)
    print(json.dumps(args.result, indent=2))


def do_document_check(project, config, persisted, args):
    target = resolve(config, args.document)
    args.result = {"document": target.name}  # what a failure before the checks finish reports
    args.result = {"documents": document_checks(project, config, [target.name])}


def do_check(project, config, persisted, args):
    checked = full_check(project, config, [args.document] if args.document else None)
    args.result = {"modules": list(module_names(config)), "documents": checked}


def do_build(project, config, persisted, args):
    build(project, config)


def do_lint(project, config, persisted, args):
    lint(project, config)


def do_lint_baseline(project, config, persisted, args):
    import latex
    latex.write_baseline(project, config)


def do_verify(project, config, persisted, args):
    verify(project, config)


def do_bib_check(project, config, persisted, args):
    if not has_module(persisted, "latex"):
        require(persisted, "bibliography")
    rows = bibliography_checks(project, persisted, args.document or None)
    args.result = {"bibliographies": rows}
    for row in rows:
        print(f"{row['document'] or 'Shared bibliography'}: {', '.join(row['files']) or '(no files declared)'}")
    print("Bibliography structure/key checks passed; backend validation occurs during make check")


def do_artifact(project, config, persisted, args):
    artifact(project, config)


def do_clean(project, config, persisted, args):
    root, _, _ = output_paths(project, config)
    if config.get("build_command"):
        raise WorkbenchError("Use the project's existing cleanup convention for custom builds")
    command = ["latexmk", "-c", "-cd"]
    if config.get("output_dir"):
        command.append(f"-outdir={local_path(project, config['output_dir'])}")
    import latex
    with operation_lock(project, "build"):
        latex.assert_build_idle(project)
        local_path(project, latex.receipt_path(config)).unlink(missing_ok=True)
        run([*command, str(root)], project)


def do_doctor(project, config, persisted, args):
    print(f"python: {sys.executable} ({sys.version.split()[0]}, the interpreter running this check)")
    required = required_tools(config)
    missing = []
    for name in required:
        executable = str(project / name) if not Path(name).is_absolute() and "/" in name else name
        path = shutil.which(executable)
        print(f"{name}: {path or 'MISSING'}")
        if not path:
            missing.append(name)
    if not missing:
        print("All required tools found")
    if missing:
        tex = [name for name in missing if name in {"latexmk", "pdflatex", "lualatex", "xelatex", "chktex", "bibtex", "biber"}]
        others = [name for name in missing if name not in tex]
        advice = ([f"a TeX distribution (TeX Live, MacTeX, MiKTeX) provides {', '.join(tex)}"] if tex else []) + (
            [f"{', '.join(others)}: needed by this project's commands"] if others else [])
        raise WorkbenchError("Missing required tools: " + ", ".join(missing),
                             hint="; ".join(advice) + f". Install what is missing, then run make {guide.command_name(project, 'doctor') or 'doctor'} again")


HANDLERS = {action.name: globals()[action.handler] for action in commands.ACTIONS}


def dispatch(project, args):
    try:
        runtime_directory = Path(__file__).resolve().parent
        if runtime_directory.name == ".latex-ai" and runtime_directory.parent != project:
            raise WorkbenchError(f"This installed runtime belongs to {runtime_directory.parent}, but the selected project is {project}",
                                 hint=f"run from its project root, or pass --project {runtime_directory.parent}; use the selected project's own runtime for another project")
        action = commands.BY_NAME[args.action]
        if args.document and not action.document:
            raise WorkbenchError(f"--document is not supported for {args.action}; this command inspects the whole project")
        persisted = config = None
        if not action.standalone:
            if not (project / CONFIG).is_file():
                raise missing_config(project)
            persisted = load_config(project)
            module = action.module or ("latex" if args.document else None)  # --document names a LaTeX document, whatever the action
            if module:
                require(persisted, module)
            config = effective_config(persisted)
            if args.document or action.view:
                target = resolve(config, args.document)
                if action.view:
                    config = target.view
                args.result = {"document": target.name}
        status = HANDLERS[action.name](project, config, persisted, args)
        return 0 if status is None else status
    except EXPECTED as error:
        if hasattr(error, "documents"):
            args.result = {"documents": error.documents}
        print(f"ERROR: {error}", file=sys.stderr)
        if getattr(error, "hint", None):
            print(f"Hint: {error.hint}", file=sys.stderr)
        return 1
    except Exception as error:  # nothing the project's files or tools should be able to cause
        return internal_fault(project, error)


if __name__ == "__main__":
    sys.exit(main())
