"""Optional LaTeX and bibliography backend; no GUI or network operations."""
from collections import Counter
import contextlib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import os
import tempfile
import time
import processes
import guide
from core import BACKENDS, CONFIG, EXPORT_FORMATS, MAKEFILES, OUTPUT_SUFFIXES, WorkbenchError, damaged_text, read_tex, local_path, read_json, run, atomic_write, path_name, operation_lock, document_paths, input_name, tracked_name, file_identity, input_identity

SEPARATOR = "\x1f"

def output_paths(project, config):
    return document_paths(project, config["root"], config.get("output_dir"))


def tex_without_comments(source):
    lines = []
    for line in source.splitlines():
        comment = re.search(r"(?<!\\)(?:\\\\)*%", line)
        lines.append(line[:comment.end() - 1] if comment else line)
    return "\n".join(lines)


def source_tree(project, root):
    """Conservative literal include traversal; the compiler remains authoritative."""
    todo, seen, result = [root], set(), []
    while todo:
        path = todo.pop()
        if path in seen or not path.is_file():
            continue
        if not path.resolve().is_relative_to(project.resolve()):
            continue
        seen.add(path)
        text = tex_without_comments(read_tex(path))
        result.append((path, text))
        for match in re.finditer(r"\\(?:input|include|subfile)\s*\{([^{}\\]+)\}", text):
            name = match[1]
            if not Path(name).suffix:
                name += ".tex"
            # Standard LaTeX resolves inputs relative to the main document;
            # local fallback also supports common import/subfile layouts.
            options = [root.parent / name, path.parent / name]
            todo.extend(p.resolve() for p in options if p.is_file())
    return result


def declared_bibs(project, config):
    root = local_path(project, config["root"]) if config.get("root") else None
    files = {local_path(project, p) for p in config.bibliography.get("files", [])}
    for _, text in source_tree(project, root) if root else []:
        for match in re.finditer(r"\\(?:bibliography|addbibresource)(?:\[[^\]]*\])?\s*\{([^{}\\]+)\}", text):
            for name in match[1].split(","):
                name = name.strip()
                if re.match(r"https?://", name):
                    raise WorkbenchError("Remote bibliography resource would break offline/CI builds")
                if not name.endswith(".bib"):
                    name += ".bib"
                path = root.parent / name
                files.add(local_path(project, str(path.relative_to(project))))
    export = config.bibliography.get("export")
    if export and (export.get("required", True) or local_path(project, export["path"]).exists()):
        files.add(local_path(project, export["path"]))
    return sorted(files)


def bib_keys(text, name):
    """Check entry boundaries/keys without pretending to validate field semantics.

    BibTeX validates actual expressions and required fields. Brace-delimited
    values may contain literal quotes, parentheses and percent characters.
    """
    if damaged_text(text):
        raise WorkbenchError(f"NUL or merge conflict marker in {name}")
    keys, pos = [], 0
    header = re.compile(r"@([A-Za-z]+)\s*([({])")
    while pos < len(text):
        match = header.search(text, pos)
        if not match:
            break
        # Ignore ordinary percent comment lines outside entries.
        line = text[text.rfind("\n", 0, match.start()) + 1:match.start()]
        if line.lstrip().startswith("%"):
            pos = text.find("\n", match.end())
            if pos < 0:
                break
            continue
        kind, opening = match[1].lower(), match[2]
        closing = "}" if opening == "{" else ")"
        start, i, depth, quoted, escaped = match.end(), match.end(), 0, False, False
        while i < len(text):
            char = text[i]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"' and depth == 0:
                quoted = not quoted
            elif char == "{":
                depth += 1
            elif char == "}" and depth:
                depth -= 1
            elif char == closing and depth == 0 and not quoted:
                break
            i += 1
        if i == len(text):
            raise WorkbenchError(f"Unterminated @{kind} entry in {name}")
        body = text[start:i]
        if kind not in {"string", "preamble", "comment"}:
            if "," not in body:
                raise WorkbenchError(f"Missing entry key/field separator in {name}")
            key = body.split(",", 1)[0].strip()
            if not key or re.search(r"[\s{},=]", key):
                raise WorkbenchError(f"Invalid bibliography key {key!r} in {name}")
            keys.append(key)
        pos = i + 1
    if "@" in text and not header.search(text):
        raise WorkbenchError(f"No recognizable bibliography entries in {name}")
    return keys


def bibliography_check(project, config):
    seen, digests = {}, {}
    export = config.bibliography.get("export")
    # BibTeX compares keys case-insensitively ("Repeated entry"); where it does not
    # process the file, folding would reject valid projects.
    fold = config.bibliography.get("backend", "none") == "bibtex"
    for path in declared_bibs(project, config):
        if not path.is_file():
            raise WorkbenchError(f"Missing bibliography file: {path.relative_to(project)}")
        data = path.read_bytes()
        keys = bib_keys(data.decode("utf-8-sig"), path.relative_to(project))
        if export and path == local_path(project, export["path"]) and export.get("required", True) and not keys:
            raise WorkbenchError(f"Required Zotero export has no entries: {export['path']}")
        for key in keys:
            identity = key.lower() if fold else key
            if identity in seen:
                first, where = seen[identity]
                alias = f" (same key as {first!r}; BibTeX ignores case)" if first != key else ""
                raise WorkbenchError(f"Duplicate bibliography key {key!r}{alias}: {where} and {path.relative_to(project)}")
            seen[identity] = (key, path.relative_to(project))
        digests[path] = hashlib.sha256(data).hexdigest()
    return digests


def chktex_warnings(project, config):
    """ChkTeX's findings as records, read from a machine format so that they can be compared with a baseline."""
    root = local_path(project, config["root"])
    if not shutil.which("chktex"):
        raise WorkbenchError("Required tool not found: chktex", hint="make doctor lists every tool this project needs")
    arguments = [*config.get("lint", {}).get("args", []), root.name]
    print("+ chktex -q " + " ".join(arguments), flush=True)
    fields = SEPARATOR.join(("%f", "%l", "%n", "%m", "%r%s%t")) + "\n"  # file, line, warning number, message, the source line
    done = subprocess.run(["chktex", "-q", "-f", fields, *arguments], cwd=root.parent, capture_output=True, text=True, errors="replace")
    rows = []
    for line in done.stdout.splitlines():
        parts = line.split(SEPARATOR)
        if len(parts) == 5 and parts[1].isdigit() and parts[2].isdigit():
            source = (root.parent / parts[0]).resolve()
            name = source.relative_to(project.resolve()).as_posix() if source.is_relative_to(project.resolve()) else parts[0]
            rows.append({"file": name, "line": int(parts[1]), "warning": int(parts[2]), "message": parts[3].strip(), "text": parts[4].strip()})
    # ChkTeX exits 0 without findings and 2 or 3 with them. A gate that cannot read its checker must fail, not pass.
    if done.returncode not in (0, 2, 3) or (done.returncode != 0 and not rows):
        raise WorkbenchError(f"Could not read ChkTeX's result (exit status {done.returncode}): " + (done.stderr.strip() or done.stdout.strip() or "no output")[-400:])
    for note in done.stderr.splitlines():  # ChkTeX's own remarks (for example about over-long lines) are passed on, not hidden
        if note.strip():
            print("ChkTeX note: " + note.strip())
    return rows


def baseline_path(config):
    return config.lint["baseline"]


def load_baseline(project, config):
    """Accepted warnings as a Counter keyed by (file, warning number, source line), or None without a baseline."""
    name = baseline_path(config)
    path = local_path(project, name)
    if not path.is_file():
        return None
    data = read_json(path, name)
    entries = data.get("accepted") if isinstance(data, dict) and data.get("schema_version") == 1 else None
    if not isinstance(entries, list) or any(not isinstance(e, dict) or not isinstance(e.get("file"), str) or not isinstance(e.get("warning"), int)
                                            or not isinstance(e.get("text"), str) or not isinstance(e.get("count"), int) or e["count"] < 1 for e in entries):
        raise WorkbenchError(f"{name} is not a lint baseline this release can read", hint=f"recreate it with {baseline_command(project, config)} (the project owner's decision)")
    accepted = Counter()
    for entry in entries:
        accepted[(entry["file"], entry["warning"], entry["text"])] += entry["count"]
    return accepted


def document_command(project, config, action):
    """The Make command that performs an action for this document, spelled as this project names it."""
    return f"make {guide.command_name(project, action) or action} DOC={config.name}"


def baseline_command(project, config):
    return document_command(project, config, "lint-baseline")


def write_baseline(project, config):
    """Record today's warnings as accepted. Explicit and the owner's decision: it is how an existing paper
    adopts the style gate without silencing the checker, and the gate stays in force for every new line."""
    rows = chktex_warnings(project, config)
    name = baseline_path(config)
    path = local_path(project, name)
    if not rows and not path.exists():
        print("ChkTeX reports no warnings: no baseline is needed")
        return
    counts = Counter((row["file"], row["warning"], row["text"]) for row in rows)
    data = {"schema_version": 1, "tool": "chktex",
            "note": "Style warnings the project's owner accepted when this baseline was written. The check fails only on warnings not listed here; "
                    "a line that is edited counts as new. Refreshing this file is the owner's decision.",
            "accepted": [{"file": file, "warning": number, "text": text, "count": count} for (file, number, text), count in sorted(counts.items())]}
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Accepted {len(rows)} warning(s) in {len({row['file'] for row in rows})} file(s) as the baseline: {name}")
    print("New warnings still fail the check. Keep this file in version control; refreshing it later is a decision for the project's owner.")


def lint(project, config):
    """The style gate. Without a baseline every ChkTeX warning fails; with one, only warnings it does not list."""
    if not config.lint.get("enabled", True):
        print("ChkTeX disabled explicitly in project configuration")
        return
    accepted = load_baseline(project, config)
    remaining = Counter(accepted or {})
    new = []
    for row in chktex_warnings(project, config):
        key = (row["file"], row["warning"], row["text"])
        if remaining[key] > 0:
            remaining[key] -= 1
        else:
            new.append(row)
    for row in new:
        print(f"{row['file']}:{row['line']}: warning {row['warning']}: {row['message']}")
        print("    " + row["text"])
    if accepted is not None:
        known, gone = sum(accepted.values()) - sum(remaining.values()), sum(remaining.values())
        print(f"ChkTeX: {known} warning(s) accepted by {baseline_path(config)}" + (f"; {gone} accepted warning(s) no longer occur (refreshing the baseline drops them)" if gone else ""))
        if new:
            raise WorkbenchError(f"ChkTeX reported {len(new)} new warning(s) beyond the accepted baseline",
                                 hint=f"correct the lines listed above. Accepting more warnings means refreshing the baseline ({baseline_command(project, config)}), "
                                      "which is the project owner's decision, not a way to get a green result")
    elif new:
        raise WorkbenchError(f"ChkTeX reported {len(new)} warning(s), and each one fails the check", hint=(
            f"correct them, or fit the checker to this manuscript: a .chktexrc beside it, or lint args in .latex-ai.json (for example [\"-n8\"] silences "
            f"warning 8 everywhere). To adopt the check on an existing paper without silencing anything, record today's warnings as accepted with "
            f"{baseline_command(project, config)}: only new ones fail from then on. Setting lint enabled to false turns the check off. Each of these is a "
            "decision for the project's owner, not a way to get a green result"))


def make_build(config):
    command = config.get("build_command") or []
    return bool(command) and Path(command[0]).name in {"make", "gmake"}


RECEIPT_SCHEMA = 3  # certifies recorder PWD resolution and protected input discovery


# Timestamps are coarse (a kernel tick, seconds on some filesystems and network mounts): a file whose
# change time is this close to a moment is treated as possibly written after it, as Git treats racy entries.
SETTLED_NS = 2_000_000_000
DIGESTS = {}  # per invocation: one command hashes each unchanged input once; nothing survives the process


def input_digest(project, name):
    """The content of an input, read through a link that leaves the project."""
    path = project.resolve() / name  # a tracked name may be a link that leaves the project: its content is read through it
    return file_digest(path) if path.is_file() else None


def file_digest(path):
    """SHA-256 of a file, hashed once per invocation while the file stays as it is."""
    stat = path.stat()
    key = (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if key in DIGESTS:
        return DIGESTS[key]
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    # Every write changes the change time, so an entry keyed by it cannot hide a change, unless the write fell
    # within the same timestamp tick as the one recorded: recently changed files are hashed afresh each time.
    if time.time_ns() - max(stat.st_mtime_ns, stat.st_ctime_ns) > SETTLED_NS:
        DIGESTS[key] = digest
    return digest


def written_during(project, name, before, started):
    """Whether a changed input may have been written after the build began, so that the compilation that read it
    cannot be shown to have read its present content.

    An input hashed when the build began (``before``) that differs now was written during it, whatever its
    timestamps say. An input discovered only now (the compiler's recorder lists it) is certified as it is when
    its change time precedes the build, since every write sets the change time; one that does not exist was
    never read.
    """
    if name in before:
        return True
    path = project.resolve() / name
    return path.exists() and (started is None or path.stat().st_ctime_ns >= started - SETTLED_NS)


def declared_inputs(project, config):
    """Files matched by the document's declared manuscript_inputs patterns."""
    names = set()
    for pattern in config.get("validation", {}).get("manuscript_inputs", []):
        names.update(filter(None, (input_name(project, path) for path in project.glob(pattern) if path.is_file())))
    return names


def command_files(project, config, authored=False, existing=True):
    """Recognised command files. Planning can include deleted candidates without resolving links."""
    root, names = project.resolve(), set()
    command = config.get("build_command") or []
    script = 1
    executable = Path(command[0]).name if command else ""
    if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", executable):
        while script < len(command) and command[script].startswith("-"):
            option = command[script]
            if option == "--":
                script += 1
                break
            if option.startswith(("-c", "-m")):
                script = len(command)
                break
            script += 2 if option in {"-W", "-X", "--check-hash-based-pycs"} else 1
    elif executable in {"sh", "bash", "dash", "zsh", "ksh", "node", "perl", "ruby"}:
        while executable in {"sh", "bash", "dash", "zsh", "ksh"} and script < len(command) and re.fullmatch(r"-[abefhkmnptuvxBCEHPT]+", command[script]):
            script += 1
        if script < len(command) and command[script] == "--":
            script += 1
    else:
        script = len(command)
    makefile_next, make_options = False, True
    for index, argument in enumerate(command):
        makefile = False
        if make_build(config) and index:
            if makefile_next:
                makefile_next = False
                makefile = True
            elif make_options and argument in {"-f", "--file", "--makefile"}:
                makefile_next = True
                continue
            elif make_options and argument.startswith(("-f", "--file=", "--makefile=")):
                argument = argument[2:] if argument.startswith("-f") else argument.partition("=")[2]
                makefile = True
            elif argument == "--":
                make_options = False
        if authored and index and index != script and not makefile:
            continue
        if not argument.startswith("-") or makefile or index in {0, script}:
            resource = (root / argument).resolve() if existing else Path(os.path.abspath(root / argument))
            if resource.is_relative_to(root) and (not existing or resource.is_file()):
                names.add(resource.relative_to(root).as_posix())
    return names


def input_roles(project, config):
    """Source wins over policy when a file is both displayed/consumed and build control."""
    sources, authored = static_inputs(project, config)
    previous = read_receipt(project, config)
    recorded = set(recorded_inputs(project, config, previous)) | current_recorder_inputs(project, config)
    roles = previous.get("input_roles", {})
    if not isinstance(roles, dict):
        roles = {}
    sources.update(name for name in recorded if roles.get(name) == "source" or
                   roles.get(name) != "make-policy" and Path(name).name not in MAKEFILES)
    commands = command_files(project, config)
    command_sources = command_files(project, config, authored=True)
    commands.update(command_sources)
    authored.update(command_sources)
    sources.update(name for name in commands
                   if not (make_build(config) and Path(name).name in MAKEFILES))  # a Makefile is policy, not source
    result = {}
    for name in MAKEFILES if make_build(config) else ():
        if (project / name).is_file():
            result[path_name(project, name)] = "make-policy"
            authored.add(name)
    for name in (".latexmkrc", "latexmkrc"):
        if (project / name).is_file():
            sources.add(name)
            authored.add(name)
    result.update({tracked_name(project, name): "source" for name in sources})
    _, _, stem = output_paths(project, config)
    outputs = {str(stem) + suffix for suffix in OUTPUT_SUFFIXES}
    authored = {tracked_name(project, name) for name in authored}
    # A suffix does not make a file generated: a displayed train.log or example.idx is source.
    return {name: role for name, role in sorted(result.items())
            if (str(project.resolve() / name) not in outputs and not name.startswith(".latex-ai/")) or name in authored}


def build_inputs(project, config):
    return {name: input_digest(project, name)
            for name, role in input_roles(project, config).items()}


def build_outputs(project, config):
    _, _, stem = output_paths(project, config)
    return {suffix: file_digest(Path(str(stem) + suffix)) if Path(str(stem) + suffix).is_file() else None
            for suffix in (".pdf", ".log")}


def receipt_path(config):
    return f".latex-ai/artifacts/documents/{config.name}/build-receipt.json"


def read_receipt(project, config):
    try:
        value = json.loads(local_path(project, receipt_path(config)).read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def recorded_inputs(project, config, receipt):
    """One safe interpretation of durable dependency names in current receipts."""
    identity = receipt.get("identity")
    inputs = receipt.get("inputs")
    if (receipt.get("schema_version") != RECEIPT_SCHEMA or not isinstance(identity, dict)
            or identity.get("root") != path_name(project, config["root"])
            or not isinstance(inputs, dict)):
        return {}
    try:
        for name, digest in inputs.items():
            if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                return {}
            if tracked_name(project, name) != name:
                return {}
    except (WorkbenchError, OSError, TypeError):
        return {}
    return inputs


def build_identity(project, config):
    """What a verified receipt certifies: the compiled target, its compiler and its bibliography
    declarations. Presentation and policy settings (the default document, lint) are not part of
    it, so changing them leaves the build current; changed input files are compared separately."""
    try:
        _, _, stem = output_paths(project, config)
        bib = config.get("bibliography", {})
        if not isinstance(bib, dict) or not isinstance(bib.get("files", []), list):
            return None
        if not all(isinstance(name, str) for name in bib.get("files", [])):
            return None
        if bib.get("backend", "none") not in BACKENDS:
            return None
        export = bib.get("export")
        if export is not None:
            if (not isinstance(export, dict) or not isinstance(export.get("path"), str)
                    or export.get("format") not in EXPORT_FORMATS
                    or not isinstance(export.get("required", True), bool)):
                return None
            local_path(project, export["path"])
        command = config.get("build_command")
        if command is not None and (not isinstance(command, list) or not command
                or not all(isinstance(arg, str) and arg for arg in command)):
            return None
        return {"root": path_name(project, config["root"]), "engine": config.get("engine", "pdflatex"),
                "output": stem.relative_to(project.resolve()).as_posix(), "build_command": config.get("build_command"),
                "bibliography": {"files": sorted(path_name(project, name) for name in bib.get("files", [])),
                                 "backend": bib.get("backend", "none"), "export": bib.get("export")}}
    except (WorkbenchError, KeyError, TypeError, ValueError):
        return None  # an unreadable recorded configuration certifies nothing


def receipt_matches(project, config, receipt):
    identity = build_identity(project, config)
    return (receipt.get("schema_version") == RECEIPT_SCHEMA and receipt.get("status") == "verified"
            and identity is not None and receipt.get("identity") == identity
            and receipt.get("inputs") == build_inputs(project, config)
            and receipt.get("outputs") == build_outputs(project, config))


def receipt_state(project, config, receipt=None):
    """current, running, failed (or interrupted), stale or missing: one reading for status, plans and reports."""
    receipt = read_receipt(project, config) if receipt is None else receipt
    if not receipt:
        return "missing"
    if receipt.get("status") == "running":
        return "running" if owner_alive(receipt) else "failed"
    if receipt.get("status") == "failed":
        return "failed"
    return "current" if receipt_matches(project, config, receipt) else "stale"


def stale_reasons(project, config, receipt):
    """Why a verified receipt no longer fits the project, in the words status prints: which settings, which
    sources and which outputs differ. Never empty for a receipt that ``receipt_matches`` refuses."""
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        return ["recorded by another workbench version; rebuild to record it again"]
    identity, recorded = build_identity(project, config), receipt.get("identity")
    if identity is None or not isinstance(recorded, dict):
        return ["the recorded build settings cannot be read; rebuild to record them again"]
    reasons = []
    settings = sorted(key for key in identity.keys() | recorded.keys() if identity.get(key) != recorded.get(key))
    if settings:
        reasons.append("build settings changed: " + ", ".join(settings))
    changed = differing(receipt.get("inputs") if isinstance(receipt.get("inputs"), dict) else {}, build_inputs(project, config))
    if changed:
        reasons.append("changed since the build: " + summary(changed))
    _, _, stem = output_paths(project, config)
    now, was = build_outputs(project, config), receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}
    for suffix in sorted(now.keys() | was.keys()):
        if now.get(suffix) != was.get(suffix):
            name = Path(str(stem) + suffix).relative_to(project.resolve()).as_posix()
            reasons.append(f"output missing: {name}" if now.get(suffix) is None else f"output changed since the build: {name}")
    return reasons or ["the build record does not certify this build; rebuild to record it again"]


def build(project, config):
    with operation_lock(project, "build"):
        return perform_build(project, config)


process_token = processes.token
process_alive = processes.alive
group_alive = processes.group_alive


def owner_alive(receipt):
    """The build is still in progress: its owner, or the compiler process group it started, is running."""
    ownership = build_ownership(receipt)
    return bool(ownership["owner_alive"] or ownership["compiler_groups"])


def build_ownership(receipt):
    """One live-process interpretation for ownership guards and user diagnostics."""
    groups = receipt.get("compiler_groups")
    return {"owner_pid": receipt.get("owner_pid"),
            "owner_alive": process_alive(receipt.get("owner_pid"), receipt.get("owner_token")),
            "compiler_groups": [group["pid"] for group in (groups if isinstance(groups, list) else [])
                                if isinstance(group, dict) and group_alive(group.get("pid"), group.get("token"))]}


def record_compiler_group(project, config, group, locked=False):
    """Make the compiler's process group part of the build's ownership before waiting for it."""
    with contextlib.nullcontext() if locked else operation_lock(project, "build-ownership", wait=True):
        for name in (".latex-ai/artifacts/active-build.json", receipt_path(config)):
            path = local_path(project, name)
            try:
                state = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            if isinstance(state, dict):
                groups = state.get("compiler_groups", [])
                groups = [item for item in groups if isinstance(item, dict) and group_alive(item.get("pid"), item.get("token"))]
                groups.append({"pid": group, "token": process_token(group)})
                atomic_write(path, json.dumps({**state, "compiler_groups": groups}))


def assert_build_idle(project):
    path = local_path(project, ".latex-ai/artifacts/active-build.json")
    if not path.exists():
        return
    try:
        state = json.loads(path.read_text())
        if not isinstance(state, dict):
            raise ValueError("expected an object")
    except (OSError, ValueError) as error:
        raise WorkbenchError("Cannot read active build ownership; inspect the local issue report before rebuilding") from error
    if owner_alive(state):
        raise WorkbenchError("Another build is active for this project; wait for it to finish")


def output_identities(project, config):
    identities = {}
    for suffix in (".pdf", ".log"):
        path = Path(str(output_paths(project, config)[2]) + suffix)
        stat = path.stat() if path.is_file() else None
        identities[suffix] = stat and [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
    return identities


def prepare_build(project, config, owner):
    with operation_lock(project, "build-ownership", wait=True):
        return prepare_build_locked(project, config, owner)


def prepare_build_locked(project, config, owner):
    started = time.time_ns()  # before any input is hashed: a write after this point is never certified unseen
    active_path = local_path(project, ".latex-ai/artifacts/active-build.json")
    assert_build_idle(project)
    previous = read_receipt(project, config)
    if previous.get("status") == "running" and owner_alive(previous):
        raise WorkbenchError("Another build is active for this project; wait for it to finish")
    from output_transaction import recover
    recover(project, config["name"])
    inputs = build_inputs(project, config)
    reusable = receipt_matches(project, config, previous)
    state = {"schema_version": RECEIPT_SCHEMA, "status": "running", "owner_pid": owner,
             "owner_token": process_token(owner), "configuration": config, "identity": build_identity(project, config), "inputs": inputs,
             "input_roles": input_roles(project, config),
             "identities": output_identities(project, config), "reusable": reusable, "started_ns": started,
             "previous_outputs": previous.get("outputs") if reusable else None}
    # Invalidate before any compilation/preflight can fail. Failed attempts cannot
    # revive an older receipt by restoring old source bytes.
    atomic_write(active_path, json.dumps({"owner_pid": owner, "owner_token": process_token(owner),
                                        "receipt": receipt_path(config)}))
    atomic_write(local_path(project, receipt_path(config)), json.dumps(state))
    source_ids = {input_identity(project, name) for name in inputs}
    stem = output_paths(project, config)[2]
    for suffix in OUTPUT_SUFFIXES:
        output = Path(str(stem) + suffix)
        if file_identity(output) in source_ids:
            raise WorkbenchError(f"Compiler output aliases a source input: {output.relative_to(project)}")
    for pattern in config.get("inputs", []):
        if not any(path.is_file() for path in project.glob(pattern)):
            raise WorkbenchError(f"Missing declared document input: {pattern}")
    state["bibliography"] = {str(path): digest for path, digest in bibliography_check(project, config).items()}
    backend = config.get("bibliography", {}).get("backend", "none")
    if backend != "none" and not shutil.which(backend):
        raise WorkbenchError(f"Required bibliography backend not found: {backend}")
    atomic_write(local_path(project, receipt_path(config)), json.dumps(state))
    return state


@contextlib.contextmanager
def compiler_start(project):
    with operation_lock(project, "build-ownership", wait=True):
        yield


def run_compiler(project, config, command, cwd=None, env=None, display=True):
    return run(command, cwd or project, env,
               started=lambda group: record_compiler_group(project, config, group, locked=True),
               startup=compiler_start(project), display=display)


def unverified_outputs(state, outputs, identities):
    """Outputs the build left untouched although no reusable verified receipt covers them."""
    return [suffix for suffix, before in state["identities"].items()
            if identities[suffix] is not None and before == identities[suffix]
            and not (state["reusable"] and outputs[suffix] == state["previous_outputs"][suffix])]


def regenerate_outputs(project, config):
    """Move unverified outputs aside and run the build once more. If it does not recreate
    them, they are put back and the check fails: nothing unverified is certified or lost."""
    _, _, stem = output_paths(project, config)
    from output_transaction import OutputTransaction
    paths = [Path(str(stem)+suffix) for suffix in (".pdf", ".log")]
    transaction = OutputTransaction(project, config['name'], paths)
    try:
        transaction.displace()
        names = " and ".join(entry['original'] for entry in transaction.entries)
        print(f"No verified receipt covers the existing {names}; regenerating", flush=True)
        compile_document(project, config, force=True)
        missing = transaction.restore_missing()
        if missing:
            name = missing[0].relative_to(project.resolve()).as_posix()
            raise WorkbenchError(f"Build did not regenerate {name}; no matching verified receipt establishes freshness",
                                 hint=f"the configured build must produce {name} from the current sources; "
                                      "the previous file was put back unchanged")
        return transaction
    except BaseException:
        transaction.rollback()
        raise


def differing(before, after):
    """Names whose digest differs between two input snapshots, including names present in only one."""
    absent = object()
    return sorted(name for name in before.keys() | after.keys() if before.get(name, absent) != after.get(name, absent))


def summary(names, limit=4):
    return ", ".join(names[:limit]) + (f" and {len(names) - limit} more" if len(names) > limit else "")


def finish_build(project, config, owner):
    state = read_receipt(project, config)
    if (state.get("status") != "running" or state.get("owner_pid") != owner or not owner_alive(state)
            or state.get("configuration") != config or "bibliography" not in state):
        raise WorkbenchError(f"Build preparation is missing or changed; rerun {document_command(project, config, 'build')}")
    after = {str(path): digest for path, digest in bibliography_check(project, config).items()}
    if state["bibliography"] != after:
        raise WorkbenchError("Bibliography changed during compilation; let export finish, then rerun make check")
    observed = build_inputs(project, config)
    outputs = build_outputs(project, config)
    identities = output_identities(project, config)
    transaction = None
    changed = differing(state["inputs"], observed)
    # An input the compiler discovered only now (a figure found by graphicx's extension search, a local
    # package), and that nobody wrote since the build began, was read as it is: its hash certifies it.
    written = [name for name in changed if written_during(project, name, state["inputs"], state.get("started_ns"))]
    if written or config.get("build_command") and unverified_outputs(state, outputs, identities):
        # Inputs may be written by the build itself: a Make rule that generates a table or a figure the
        # document includes, or a source edited while the compiler ran. No compilation has yet been proved
        # to read their present content. Snapshot them, compile once more with every hash protected, and
        # require the whole set to stay unchanged.
        # The project's own build may likewise judge its outputs current (Make or a custom script compares
        # timestamps) although no verified receipt covers them: after a configuration change, a workbench
        # upgrade, a Makefile edit or a build outside the workbench. Regenerate them once instead of failing
        # until someone deletes them, as latexmk -g does for a native build.
        if written:
            print(f"Inputs were written during the build ({summary(written)}); rebuilding once with their hashes protected", flush=True)
        transaction = regenerate_outputs(project, config)
        settled = build_inputs(project, config)
        if settled != observed:
            unstable = differing(observed, settled)
            raise WorkbenchError(f"Build inputs changed during execution: {summary(unstable)}",
                                 hint="a file the build rewrites on every run cannot be certified; make the generator write only when the content "
                                      "differs, or edit sources only while no build is running, then rerun to establish freshness")
        outputs = build_outputs(project, config)
        identities = output_identities(project, config)
    _, _, stem = output_paths(project, config)
    for suffix, before_identity in state["identities"].items():
        after_identity = identities[suffix]
        if after_identity is None or (before_identity == after_identity and not
                (state["reusable"] and outputs[suffix] == state["previous_outputs"][suffix])):
            name = Path(str(stem) + suffix).relative_to(project.resolve()).as_posix()
            raise WorkbenchError(f"Build did not {'write' if after_identity is None else 'rewrite'} {name}; no matching verified receipt establishes freshness",
                                 hint=f"the build command must produce {name} from the current sources; check its output location "
                                      f"(output_dir in {CONFIG}) and that it writes both the PDF and its log")
    verify(project, config, check_receipt=False, report=False)  # a gate only: the check that follows reports once
    atomic_write(local_path(project, receipt_path(config)), json.dumps({"schema_version": RECEIPT_SCHEMA, "status": "verified",
                 "identity": build_identity(project, config), "inputs": observed, "input_roles": input_roles(project, config), "outputs": outputs}, indent=2) + "\n")
    if transaction:
        transaction.commit()
    local_path(project, ".latex-ai/artifacts/active-build.json").unlink(missing_ok=True)


def perform_build(project, config):
    active = local_path(project, ".latex-ai/artifacts/active-build.json")
    before = active.read_bytes() if active.is_file() else None
    try:
        return execute_build(project, config)
    finally:
        try:
            state = json.loads(active.read_text())
            if (active.read_bytes() != before and state.get("owner_pid") == os.getpid()
                    and state.get("owner_token") == process_token(os.getpid())):
                path = local_path(project, state["receipt"])
                receipt = read_receipt(project, config)
                if receipt.get("status") == "running":
                    atomic_write(path, json.dumps({**receipt, "status": "failed"}))
                if not owner_alive({**state, "owner_pid": None}):
                    active.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


def execute_build(project, config):
    if os.environ.get("LATEX_AI_BUILD_ACTIVE"):
        raise WorkbenchError("Recursive build_command: do not delegate to make build, all, check, validate or document-check")
    state = prepare_build(project, config, os.getpid())
    compile_document(project, config, force=not state["reusable"])
    finish_build(project, config, os.getpid())


def compile_document(project, config, force=False):
    """One compiler path for initial execution and protected regeneration."""
    root, out, stem = output_paths(project, config)
    env = {**os.environ, "LATEX_AI_BUILD_ACTIVE": "1",
           "LATEX_AI_BUILD_FORCE": "1" if force else "0"}
    if config.get("build_command"):
        run_compiler(project, config, config["build_command"], env=env)
    else:
        args = ["latexmk", "-pdf", "-synctex=1", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "-recorder", "-cd"]
        # A first/invalidated receipt requires actual regeneration, even when
        # latexmk's timestamp database believes existing artifacts are current.
        if force:
            args.append("-g")
        if config.get("output_dir"):
            out.mkdir(parents=True, exist_ok=True)
            args.append(f"-outdir={out}")
        before_log = output_identities(project, config)[".log"]
        try:
            run_compiler(project, config, [*args, str(root)], env=env)
        except WorkbenchError as error:
            if not str(error).startswith("Command failed"):
                raise  # for example a missing tool: its own message and hint apply
            raise compiler_error(project, config, stem, error, before_log) from error


LOG_LINE = 79  # TeX wraps its log at this many characters (max_print_line), so a long message goes on in the next line


def log_location(project, log):
    return log.relative_to(project.resolve()).as_posix() if log.is_relative_to(project.resolve()) else str(log)


def read_the_log(project, config, log):
    """The Hint of a failure whose details are in the compiler's log: where it is, and what to run once the source is right."""
    rerun = document_command(project, config, "document-check") if config.get("name") else "make check"
    return f"the full log is {log_location(project, log)}; correct the source, then run {rerun}"


def compiler_error(project, config, stem, error, before_log):
    """Lead with the first TeX error from this run's log rather than the compiler command line."""
    log = Path(str(stem) + ".log")
    first = None
    changed = False
    try:
        if output_identities(project, config)[".log"] == before_log:
            raise OSError("this invocation did not change its log")
        changed = True
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, line in enumerate(lines):
            if re.match(r"^(?:\S.*?:\d+: |! )", line):
                first = line
                while len(lines[number]) == LOG_LINE and number + 1 < len(lines):
                    number += 1
                    first += lines[number]
                first = first.strip()
                break
    except OSError:
        pass
    if first is None:
        log_hint = f" or {log_location(project, log)}" if changed else ""
        rerun = document_command(project, config, "document-check") if config.get("name") else "make check"
        return WorkbenchError(str(error), hint=f"read the compiler output above{log_hint}, correct the source, then run {rerun}")
    return WorkbenchError(f"{config['root']}: {first}", hint=read_the_log(project, config, log))


FATAL_LOG = (
    r"(?:Citation|Reference)\s+.+?\s+(?:on page \d+\s+)?undefined",
    r"There were undefined (?:citations|references)",
    r"Label\s+.+?multiply defined",
    r"There were multiply-defined labels",
    r"Please \(re\)run BibTeX",
    r"Rerun to get (?:cross-references|citations|outlines) right",
    r"Label\(s\) may have changed",
    r"No file .+?\.bbl",
    r"(?:^|\n)!\s",
    r"Warning--(?:I didn't find a database entry|Repeated entry|empty .+? in)",
    r"Warning--.*(?:not found|doesn't exist)",
    r"I couldn't open database file",
    r"I was expecting a [`'](?:,|=|\})",
)


def verify(project, config, check_receipt=True, report=True):
    bibliography_check(project, config)
    build_command = document_command(project, config, "build")
    if check_receipt and not receipt_matches(project, config, read_receipt(project, config)):
        raise WorkbenchError(f"Build freshness is unverified; run {build_command} to establish a verified receipt")
    _, _, stem = output_paths(project, config)
    log = stem.parent / (stem.name + ".log")
    if not log.is_file():
        raise WorkbenchError(f"No compiler log; run {build_command} first or correct output_dir")
    fatal, warnings = [], []
    logs = [log]
    if config.get("bibliography", {}).get("backend", "none") != "none":
        logs.append(stem.parent / (stem.name + ".blg"))
    for path in logs:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fatal.extend(f"{path.name}: {m[0].strip()}" for pattern in FATAL_LOG for m in re.finditer(pattern, text, re.I | re.M))
        warnings.extend(f"{path.name}: {line.strip()}" for line in text.splitlines()
                        if re.search(r"Warning|Overfull|Underfull", line))
    if report:
        for warning in dict.fromkeys(warnings):
            print("WARNING: " + warning)
    if fatal:
        raise WorkbenchError("Unresolved manuscript integrity errors:\n" + "\n".join(dict.fromkeys(fatal)), hint=read_the_log(project, config, log))
    pdf = stem.parent / (stem.name + ".pdf")
    if not pdf.is_file():
        raise WorkbenchError(f"Missing or invalid PDF: {pdf}")
    with pdf.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise WorkbenchError(f"Missing or invalid PDF: {pdf}")
    if report:
        print("Citation/reference integrity checks passed")


def artifact(project, config):
    with operation_lock(project, "build"):
        assert_build_idle(project)
        return collect_artifact(project, config)


def collect_artifact(project, config):
    receipt = read_receipt(project, config)
    verify(project, config)
    _, _, stem = output_paths(project, config)
    pdf = stem.parent / (stem.name + ".pdf")
    if not pdf.is_file():
        raise WorkbenchError("Build the document before collecting its PDF", hint=f"run {document_command(project, config, 'build')} first")
    name = config.get("name")
    destination = f".latex-ai/artifacts/documents/{name}/document.pdf"
    path = local_path(project, destination)
    if path != project.resolve() / destination or (path.exists() and path.stat().st_nlink > 1):
        raise WorkbenchError(f"Refusing linked PDF export destination: {destination}",
                             hint="move the link aside before exporting; it may point to an authored file")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    descriptor, temporary = tempfile.mkstemp(prefix=".latex-ai-tmp-", dir=path.parent)
    os.close(descriptor)
    try:
        shutil.copyfile(pdf, temporary)
        if not receipt_matches(project, config, receipt) or file_digest(Path(temporary)) != receipt['outputs']['.pdf']:
            raise WorkbenchError("Build changed during PDF export; the previous export was preserved",
                                 hint=f"wait for writes to finish, then run {document_command(project, config, 'build')} and export again")
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print("Collected " + destination)


def recorder_inputs(project, recorder):
    """Canonical local inputs in a TeX recorder, using its recorded execution directory.

    PWD is authoritative for relative INPUT lines, including custom commands
    launched outside the root's directory. Missing context cannot certify a
    relative input. A link inside the project that leads out of it is tracked under its own
    spelling; system files outside the project remain an adapter boundary.
    """
    dependencies, directory = set(), None
    for line in recorder.read_text(errors="replace").splitlines():
        if line.startswith("PWD "):
            directory = Path(line[4:])
            if not directory.is_absolute() or "\0" in line:
                raise WorkbenchError(f"Invalid compiler working directory in {recorder}",
                                     hint="rerun the compiler with a valid recorder; declare hidden inputs in the document's inputs")
        elif line.startswith("INPUT "):
            resource = Path(line[6:])
            if not resource.is_absolute():
                if directory is None:
                    raise WorkbenchError(f"Relative compiler input without PWD in {recorder}",
                                         hint="rerun the compiler with a valid recorder; declare hidden inputs in the document's inputs")
                resource = directory / resource
            name = input_name(project, resource)
            if name is not None:
                dependencies.add(name)
    return dependencies


GRAPHICS = (".pdf", ".png", ".jpg", ".jpeg", ".jbig2", ".jb2", ".mps", ".eps", ".ps")  # graphicx's search, all drivers


def current_recorder_inputs(project, config):
    fls = Path(str(output_paths(project, config)[2]) + ".fls")
    return recorder_inputs(project, fls) if fls.is_file() and fls.resolve().is_relative_to(project) else set()


def static_inputs(project, config):
    """Potential static dependencies and explicit source reads; mentioning a filename is not reading it."""
    root, _, _ = output_paths(project, config)
    dependencies = {config["root"], *config.get("bibliography", {}).get("files", [])}
    dependencies.update(declared_inputs(project, config))
    export = config.bibliography.get("export")
    if export:
        dependencies.add(export["path"])
    authored = set(dependencies)
    sources = source_tree(project, root)
    graphics_paths = {""}
    for _, text in sources:
        for group in re.findall(r"\\graphicspath\s*\{((?:\s*\{[^{}\\]*\}\s*)*)\}", text):
            graphics_paths.update(re.findall(r"\{([^{}]*)\}", group))
    for path, text in sources:
        dependencies.add(path.relative_to(project).as_posix())
        authored.add(path.relative_to(project).as_posix())
        literals = re.findall(r"\\(?:includegraphics|lstinputlisting|verbatiminput|VerbatimInput|pgfplotstableread|csvreader|input|include|subfile)(?:\[[^\]]*\])?\s*\{([^{}\\]+)\}", text)
        literals += [name if Path(name).suffix else name + ".tex" for name in
                      re.findall(r"\\(?:input|include|subfile)\s*\{([^{}\\]+)\}", text)]
        literals += re.findall(r"\\inputminted(?:\[[^\]]*\])?\s*\{[^{}]+\}\s*\{([^{}\\]+)\}", text)
        resources = list(literals)
        # Macro-agnostic: any braced literal that looks like a file name (\verbatiminput,
        # \pgfplotstableread, \csvreader, ...). Unlike the recorder file below, this is
        # available on a fresh checkout. Extra candidates only add conservative checks.
        resources += re.findall(r"\{\s*\"?([^{}\\\n]+?\.[A-Za-z0-9]{1,8})\"?\s*\}", text)
        resources += re.findall(r"\{\s*([^{}\\\s]*(?:Makefile|makefile|GNUmakefile))\s*\}", text)
        # BibTeX reads the style itself, so the recorder of the TeX run never lists it. Only a style
        # that exists beside the document counts: creating a local one later still changes the input set.
        styles = [name if name.endswith(".bst") else name + ".bst"
                  for name in re.findall(r"\\bibliographystyle\s*\{([^{}\\]+)\}", text)]
        # Files the compiler chooses by search, so a source names them without their extension: graphicx tries
        # each graphics extension in turn, and a package or class beside the document shadows the system one.
        # Those that exist are inputs; one created later changes the input set and so the build's validity.
        styles += [str(Path(folder) / name.strip()) + extension
                   for name in re.findall(r"\\includegraphics\*?(?:\[[^\]]*\])*\s*\{([^{}\\]+)\}", text)
                   for folder in sorted(graphics_paths) for extension in (("",) if Path(name.strip()).suffix else GRAPHICS)]
        styles += [name.strip() + suffix for command, suffix in (("usepackage|RequirePackage", ".sty"), ("documentclass|LoadClass", ".cls"))
                   for names in re.findall(r"\\(?:" + command + r")\s*(?:\[[^\]]*\])?\s*\{([^{}\\]+)\}", text)
                   for name in names.split(",") if name.strip()]
        for names, existing in ((resources, False), (styles, True)):
            for name in names:
                for parent in (root.parent, path.parent):
                    if (tracked := input_name(project, parent / name)) is not None and (not existing or (parent / name).is_file()):
                        dependencies.add(tracked)
                        if existing or name in literals:
                            authored.add(tracked)
    return dependencies, authored


def manuscript_dependencies(project, config, include_receipt=True, command_inputs=True):
    dependencies, _ = static_inputs(project, config)
    if include_receipt:
        dependencies.update(recorded_inputs(project, config, read_receipt(project, config)))
    dependencies.update(current_recorder_inputs(project, config))
    if command_inputs:
        dependencies.update(command_files(project, config))
    return dependencies
