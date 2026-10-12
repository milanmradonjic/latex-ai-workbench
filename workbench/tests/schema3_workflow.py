"""Install and host the public mixed-notes example using generated document CI."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from adapters import workflow

FIXTURE = "workbench/examples/tex-notes"
DESTINATION = PACKAGE.parent / ".github/workflows/schema3-acceptance.yml"


def configuration():
    config = json.loads((PACKAGE / "examples/tex-notes/.latex-ai.json").read_text())
    config["integrations"]["ci"]["enabled"] = True
    config["validation"] = {"package": None}
    return config


def generated_workflow():
    """Only relocate generated commands; document selection remains the adapter's."""
    text = workflow(configuration()).replace("name: LaTeX AI Workbench", "name: Schema-3 acceptance", 1)
    text = text.replace("    env:\n", f"    defaults:\n      run:\n        working-directory: {FIXTURE}\n    env:\n", 1)
    text = text.replace("LATEX_AI_BASE: ${{ github.event.pull_request.base.sha || github.event.before }}", "LATEX_AI_BASE: '0000000000000000000000000000000000000000'")
    text = text.replace("      - name: Select validation\n", "      - name: Install synthetic reference\n        working-directory: .\n        run: python3 -B workbench/tests/schema3_workflow.py --install\n      - name: Select validation\n", 1)
    text = text.replace("          run: |\n", f"          run: |\n            cd {FIXTURE}\n")
    text = text.replace("          path: .latex-ai/", f"          path: {FIXTURE}/.latex-ai/")
    text += "      - name: Verify document state and selection\n        run: python3 -B ../../tests/schema3_workflow.py --verify\n"
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--generate", action="store_true")
    group.add_argument("--install", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    fixture = PACKAGE / "examples/tex-notes"
    if args.generate:
        DESTINATION.write_text(generated_workflow())
    elif args.install:
        (fixture / ".latex-ai.json").write_text(json.dumps(configuration(), indent=2) + "\n")
        subprocess.run([sys.executable, "-B", str(PACKAGE / "latex-ai-init"), "init", str(fixture)], check=True)
    else:
        def report(*words):
            value = json.loads(subprocess.check_output([sys.executable, "-B", str(fixture / ".latex-ai/workbench.py"), *words, "--json"], cwd=fixture))
            return value["result"] if words[0] == "documents" else value
        states = report("documents")
        assert len(states) == 3 and all(row["state"] == "current" for row in states), states
        for row in states:
            path = fixture / f".latex-ai/artifacts/documents/{row['id']}/document.pdf"
            assert path.read_bytes().startswith(b"%PDF-"), path
        assert report("plan", "--files", "notes/state.tex")["documents"] == ["notebook"]
        assert set(report("plan", "--files", "notes/shared.tex")["documents"]) == {"paper", "derivation", "notebook"}
        print("Three current documents, independent PDF exports, and shared/fragment selection verified")


if __name__ == "__main__":
    main()
