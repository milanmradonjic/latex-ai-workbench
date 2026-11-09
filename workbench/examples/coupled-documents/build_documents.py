"""Build two TeX documents that cite each other, such as an article and its supplement.

Each document reads the other's .aux file (xr-hyper), so one build is not enough:
a label that moves in one document changes the references in the other. This
adapter builds the selected document and its companion with incremental latexmk,
records which companion .aux each document last consumed, and repeats until both
have consumed the other's current state, at most MAX_ROUNDS times.

It is project-owned code, not part of the workbench runtime. Its cache records
consumed .aux states only; it never establishes that a build is valid. The
workbench decides that from its own receipt, and passes LATEX_AI_BUILD_FORCE=1
when the PDF and log must be regenerated even though nothing looks changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

# Edit these to fit the project. Both names are TeX file stems in SOURCES and
# must match the keys under "documents" in .latex-ai.json.
DOCUMENTS = ("paper", "supplement")
PROJECT = Path(__file__).resolve().parent
SOURCES = PROJECT                      # folder of the .tex files; latexmk runs here
OUTDIR = "build"                       # latexmk -outdir, and each \externaldocument{build/NAME}
BUILD = SOURCES / OUTDIR
STAMP = BUILD / "coupled-inputs.json"
INPUT_PATTERNS = ("*.tex", "*.bib", "*.cls", "*.bst", "*.sty", "figures/*")
MAX_ROUNDS = 6


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    """Every file whose change makes the cached state untrustworthy, by content."""
    paths = {p for pattern in INPUT_PATTERNS for p in SOURCES.glob(pattern) if p.is_file()}
    paths |= {Path(__file__).resolve(), PROJECT / ".latex-ai.json"}
    paths |= {p for directory in (PROJECT, SOURCES) for name in (".latexmkrc", "latexmkrc")
              if (p := directory / name).is_file()}
    return {p.relative_to(PROJECT).as_posix(): digest(p) for p in sorted(paths)}


def auxiliaries():
    return {name: digest(p) if (p := BUILD / (name + ".aux")).is_file() else None
            for name in DOCUMENTS}


def output_identities(name):
    result = []
    for suffix in (".pdf", ".log"):
        try:
            stat = (BUILD / (name + suffix)).stat()
            result.append((stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        except FileNotFoundError:
            result.append(None)
    return result


def compile_one(name, force=False, *, log):
    command = ["latexmk", "-pdf", "-synctex=1", "-interaction=nonstopmode", "-halt-on-error",
               "-file-line-error", "-recorder", "-outdir=" + OUTDIR]
    commands = []
    # A failed TeX run can leave a missing or truncated AUX while the surviving
    # build history schedules BibTeX first. Bootstrap the AUX, then run normally.
    auxiliary = BUILD / (name + ".aux")
    aux = auxiliary.read_bytes() if auxiliary.is_file() else b""
    # A bibliography needs \bibdata and \bibstyle in the AUX; documents without
    # one are never "incomplete" for lack of them.
    uses_bibliography = b"\\bibliography{" in (SOURCES / (name + ".tex")).read_bytes()
    incomplete = not aux or uses_bibliography and any(
        marker not in aux for marker in (b"\\bibdata{", b"\\bibstyle{"))
    history = any((BUILD / (name + suffix)).is_file() for suffix in (".log", ".fls", ".fdb_latexmk"))
    if incomplete and history:
        commands.append(command + ["-bibtex-", "-g"])
    if force:
        command.append("-g")
    commands.append(command)
    print(f"  {name}: {'regenerate' if force else 'incremental'}", flush=True)
    for command in commands:
        with log.open("a") as stream:
            stream.write("\n$ " + " ".join(command + [name + ".tex"]) + "\n")
            stream.flush()
            completed = subprocess.run(command + [name + ".tex"], cwd=SOURCES,
                                       stdout=stream, stderr=subprocess.STDOUT)
        if completed.returncode:
            tail = "\n".join(log.read_text(errors="replace").splitlines()[-30:])
            raise RuntimeError(f"latexmk failed for {name} (exit {completed.returncode}). "
                               f"Full output: {log}\n{tail}")


def settle(document, *, log, force=False):
    before = sources()
    original_outputs = output_identities(document)
    try:
        saved = json.loads(STAMP.read_text())
    except (OSError, ValueError):
        saved = {}
    consumed = saved.get("consumed", {}) if isinstance(saved, dict) else {}
    if not isinstance(consumed, dict):
        consumed = {}
    # A failed or interrupted invocation cannot leave a successful cache behind.
    STAMP.unlink(missing_ok=True)
    companion = dict(zip(DOCUMENTS, reversed(DOCUMENTS)))
    pending = [document, companion[document]]
    for _ in range(MAX_ROUNDS):
        for name in pending:
            imported = auxiliaries()[companion[name]]
            identities = output_identities(name)
            compile_one(name, force=None in identities, log=log)
            # Some latexmk configurations ignore changes to external AUX files.
            # A no-op cannot prove it consumed a different companion state.
            needs_import = imported is not None and consumed.get(name) != imported
            needs_receipt = force and name == document and output_identities(name) == original_outputs
            if (needs_import or needs_receipt) and output_identities(name) == identities:
                compile_one(name, force=True, log=log)
            if None in output_identities(name):
                raise RuntimeError(f"Missing PDF/log after building {name}; see {log}")
            consumed[name] = imported
            if sources() != before:
                raise RuntimeError("Source inputs changed during compilation; rerun after edits finish")
        aux = auxiliaries()
        pending = [name for name in DOCUMENTS
                   if aux[companion[name]] is None or consumed.get(name) != aux[companion[name]]]
        if not pending:
            state = json.dumps({"sources": before, "auxiliaries": aux, "consumed": consumed}, indent=2) + "\n"
            temporary = STAMP.with_suffix(".tmp")
            temporary.write_text(state)
            temporary.replace(STAMP)
            return
    raise RuntimeError(f"Cross-references did not converge after {MAX_ROUNDS} rounds; see {log}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("document", choices=DOCUMENTS)
    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)
    log = BUILD / f"{args.document}.latexmk.log"
    log.write_text("")
    print(f"Settling cross-references; full compiler output: {log}", flush=True)
    settle(args.document, log=log, force=os.environ.get("LATEX_AI_BUILD_FORCE") == "1")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)
