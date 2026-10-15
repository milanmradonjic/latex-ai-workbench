"""Local defect capture: internal faults and the explicit ``issue`` report.

Nothing here contacts a network or any service. An internal fault is kept in the OS
temp directory, never in the project, so read-only commands stay read-only; the report is
written only when ``issue`` is run, under the project's ignored artifacts directory.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import traceback

from core import VERSION, WorkbenchError, git_output, local_path

REPORTS = ".latex-ai/artifacts/issues"
KEEP = 20
TOOLS = ("make", "git", "latexmk", "pdflatex", "chktex", "bibtex")


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def fault_dir(project):
    """Per user: the first user's private directory of a shared name would refuse every later user."""
    user = os.getuid() if hasattr(os, "getuid") else "user"
    return Path(tempfile.gettempdir()) / f"latex-ai-faults-{user}" / hashlib.sha256(str(project).encode()).hexdigest()[:16]


def record_fault(project, error, argv):
    """Keep an internal fault's traceback outside the project; never raises, never masks the fault."""
    try:
        directory = fault_dir(project)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        record = {"created": stamp(), "workbench_version": VERSION, "arguments": list(argv),
                  "error_type": type(error).__name__, "message": str(error),
                  "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
                  "python": sys.version.split()[0], "platform": platform.platform()}
        path = directory / f"fault-{record['created']}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
        for old in sorted(directory.glob("fault-*.json"))[:-KEEP]:
            old.unlink()
        return path
    except Exception:
        return None


def recent_faults(project, limit=5):
    found = []
    try:
        for path in sorted(fault_dir(project).glob("fault-*.json"))[-limit:]:
            found.append(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return found


DIFFERING = ("modified locally", "missing", "unreadable")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_state(project):
    """(record, None) of the record init and runtime leave (.latex-ai/installation.json), or (None, why not)."""
    try:
        record = json.loads((project / ".latex-ai/installation.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return None, f"unreadable: {error}"
    if (not isinstance(record, dict) or not isinstance(record.get("files"), dict)
            or not isinstance(record.get("version"), (str, type(None)))
            or any(not isinstance(entry, (str, dict)) for entry in record["files"].values())):
        return None, "unreadable: not an installation record (a version, and a \"files\" object, are expected)"
    return record, None


def recorded_digests(project):
    """{runtime file: sha256 of what the workbench wrote}, or None. Records of earlier releases are read too."""
    record, _ = read_state(project)
    if record is None:
        return None
    digests = {}
    for name, entry in record["files"].items():
        digest = entry if isinstance(entry, str) else entry.get("installed_sha256") if isinstance(entry, dict) else None
        if isinstance(digest, str) and name.startswith(".latex-ai/"):
            digests[name] = digest
    return digests


def installation(project):
    """The runtime files against the digests recorded when they were written: an edited or missing one explains odd behaviour.

    Only the workbench's own runtime files are compared; policy, Makefile and editor files are the project's.
    """
    record, problem = read_state(project)
    if record is None:
        return {"record": problem}
    files = {}
    for name, digest in (recorded_digests(project) or {}).items():
        path = project / name
        if not path.is_file():
            files[name] = "missing"
            continue
        try:
            files[name] = "unmodified" if sha256_text(path.read_text(encoding="utf-8")) == digest else "modified locally"
        except (OSError, ValueError):
            files[name] = "unreadable"
    return {"record_version": record.get("version"), "runtime_version": VERSION,
            "version_matches": record.get("version") == VERSION, "files": files,
            "differing": sorted(name for name, state in files.items() if state in DIFFERING)}


def version_report(project):
    """The project's version stamp as `make doctor` prints it: what the installation record says, what the vendored runtime is, and which runtime files were edited or are missing."""
    state = installation(project)
    if "record" in state:
        return [f"stamp: .latex-ai/installation.json is {state['record']}"]
    differing = state["differing"]
    return [f"stamp: .latex-ai/installation.json records {state['record_version']}; the vendored runtime is {state['runtime_version']}" + ("" if state["version_matches"] else " (they differ)"),
            "runtime files: " + (f"all {len(state['files'])} unmodified" if not differing else ", ".join(f"{name} ({state['files'][name]})" for name in differing))]


def template_report(project, template):
    """The template's side: what the installer of the release in that folder says of this project, by its own read-only `diff`, so that there is one rule for what differs."""
    folder = Path(template).expanduser().resolve()
    installer = folder / "latex-ai-init"
    if not (installer.is_file() and (folder / "core.py").is_file()):
        raise WorkbenchError(f"{folder} is not a workbench folder: it has no latex-ai-init and core.py",
                             hint="give the folder that holds latex-ai-init, the templates and the runtime together, the one the installer is run from")
    try:
        done = subprocess.run([sys.executable, str(installer), "diff", str(project)], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as error:
        raise WorkbenchError(f"The installer in {folder} could not be run: {error}") from error
    if done.returncode not in (0, 1):  # 1 means that a runtime file differs, which is a report; the installer's refusals are 2
        raise WorkbenchError("That release's installer stopped: " + (done.stderr.strip() or done.stdout.strip() or f"exit status {done.returncode}"),
                             hint="it names the setting or file it stopped at; docs/upgrading.md in that folder says what to do")
    return [f"template: {folder}", *("  " + line for line in done.stdout.splitlines())]


def tool_versions():
    found = {"python": f"{sys.executable} ({platform.python_version()})", "platform": platform.platform()}
    for tool in TOOLS:
        path = shutil.which(tool)
        if not path:
            found[tool] = "not found"
            continue
        try:
            done = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
            line = next((l.strip() for l in (done.stdout + done.stderr).splitlines() if l.strip()), "no output")
            found[tool] = f"{path}: {line}"
        except (OSError, subprocess.SubprocessError):
            found[tool] = f"{path}: version unavailable"
    return found


def git_state(project):
    def query(*args):
        return git_output(project, *args)
    try:
        status = query("status", "--porcelain", "--untracked-files=all")  # files, not folders: the same count as the changes row
        return {"branch": query("rev-parse", "--abbrev-ref", "HEAD"), "head": query("rev-parse", "--short", "HEAD"),
                "uncommitted_files": None if status is None else len(status.splitlines())}
    except (OSError, subprocess.SubprocessError):
        return None


def collect(function, *args):
    """One evidence section; a defect in it is recorded in the report instead of stopping the report."""
    try:
        return function(*args)
    except Exception as error:
        return {"unavailable": f"{type(error).__name__}: {error}"}


def write_report(project, config, config_error, plan, note="", command=""):
    """Collect evidence for a suspected workbench defect into one local file and return its path.

    The report exists to capture a defect, so no single section may be able to prevent it: each is
    collected on its own and a failure is written into the report as that section's content."""
    directory = local_path(project, REPORTS)
    directory.mkdir(parents=True, exist_ok=True)
    report = {"kind": "latex-ai-workbench issue report", "created": stamp(), "workbench_version": VERSION,
              "privacy": "Local file; nothing is sent anywhere. It holds project paths and configuration, so review it before sharing.",
              "observed_and_expected": note, "command": command,
              "installation": collect(installation, project), "configuration": config, "configuration_error": config_error,
              "plan": plan, "git": collect(git_state, project),
              "tools": collect(tool_versions), "recent_internal_faults": collect(recent_faults, project)}
    path = directory / f"report-{report['created']}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path, report
