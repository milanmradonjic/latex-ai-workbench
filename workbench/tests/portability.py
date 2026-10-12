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
TOOLS = ("python3", "make", "latexmk", "pdflatex", "lualatex", "xelatex", "chktex", "bibtex", "biber")

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

    def init(name, root, *flags):
        run(name + "-init", root, [sys.executable, str(CLI), "init", str(root), *flags])

    def config(root, change):
        path = root / ".latex-ai.json"
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data, indent=2) + "\n")

    pdf = create("pdflatex-bibtex", {
        "paper.tex": "\\documentclass{article}\n\\begin{document}\n\\section{Test}\\label{sec:test}\nSee Section~\\ref{sec:test} and fixture~\\cite{fixture}.\n\\bibliographystyle{plain}\n\\bibliography{bib/references}\n\\end{document}\n",
        "bib/references.bib": BIB,
    })
    init("pdflatex", pdf)
    run("pdflatex-check", pdf, ["make", "check"])
    run("pdflatex-artifact", pdf, ["make", "pdf-artifact"])
    if not (pdf / ".latex-ai/artifacts/documents/manuscript/document.pdf").is_file():
        raise RuntimeError("Missing collected PDF")
    run("pdflatex-audit", pdf, [sys.executable, str(CLI), "audit", str(pdf)])
    run("pdflatex-upgrade", pdf, [sys.executable, str(CLI), "upgrade", str(pdf)])
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

    lua = create("lua-biber-multifile", {
        "paper.tex": "% !TeX program = lualatex\n\\documentclass{article}\n\\usepackage[backend=biber]{biblatex}\n\\addbibresource{bib/references.bib}\n\\begin{document}\n\\input{chapters/result}\n\\printbibliography{}\n\\end{document}\n",
        "chapters/result.tex": "\\section{Result}\\label{sec:result}\nSee Section~\\ref{sec:result} and fixture~\\autocite{fixture}.\n",
        "bib/references.bib": BIB,
        ".vscode/settings.json": '{"editor.tabSize": 3, "latex-workshop.latex.autoBuild.run": "never"}\n',
    })
    init("lua", lua)
    config(lua, lambda c: c["modules"]["bibliography"].update(export={"path": "bib/references.bib", "required": True, "format": "biblatex"}))
    run("lua-biber-check", lua, ["make", "check"])
    if json.loads((lua / ".vscode/settings.json").read_text())["editor.tabSize"] != 3:
        raise RuntimeError("Editor preference lost")

    nested = create("xelatex-nested", {"source/thesis.v1.tex": PLAIN})
    init("xelatex", nested, "--engine", "xelatex")
    config(nested, lambda c: c["modules"]["latex"]["documents"]["manuscript"].update(output_dir="build"))
    run("xelatex-check", nested, ["make", "check"])
    run("xelatex-upgrade", nested, [sys.executable, str(CLI), "upgrade", str(nested)])
    run("xelatex-artifact", nested, ["make", "pdf-artifact"])

    custom_make = "pdf:\n\tlatexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex\n"
    custom = create("existing-build", {"paper.tex": PLAIN, "Makefile": custom_make,
                                         "AGENTS.md": "Preserve this project's semantic policy.\n",
                                         ".github/workflows/custom.yml": "name: Existing workflow\non: workflow_dispatch\n"})
    init("existing", custom, "--engine", "pdflatex", "--build-command", '["make", "pdf"]')
    if not (custom / "Makefile").read_text().startswith(custom_make):
        raise RuntimeError("Existing Makefile overwritten")
    run("existing-check", custom, ["make", "-j2", "check"])
    run("existing-upgrade", custom, [sys.executable, str(CLI), "upgrade", str(custom)])
    run("existing-audit", custom, [sys.executable, str(CLI), "audit", str(custom)])

    gnumake = "build:\n\tlatexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex\n"
    gnu = create("existing-gnumakefile", {"paper.tex": PLAIN, "GNUmakefile": gnumake})
    init("gnumakefile", gnu, "--engine", "pdflatex")
    if "Makefile" in {p.name for p in gnu.iterdir()} or not (gnu / "GNUmakefile").read_text().startswith(gnumake):
        raise RuntimeError("Active GNUmakefile was not preserved")
    run("gnumakefile-check", gnu, ["make", "check"])
    run("gnumakefile-upgrade", gnu, [sys.executable, str(CLI), "upgrade", str(gnu)])
    run("gnumakefile-audit", gnu, [sys.executable, str(CLI), "audit", str(gnu)])

    # Compiler-dependent failure checks bypass lint intentionally to prove
    # unresolved citations/references fail after a successful PDF build.
    bad = create("integrity-negative", {"paper.tex": PLAIN})
    init("negative", bad, "--no-lint")
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

    notebook = create("notes-only", {})
    init("notes-only", notebook, "--profile", "notebook")
    run("notes-only-doctor", notebook, ["make", "doctor"])
    run("notes-only-check", notebook, ["make", "check"])
    run("notes-only-audit", notebook, [sys.executable, str(CLI), "audit", str(notebook)])
    if (notebook / ".latex-ai/latex.py").exists() or (notebook / ".vscode").exists():
        raise RuntimeError("Notes-only project acquired a LaTeX/editor module")

    numerical = create("numerics-no-tex", {})
    shutil.copytree(PACKAGE / "examples/decay", numerical, dirs_exist_ok=True)
    init("numerical", numerical)
    run("numerical-doctor", numerical, ["make", "doctor"])
    run("numerical-run", numerical, ["make", "run", "TASK=decay"])
    run("numerical-figure", numerical, ["make", "figure", "TASK=decay"])
    run("numerical-check", numerical, ["make", "check"])
    run("numerical-freshness", numerical, ["make", "freshness"])
    run("numerical-audit", numerical, [sys.executable, str(CLI), "audit", str(numerical)])
    # Change parameters, prove read-only stale propagation, then refresh explicitly.
    parameters = numerical / "parameters.json"
    original = parameters.read_bytes()
    value = json.loads(original)
    value["gamma"] = 2.0
    parameters.write_text(json.dumps(value))
    before = {p.relative_to(numerical).as_posix(): p.read_bytes() for p in numerical.rglob("*") if p.is_file()}
    run("numerical-stale", numerical, ["make", "freshness"], expected=1, diagnostic="upstream task is stale")
    after = {p.relative_to(numerical).as_posix(): p.read_bytes() for p in numerical.rglob("*") if p.is_file()}
    if before != after:
        raise RuntimeError("Freshness inspection modified files")
    run("numerical-stale-validate", numerical, [sys.executable, ".latex-ai/workbench.py", "validate", "--files", "parameters.json"], expected=1, diagnostic="was not produced from the current parameters")
    run("numerical-refresh-run", numerical, ["make", "run", "TASK=decay"])
    run("numerical-refresh-figure", numerical, ["make", "figure", "TASK=decay"])
    run("numerical-refreshed-check", numerical, ["make", "check"])
    relocated = base / "relocated project"
    shutil.copytree(numerical, relocated)
    run("numerical-relocated-check", relocated, ["make", "check"])
    run("numerical-disable", numerical, [sys.executable, str(CLI), "configure", str(numerical), "--disable", "numerics", "--disable", "figures", "--disable", "freshness"])
    run("numerical-disabled-check", numerical, ["make", "check"])
    if not (numerical / "figures/decay.svg").is_file() or not list((numerical / "results/runs").glob("*/record.json")):
        raise RuntimeError("Module disable discarded research artifacts")

    run("mixed-upgrade", bad, [sys.executable, str(CLI), "upgrade", str(bad)])
    run("mixed-enable-notes", bad, [sys.executable, str(CLI), "configure", str(bad), "--enable", "notes"])
    run("mixed-check", bad, ["make", "check"])
    run("mixed-audit", bad, [sys.executable, str(CLI), "audit", str(bad)])

    # Named notebooks cover independent engines, receipts and exports with the
    # real lint policy. No format conversion or scientific task is involved.
    for engine in ("pdflatex", "lualatex", "xelatex"):
        name = "tex-notebook-" + engine
        project = create(name, {"notes/derivation.tex": PLAIN})
        init(name, project, "--profile", "tex-notebook", "--engine", engine)
        run(name + "-register", project, [sys.executable, str(CLI), "configure", str(project),
                                         "--document", "derivation", "--root", "notes/derivation.tex", "--engine", engine])
        run(name + "-check", project, ["make", "-j4", "check"])
        for target in ("notebook", "derivation"):
            run(name + "-export-" + target, project, ["make", "latex-ai-pdf-artifact", "DOC=" + target])
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
        run(name + "-audit", project, [sys.executable, str(CLI), "audit", str(project)])

    mixed_notes = create("mixed-tex-notes", {})
    shutil.copytree(PACKAGE / "examples/tex-notes", mixed_notes, dirs_exist_ok=True)
    init("mixed-tex-notes", mixed_notes)
    run("mixed-tex-notes-check", mixed_notes, ["make", "check"])
    run("mixed-tex-notes-export", mixed_notes, ["make", "latex-ai-pdf-artifact", "DOC=derivation"])
    if not (mixed_notes / ".latex-ai/artifacts/documents/derivation/document.pdf").is_file():
        raise RuntimeError("Mixed notes example failed to export its named PDF")
    run("mixed-tex-notes-fragment-validation", mixed_notes,
        [sys.executable, ".latex-ai/workbench.py", "validate", "--files", "notes/state.tex"])
    run("mixed-tex-notes-audit", mixed_notes, [sys.executable, str(CLI), "audit", str(mixed_notes)])
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
