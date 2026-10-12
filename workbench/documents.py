"""What the declared LaTeX documents are doing: dependency routing, build states and failed builds.

The documents themselves (specifications, resolution, validation) are in ``schema``; this module needs the LaTeX
backend and is installed with it.
"""
import fnmatch
from pathlib import Path

from schema import specifications


def dependency_index(project, config, changed=()):
    from latex import manuscript_dependencies
    result = {}
    for target in specifications(config):
        view = target.view
        names = manuscript_dependencies(project, view)
        for name in changed:
            if any(fnmatch.fnmatchcase(name, Path(pattern).as_posix()) for pattern in view.get("validation", {}).get("manuscript_inputs", [])):
                names.add(name)
        result[target.name] = names
    return result


def report(project, config):
    from latex import receipt_state, read_receipt, build_ownership, stale_reasons
    rows = []
    for target in specifications(config):
        view = target.view
        receipt = read_receipt(project, view)
        row = {"id": target.name, "root": view["root"], "engine": view["engine"],
               "default": target.default, "state": receipt_state(project, view, receipt)}
        if row["state"] == "running":
            row["ownership"] = build_ownership(receipt)
        elif row["state"] == "stale":
            row["reasons"] = stale_reasons(project, view, receipt)
        rows.append(row)
    return rows


def failed(project, config):
    """Documents whose last build failed or was interrupted: read-only, without hashing inputs."""
    from latex import read_receipt, owner_alive
    names = []
    for target in specifications(config):
        receipt = read_receipt(project, target.view)
        if receipt.get("status") == "failed" or receipt.get("status") == "running" and not owner_alive(receipt):
            names.append(target.name)
    return names
