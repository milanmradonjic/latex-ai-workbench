# Several TeX documents in one project

This synthetic example has a paper, an independent TeX derivation, a TeX
notebook, a shared macro file and a Markdown navigation index.

Copy this directory into a fresh project, then run:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/project
cd /path/to/project
make doctor
make check
make document-check DOC=derivation
make pdf-artifact DOC=derivation
```

Setup preserves the included schema-4 configuration. It enables local PDF
export while leaving the editor integration disabled. ChkTeX is required
by the example's default lint policy.

Edit `notes/state.tex`: its consumer is `notebook`. Edit `notes/shared.tex`:
all three documents consume it. Preview selection without requiring Git history:

```sh
python3 .latex-ai/workbench.py plan --files notes/state.tex --json
python3 .latex-ai/workbench.py plan --files notes/shared.tex --json
```

Build receipts and PDFs are independent under
`.latex-ai/artifacts/documents/<id>/`. Source notes stay editable and are
never touched by the workbench. See the [TeX notes guide](../../docs/tex-notes.md).
