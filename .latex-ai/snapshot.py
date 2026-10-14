"""Snapshots: a restorable copy of every file of the project, kept in Git repositories of their own outside the project.

`make snapshot` commits the project's files whatever the project's own Git or .gitignore says, and leaves the project's own repository untouched. There are two
tiers: the fine tier takes every snapshot and keeps one to two weeks, the daily tier takes the first snapshot of each UTC day and keeps one to two months. A tier
has two repositories used by turns: its period (a week, a month) numbers the one it writes to by parity, and a repository older than the previous period is
deleted, which is the only deleting this module does, and only of a folder it made itself. Restoring is Git's own `checkout`; `make snapshots` prints the command.
"""
import hashlib
import json
import os
import posixpath
import re
import shlex
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from core import CONFIG, GENERATED_TREES, OUTPUT_SUFFIXES, WorkbenchError, atomic_write, environment_root
from guide import command_name

LIMIT = 25 * 1024 * 1024  # a larger file is named in the output and not copied
PERIODS = {"fine": lambda now: int(now.timestamp() // 86400) // 7,    # a week of UTC days
           "daily": lambda now: now.year * 12 + now.month - 1}        # a calendar month
MEANING = {"fine": "every snapshot, kept one to two weeks", "daily": "the first of each day, kept one to two months"}
FOLDER_MARK, REPOSITORY_MARK, PERIOD = "PROJECT", "SNAPSHOT-REPOSITORY", "PERIOD"  # what marks a folder, and a repository, as made by this module
PRUNED = GENERATED_TREES - {".latex-ai"}                    # the runtime itself is kept: a restored project needs the version that wrote its configuration
LEFT_OUT = {".latex-ai/artifacts", ".latex-ai/backups"}     # state of the running workbench, and the installer's backups
BUILD_FILES = tuple(suffix for suffix in OUTPUT_SUFFIXES if suffix != ".pdf")  # a PDF beside the sources may be a figure; the rest is what a compiler writes
IDENTITY = {"GIT_AUTHOR_NAME": "snapshot", "GIT_AUTHOR_EMAIL": "snapshot@localhost.invalid",
            "GIT_COMMITTER_NAME": "snapshot", "GIT_COMMITTER_EMAIL": "snapshot@localhost.invalid"}


def location():
    """The folder that holds the snapshots of every project."""
    return Path(os.environ.get("LATEX_AI_SNAPSHOT_DIR") or Path.home() / ".snapshots").expanduser().resolve()


def need_git():
    if not shutil.which("git"):
        raise WorkbenchError("Git is not installed, and the snapshots are Git repositories", hint="install Git, then run the command again")


def git(path, project, *arguments, input=None, check=True, now=None):
    """One Git command on a snapshot repository (and the project's files as its work tree). Nothing of the user's own Git reaches it: no GIT_ variable,
    no configuration file, no template, no hook."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(IDENTITY, GIT_DIR=str(path), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    if project:
        env["GIT_WORK_TREE"] = str(project)
    if now:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{int(now.timestamp())} +0000"
    done = subprocess.run(["git", *arguments], input=input, capture_output=True, env=env, cwd=project or path.parent)
    if check and done.returncode:
        raise WorkbenchError(f"git {arguments[0]} failed in {path}: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout.decode(errors="replace").strip()


def open_store(project, base, create):
    """The folder of this project's snapshots, made when asked; a folder of that name that this module did not make is refused, and is not touched."""
    name = re.sub(r"[^\w.-]+", "_", project.name) or "project"
    store = base / f"{name}-{hashlib.sha256(str(project).encode()).hexdigest()[:8]}"
    if store.is_symlink() or (store.exists() and not (store / FOLDER_MARK).is_file()):
        raise WorkbenchError(f"{store} exists, but the workbench did not make it; nothing in it was touched",
                             hint="move or delete it, or give LATEX_AI_SNAPSHOT_DIR another folder")
    if create and not store.exists():
        atomic_write(store / FOLDER_MARK, f"{project}\n")
    return store if store.exists() else None


def repository(store, name):
    """A repository of the store that carries the mark; a link, or a folder without it, is refused whatever it holds."""
    path = store / name
    if path.is_symlink() or not (path / REPOSITORY_MARK).is_file():
        raise WorkbenchError(f"{path} is not a snapshot repository made by the workbench; nothing in it was touched", hint="delete it yourself if it is not wanted")
    return path


def period_of(path):
    try:
        return int((path / PERIOD).read_text())
    except (OSError, ValueError):
        raise WorkbenchError(f"{path / PERIOD} cannot be read, so the age of {path.name} is unknown; nothing in it was touched",
                             hint="delete the folder yourself if its snapshots are not wanted") from None


def current(store, tier, now):
    """The repository the tier writes to now: first every repository older than the previous period is deleted, then the one of this period is made if it is missing."""
    period = PERIODS[tier](now)
    for slot in (0, 1):
        name = f"{tier}-{slot}"
        if (store / name).exists() or (store / name).is_symlink():
            path = repository(store, name)
            if period_of(path) < period - 1:
                shutil.rmtree(path)
    path = store / f"{tier}-{period % 2}"
    if not path.exists():
        git(path, None, "init", "--quiet", "--bare", "--template=")
        atomic_write(path / REPOSITORY_MARK, "made by the workbench; the snapshots of one tier, in rotation\n")
        atomic_write(path / PERIOD, f"{period}\n")
    return repository(store, path.name)


def output_folders(project):
    """The folders that hold only build output, as the configuration declares them; read leniently, since a snapshot has to work when the configuration is broken."""
    try:
        documents = [d for d in json.loads((project / CONFIG).read_text(encoding="utf-8"))["modules"]["latex"]["documents"].values() if isinstance(d, dict)]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return set()
    roots = [PurePosixPath(posixpath.normpath(d["root"])) for d in documents if isinstance(d.get("root"), str)]
    outputs = {PurePosixPath(posixpath.normpath(d["output_dir"])) for d in documents if isinstance(d.get("output_dir"), str)}
    return {out.as_posix() for out in outputs if out.parts and not any(root.is_relative_to(out) for root in roots)}


def project_files(project):
    """(the files to keep, the files over the limit as (name, size)): every file and link of the project except Git's own folders, environments, caches,
    the compiler's files and the build output folders. The project's .gitignore does not apply: what it ignores is often what a person would miss."""
    left_out = LEFT_OUT | output_folders(project)
    kept, large = [], []

    def fail(error):
        raise error  # a folder that cannot be read is an error: a safety copy must not leave it out without saying so

    for directory, folders, files in os.walk(project, onerror=fail):
        here = Path(directory)
        links = [name for name in folders if (here / name).is_symlink()]  # a link to a folder is kept as a link, and not followed
        folders[:] = sorted(name for name in folders if name not in links and name not in PRUNED and not environment_root(here / name)
                            and (here / name).relative_to(project).as_posix() not in left_out)
        for name in sorted(files + links):
            info = (here / name).lstat()
            if name.endswith(BUILD_FILES) or not (stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                continue
            relative = (here / name).relative_to(project).as_posix()
            if info.st_size > LIMIT:
                large.append((relative, info.st_size))
            else:
                kept.append(relative)
    return kept, large


def commit_files(path, project, files, note, now):
    """Make the repository's tree the project's files; (the commit, whether it is a new one). An unchanged tree makes no commit."""
    git(path, project, "read-tree", "--empty")
    git(path, project, "update-index", "--add", "--remove", "-z", "--stdin", input=b"".join(os.fsencode(name) + b"\0" for name in files))
    tree = git(path, project, "write-tree")
    parent = git(path, project, "rev-parse", "--verify", "--quiet", "HEAD", check=False)
    if parent and git(path, project, "rev-parse", f"{parent}^{{tree}}") == tree:
        return parent, False
    commit = git(path, project, "commit-tree", tree, "-m", note or "snapshot", *(["-p", parent] if parent else []), now=now)
    git(path, project, "update-ref", "HEAD", commit)
    return commit, True


def take(project, note="", base=None, now=None):
    """Snapshot the project: always into the fine tier, and into the daily tier when it has none yet today. Prints what happened, and returns it."""
    project, now = Path(project).resolve(), now or datetime.now(timezone.utc)
    base = Path(base).resolve() if base else location()
    if base.is_relative_to(project):
        raise WorkbenchError(f"The snapshot folder {base} is inside the project, so every snapshot would contain the one before",
                             hint="give LATEX_AI_SNAPSHOT_DIR a folder outside the project, or leave it unset (the default is ~/.snapshots)")
    need_git()
    files, large = project_files(project)
    store = open_store(project, base, create=True)
    fine, daily = current(store, "fine", now), current(store, "daily", now)  # both are opened, and the old ones deleted, before anything is written
    commit, changed = commit_files(fine, project, files, note, now)
    last = git(daily, None, "log", "-1", "--format=%ct", check=False)
    first_today = not last or int(last) // 86400 != int(now.timestamp()) // 86400
    if first_today:
        commit_files(daily, project, files, note, now)
    print((f"Snapshot {commit[:7]}: {len(files)} files" + (" (the first of today: kept in the daily tier too)" if first_today else "")) if changed
          else f"Nothing changed since snapshot {commit[:7]} ({len(files)} files)")
    for name, size in large:
        print(f"Left out, over {LIMIT // 1024 // 1024} MB: {name} ({size / 1024 / 1024:.1f} MB)")
    lister = command_name(project, "snapshots")  # a project without the 4.7 Makefile has no target for it
    print(f"Kept in {store}; {'make ' + lister if lister else 'the snapshots action of the runtime'} lists the snapshots and says how to restore one.")
    return {"commit": commit, "changed": changed, "files": len(files), "skipped": [name for name, _ in large], "store": str(store)}


def listing(project, base=None):
    """Print the project's snapshots, newest first within each tier, and the Git command that restores a file from the newest; returns them."""
    project = Path(project).resolve()
    store = open_store(project, Path(base).resolve() if base else location(), create=False)
    rows = []
    for tier in PERIODS:
        for slot in (0, 1):
            if store is not None and (store / f"{tier}-{slot}").exists():
                path = repository(store, f"{tier}-{slot}")
                need_git()
                for line in git(path, None, "log", "--format=%h %ct %s", check=False).splitlines():
                    short, seconds, label = line.split(" ", 2)
                    rows.append({"tier": tier, "repository": path.name, "commit": short, "time": int(seconds), "label": label, "path": str(path)})
    if not rows:
        taker = command_name(project, "snapshot")
        print(f"No snapshots of {project.name} yet: {'make ' + taker if taker else 'the snapshot action of the runtime'} makes one.")
        return {"snapshots": []}
    print(f"Snapshots of {project.name}, in {store}")
    for tier in PERIODS:
        if any(row["tier"] == tier for row in rows):
            print(f"\n{tier} tier ({MEANING[tier]})")
            for row in sorted((row for row in rows if row["tier"] == tier), key=lambda row: -row["time"]):
                print(f"  {row['commit']}  {datetime.fromtimestamp(row['time']).strftime('%Y-%m-%d %H:%M')}  {row['repository']}  {row['label']}")
    newest = max(rows, key=lambda row: row["time"])
    prefix = f"git --git-dir={shlex.quote(newest['path'])} --work-tree={shlex.quote(str(project))}"
    print(f"\nWith Git, from the newest ({newest['commit']}); for another, use its id and its repository, the folder of that name in the store:"
          f"\n  see what changed since it:      {prefix} diff {newest['commit']} --stat"
          f"\n  restore one file from it:\n  {prefix} checkout {newest['commit']} -- FILE"
          f"\n  restore every file it has (a file made since stays):\n  {prefix} checkout {newest['commit']} -- .")
    return {"snapshots": rows}
