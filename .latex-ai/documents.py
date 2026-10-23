"""What the declared LaTeX documents are doing: build states and failed builds.

The documents themselves (specifications, resolution, validation) are in ``schema``; this module needs the LaTeX
backend and is installed with it.
"""
from schema import specifications


def report(project, config):
    from latex import receipt_state, read_receipt, build_ownership, stale_reasons
    rows = []
    for target in specifications(config):
        view = target.view
        receipt = read_receipt(project, view)
        row = {"id": target.name, "root": view["root"], "engine": view["engine"],
               "builder": "build_command" if view.get("build_command") else "latexmk",
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
