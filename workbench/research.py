"""Optional research modules: explicit commands, records and read-only checks."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import uuid

from task_graph import FORMAT, tasks, checked_tasks, task_inputs, TaskGraph

import guide
from core import VERSION, WorkbenchError, git_output, has_module, input_identity, local_path, module_config, read_json, run, path_name, path_identity, tracked_name, atomic_write, operation_lock
from schema import load_config

def encoded(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprints(project, names):
    return {name: sha(local_path(project, name).read_bytes()) if local_path(project, name).is_file() else None for name in names}


def file_identity(project, names):
    """Stat identity per path. Any write or replacement changes it, even with identical bytes.

    ctime is included because the kernel sets it on every modification and a
    command cannot preserve it (unlike mtime under ``cp -p``/``copy2``).
    """
    identity = {}
    for name in names:
        path = local_path(project, name)
        stat = path.stat() if path.is_file() else None
        identity[name] = stat and (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino)
    return identity


def definition(task):
    return sha(encoded(task).encode())


def git_state(project):
    return {"head": git_output(project, "rev-parse", "HEAD"),
            "status": git_output(project, "status", "--short", "--untracked-files=all")}


def require_module(config, name):
    if not has_module(config, name):
        raise guide.module_disabled(config, name)


class RunRecords(list):
    """Authoritative JSON records with an in-memory latest-run index."""
    def __init__(self, records=(), paths=None):
        super().__init__(records)
        self.paths = paths or {}  # invocation-local locations; never written into archived records
        self.latest = {}
        for record in self:
            key = (record.get("module"), record.get("task"))
            if key not in self.latest or record["started"] > self.latest[key]["started"]:
                self.latest[key] = record


def load_records(project, config, exclude=None):
    """Run records of the provenance archive; ``exclude`` is a record directory to skip."""
    base = local_path(project, module_config(config, "provenance")["path"])
    records, paths = [], {}
    if base.exists():
        for path in base.glob("*/record.json"):
            if not path.resolve().is_relative_to(project):
                raise WorkbenchError("Run record escapes project")
            if exclude is not None and path.parent == exclude:
                continue
            record = read_json(path, path.resolve().relative_to(project).as_posix())
            if not isinstance(record, dict) or record.get("schema_version") != 1:
                raise WorkbenchError(f"Unsupported run record: {path}")
            # Fields the freshness logic relies on; a damaged record must be reported, not crash it.
            if (not isinstance(record.get("started"), str)
                    or any(not isinstance(record.get(key), str) for key in ("module", "task"))
                    or any(not isinstance(record.get(key) or {}, dict) for key in ("inputs", "outputs"))):
                raise WorkbenchError(f"Malformed run record: {path}")
            records.append(record)
            paths[id(record)] = path.relative_to(project).as_posix()
    return RunRecords(records, paths)


def history(project, config):
    """Read-only archive index, including tasks whose modules are now disabled."""
    require_module(config, "provenance")
    records = load_records(project, config)
    return [{"started": record["started"], "module": record["module"], "task": record["task"],
             "status": record.get("status", "unknown"), "record": records.paths[id(record)]}
            for record in sorted(records, key=lambda r: (r["started"], records.paths[id(r)]), reverse=True)]


def latest_record(records, module, name):
    if isinstance(records, RunRecords):
        return records.latest.get((module, name))
    matching = [r for r in records if r.get("module") == module and r.get("task") == name]
    return max(matching, key=lambda r: r["started"]) if matching else None


def own_reasons(project, task, latest, inputs=None, outputs=None):
    """Why the latest record no longer vouches for a task; empty means current.

    One definition of "current" for freshness reports and for run: ``inputs``
    (fingerprints taken earlier) and ``outputs`` (a subset of paths) narrow the
    comparison. Upstream producers are judged separately by freshness.
    """
    if latest is None:
        return ["no recorded run"]
    if latest.get("status") != "success":
        return ["latest run did not succeed"]
    reasons = []
    if latest.get("definition_sha256") != definition(task):
        reasons.append("task configuration changed")
    if latest.get("inputs") != (fingerprints(project, task_inputs(project, task)) if inputs is None else inputs):
        reasons.append("declared input content changed or is missing")
    recorded = latest.get("outputs") or {}
    if outputs is None:
        changed = latest.get("outputs") != fingerprints(project, task["outputs"])
    else:
        changed = {path: recorded.get(path) for path in outputs} != fingerprints(project, outputs)
    if changed:
        reasons.append("output content changed or is missing")
    return reasons


def terminated(signum, frame):
    """Turn SIGTERM into a normal exit so an interrupted run still writes its record."""
    raise SystemExit(128 + signum)


def task_lock(project, module, name):
    """Serialise explicit runs of one task: a concurrent run would see the other's
    unfinished record as the latest one and wrongly reject a still-current output.

    It is the project's own operation lock (core.operation_lock), shared by every process that
    works in the project; a run that cannot take it does not start.
    """
    return operation_lock(project, f"task-{module}-{name}",
                          busy=f"Another run of {module}/{name} is in progress in this project; rerun after it finishes")


def execute(project, config, module, name, expensive=False):
    require_module(config, module)
    declared = tasks(project, config, module)
    if name not in declared:  # also keeps the name safe to use in a file name
        raise WorkbenchError(f"Unknown {module} task: {name}", hint=f"Declared {module} tasks: {', '.join(declared) or 'none'}")
    if os.environ.get("WORKBENCH_TASK_ACTIVE") == str(project):
        raise WorkbenchError("Recursive research command; task must not invoke itself through the workbench")
    with task_lock(project, module, name):
        records = load_records(project, config) if has_module(config, "provenance") else RunRecords()
        graph = TaskGraph.load(project, config, records)
        upstream = stale_upstream(project, config, module, name, graph, records)
        for producer in upstream:
            print(f"WARNING: {producer} is stale, so this {module} task is built from its old output; refresh {producer} first, then run this again")
        return run_task(project, config, module, name, expensive, upstream, graph)


def stale_upstream(project, config, module, name, graph=None, records=None):
    """Stale producers of this task's inputs. Nothing upstream is ever run implicitly, so the run proceeds;
    it is said, and recorded, that the result was built from their old outputs."""
    if not has_module(config, "freshness"):
        return []
    report = freshness(project, config, graph, records)
    reasons = next((item["reasons"] for item in report if (item["module"], item["task"]) == (module, name)), [])
    prefix = "upstream task is stale: "
    return [reason[len(prefix):] for reason in reasons if reason.startswith(prefix)]


def run_task(project, config, module, name, expensive=False, upstream=(), graph=None):
    graph = graph or TaskGraph.load(project, config)
    task = graph.definitions[(module, name)]
    names = graph.inputs[(module, name)]
    before = fingerprints(project, names)
    missing = [key for key, value in before.items() if value is None]
    if missing:
        raise WorkbenchError("Missing declared inputs: " + ", ".join(missing))
    env = {**os.environ, "WORKBENCH_TASK_ACTIVE": str(project)}
    record_dir = None
    record = {"schema_version": 1, "workbench_version": VERSION, "module": module, "task": name,
              "started": datetime.now(timezone.utc).isoformat(), "status": "running",
              "definition": task, "definition_sha256": definition(task), "inputs": before,
              "source": git_state(project), "platform": platform.platform(), "python": sys.version,
              "executables": {}, "checks": [], "outputs": {}, "stale_upstream": list(upstream)}
    if has_module(config, "provenance"):
        base = local_path(project, module_config(config, "provenance")["path"])
        record_dir = local_path(project, str((base / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex)).relative_to(project)))
        record_dir.mkdir(parents=True)
    try:
        outer = signal.signal(signal.SIGTERM, terminated)
    except ValueError:  # not the main thread: keep the caller's handling
        outer = None
    try:
        if record_dir:
            for path in names:
                destination = record_dir / "inputs" / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local_path(project, path), destination)
                if sha(destination.read_bytes()) != before[path]:
                    raise WorkbenchError("Input changed while taking provenance snapshot")
            record["snapshots"] = {path: "inputs/" + path for path in names}
            atomic_write(record_dir / "record.json", encoded(record))
        commands = [task["command"], *[c["command"] for c in task.get("checks", [])]]
        for command in commands:
            executable = str(project / command[0]) if not Path(command[0]).is_absolute() and "/" in command[0] else command[0]
            record["executables"][command[0]] = shutil.which(executable)
        probe = task.get("environment", {}).get("command")
        if probe:
            proc = subprocess.run(probe, cwd=project, env=env, capture_output=True, text=True)
            record["environment"] = {"command": probe, "stdout": proc.stdout, "stderr": proc.stderr, "exit_status": proc.returncode}
            if proc.returncode:
                raise WorkbenchError("Environment capture failed")
        written = file_identity(project, task["outputs"])
        run(task["command"], project, env)
        # An untouched output is a previous result. A tool may legitimately skip
        # it only if the last successful record already vouches for this exact
        # definition, these inputs and that output; otherwise it is stale data.
        untouched = [path for path, identity in file_identity(project, task["outputs"]).items() if identity is not None and identity == written[path]]
        vouched, previous, baseline = [], None, None
        if record_dir:
            try:
                archive = load_records(project, config, exclude=record_dir)
                previous = latest_record(archive, module, name)
                baseline = latest_record([r for r in archive if r.get("status") == "success"], module, name)
            except (OSError, ValueError, WorkbenchError):
                pass  # unreadable archive: no vouching (strict rule) and no comparison
        if untouched and previous is not None and not own_reasons(project, task, previous, inputs=before, outputs=untouched):
            vouched = untouched
        stale = [path for path in untouched if path not in vouched]
        if stale:
            raise WorkbenchError("Command exited successfully without rewriting declared outputs: " + ", ".join(stale))
        record["unchanged_outputs"] = vouched
        for check in task.get("checks", []):
            if check["cost"] == "expensive" and not expensive:
                record["checks"].append({**check, "status": "skipped"})
                continue
            record["checks"].append({**check, "status": "failed"})
            run(check["command"], project, env)
            record["checks"][-1]["status"] = "passed"
        after = fingerprints(project, names)
        if before != after:
            raise WorkbenchError("Inputs changed during execution; record cannot be marked successful")
        record["outputs"] = fingerprints(project, task["outputs"])
        if any(value is None for value in record["outputs"].values()):
            raise WorkbenchError("Command did not produce all declared outputs")
        # File identity shows a write happened, not that the content came from these inputs. The
        # telltale of a skipped or no-op regeneration is an output with the previous bytes after
        # its inputs or definition changed; legitimate (insensitive input, deterministic result) but
        # worth a reviewer's eye, so it is recorded and printed rather than failed.
        record["warnings"] = []
        if baseline is not None and (baseline.get("inputs") != before or baseline.get("definition_sha256") != record["definition_sha256"]):
            recorded = baseline.get("outputs") or {}
            record["warnings"] = [f"{path} has the same bytes as the previous successful run although the declared inputs or task definition changed"
                                  for path, digest in record["outputs"].items() if recorded.get(path) == digest and path not in vouched]
            for warning in record["warnings"]:
                print("WARNING: " + warning)
        if record_dir:
            for path in task["outputs"]:
                destination = record_dir / "outputs" / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local_path(project, path), destination)
                if sha(destination.read_bytes()) != record["outputs"][path]:
                    raise WorkbenchError("Output changed while archiving run")
        record["status"] = "success"
    except (OSError, WorkbenchError) as error:
        record["status"] = "failed"
        record["error"] = str(error)
        raise
    except BaseException as error:  # Ctrl-C or SIGTERM: the attempt stays visible, as interrupted
        record["status"] = "interrupted"
        record["error"] = f"Interrupted: {error!r}"
        raise
    finally:
        if outer is not None:
            signal.signal(signal.SIGTERM, outer)
        record["finished"] = datetime.now(timezone.utc).isoformat()
        if record_dir:
            atomic_write(record_dir / "record.json", encoded(record))
            print("Run record: " + str((record_dir / "record.json").relative_to(project)))
    return record


def freshness(project, config, graph=None, records=None):
    require_module(config, "freshness")
    if records is None:
        records = load_records(project, config)
    graph = graph or TaskGraph.load(project, config, records)
    # Hash each canonical file once per inspection; no cache survives an invocation.
    names = {path for key, task in graph.definitions.items()
             for path in graph.inputs[key] + task["outputs"]}
    hashes = fingerprints(project, sorted({path_name(project, name) for name in names}))
    indexed = {}
    for key, task in graph.definitions.items():
        latest = latest_record(records, *key)
        inputs = {name: hashes[path_name(project, name)] for name in graph.inputs[key]}
        reasons = own_reasons(project, task, latest, inputs=inputs, outputs=())
        if latest and latest.get("status") == "success" and latest.get("outputs") != {
                name: hashes[path_name(project, name)] for name in task["outputs"]}:
            reasons.append("output content changed or is missing")
        indexed[key] = {"module": key[0], "task": key[1], "status": "stale" if reasons else "current", "reasons": reasons}
    for key in graph.order:
        item = indexed[key]
        for dependency in sorted(graph.dependencies[key]):
            if indexed[dependency]["status"] == "stale":
                item["reasons"].append("upstream task is stale: " + "/".join(dependency))
                item["status"] = "stale"
    return [indexed[key] for key in graph.order]


def check_claims(project, config):
    if not has_module(config, "claims"):
        return
    manifest = module_config(config, "claims")["manifest"]
    data = read_json(local_path(project, manifest), manifest)
    if not isinstance(data, dict) or set(data) - {"schema_version", "claims"} or data.get("schema_version") != 1 or not isinstance(data.get("claims"), list):
        raise WorkbenchError("Invalid claims manifest")
    ids = set()
    for claim in data["claims"]:
        if not isinstance(claim, dict) or set(claim) - {"id", "text", "status", "evidence", "notes"}:
            raise WorkbenchError("Invalid claim entry")
        key = claim.get("id")
        if not isinstance(key, str) or not key or key in ids or not isinstance(claim.get("text"), str) or not claim["text"]:
            raise WorkbenchError("Claims need unique id and nonempty text")
        ids.add(key)
        if claim.get("status") not in ("proposed", "supported", "needs-review", "rejected"):
            raise WorkbenchError("Unknown claim review status")
        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list) or claim["status"] == "supported" and not evidence:
            raise WorkbenchError("Supported claims need declared evidence")
        for name in evidence:
            if not local_path(project, name).is_file():
                raise WorkbenchError(f"Missing claim evidence: {name}")
    print("Claim links/status structure checked; scientific support requires human review")


def inspect(project, config, run_checks=False, modules=None):
    records = load_records(project, config) if has_module(config, "provenance") else RunRecords()
    graph = TaskGraph.load(project, config, records)
    def enabled(name):
        return has_module(config, name) and (modules is None or name in modules)
    if enabled("notes"):
        values = module_config(config, "notes")
        base = local_path(project, values["path"])
        for name in (values["index"], values["session_state"]):
            if not (base / name).is_file():
                raise WorkbenchError(f"Missing notes file: {base / name}; recreate it or disable the notes module (configure --disable notes)")
    # The freshness report comes first: a check that fails on a stale result is then read in its light.
    report = freshness(project, config, graph, records) if enabled("freshness") else []
    for item in report:
        print(f"{item['module']}/{item['task']}: {item['status']}" + (" (" + "; ".join(item["reasons"]) + ")" if item["reasons"] else ""))
    stale = {(item["module"], item["task"]) for item in report if item["status"] == "stale"}
    steps = refresh_commands(project, report, graph) if stale else []
    for module in ("numerics", "figures"):
        if not enabled(module):
            continue
        for (task_module, name), task in graph.definitions.items():
            if task_module != module:
                continue
            if run_checks:
                for check in task.get("checks", []):
                    if check["cost"] == "cheap":
                        if os.environ.get("WORKBENCH_TASK_ACTIVE") == str(project):
                            raise WorkbenchError("Recursive research check")
                        try:
                            run(check["command"], project, {**os.environ, "WORKBENCH_TASK_ACTIVE": str(project)})
                        except WorkbenchError as error:
                            raise WorkbenchError(f"Check of {module}/{name} failed: {error}", hint=(
                                f"{module}/{name} is stale, so its check ran on an old result; refresh it: " + "; ".join(steps) if (module, name) in stale and steps
                                else f"the check declared for {module}/{name} rejected its current outputs; its own output above says why"))
    if enabled("claims"):
        check_claims(project, config)
    if stale:
        raise WorkbenchError("Stale research outputs; inspect the report and run selected tasks explicitly",
                             hint=("; ".join(steps) + " (nothing runs until you ask)") if steps else None)


def refresh_commands(project, report, graph=None):
    """The explicit commands that refresh the stale tasks of a freshness report, under the names that work here."""
    text, steps = guide.makefile_text(project), []
    graph = graph or TaskGraph.load(project, load_config(project))
    indexed = {(item["module"], item["task"]): item for item in report}
    for key in graph.order:
        item = indexed[key]
        if item["status"] == "stale":
            action = "run" if item["module"] == "numerics" else "figure"
            name = guide.usable_name(text, action, "latex-ai-" + action)
            if name:
                steps.append(f"make {name} TASK={item['task']}")
    return steps


def claim_evidence(project, config):
    """Evidence paths named by the claim ledger; an unreadable ledger names none (its own edits select the check)."""
    try:
        data = json.loads(local_path(project, module_config(config, "claims")["manifest"]).read_text(encoding="utf-8"))
        return {path_name(project, name) for claim in data["claims"] for name in claim.get("evidence", []) if isinstance(name, str) and name}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, WorkbenchError):
        return set()


def affected(project, config, paths):
    selected = set()
    records = load_records(project, config) if has_module(config, "provenance") else RunRecords()
    graph = TaskGraph.load(project, config, records, changed=paths)
    identities = {input_identity(project, p) for p in paths}  # a changed path may be a link that leaves the project
    paths = {tracked_name(project, p) for p in paths}
    for module in ("numerics", "figures"):
        if has_module(config, module):
            if path_name(project, module_config(config, module)["manifest"]) in paths:
                selected.add(module)
            for key, task in graph.definitions.items():
                if key[0] == module and identities & {path_identity(project, p) for p in graph.inputs[key] + task["outputs"]}:
                    selected.add(module)
    for module in ("claims", "notes"):
        if has_module(config, module):
            values = module_config(config, module)
            if (values.get("manifest") and path_name(project, values["manifest"]) in paths) or (values.get("path") and any(name.startswith(path_name(project, values["path"]) + "/") for name in paths)):
                selected.add(module)
            elif module == "claims" and set(paths) & claim_evidence(project, config):
                selected.add(module)  # a changed or deleted evidence file can break a claim link
    if has_module(config, "freshness") and (selected & {"numerics", "figures"} or any(name.startswith(path_name(project, module_config(config, "provenance")["path"]) + "/") for name in paths)):
        selected.add("freshness")
    return sorted(selected)


def tools(project, config):
    required = set()
    for module in ("numerics", "figures"):
        for task in tasks(project, config, module).values():
            required.add(task["command"][0])
            required.update(check["command"][0] for check in task.get("checks", []))
            if task.get("environment", {}).get("command"):
                required.add(task["environment"]["command"][0])
    return sorted(required)
