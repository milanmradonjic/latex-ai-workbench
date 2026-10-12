"""Validated research task definitions and one shared dependency graph."""
from dataclasses import dataclass
from pathlib import Path

from core import GENERATED_TREES, WorkbenchError, has_module, local_path, module_config, read_json, path_name, path_identity, tracked_name

FORMAT = 'the task format is described under "Task manifests" in docs/research.md of the workbench package'

def argv(value, label):
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and x and "\0" not in x for x in value):
        raise WorkbenchError(f'{label} must be a list of words such as ["python3", "analysis/run.py"], not one shell string')
    return value


def tasks(project, config, module):
    """Declared tasks of one module. Every problem in a manifest is reported with the manifest's name."""
    if not has_module(config, module):
        return {}
    manifest = module_config(config, module)["manifest"]
    data = read_json(local_path(project, manifest), manifest)
    try:
        return checked_tasks(project, config, data)
    except WorkbenchError as error:
        raise WorkbenchError(f"{manifest}: {error}", hint=error.hint or FORMAT)


def checked_tasks(project, config, data):
    # "example" is the installer's commented sample beside the task list; it is never read as a task.
    if not isinstance(data, dict) or set(data) - {"schema_version", "tasks", "example"} or data.get("schema_version") != 1 or not isinstance(data.get("tasks"), dict):
        raise WorkbenchError('expected {"schema_version": 1, "tasks": {...}} (plus, optionally, the installer\'s "example") at the top level')
    for name, task in data["tasks"].items():
        if not isinstance(name, str) or not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
            raise WorkbenchError(f"Invalid task name: {name!r}")
        if not isinstance(task, dict) or set(task) - {"description", "command", "inputs", "outputs", "checks", "environment", "rng"}:
            raise WorkbenchError(f"Invalid task: {name}")
        argv(task.get("command"), name + ".command")
        for field in ("inputs", "outputs"):
            values = task.get(field)
            if not isinstance(values, list) or not values or not all(isinstance(value, str) for value in values) or len(set(values)) != len(values):
                raise WorkbenchError(f"{name}.{field} must be a nonempty list of distinct file paths")
            if len({path_identity(project, p) for p in values}) != len(values):
                raise WorkbenchError(f"{name}.{field} contains aliases of the same file")
            for value in values:
                target = local_path(project, value)
                if target == project or target.is_dir() or ".." in Path(value).parts or Path(value).parts[0] in GENERATED_TREES:
                    raise WorkbenchError(f"Reserved or non-file task path: {value}")
        if {path_identity(project, p) for p in task["inputs"]} & {path_identity(project, p) for p in task["outputs"]}:
            raise WorkbenchError(f"{name}: inputs and outputs overlap")
        if has_module(config, "provenance"):
            archive = local_path(project, module_config(config, "provenance")["path"])
            if any(local_path(project, path).is_relative_to(archive) for path in task["inputs"] + task["outputs"]):
                raise WorkbenchError("Task inputs/outputs cannot overlap the run archive")
        checks = task.get("checks", [])
        if not isinstance(checks, list):
            raise WorkbenchError("checks must be a list")
        for check in checks:
            if not isinstance(check, dict) or set(check) - {"command", "cost"} or check.get("cost") not in ("cheap", "expensive"):
                raise WorkbenchError("Each check needs command and explicit cheap/expensive cost")
            argv(check.get("command"), name + ".check")
        environment = task.get("environment", {})
        if not isinstance(environment, dict) or set(environment) - {"command", "files"}:
            raise WorkbenchError("environment supports command and files")
        if "command" in environment:
            argv(environment["command"], name + ".environment")
        if not isinstance(environment.get("files", []), list):
            raise WorkbenchError("environment.files must be a list")
        for value in environment.get("files", []):
            local_path(project, value)
        if "rng" in task and not isinstance(task["rng"], dict):
            raise WorkbenchError("rng must be an object describing generator, seed and relevant details")
    return data["tasks"]


def launcher(project, command):
    """A project script executed directly as ``command[0]`` is source, so it is an input.

    Interpreters (binaries, links such as ``.venv/bin/python``) are not: only a
    file starting with ``#!`` qualifies, and their identity is recorded as an executable.
    """
    name = command[0]
    if "/" not in name or Path(name).is_absolute():
        return None
    path = project / name
    try:
        if path.is_symlink() or not path.is_file():
            return None
        local_path(project, name)
        with path.open("rb") as stream:
            return Path(name).as_posix() if stream.read(2) == b"#!" else None
    except (OSError, WorkbenchError):
        return None


def task_inputs(project, task, recorded=(), changed=()):
    inputs = set(task["inputs"]) | set(task.get("environment", {}).get("files", []))
    outputs = {path_identity(project, p) for p in task["outputs"]}
    commands = [task["command"], *[c["command"] for c in task.get("checks", [])]]
    if task.get("environment", {}).get("command"):
        commands.append(task["environment"]["command"])
    for command in commands:
        script = launcher(project, command)
        if (not script and "/" in command[0] and not Path(command[0]).is_absolute()
                and not (project / command[0]).exists() and not (project / command[0]).is_symlink()):
            name = path_name(project, command[0])
            if name in recorded or name in changed:
                script = name
        if script and path_identity(project, script) not in outputs:
            inputs.add(script)
        # Virtualenv executables often link outside the project. Record their
        # identity separately; snapshot source/config files, not interpreters.
        for argument in command[1:]:
            if not argument.startswith("-") and not Path(argument).is_absolute():
                candidate = local_path(project, argument)
                name = path_name(project, argument)
                # Missing dependencies stay in the graph. History preserves arbitrary
                # file arguments; changed names also cover deletion before a first run.
                inferred = candidate.is_file() or name in recorded or name in changed
                if inferred and path_identity(project, argument) not in outputs:
                    inputs.add(argument)
    if {path_identity(project, p) for p in inputs} & outputs:
        raise WorkbenchError("Task inputs and outputs overlap (including environment files)")
    return sorted({path_name(project, p) for p in inputs})


@dataclass
class TaskGraph:
    definitions: dict
    inputs: dict
    dependencies: dict
    order: tuple

    @classmethod
    def load(cls, project, config, records=(), changed=()):
        definitions = {(module, name): task for module in ("numerics", "figures")
                       for name, task in tasks(project, config, module).items()}
        latest = getattr(records, "latest", None)
        if latest is None:
            latest = {}
            for record in records:
                key = (record.get("module"), record.get("task"))
                if key not in latest or record["started"] > latest[key]["started"]:
                    latest[key] = record
        changed = {tracked_name(project, path) for path in changed}
        inputs = {key: task_inputs(project, task,
                                  recorded=(latest.get(key, {}).get("inputs") or {}), changed=changed)
                  for key, task in definitions.items()}
        producers = {}
        for key, task in definitions.items():
            for output in task["outputs"]:
                identity = path_identity(project, output)
                if identity in producers:
                    raise WorkbenchError(f"Multiple producers declare output: {output}")
                producers[identity] = key
        dependencies = {key: {producers[identity] for path in values
                              if (identity := path_identity(project, path)) in producers}
                        for key, values in inputs.items()}
        active, done, order = set(), set(), []

        def visit(key):
            if key in active:
                raise WorkbenchError("Cyclic research task dependencies")
            if key in done:
                return
            active.add(key)
            for dependency in sorted(dependencies[key]):
                visit(dependency)
            active.remove(key)
            done.add(key)
            order.append(key)

        for key in definitions:
            visit(key)
        return cls(definitions, inputs, dependencies, tuple(order))

