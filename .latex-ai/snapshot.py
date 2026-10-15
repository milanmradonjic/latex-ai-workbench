"""Snapshots: a restorable copy of every file of the project, kept in Git repositories of their own outside the project.

A snapshot commits the project's files whatever the project's own Git or .gitignore says, and leaves the project's own repository untouched. There are three
stores, each a repository of its own, so that what goes into one can never push anything out of another: `manual` (what `make snapshot` takes; nothing in it is ever
deleted by the workbench), `weekly` (a timer asks every day, and the first snapshot of each calendar week is kept; the newest 6 stay) and `frequent` (a timer asks
every half hour, a snapshot is kept when files changed; the newest 60 stay). A snapshot is a commit of its own with no parent, named by a number that only grows
(refs/snapshots/00000042), so dropping the oldest of a store is deleting one reference and the files only it held. The clock decides when a snapshot is taken
(which week it is) and never what is deleted: only the count does. Restoring is Git's own `checkout`; `make snapshots` prints the command.
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
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from core import CONFIG, GENERATED_TREES, OUTPUT_SUFFIXES, WorkbenchError, environment_root, operation_lock
from guide import command_name

LIMIT = 25 * 1024 * 1024  # a larger file is named in the output and not copied
PATIENCE = 60  # seconds a snapshot waits for another snapshot of the same project: a timer's runs for one project can start together
TIERS = ("manual", "weekly", "frequent")
KEEP = {"weekly": 6, "frequent": 60}  # how many each keeps; `manual` is not here: it keeps all
REFS = "refs/snapshots/"
FOLDER_MARK, REPOSITORY_MARK = "PROJECT", "SNAPSHOT-REPOSITORY"  # what marks a folder, and a repository, as made by this module
PRUNED = GENERATED_TREES - {".latex-ai"}                    # the runtime itself is kept: a restored project needs the version that wrote its configuration
LEFT_OUT = {".latex-ai/artifacts", ".latex-ai/backups"}     # state of the running workbench, and the installer's backups
BUILD_FILES = tuple(suffix for suffix in OUTPUT_SUFFIXES if suffix != ".pdf")  # a PDF beside the sources may be a figure; the rest is what a compiler writes
IDENTITY = {"GIT_AUTHOR_NAME": "snapshot", "GIT_AUTHOR_EMAIL": "snapshot@localhost.invalid",
            "GIT_COMMITTER_NAME": "snapshot", "GIT_COMMITTER_EMAIL": "snapshot@localhost.invalid"}
BYTES_AS_THEY_ARE = "* -text -eol -ident -filter -working-tree-encoding\n"  # info/attributes outranks the project's .gitattributes and the user's core.autocrlf, at snapshot and at restore


def meaning(tier):
    return {"manual": "yours: all kept, and none is ever deleted by the workbench", "weekly": f"the first of each calendar week: the newest {KEEP['weekly']} kept",
            "frequent": f"for a timer, when files changed: the newest {KEEP['frequent']} kept"}[tier]


def location():
    """The folder that holds the snapshots of every project."""
    if os.environ.get("LATEX_AI_SNAPSHOT_DIR"):
        return Path(os.environ["LATEX_AI_SNAPSHOT_DIR"]).expanduser().resolve()
    try:
        return (Path.home() / ".snapshots").resolve()
    except RuntimeError:
        raise WorkbenchError("Cannot tell where the home folder is, so there is no default place for the snapshots",
                             hint="give LATEX_AI_SNAPSHOT_DIR a folder outside the project") from None


def need_git():
    if not shutil.which("git"):
        raise WorkbenchError("Git is not installed, and the snapshots are Git repositories", hint="install Git, then run the command again")


def git(path, project, *arguments, input=None, now=None):
    """One Git command on a snapshot repository (and the project's files as its work tree). Nothing of the user's own Git reaches it: no GIT_ variable,
    no configuration file (HOME and XDG_CONFIG_HOME are moved, which every Git version honours), no template, no hook."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(IDENTITY, GIT_DIR=str(path), GIT_CONFIG_NOSYSTEM="1", HOME=str(path), XDG_CONFIG_HOME=str(path))
    if project:
        env["GIT_WORK_TREE"] = str(project)
    if now:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{int(now.timestamp())} +0000"
    done = subprocess.run(["git", *arguments], input=input, capture_output=True, env=env, cwd=project or path.parent)
    if done.returncode:
        raise WorkbenchError(f"git {arguments[0]} failed in {path}: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout.decode(errors="replace").strip()


def build(parent, name, fill):
    """Make a folder whole or not at all: it is filled under a temporary name inside its parent (private to the user) and then renamed, so that a run that
    is interrupted or finds the disk full leaves nothing that looks like a folder of ours but is not complete."""
    path = Path(tempfile.mkdtemp(prefix=".making-", dir=parent))
    fill(path)
    os.rename(path, parent / name)


def project_key(project):
    """Eight hex digits of a hash of the project's path: what tells two projects with one name apart, in the store's name and in its lock's."""
    return hashlib.sha256(os.fsencode(project)).hexdigest()[:8]


def open_store(project, base, create):
    """The folder of this project's snapshots, made when asked; a folder of that name that this module did not make for this project is refused, untouched."""
    name = re.sub(r"[^\w.-]+", "_", project.name)[:60] or "project"
    store = base / f"{name}-{project_key(project)}"
    mark = store / FOLDER_MARK
    if store.is_symlink() or (store.exists() and not (mark.is_file() and mark.read_bytes() == os.fsencode(project) + b"\n")):
        raise WorkbenchError(f"{store} exists, but the workbench did not make it for this project; nothing in it was touched",
                             hint="move or delete it, or give LATEX_AI_SNAPSHOT_DIR another folder")
    if create and not store.exists():
        build(base, store.name, lambda path: (path / FOLDER_MARK).write_bytes(os.fsencode(project) + b"\n"))
    return store if store.exists() else None


def initialize(path):
    git(path, None, "init", "--quiet", "--bare", "--template=")
    git(path, None, "config", "core.hooksPath", os.devnull)  # the user's hooks do not run at a restore
    (path / "info").mkdir(exist_ok=True)
    (path / "info/attributes").write_text(BYTES_AS_THEY_ARE)
    (path / REPOSITORY_MARK).write_text("made by the workbench; the snapshots of one store, each a commit of its own\n")


def repository(store, tier, create=False):
    """The repository of one store, made when asked; a link, or a folder without the mark, is refused whatever it holds."""
    path = store / tier
    if create and not path.exists() and not path.is_symlink():
        build(store, tier, initialize)
    if path.is_symlink() or not (path / REPOSITORY_MARK).is_file():
        raise WorkbenchError(f"{path} is not a snapshot repository made by the workbench; nothing in it was touched", hint="delete it yourself if it is not wanted")
    return path


def records(path):
    """The store's snapshots, oldest first: (number, commit, tree, seconds, label). A reference that is not a number is not ours, and is left out."""
    rows = []
    for line in filter(None, git(path, None, "for-each-ref", "--sort=refname", "--format=%(refname)\t%(objectname)\t%(tree)\t%(committerdate:raw)\t%(subject)", REFS).split("\n")):
        ref, commit, tree, date, label = line.split("\t", 4)  # not splitlines(): a label may hold characters it treats as line ends
        if re.fullmatch(r"[0-9]{8}", ref[len(REFS):]):
            rows.append((int(ref[len(REFS):]), commit, tree, int(date.split()[0]), label))
    return rows


def week(seconds):
    """The calendar week, Monday to Sunday, in the user's own time."""
    return datetime.fromtimestamp(seconds).isocalendar()[:2]


def output_folders(project):
    """The folders that hold only build output, as the configuration declares them (a document's own output_dir, or the default it inherits); read leniently,
    since a snapshot has to work when the configuration is broken."""
    try:
        latex = json.loads((project / CONFIG).read_text(encoding="utf-8"))["modules"]["latex"]
        inherited = latex.get("defaults", {}).get("output_dir")
        documents = [d for d in latex["documents"].values() if isinstance(d, dict)]
        roots = [PurePosixPath(posixpath.normpath(d["root"])) for d in documents if isinstance(d.get("root"), str)]
        outputs = {PurePosixPath(posixpath.normpath(d.get("output_dir", inherited))) for d in documents if isinstance(d.get("output_dir", inherited), str)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return set()
    return {out.as_posix() for out in outputs if out.parts and not any(root.is_relative_to(out) for root in roots)}


def compiler_file(here, name):
    """A file a compiler wrote beside its source: one of the compiler's suffixes, and a .tex of the same stem next to it. A train.log or a solver.out is data, and kept."""
    return any(name.endswith(suffix) and (here / (name[:-len(suffix)] + ".tex")).is_file() for suffix in BUILD_FILES)


def project_files(project):
    """(the files to keep, the files over the limit as (name, size)): every file and link of the project except Git's own folders and files (a submodule's `.git`),
    environments, caches, the compiler's files and the build output folders. The project's .gitignore does not apply: what it ignores is often what a person would
    miss. Sockets and pipes are not files, and are not kept."""
    left_out = LEFT_OUT | output_folders(project)
    kept, large = [], []

    def fail(error):
        raise error  # a folder that cannot be read is an error: a safety copy must not leave it out without saying so

    for directory, folders, files in os.walk(project, onerror=fail):
        here = Path(directory)
        links = [name for name in folders if (here / name).is_symlink()]  # a link to a folder is kept as a link, and not followed
        folders[:] = sorted(name for name in folders if name not in links and name.lower() not in PRUNED and not environment_root(here / name)
                            and (here / name).relative_to(project).as_posix() not in left_out)
        for name in sorted(files + links):
            try:
                info = (here / name).lstat()
            except FileNotFoundError:
                continue  # gone since the folder was listed: a compiler's temporary file
            if name.lower() == ".git" or compiler_file(here, name) or not (stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                continue
            relative = (here / name).relative_to(project).as_posix()
            if info.st_size > LIMIT:
                large.append((relative, info.st_size))
            else:
                kept.append(relative)
    return kept, large


def snapshot_into(path, tier, project, files, note, now):
    """Take one snapshot into a store: (its record, "taken" | "same" | "week", the numbers dropped to keep the newest few). It is not taken when the files are
    those of the newest snapshot of the store, or, in the weekly store, when that one is from this calendar week."""
    rows = records(path)
    newest = rows[-1] if rows else None
    if tier == "weekly" and newest and week(newest[3]) == week(now.timestamp()):
        return newest, "week", []
    (path / "index.lock").unlink(missing_ok=True)  # left by a run that was killed while Git held it; the project's lock is ours, so nothing else is writing the index
    git(path, project, "read-tree", "--empty")
    git(path, project, "update-index", "--add", "--remove", "-z", "--stdin", input=b"".join(os.fsencode(name) + b"\0" for name in files))
    tree = git(path, project, "write-tree")
    if newest and newest[2] == tree:
        return newest, "same", []
    commit = git(path, project, "commit-tree", tree, "-m", note.strip() or "snapshot", now=now)
    number = (newest[0] if newest else 0) + 1
    git(path, project, "update-ref", f"{REFS}{number:08d}", commit, "")  # the empty old value: the reference must not exist yet
    dropped = [row[0] for row in rows[:max(0, len(rows) + 1 - KEEP[tier])]] if tier in KEEP else []
    for old in dropped:
        git(path, None, "update-ref", "-d", f"{REFS}{old:08d}")
    if dropped:
        git(path, None, "prune", "--expire=now")  # the files only the dropped snapshots held
    return (number, commit, tree, int(now.timestamp()), note.strip() or "snapshot"), "taken", dropped


def take(project, tier="manual", note="", base=None, now=None):
    """Snapshot the project into one store. Prints what happened, and returns it. One snapshot at a time: a second one waits a few seconds for the first,
    and says so if it is still running."""
    if tier not in TIERS:
        raise WorkbenchError(f"No snapshot store called {tier}", hint="the stores are " + ", ".join(TIERS))
    project, now = Path(project).resolve(), now or datetime.now(timezone.utc)
    base = Path(base).resolve() if base else location()
    if base.is_relative_to(project):
        raise WorkbenchError(f"The snapshot folder {base} is inside the project, so every snapshot would contain the one before",
                             hint="give LATEX_AI_SNAPSHOT_DIR a folder outside the project, or leave it unset (the default is ~/.snapshots)")
    need_git()
    base.mkdir(mode=0o700, parents=True, exist_ok=True)  # private: a snapshot holds every file of the project, whoever may read them
    with operation_lock(base, "snapshot-" + project_key(project), wait=PATIENCE, busy="Another snapshot of this project is being taken; wait for it, then run this again"):
        files, large = project_files(project)
        store = open_store(project, base, create=True)
        (number, commit, *_), status, dropped = snapshot_into(repository(store, tier, create=True), tier, project, files, note, now)
    print({"taken": f"Snapshot #{number} ({commit[:7]}) in the {tier} store: {len(files)} files",
           "same": f"Nothing changed since snapshot #{number} in the {tier} store ({len(files)} files)",
           "week": f"This week already has a snapshot in the weekly store (#{number})"}[status])
    for old in dropped:
        print(f"Dropped snapshot #{old}: the {tier} store keeps the newest {KEEP[tier]}")
    for name, size in large:
        print(f"Left out, over {LIMIT // 1024 // 1024} MB: {name} ({size / 1024 / 1024:.1f} MB)")
    lister = command_name(project, "snapshots")  # a project without the 4.7 Makefile has no target for it
    print(f"Kept in {store}; {'make ' + lister if lister else 'the snapshots action of the runtime'} lists the snapshots and says how to restore one.")
    return {"tier": tier, "number": number, "commit": commit, "status": status, "changed": status == "taken", "files": len(files),
            "skipped": [name for name, _ in large], "dropped": dropped, "store": str(store)}


def listing(project, base=None):
    """Print the project's snapshots, newest first in each store, and the Git command that restores a file from the newest; returns them."""
    project = Path(project).resolve()
    store = open_store(project, Path(base).resolve() if base else location(), create=False)
    rows = []
    if store is not None:
        need_git()
    for tier in TIERS:
        if store is not None and (store / tier).exists():
            path = repository(store, tier)
            rows += [{"tier": tier, "number": number, "commit": commit[:7], "time": seconds, "label": label, "path": str(path)}
                     for number, commit, _, seconds, label in records(path)]
    if not rows:
        taker = command_name(project, "snapshot")
        print(f"No snapshots of {project.name} yet: {'make ' + taker if taker else 'the snapshot action of the runtime'} makes one.")
        return {"snapshots": []}
    print(f"Snapshots of {project.name}, in {store}")
    for tier in TIERS:
        if any(row["tier"] == tier for row in rows):
            print(f"\n{tier} store ({meaning(tier)})")
            for row in sorted((row for row in rows if row["tier"] == tier), key=lambda row: -row["number"]):
                print(f"  #{row['number']:<5}{row['commit']}  {datetime.fromtimestamp(row['time']).strftime('%Y-%m-%d %H:%M')}  {row['label']}")
    newest = max(rows, key=lambda row: (row["time"], row["number"]))
    prefix = f"git --git-dir={shlex.quote(newest['path'])} --work-tree={shlex.quote(str(project))}"
    print(f"\nWith Git, from the newest (#{newest['number']}, {newest['commit']}); for another, use its id and its store's repository, the folder of that name in {store}:"
          f"\n  what changed since it:   {prefix} diff {newest['commit']} --stat"
          f"\n  one file back:           {prefix} checkout {newest['commit']} -- FILE"
          f"\n  every file it has back:  {prefix} checkout {newest['commit']} -- .   (a file made since stays, and edits since are overwritten: make a snapshot first)")
    return {"snapshots": rows}
