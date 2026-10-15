#!/usr/bin/env python3
"""Real compiler tests in newly created synthetic projects; never initialize Git."""
import json
import argparse
import os
from test_support import fixture_env
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil

PACKAGE = Path(__file__).resolve().parents[1]
CLI = PACKAGE / "latex-ai-init"
PARENT = Path(os.environ.get("LATEX_AI_PORTABILITY_PARENT", tempfile.gettempdir()))
TOOLS = ("python3", "make", "latexmk", "pdflatex", "chktex", "bibtex")

BIB = """% Synthetic validation fixture, not a literature reference.
@misc{fixture,
  title = {Synthetic test fixture},
  note = {Not a literature reference},
  year = {2000}
}
"""
PLAIN = "\\documentclass{article}\n\\begin{document}\nSynthetic portability test.\n\\end{document}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-parent", type=Path, default=PARENT)
    args = parser.parse_args()
    base = Path(tempfile.mkdtemp(prefix="latex-ai-portability-", dir=args.output_parent))
    logs = base / "test-logs"
    logs.mkdir()
    missing = [name for name in TOOLS if not shutil.which(name)]
    if missing:
        report = {"project_directory": str(base), "results": [], "all_passed": False,
                  "status": "blocked", "missing_tools": missing}
        (base / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print("Portability checks blocked; missing tools: " + ", ".join(missing), file=sys.stderr)
        print("Preflight report: " + str(base / "report.json"), file=sys.stderr)
        return 2
    # TeX caches stay inside the synthetic tree, including Lua font caches.
    env = fixture_env(TEXMFVAR=str(base / "tex-cache"), TEXMFCACHE=str(base / "tex-cache"), PYTHONDONTWRITEBYTECODE="1")
    results = []

    def run(name, cwd, argv, expected=0, diagnostic=None):
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True)
        (logs / (name + ".log")).write_text(proc.stdout + proc.stderr)
        passed = proc.returncode == expected if expected == 0 else proc.returncode != 0
        if diagnostic:
            passed = passed and diagnostic in proc.stdout + proc.stderr
        results.append({"test": name, "passed": passed, "exit_status": proc.returncode})
        # Persist progress before a failed fixture stops subsequent dependent tests.
        (base / "report.json").write_text(json.dumps({"project_directory": str(base), "results": results,
                                                    "all_passed": False, "status": "running" if passed else "failed"}, indent=2) + "\n")
        print(("PASS " if passed else "FAIL ") + name, flush=True)
        if not passed:
            print((proc.stdout + proc.stderr)[-4000:])
            raise RuntimeError(f"Failed {name}; full log: {logs / (name + '.log')}")

    def create(name, files):
        root = base / name
        root.mkdir()
        for filename, content in files.items():
            path = root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return root

    def declare(root, root_file="paper.tex", backend="none", bibliography=(), lint=True, command=None):
        path = root / ".latex-ai.json"
        if not path.exists():
            path.write_text(json.dumps({"schema_version": 4, "default_document": "manuscript",
                "documents": {"manuscript": {"root": root_file, "backend": backend, "lint": {"enabled": lint},
                    "build_command": command, "output_dir": "." if command else None}},
                "bibliography": {"files": list(bibliography)}, "integrations": {"editor": False}}, indent=2) + "\n")

    def init(name, root, **settings):
        declare(root, **settings)
        run(name + "-init", root, [sys.executable, str(CLI), "init", str(root)])

    def config(root, change):
        path = root / ".latex-ai.json"
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data, indent=2) + "\n")

    pdf = create("pdflatex-bibtex", {
        "paper.tex": "\\documentclass{article}\n\\begin{document}\n\\section{Test}\\label{sec:test}\nSee Section~\\ref{sec:test} and fixture~\\cite{fixture}.\n\\bibliographystyle{plain}\n\\bibliography{bib/references}\n\\end{document}\n",
        "bib/references.bib": BIB,
    })
    init("pdflatex", pdf, backend="bibtex", bibliography=("bib/references.bib",))
    run("pdflatex-check", pdf, ["make", "check"])
    run("pdflatex-artifact", pdf, ["make", "pdf-artifact"])
    if not (pdf / ".latex-ai/artifacts/documents/manuscript/document.pdf").is_file():
        raise RuntimeError("Missing collected PDF")
    run("pdflatex-diff", pdf, [sys.executable, str(CLI), "diff", str(pdf)])
    run("pdflatex-runtime", pdf, [sys.executable, str(CLI), "runtime", str(pdf)])
    # No Git initialization is needed to prove docs-only runtime selection.
    (pdf / "README.md").write_text("Synthetic [manuscript](paper.tex) notes.\n")
    runtime = pdf / ".latex-ai/workbench.py"
    compiled_pdf = pdf / ".latex-ai/artifacts/documents/manuscript/build/paper.pdf"
    before = compiled_pdf.read_bytes()
    run("docs-only-plan", pdf, [sys.executable, str(runtime), "plan", "--files", "README.md", "--json"])
    run("docs-only-validate", pdf, [sys.executable, str(runtime), "validate", "--files", "README.md"], diagnostic="No manuscript build selected")
    if compiled_pdf.read_bytes() != before:
        raise RuntimeError("Documentation validation changed the manuscript PDF")
    (pdf / "README.md").write_text("[Broken link](missing.md)\n")
    run("docs-broken-link", pdf, [sys.executable, str(runtime), "validate", "--files", "README.md"], expected=1, diagnostic="Broken local Markdown link")
    (pdf / "README.md").write_text("Synthetic notes.\n")
    run("tex-selected-validate", pdf, [sys.executable, str(runtime), "validate", "--files", "paper.tex"], diagnostic="Citation/reference integrity checks passed")

    # The style gate on a paper that already has warnings, with the real ChkTeX: a warning fails; the baseline
    # accepts it without silencing the checker; a new warning still fails.
    clean = (pdf / "paper.tex").read_text()
    (pdf / "paper.tex").write_text(clean.replace("See Section~\\ref", "See Section \\ref"))
    run("lint-warning-fails", pdf, ["make", "lint"], expected=1, diagnostic="each one fails the check")
    run("lint-baseline-write", pdf, ["make", "lint-baseline"], diagnostic="as the baseline: .latex-ai/lint-baselines/manuscript.json")
    run("lint-baseline-accepts", pdf, ["make", "check"], diagnostic="accepted by .latex-ai/lint-baselines/manuscript.json")
    (pdf / "paper.tex").write_text((pdf / "paper.tex").read_text().replace("\\section{Test}", "A \"new\" remark.\n\\section{Test}"))
    run("lint-new-warning-fails", pdf, ["make", "lint"], expected=1, diagnostic="beyond the accepted baseline")
    (pdf / "paper.tex").write_text(clean)
    (pdf / ".latex-ai/lint-baselines/manuscript.json").unlink()

    multi = create("multifile-bibtex", {
        "paper.tex": "\\documentclass{article}\n\\begin{document}\n\\input{chapters/result}\n\\bibliographystyle{plain}\n\\bibliography{bib/references}\n\\end{document}\n",
        "chapters/result.tex": "\\section{Result}\\label{sec:result}\nSee Section~\\ref{sec:result} and fixture~\\cite{fixture}.\n",
        "bib/references.bib": BIB,
    })
    init("multifile", multi, backend="bibtex", bibliography=("bib/references.bib",))
    config(multi, lambda c: c["bibliography"].update(export={"path": "bib/references.bib", "required": True, "format": "bibtex"}))
    run("multifile-check", multi, ["make", "check"])

    nested = create("nested-root", {"source/thesis.v1.tex": PLAIN})
    init("nested", nested, root_file="source/thesis.v1.tex")
    config(nested, lambda c: c["documents"]["manuscript"].update(output_dir="build"))
    run("nested-check", nested, ["make", "check"])
    run("nested-runtime", nested, [sys.executable, str(CLI), "runtime", str(nested)])
    run("nested-artifact", nested, ["make", "pdf-artifact"])

    # A project with a build of its own: init writes beside the workflow it has, the project's Make target goes in after it.
    custom = create("existing-build", {"paper.tex": PLAIN, ".github/workflows/custom.yml": "name: Existing workflow\non: workflow_dispatch\n"})
    init("existing", custom, command=["make", "pdf"])
    with (custom / "Makefile").open("a") as stream:
        stream.write("\npdf:\n\tlatexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex\n")
    if sorted(p.name for p in (custom / ".github/workflows").iterdir()) != ["custom.yml"]:
        raise RuntimeError("A workflow appeared or went")
    run("existing-check", custom, ["make", "-j2", "check"])
    run("existing-runtime", custom, [sys.executable, str(CLI), "runtime", str(custom)])
    run("existing-diff", custom, [sys.executable, str(CLI), "diff", str(custom)], expected=0)

    # A file the project has is never merged into: init refuses it, and writes nothing.
    gnu = create("existing-gnumakefile", {"paper.tex": PLAIN, "GNUmakefile": "build:\n\tlatexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex\n"})
    declare(gnu)
    run("gnumakefile-refused", gnu, [sys.executable, str(CLI), "init", str(gnu)], expected=2, diagnostic="GNUmakefile")
    if {p.name for p in gnu.iterdir()} != {"paper.tex", "GNUmakefile", ".latex-ai.json"}:
        raise RuntimeError("A refused init wrote files")

    # Compiler-dependent failure checks bypass lint intentionally to prove
    # unresolved citations/references fail after a successful PDF build.
    bad = create("integrity-negative", {"paper.tex": PLAIN})
    init("negative", bad, lint=False)
    run("negative-baseline", bad, ["make", "check"])
    for name, body in [
        ("undefined-reference", "Missing~\\ref{absent}."),
        ("duplicate-label", "\\section{One}\\label{same}\n\\section{Two}\\label{same}"),
        ("undefined-citation", "Missing~\\cite{absent}."),
    ]:
        (bad / "paper.tex").write_text("\\documentclass{article}\n\\begin{document}\n" + body + "\n\\end{document}\n")
        run(name, bad, ["make", "check"], expected=1, diagnostic="Unresolved manuscript integrity errors")
    (pdf / "bib/references.bib").write_text(BIB + BIB)
    run("duplicate-bibliography-key", pdf, ["make", "bib-check"], expected=1, diagnostic="Duplicate bibliography key")
    (pdf / "bib/references.bib").write_text('@misc{fixture,title={Truncated}\n')
    run("truncated-bibliography", pdf, ["make", "bib-check"], expected=1, diagnostic="Unterminated")
    (pdf / "bib/references.bib").write_text(BIB)
    (bad / "paper.tex").write_text(PLAIN)
    run("negative-recovered", bad, ["make", "check"])

    notebook = create("notes-only", {"notes/session.md": "A question.\n"})
    run("notes-only-refused", notebook, [sys.executable, str(CLI), "init", str(notebook)], expected=2,
        diagnostic="Installation requires an explicit .latex-ai.json")
    if sorted(p.name for p in notebook.iterdir()) != ["notes"]:
        raise RuntimeError("Refused non-LaTeX installation wrote files")

    run("mixed-runtime", bad, [sys.executable, str(CLI), "runtime", str(bad)])
    run("mixed-check", bad, ["make", "check"])
    run("mixed-diff", bad, [sys.executable, str(CLI), "diff", str(bad)])

    # Named documents cover independent receipts and exports with the
    # real lint policy. No format conversion is involved.
    notebook_source = "\\documentclass{article}\n\\begin{document}\n\\section*{Notebook}\n\\input{session-state.tex}\n\\end{document}\n"
    name = "named-documents"
    project = create(name, {"main.tex": PLAIN, "notes/derivation.tex": PLAIN, "notes/notebook.tex": notebook_source,
                            "notes/session-state.tex": "\\section*{Current question}\n"})
    init(name, project, root_file="main.tex")
    for document, root in (("notebook", "notes/notebook.tex"), ("derivation", "notes/derivation.tex")):
        config(project, lambda c, document=document, root=root: c["documents"].update({document: {"root": root}}))
    run(name + "-check", project, ["make", "-j4", "check"])
    for target in ("notebook", "derivation"):
        run(name + "-export-" + target, project, ["make", "pdf-artifact", "DOC=" + target])
        if not (project / f".latex-ai/artifacts/documents/{target}/document.pdf").is_file():
            raise RuntimeError("Missing named PDF: " + target)
    receipts = project / ".latex-ai/artifacts/documents"
    derivation_receipt = (receipts / "derivation/build-receipt.json").read_bytes()
    state = project / "notes/session-state.tex"
    state.write_text(state.read_text() + "\nSynthetic edited fragment.\n")
    run(name + "-fragment-validation", project, [sys.executable, ".latex-ai/workbench.py", "validate",
                                               "--files", "notes/session-state.tex"])
    if (receipts / "derivation/build-receipt.json").read_bytes() != derivation_receipt:
        raise RuntimeError("Fragment validation rebuilt an unrelated document")
    run(name + "-incremental-check", project, ["make", "-j4", "check"])
    run(name + "-diff", project, [sys.executable, str(CLI), "diff", str(project)])

    mixed_notes = create("mixed-tex-notes", {})
    shutil.copytree(PACKAGE / "examples/tex-notes", mixed_notes, dirs_exist_ok=True)
    init("mixed-tex-notes", mixed_notes)
    run("mixed-tex-notes-check", mixed_notes, ["make", "check"])
    run("mixed-tex-notes-export", mixed_notes, ["make", "pdf-artifact", "DOC=derivation"])
    if not (mixed_notes / ".latex-ai/artifacts/documents/derivation/document.pdf").is_file():
        raise RuntimeError("Mixed notes example failed to export its named PDF")
    run("mixed-tex-notes-fragment-validation", mixed_notes,
        [sys.executable, ".latex-ai/workbench.py", "validate", "--files", "notes/state.tex"])
    run("mixed-tex-notes-diff", mixed_notes, [sys.executable, str(CLI), "diff", str(mixed_notes)])
    report = {"project_directory": str(base), "results": results, "all_passed": all(r["passed"] for r in results)}
    (base / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Synthetic projects and logs: " + str(base))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
