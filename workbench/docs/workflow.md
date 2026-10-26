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
    edit --> validate["Batch complete<br/>make validate"]
    edit -. "Optional PDF preview" .-> preview["make build DOC=name"]
    preview -. "Continue the agreed batch" .-> edit
    edit -. "Optional check preview" .-> plan["make validation-plan"]
    plan --> validate
    validate --> passed{"Selected checks pass?"}
    passed -->|No| diagnose["Read diagnostics<br/>Correct the relevant files"]
    diagnose --> edit
    passed -->|Yes| review["Review edits, scientific reasoning,<br/>and presentation as applicable<br/>Git checkpoint at session end or handoff"]
    review --> done["Change ready for review or delivery"]
    done -. "Next small request in the same session" .-> edit
    review -. "Optional manuscript delivery" .-> export["Export current PDF<br/>make pdf-artifact DOC=name"]
    classDef command fill:#eff6ff,stroke:#2563eb,color:#172554
    classDef human fill:#f1f5f9,stroke:#64748b,color:#0f172a
    classDef result fill:#f0fdf4,stroke:#16a34a,color:#14532d
    class inspect,preview,plan,validate,export command
    class edit,diagnose,review human
    class done result
```

`make validate` prints its own plan. Use `make validation-plan` separately only
when the preview affects a decision. Run validation at the end of the requested
batch, before delivery or Git handoff; a single editing request ends at delivery.
A PDF preview during an ongoing batch is not completed validation.

Git inspection follows the editing session, which may span successive requests.
Inspect branch/status and relevant diffs at its start, and review the relevant
diff and status at its completion or Git handoff. Between those checkpoints,
read the current target passage before patching it and refresh relevant Git
checks when state/context changes. Completing a validation batch does not itself
end this session. See [successive edits](daily-use.md#git-inspection-during-successive-edits).

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
  `build_command` is invoked each time and may implement incremental work using
  the [freshness hint](configuration.md#build-receipts-and-recovery). Reference verification and lint still run. Numerical tests and visual review
  remain task-specific work.

A **current build** means its inputs and outputs match its receipt. It does not
mean lint passed or the science is correct. A **Files pass** does not certify a PDF.
See the [complete routing rules](validation.md) and [build receipts](architecture.md).

For deliberate single-document work, use `make document-check DOC=name` or
`make build DOC=name`. For the whole manuscript, `make check` always checks all
declared documents. See [daily use](daily-use.md) and [named documents](tex-notes.md).
