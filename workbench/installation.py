"""Atomic installation transactions, file ownership checks, locking and recovery."""
from datetime import datetime, timezone
import json
import shutil
from core import WorkbenchError, local_path, atomic_write, operation_lock

STATE = ".latex-ai/installation.json"
TRANSACTION = ".latex-ai/transaction.json"


def encoded(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"

def read(project, name):
    path = local_path(project, name)
    # A write destination must not be redirected even within the project.
    cursor = project / name
    while cursor != project:
        if cursor.is_symlink():
            raise WorkbenchError(f"Refusing symlink destination: {name}")
        cursor = cursor.parent
    if path.exists() and not path.is_file():
        raise WorkbenchError(f"Expected a file: {name}")
    return path.read_text(encoding="utf-8") if path.exists() else None


def publish(project, name, text):
    """Write installer text in the line endings the file already uses.

    Planning reads files with normalized newlines so one comparison serves every platform; the
    owner's CRLF file must not come back as LF, or a whole authored file shows up as changed.
    """
    path = project / name
    if path.is_file():
        data = path.read_bytes()
        crlf = data.count(b"\r\n")
        if crlf > data.count(b"\n") - crlf:
            text = text.replace("\n", "\r\n")
    atomic_write(path, text)


def installation_lock(project):
    return operation_lock(project, "installation")


def pending_transaction(project):
    if read(project, TRANSACTION) is not None:
        raise WorkbenchError("Unfinished installation transaction; run latex-ai-init recover PROJECT before continuing",
                             hint="recovery restores the previous files and refuses to overwrite subsequent local edits")


def recover(project):
    """Roll back an interrupted transaction; callers hold the installation lock."""
    text = read(project, TRANSACTION)
    if text is None:
        return False
    journal = json.loads(text)
    updates = journal.get("updates") if isinstance(journal, dict) and journal.get("schema_version") == 1 else None
    if not isinstance(updates, list) or not updates:
        raise WorkbenchError("Damaged installation transaction journal; preserve it for manual recovery")
    names = set()
    for update in updates:
        if (not isinstance(update, dict) or set(update) != {"path", "before", "after"}
                or not isinstance(update["path"], str) or not isinstance(update["after"], str)
                or update["before"] is not None and not isinstance(update["before"], str)):
            raise WorkbenchError("Damaged installation transaction entry")
        name = update["path"]
        resolved = local_path(project, name)
        if (resolved == local_path(project, TRANSACTION) or resolved.is_relative_to(project / ".git")
                or resolved in names):
            raise WorkbenchError("Invalid installation transaction path")
        names.add(resolved)
        if read(project, name) not in (update["before"], update["after"]):
            raise WorkbenchError(f"Recovery would overwrite a subsequent edit: {name}; reconcile with the journal first")
    for update in reversed(updates):
        current = read(project, update["path"])
        if current == update["before"]:
            continue
        if current != update["after"]:
            raise WorkbenchError(f"Concurrent edit during recovery: {update['path']}")
        path = project / update["path"]
        if update["before"] is None:
            path.unlink()
        else:
            publish(project, update["path"], update["before"])
    (project / TRANSACTION).unlink()
    return True


def apply(project, updates):
    with installation_lock(project):
        return apply_locked(project, updates)


def apply_locked(project, updates):
    pending_transaction(project)
    if not updates:
        return None
    # The manifest commits the installation version only after all other files.
    updates = sorted(updates, key=lambda update: update["path"] == STATE)
    for update in updates:
        if read(project, update["path"]) != update["before"]:
            raise WorkbenchError(f"File changed after planning: {update['path']}; nothing applied")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = project / ".latex-ai" / "backups" / stamp
    for update in updates:
        if update["before"] is not None:
            read(project, str((backup / update["path"]).relative_to(project)))
    for update in updates:
        if update["before"] is not None:  # the original bytes, not their normalized reading
            destination = backup / update["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local_path(project, update["path"]), destination)
    atomic_write(local_path(project, TRANSACTION), encoded({"schema_version": 1, "updates": updates}))
    try:
        for update in updates:
            if read(project, update["path"]) != update["before"]:
                raise WorkbenchError(f"Concurrent edit detected: {update['path']}")
            publish(project, update["path"], update["after"])
    except BaseException:
        try:
            recover(project)
        except BaseException:
            pass  # retain the journal; recovery will diagnose any intervening edits
        raise
    (project / TRANSACTION).unlink()
    return str(backup.relative_to(project)) if backup.exists() else None

