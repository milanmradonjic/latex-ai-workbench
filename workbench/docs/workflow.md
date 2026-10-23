# Workflow at a glance

These diagrams show the Workbench 6 workflow. GitHub renders the Mermaid diagrams
directly; their source stays editable alongside the documentation.

## Research and manuscript inputs

Research tools are explicit project operations. Run the relevant numerical tests
and review results before transferring them into the manuscript.

```mermaid
flowchart LR
    analysis["Analysis and calculations"] --> data["Checked data"]
    data --> render["Render figures<br/>and visually review them"]
    render --> figures["Approved figure files"]
    notes["Notes, reviews, and research findings"] --> transfer["Transfer approved results<br/>manually or with an agent"]
    transfer --> tex["LaTeX source"]
    classDef research fill:#f1f5f9,stroke:#64748b,color:#0f172a
    classDef manuscript fill:#eff6ff,stroke:#2563eb,color:#172554
    class analysis,data,render,notes,transfer research
    class figures,tex manuscript
```

Ordinary Markdown, JSON, and Python are working material. Workbench does not
automatically run calculations or render figures. A project's configured custom
builder still performs whatever that project explicitly declares as its build.

## The daily loop

Start from the project root. Before a risky edit or upgrade, use
[`make snapshot`](snapshots.md) to keep a recoverable copy outside the project.

```mermaid
flowchart TD
    inspect["Inspect<br/>make status, AGENTS.md, and config"] --> edit["Edit project files"]
    edit --> plan["Preview<br/>make validation-plan"]
    plan --> validate["Run<br/>make validate"]
    validate --> passed{"Selected checks pass?"}
    passed -->|No| diagnose["Read diagnostics<br/>Correct the relevant files"]
    diagnose --> edit
    passed -->|Yes| review["Review the diff, scientific reasoning,<br/>and presentation as applicable"]
    review --> done["Change ready for review or delivery"]
    review -. "Optional manuscript delivery" .-> export["Export current PDF<br/>make pdf-artifact DOC=name"]
    classDef command fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef human fill:#f1f5f9,stroke:#64748b,color:#0f172a
    classDef result fill:#f0fdf4,stroke:#16a34a,color:#14532d
    class inspect,plan,validate,export command
    class edit,diagnose,review human
    class done result
```

Export requires a current build receipt and verifies the PDF before copying it
to `.latex-ai/artifacts/documents/NAME/document.pdf`. If a manuscript build is
needed, run `make check` first. Preparing or replacing delivery copies is a
separate deliberate step; export does not replace supplied delivery PDFs.

## What validation selects

`make validation-plan` explains this decision without running checks.
`make validate` executes the selected level. Mixed changes select Full if any
non-exempt changed path requires it.

```mermaid
flowchart TD
    scope["Changed paths<br/>Git comparison or explicit file scope"] --> recovery{"Automatic comparison unavailable,<br/>or a previous build failed/interrupted?"}
    recovery -->|Yes| full["FULL<br/>File checks, then make check once<br/>Every declared document"]
    recovery -->|No| classify["Classify all changed paths<br/>Archives and patches are file-only;<br/>configured paths stay active"]
    classify --> trigger{"Any active TeX/bib/figure/data,<br/>build control, or unclassified path?"}
    trigger -->|Yes| full
    trigger -->|No| files["FILES<br/>Lightweight file and policy checks<br/>No manuscript build"]
    files --> result["Report checks and outcome"]
    full --> result
    classDef command fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef light fill:#f1f5f9,stroke:#64748b,color:#0f172a
    classDef complete fill:#fff7ed,stroke:#ea580c,color:#7c2d12
    class scope,classify,result command
    class files light
    class full complete
```

- Historical directories are named exactly `archive`, at any depth. Their contents
  remain file-only regardless of extension, except paths `.latex-ai.json` names.
  Copy or move a historical file out before making it an active build input. `.diff` and
  `.patch` files receive text-integrity checks without interpreting embedded code.
- Ordinary Markdown/JSON/Python changes get file checks. Configured builders,
  lint baselines, Makefiles, project/runtime settings, and editor integration are
  build controls even when their extension is JSON or Python.
- A clean Git comparison with no failed build selects no manuscript check.
  Without Git/history, automatic selection uses Full; explicit `--files` scope
  remains available. See [comparison and recovery](validation.md#comparison-and-recovery).
- Full validation covers every declared document, including projects with shared
  outputs or cross-references. latexmk recompiles only what changed; a configured
  `build_command` runs in full each time. Reference verification and lint still run. Numerical tests and visual review
  remain task-specific work.

A **current build** means its inputs and outputs match its receipt. It does not
mean lint passed or the science is correct. A **Files pass** does not certify a PDF.
See the [complete routing rules](validation.md) and [build receipts](architecture.md).

For deliberate single-document work, use `make document-check DOC=name` or
`make build DOC=name`. For the whole manuscript, `make check` always checks all
declared documents. See [daily use](daily-use.md) and [named documents](tex-notes.md).
