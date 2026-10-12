# Mixed Markdown and TeX notes

This synthetic example has a paper, an independent TeX derivation, a TeX
notebook, a shared macro file and a Markdown navigation index. It does not need
Pandoc because the optional Markdown rendering module is not enabled.

Copy this directory into a fresh project, then run:

```sh
python3 /path/to/workbench/latex-ai-init init /path/to/project --dry-run --diff
python3 /path/to/workbench/latex-ai-init init /path/to/project
cd /path/to/project
make latex-ai-doctor
make check
make latex-ai-document-check DOC=derivation
make latex-ai-pdf-artifact DOC=derivation
```

Setup preserves the included schema-3 configuration. It enables local PDF
export while leaving CI and editor integration disabled. ChkTeX is required
by the example's default lint policy.

Edit `notes/state.tex`: its consumer is `notebook`. Edit `notes/shared.tex`:
all three documents consume it. Preview selection without requiring Git history:

```sh
python3 .latex-ai/workbench.py plan --files notes/state.tex --json
python3 .latex-ai/workbench.py plan --files notes/shared.tex --json
```

Build receipts and PDFs are independent under
`.latex-ai/artifacts/documents/<id>/`. Source notes stay editable and are
preserved on upgrade. See the [TeX notes guide](../../docs/tex-notes.md).
