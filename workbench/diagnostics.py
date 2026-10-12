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

from core import VERSION, git_output, has_module, local_path

REPORTS = ".latex-ai/artifacts/issues"
KEEP = 20
TOOLS = ("make", "git", "latexmk", "pdflatex", "lualatex", "xelatex", "chktex", "bibtex", "biber", "pandoc")


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
# Whole files the project is expected to add to: what it writes above or below the installed text is its own
# and is kept on upgrade. Runtime, guardrail and workflow files are not in this set.
EXTENDABLE = frozenset({"AGENTS.md", "CLAUDE.md", ".gitignore", "Makefile", "makefile", "GNUmakefile"})


MANIFEST_SCHEMA = 2  # 2: files installed whole are recorded by digest; 1 (still read) kept their full text twice


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def managed_text(record):
    """The text the installer wrote, where the record keeps it: merged and extendable files only."""
    return record.get("upstream", record.get("installed"))


def is_installed(record, text):
    """Whether a file still holds exactly what the installer wrote."""
    if "installed_sha256" in record:
        return sha256_text(text) == record["installed_sha256"]
    return text == record.get("installed")


def file_record(name, strategy, installed, upstream):
    """A manifest record that keeps text only where a later merge needs it: a managed block and merged settings
    need the previous text for three-way merging, an extendable file the installed text to find within the project's.
    A file installed whole is compared, never merged, so its digest is enough; a seeded file belongs to the project."""
    if strategy == "seed":
        return {"strategy": "seed"}
    if strategy == "full":
        record = {"strategy": "full", "installed_sha256": sha256_text(installed)}
        if name in EXTENDABLE:
            record["upstream"] = upstream
        return record
    return {"strategy": strategy, "installed": installed, "upstream": upstream}


def current_record(name, record):
    """A record of either manifest schema in the form the current one writes."""
    if record.get("strategy") == "full" and "installed_sha256" not in record and isinstance(record.get("installed"), str):
        return file_record(name, "full", record["installed"], managed_text(record))
    return file_record(name, "seed", None, None) if record.get("strategy") == "seed" else record


def extends(name, record, current):
    """True when an extendable file still holds the text the installer wrote, intact and exactly once."""
    managed = managed_text(record)
    return name in EXTENDABLE and isinstance(managed, str) and bool(managed) and current.count(managed) == 1


def installation(project):
    """Installed files against the manifest baselines: modified or missing files explain upgrade conflicts.

    Only a whole file the installer owns can differ. A managed block sits inside a file the project owns,
    editor settings are merged with the project's own, and seeded notes and manifests belong to the
    project once created (it may edit or delete them), so none of those is compared. A Makefile, policy or
    ignore file installed whole may be added to around the installed text.
    """
    try:
        manifest = json.loads((project / ".latex-ai/installation.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return {"manifest": f"unreadable: {error}"}
    records = manifest.get("files") if isinstance(manifest, dict) else None
    if (not isinstance(records, dict) or not isinstance(manifest.get("version"), (str, type(None)))
            or any(not isinstance(record, dict) or not isinstance(record.get("strategy"), str) for record in records.values())):
        return {"manifest": "unreadable: not an installation record (version, and a \"files\" object of file records, are expected)"}
    files = {}
    for name, record in records.items():
        path = project / name
        strategy = record["strategy"]
        if strategy == "seed":
            files[name] = "project-owned" if path.is_file() else "project-owned (deleted)"
        elif not path.is_file():
            files[name] = "missing"
        elif strategy == "block":
            files[name] = "managed block"
        elif strategy == "json":
            files[name] = "merged settings"
        else:
            try:
                current = path.read_text(encoding="utf-8")
                files[name] = "unmodified" if is_installed(record, current) else "extended by the project" if extends(name, record, current) else "modified locally"
            except (OSError, ValueError):
                files[name] = "unreadable"
    return {"manifest_version": manifest.get("version"), "runtime_version": VERSION,
            "version_matches": manifest.get("version") == VERSION, "files": files,
            "differing": sorted(name for name, state in files.items() if state in DIFFERING)}


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


def runs(project, config):
    if config is None or not has_module(config, "provenance") or not (has_module(config, "numerics") or has_module(config, "figures")):
        return None
    try:
        import research
        records = research.load_records(project, config)
        summary = {}
        for module in ("numerics", "figures"):
            for name in research.tasks(project, config, module):
                latest = research.latest_record(records, module, name)
                summary[f"{module}/{name}"] = None if latest is None else {key: latest.get(key) for key in ("status", "started", "error", "warnings", "unchanged_outputs")}
        return summary
    except Exception as error:
        return {"unavailable": f"{type(error).__name__}: {error}"}


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
              "plan": plan, "runs": collect(runs, project, config), "git": collect(git_state, project),
              "tools": collect(tool_versions), "recent_internal_faults": collect(recent_faults, project)}
    path = directory / f"report-{report['created']}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path, report
