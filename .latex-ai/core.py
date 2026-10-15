"""Dependency-free core utilities and versioned module configuration."""
import copy
import contextlib
import errno
from contextvars import ContextVar
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import processes

VERSION = "4.10.1"
CONFIG = ".latex-ai.json"
# Trees that are never project sources: version control, workbench state, environments, caches and installed packages. Every
# walk and every check of a declared path agrees on them; the installer adds the folders it alone leaves out.
GENERATED_TREES = frozenset({".git", ".latex-ai", ".venv", "__pycache__", "node_modules", "site-packages", "dist-packages"})
CAPTURE_COMMANDS = ContextVar("capture_workbench_commands", default=False)

class WorkbenchError(Exception):
    """An ordinary, expected failure; `hint` says what to do next and is printed after the message."""
    def __init__(self, message="", hint=None):
        super().__init__(message)
        self.hint = hint


def local_path(project, value):
    """Reject paths escaping the project, including through symlinks."""
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise WorkbenchError(f"Expected a project-relative path, got {value!r}")
    path = (project / value).resolve()
    if not path.is_relative_to(project.resolve()) or any(c in value for c in "\n\r\0"):
        raise WorkbenchError(f"Path escapes project or contains control characters: {value!r}")
    return path


def path_name(project, value):
    """Canonical project-relative spelling; diagnostics may retain the original value."""
    return local_path(project, value).relative_to(project.resolve()).as_posix()


def input_name(project, path):
    """The name under which a file a document reads is tracked; None when it is out of the project's reach.

    A file inside the project has its canonical spelling. A link inside the project that leads out of
    it (a shared figure folder, a data directory) keeps the spelling of the link itself: its content is
    part of the document although the project cannot contain it. Other files outside the project, such
    as the TeX distribution's own, remain an adapter boundary.
    """
    root, path = project.resolve(), Path(path)
    if any(c in str(path) for c in "\n\r\0"):
        return None
    resolved = path.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    linked = Path(os.path.abspath(path))  # normalized without following links; '..' would change what it names
    if ".." not in path.parts and linked.is_relative_to(root):
        return linked.relative_to(root).as_posix()
    return None


def tracked_name(project, value):
    """``path_name`` for a dependency, which may be a link that leaves the project."""
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise WorkbenchError(f"Expected a project-relative path, got {value!r}")
    name = input_name(project, project.resolve() / value)
    if name is None:
        raise WorkbenchError(f"Path escapes project or contains control characters: {value!r}")
    return name


def file_identity(path):
    if path.is_file():
        stat = path.stat()
        return ("inode", stat.st_dev, stat.st_ino)
    return ("path", str(path))


def path_identity(project, value):
    """Dependency identity, including existing hard-link aliases."""
    return file_identity(local_path(project, value))


def input_identity(project, value):
    """``path_identity`` for a dependency name; a link that leaves the project is identified by its content's file."""
    return file_identity(project.resolve() / tracked_name(project, value))


OUTPUT_SUFFIXES = (".pdf", ".log", ".aux", ".fls", ".fdb_latexmk", ".bbl", ".blg",
                   ".bcf", ".toc", ".out", ".run.xml", ".synctex", ".synctex.gz",
                   ".lof", ".lot", ".loa", ".lol", ".loe", ".thm", ".idx", ".ind", ".ilg", ".glo", ".gls", ".glg",
                   ".acn", ".acr", ".alg", ".glsdefs", ".ist", ".nlo", ".nls", ".nlg", ".nav", ".snm", ".vrb", ".dvi", ".xdv")


def document_paths(project, root_name, output_dir=None):
    """One containment rule for compiler output children."""
    root = local_path(project, root_name)
    out = local_path(project, output_dir) if output_dir else root.parent
    stem = out / root.stem
    name = stem.relative_to(project.resolve()).as_posix()
    for suffix in OUTPUT_SUFFIXES:
        local_path(project, name + suffix)  # the child itself may be an escaping symlink
    return root, out, stem


def environment_root(path):
    """A Python virtual or conda environment, whatever it is named."""
    return (path / "pyvenv.cfg").is_file() or (path / "conda-meta").is_dir()


def git_read_env():
    """Environment for read-only Git queries.

    Even ``git status``/``git diff`` normally rewrite .git/index when file stat
    data is stale; GIT_OPTIONAL_LOCKS=0 stops that, so querying never changes Git state.
    """
    return {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


def git_output(project, *arguments, timeout=15):
    """Optional read-only Git metadata; absent Git/history is unavailable data."""
    try:
        result = subprocess.run(["git", "-C", str(project), *arguments], capture_output=True,
                                text=True, env=git_read_env(), timeout=timeout)
        return result.stdout.rstrip() if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def damaged_text(text):
    """NUL bytes or leftover merge-conflict markers.

    A line of ``=======`` alone is valid Markdown/RST/AsciiDoc (a setext heading
    underline), so only the ``<<<<<<<`` and ``>>>>>>>`` marker lines count.
    """
    return "\0" in text or bool(re.search(r"^(?:<<<<<<< |>>>>>>> )", text, re.M))


def read_tex(path):
    """TeX source for static inspection. Older manuscripts use 8-bit encodings (inputenc latin1); the
    compiler reads those, so a scan for file names and markers must too. Every byte decodes as Latin-1."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def read_json(path, name):
    """Parse one of the project's JSON files. Several are read by a single command, so a syntax error names its file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:  # malformed JSON, or bytes that are not UTF-8
        raise WorkbenchError(f"{name} is not valid JSON: {error}", hint=f"correct the syntax of {name}; version control has the last good copy")


def line_buffered():
    """Write each output line as it is produced. Through a pipe (how agents and CI capture a command) Python
    otherwise holds standard output back, and an error on standard error overtakes the lines that explain it."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except (AttributeError, ValueError, OSError):
            pass  # a replaced or closed stream: nothing to configure


def run(command, cwd, env=None, started=None, display=True, startup=None):
    """Run one command. With ``started`` (POSIX), the command gets its own process group, whose ID
    is passed to ``started`` before waiting: the caller records it, and an interrupted caller stops
    the whole group (a compiler and its children), not just the immediate child."""
    executable = str(Path(cwd) / command[0]) if not Path(command[0]).is_absolute() and "/" in command[0] else command[0]
    if not shutil.which(executable):
        raise WorkbenchError(f"Required tool not found: {command[0]}", hint="the doctor command (make doctor, or make latex-ai-doctor) lists every tool this project needs")
    if display:
        print("+ " + " ".join(command), flush=True)
    capture = CAPTURE_COMMANDS.get()
    grouped = started is not None and os.name == "posix"
    output = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True, "errors": "replace"} if capture else {}
    descriptors = {"pass_fds": processes.jobserver_fds(env)} if os.name == "posix" else {}
    process = None
    gate = None
    try:
        # The caller may serialize spawning and publication of ownership so a
        # dead owner cannot expose an unrecorded live compiler to a new build.
        with startup if startup is not None else contextlib.nullcontext():
            launched = command
            if grouped:
                gate = os.pipe()
                descriptors['pass_fds'] += (gate[0],)
                launched = [sys.executable, '-B', str(Path(processes.__file__).resolve()), '--launch', str(gate[0]), *command]
            process = subprocess.Popen(launched, cwd=cwd, env=env, start_new_session=grouped,
                                       stdin=None, **descriptors, **output)
            if grouped:
                started(process.pid)
                os.write(gate[1], b'1')
                os.close(gate[0]); os.close(gate[1])
                gate = None
        stdout, stderr = process.communicate()
    except BaseException:
        if process is not None:
            stop_process(process, grouped)
        raise
    finally:
        if gate is not None:
            os.close(gate[0]); os.close(gate[1])
    if capture:
        print(stdout, end="")
        print(stderr, end="", file=sys.stderr)
    if process.returncode:
        raise WorkbenchError(f"Command failed with exit status {process.returncode}: {' '.join(command)}")


stop_process = processes.stop


MAKEFILES = ("GNUmakefile", "makefile", "Makefile")  # the order in which GNU Make itself looks for one


# A module names the runtime file that serves it and declares its configuration defaults. Paths belong to the
# project; the installer resolves these defaults once, never during an upgrade.
MODULES = {
    "latex": {"runtime": "latex.py", "defaults": {"default_document": "manuscript", "documents": {"manuscript": {"root": "main.tex"}}}},
    "bibliography": {"runtime": "latex.py", "defaults": {"files": [], "export": None}},
}
# Modules of workbench 3 that workbench 4 no longer has. A configuration naming one is refused with a hint, not as an unknown name.
# What a document is built with by default: one engine, and BibTeX or no bibliography program. A document that needs more declares a build_command.
ENGINES = ("pdflatex",)
BACKENDS = ("none", "bibtex")
EXPORT_FORMATS = ("bibtex",)
REMOVED_MODULES = ("notes", "markdown", "numerics", "figures", "provenance", "freshness", "claims")


def has_module(config, name):
    return name in config.get("modules", {})


def module_config(config, name):
    if name == "latex":
        return copy.deepcopy(config.get("modules", {}).get(name, {}))
    return {**copy.deepcopy(MODULES[name]["defaults"]), **config.get("modules", {}).get(name, {})}


def integrations(config):
    adapter = config.get("integrations", {})
    if not isinstance(adapter, dict):
        raise WorkbenchError("integrations must be an object")
    return {"editor": adapter.get("editor", False)}


def atomic_write(path, data):
    """Publish complete state (UTF-8 text, or bytes) with one replacement, preserving existing mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, name = tempfile.mkstemp(prefix=".latex-ai-tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data if isinstance(data, bytes) else data.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


LOCKS = ".latex-ai/artifacts/locks"


def lock_file(project, operation):
    """Open (creating if needed) the project's lock file of one operation.

    Opened for writing where possible: on NFS, flock is emulated by byte-range locks, and an exclusive one needs a
    writable descriptor. A lock file another user created is shared as the project directory is: group-writable
    when the project is, and read-only (enough for a local flock) otherwise.
    """
    directory = project / LOCKS
    if not directory.is_dir():
        directory.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):  # whoever may write the project may create the locks it needs
            os.chmod(directory, project.stat().st_mode & 0o2777)
    path = directory / f"{operation}.lock"
    if os.name == "nt":
        return path.open("a+b")
    try:
        created = not path.exists()
        descriptor, mode = os.open(path, os.O_RDWR | os.O_CREAT, 0o666), "r+b"
        if created:
            with contextlib.suppress(OSError):
                os.chmod(path, 0o644 | (project.stat().st_mode & 0o022))
    except PermissionError:
        descriptor, mode = os.open(path, os.O_RDONLY), "rb"
    return os.fdopen(descriptor, mode)


BUSY = {getattr(errno, name) for name in ("EAGAIN", "EWOULDBLOCK", "EACCES", "EDEADLK") if hasattr(errno, name)}


@contextlib.contextmanager
def operation_lock(project, operation, wait=False, busy=None):
    """Refuse concurrent state-changing operations of one project.

    The lock file lives beside the state it protects, in the project's ignored artifacts directory: every
    process that works in the project contends on the same file, whoever runs it, whatever its temporary
    directory and whichever path reaches the project. A lock that cannot be taken stops the operation;
    ``busy`` is the message when another process holds it.
    """
    try:
        stream = lock_file(project, operation)
    except OSError as error:
        raise WorkbenchError(f"Cannot create the {operation} lock in {LOCKS}: {error}",
                             hint="the project directory must be writable by whoever runs this command") from error
    with stream:
        deadline = time.monotonic() + (5 if wait is True else wait)  # True: a few seconds; a number: that many
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.write(b"0"); stream.flush(); stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as error:
                if os.name != "nt" and error.errno not in BUSY:  # not contention: a filesystem that cannot lock
                    raise WorkbenchError(f"Cannot lock {operation} in {LOCKS}: {error}",
                                         hint="the project's filesystem must support file locks (flock)") from error
                if time.monotonic() >= deadline:
                    raise WorkbenchError(busy or f"Cannot lock {operation}; another operation may be running") from error
                time.sleep(.01)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def make_goals(command):
    """The goals a `make` build command names, beyond its flags and assignments; none for any other command."""
    if not (isinstance(command, (list, tuple)) and command and isinstance(command[0], str) and Path(command[0]).name in {"make", "gmake"}):
        return set()
    return {argument for argument in command[1:] if isinstance(argument, str) and not argument.startswith("-") and "=" not in argument}


def effective_config(config):
    """One in-memory schema with defaults; never rewrites the persisted configuration."""
    result = copy.deepcopy(config)
    result["modules"] = {name: module_config(result, name) for name in MODULES if has_module(result, name)}
    result["integrations"] = integrations(result)
    return result


def module_names(config):
    return tuple(name for name in MODULES if has_module(config, name))


# Every file of the distribution whose change affects installed projects: the planner treats a change to
# one as a build/configuration change. runtime_sources (below) is the subset a given project receives.
RUNTIME_FILES = ("runtime.py", "commands.py", "schema.py", "core.py", "latex.py", "documents.py", "diagnostics.py",
                 "guide.py", "processes.py", "output_transaction.py", "snapshot.py",
                 "bootstrap.py", "latex-ai-init")


def runtime_sources(config):
    return {"runtime.py": "workbench.py", "commands.py": "commands.py", "schema.py": "schema.py", "core.py": "core.py", "diagnostics.py": "diagnostics.py", "guide.py": "guide.py",
            "processes.py": "processes.py", "snapshot.py": "snapshot.py",
            **{MODULES[name]["runtime"]: MODULES[name]["runtime"] for name in module_names(config)},
            **({"documents.py": "documents.py"} if has_module(config, "latex") else {}),
            **({"output_transaction.py": "output_transaction.py"} if has_module(config, "latex") else {})}


# The checks `validate` can run, in their order. Which of them a change needs is decided once, in validation_actions.
VALIDATION_ACTIONS = {
    "unit": {"label": "Test workbench", "argv": ("make", "-C", "{package}", "test")},
    "bibliography": {"label": "Check bibliography", "argv": ("make", "latex-ai-bib-check")},
    "portability": {"label": "Test compiler portability", "argv": ("make", "-C", "{package}", "portability")},
    "full": {"label": "Check project", "argv": ("make", "check")},
}


def validation_argv(name, package="workbench"):
    return [word.replace("{package}", package) for word in VALIDATION_ACTIONS[name]["argv"]]


def validation_actions(plan):
    full = bool(plan["manuscript"] or plan["fallback"])
    # A project-wide make check covers the bibliography check, so it is selected on its own only without a full check.
    return [name for name in VALIDATION_ACTIONS
            if (full if name == "full" else plan.get(name, False) and (name in {"unit", "portability"} or not full))]
