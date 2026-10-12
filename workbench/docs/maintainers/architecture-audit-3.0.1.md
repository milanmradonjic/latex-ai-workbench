# Architecture audit of workbench 3.0.1

Audited commit `7670d72` ("Repair the audited 3.0.0 defects and add a guide"), 2026-10-12.
This is an assessment and a set of proposals.

**Status after 3.0.2.** Release 3.0.2 repaired F1–F6 and F12, the lock and atomic-write
parts of F9, and the unselectable CI steps of F14 (see
[the 3.0.2 verification record](verification-3.0.2.md)). The following remain open:

- F7 and F8 (layering and the command registry)
- the other parts of F9
- F10 (planner precision)
- F11 (opaque adoption by default)
- F13 (archive layout)
- the container and SHA-pinning parts of F14
- F15 (test organisation)

These are larger refactors or need hosted or platform validation. The order of work is in [the plan after 3.0.2](plan-after-3.0.2.md).

## Verdict

The architecture is sound in its main ideas. Make is the one interface. The runtime is
vendored per project. Freshness is decided by hash receipts and not by timestamps.
Scientific runs are explicit, and the installer plans every change before it writes
anything. The safety properties it claims mostly hold, and the regression suite is
large (351 tests, all passing here).

Its main weaknesses are cost and coupling. Most of the cost sits in two places:
adopting a project's own Make recipes ("phased ownership"), and a few cross-cutting
primitives that were each written several times. The 3.0.1 repairs fixed the reported
symptoms. Two of them, though, carry costs that can be avoided: one fix removed
cross-user locking, and another doubles first builds.

| # | Finding | Kind | Priority |
|---|---|---|---|
| F1 | Per-user locks no longer exclude two users of one project; the research task lock silently does nothing for the second user | Defect (reproduced) | P0 |
| F2 | On GNU Make < 4.3 (stock macOS 3.81), an adopted-Make adapter makes **every** target fail, the project's own included | Defect (reproduced by inspection) | P0 |
| F3 | A non-UTF-8 TeX source makes `init`, `plan`, `status`, `build` fail with a bare codec error that names no file | Defect (reproduced) | P1 |
| F4 | The generated-input repair compiles every first build twice when the compiler finds an input the static scan missed (the usual case) | Optimality of a fix (measured) | P1 |
| F5 | Each input is hashed about 4 times per `document-check` | Efficiency (measured) | P2 |
| F6 | `installation.json` stores the full text of every managed file twice (536 KB, about 90% of it runtime code) | Design | P1 |
| F7 | Layering is inverted and imports are circular; `config` means two things | Structure | P2 |
| F8 | Command metadata lives in 6 tables; dispatch is a 190-line `if/elif` | Structure | P2 |
| F9 | Primitives are duplicated: 3 lock implementations, 2 atomic writers, 2 Markdown link checkers, 6 excluded-tree sets | Structure | P1 (locks) / P2 |
| F10 | The planner rebuilds **all** documents when any unreferenced `.png`/`.csv` changes | Efficiency | P2 |
| F11 | Phased Make adoption is the area with the most defects | Design risk | P1 |
| F12 | Process identity reads `/proc` only; on macOS a reused PID can keep a dead build "running" | Portability | P2 |
| F13 | The provenance archive copies all inputs and outputs on every run, and every command reads every record | Scaling | P2 |
| F14 | CI starts one TeX container per document, one after another; third-party actions are pinned to tags only | CI | P2 |
| F15 | Tests are organised by release and audit, not by component | Maintainability | P3 |

## Scope and method

- I read all runtime and installer modules: `core`, `runtime`, `documents`, `latex`,
  `research`, `task_graph`, `markdown`, `bootstrap`, `adapters`, `installation`,
  `diagnostics`, `processes`, `output_transaction`, `make_graph`, `guide`, and the
  structure of `handbook`. I also read the three workflows, the generated Makefile
  adapters, the templates and the maintainer records.
- I ran `make -C workbench test` with Python 3.13.16 and GNU Make 4.3: 351 tests,
  OK, 20 skipped. No TeX tools are installed in this environment, so the 20
  compiler-dependent tests and `make portability` did not run.
- I reproduced each finding marked "reproduced" or "measured" with throwaway projects
  in a scratch directory, using two real Unix users for F1. Nothing in the repository
  was changed.

## Architecture as built

```
            latex-ai-init (bootstrap.py)                 project Makefile (managed block)
   plan ─► adapters.py ─► installation.py (journal)         │  make <cmd>  ─►  .latex-ai/workbench.py (runtime.py)
                                                            ▼
   ┌──────────── core.py: paths, config schema, run(), locks, validation actions ────────────┐
   │ documents.py (named documents) ◄──► latex.py (receipts, build, verify, lint, bib)        │
   │ research.py + task_graph.py (runs, freshness, claims)      markdown.py (Pandoc)          │
   │ guide.py / handbook.py (help, status, guide)   diagnostics.py (faults, issue reports)    │
   │ processes.py (process identity, groups)   output_transaction.py   make_graph.py          │
   └──────────────────────────────────────────────────────────────────────────────────────────┘
   State: .latex-ai/installation.json · .latex-ai/artifacts/documents/<id>/build-receipt.json
          .latex-ai/artifacts/active-build.json · results/runs/<stamp>/record.json · $TMPDIR locks
```

Strengths worth keeping:

- **One execution contract.** Editor tasks, CI and agents all call the same Make
  commands, and `VALIDATION_ACTIONS` feeds both local validation and the generated CI.
- **Receipts by content.** Builds are certified by input and output hashes plus the
  build identity, so the PDF is never trusted just because it exists.
- **A careful installer.** It plans first and supports three-way merges. It keeps a
  journal and can roll back. It never mutates Git and preserves the original bytes
  and line endings.
- **Explicit science.** Validation never starts a run. Run records keep failed and
  interrupted attempts too.
- **Clear failure classes.** Exit 1 means an ordinary failure; exit 70 means an
  internal fault with a local report. Agents can act on that distinction.

## Findings and proposals

### F1 — Locks: the 3.0.1 per-user repair removed cross-user exclusion (P0)

**Evidence.** `core.operation_lock` (`core.py:470-498`) now puts locks in
`$TMPDIR/latex-ai-operation-locks-<uid>`. Two users who build the same shared project
therefore take *different* lock files. I reproduced this with users `alice` and `bob`.
`alice` held the `build` lock in a background process, and `bob` acquired the "same"
lock while she still held it:

```
30033 holds build lock
30034 holds build lock        ← concurrent, same project
```

`research.task_lock` (`research.py:148-174`) still uses the shared directory
`$TMPDIR/latex-ai-locks`, which the first user creates with mode `0700`. For the
second user, `open()` raises `PermissionError`. The code catches it, sets
`stream = None` and runs **unlocked without saying so**. I reproduced this too. This
is the same defect class that 3.0.1 repaired for operation locks, left in a second
copy of the code. `diagnostics.fault_dir` has the same pattern, but there it only
loses fault records.

Because the lock key is `sha256(resolved path)`, the same project reached through two
different mount paths also gets two locks. So do two processes with different
`TMPDIR` values, for example a GUI editor and a terminal.

**Impact.** Two concurrent builds or runs can interleave writes to
`active-build.json`, the receipt and the output journal. `assert_build_idle` is not a
substitute: it reads and then writes without holding a lock that both processes
share.

**Proposal.** Keep locks with the state they protect: inside the project, in the
directory that is already ignored by Git. Anyone who can write the project can then
take the lock, everyone contends on the same file, and nothing is left behind in
`/tmp`. Use one implementation for all three callers, and make it fail closed:

```python
# core.py
LOCKS = ".latex-ai/artifacts/locks"

@contextlib.contextmanager
def operation_lock(project, operation, wait=False):
    directory = project / LOCKS
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"{operation}.lock").open("a+b") as stream:
        _acquire(stream, operation, timeout=5 if wait else 0)   # flock / msvcrt, raises WorkbenchError
        try:
            yield
        finally:
            _release(stream)

# research.py
def task_lock(project, module, name):
    return operation_lock(project, f"task-{module}-{name}")   # no silent unlocked fallback
```

The mode should come from the project directory's own permissions, without `0700`.
Locks in the project also survive a change of `TMPDIR`. On NFS, `flock` is emulated
with byte-range locks on Linux 2.6.12 and later, which is good enough here. Also
replace `test_operation_locks_are_private_to_the_user` with a test that **two users
contend**.

### F2 — The adopted-Make adapter breaks every target on GNU Make < 4.3 (P0)

**Evidence.** I installed a project with `--build-command '["make","pdf"]'`. The
generated block places

```make
ifneq ($(filter manuscript,$(or $(DOC),manuscript))$(filter $(LATEX_AI_CHECK_GOALS),...),)
...
ifeq ($(filter extra-prereqs,$(.FEATURES)),)
$(error Adopted build receipts require GNU Make 4.3 or later with extra-prereqs)
endif
```

The outer condition is true whenever `DOC` is unset, so the `$(error)` is evaluated
when Make *parses* the file, for every goal. On macOS's `/usr/bin/make` (GNU Make 3.81)
that means `make pdf`, `make help` and `make status` all fail. `make pdf` is the
project's own pre-existing target. `docs/installing.md` documents the 4.3 requirement,
but the installer does not check it before rewriting the user's Makefile.

**Proposal.**

1. *Install time.* When `phased` is chosen in `adapters.make_adapter`, have the
   installer run `make --version` (or `make -p -f /dev/null` and read `.FEATURES`). If
   `extra-prereqs` is missing, refuse with a CONFLICT before writing, and suggest the
   opaque adoption from F11 or `gmake`.
2. *Run time.* Move the `$(error)` inside the inner
   `ifneq ($(filter $(LATEX_AI_BUILD_GOALS),...),)`, so it fires only for the goals
   that need phase hooks. The project's own targets and the read-only commands keep
   working.

### F3 — Non-UTF-8 TeX sources cause unexplained failures (P1)

**Evidence.** `latex.source_tree` (`latex.py:37`) and `bootstrap.discover`
(`bootstrap.py:66`) read TeX files with a strict `encoding="utf-8"`. I made a project
whose `chap.tex` is Latin-1 (`\usepackage[latin1]{inputenc}`):

```
$ latex-ai-init init l1
ERROR: 'utf-8' codec can't decode byte 0xe9 in position 3: invalid continuation byte
$ python3 .latex-ai/workbench.py plan
ERROR: 'utf-8' codec can't decode byte 0xe9 in position 3: invalid continuation byte
```

`build`, `check` and `status` hit the same path through `manuscript_dependencies`. The
message names no file. During `init`, *any* `.tex` file anywhere in the tree causes
it, including files that are not part of the manuscript.

**Proposal.** The static scan exists only to find dependency candidates, and the
compiler is authoritative. So decode leniently and say once which file is not UTF-8:

```python
def read_tex(path):
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")   # every byte maps; macro and file names are ASCII in practice
```

Use this in `source_tree`, `discover` and `declared_bibs`. In `discover`, skip
unreadable non-root files instead of aborting.

### F4 — Generated-input repair: the first build compiles twice (P1)

**Evidence.** `finish_build` (`latex.py:624-644`) runs a full protected recompilation
whenever the observed input set differs from the set hashed at preparation. Before a
first build, that set comes only from the static scan, which misses the most common
idioms. `\includegraphics{fig}` without an extension (graphicx searches
`.pdf/.png/.jpg`) and a local `\usepackage{mystyle}` are both found only by the
recorder. I measured this with the fixture compiler:

```
Inputs were generated or discovered during the build (fig.png); rebuilding once with their hashes protected
compilations: 2
```

For a native latexmk build, the second compilation adds `-g` (forced). A thesis
therefore pays twice the compile time on its first build. It pays again on every
build that adds a local package or figure. This is the 3.0.1 repair working as
designed: the cost is the price of its proof.

**Proposal: certify discovered inputs that existed unchanged before the build, and
recompile only for files written during it.** A discovered input whose inode change
time (`st_ctime_ns`) is earlier than the build's start was not modified during the
compilation. User space cannot set ctime, and every write updates it. So its hash
after the build is what the compiler read:

```python
# prepare_build_locked
state["started_ns"] = time.time_ns()

# finish_build
changed = differing(state["inputs"], observed)
written = [n for n in changed if modified_since(project, n, state["started_ns"])]
if written or (config.get("build_command") and unverified_outputs(...)):
    transaction = regenerate_outputs(project, config)        # current protected path
# names in `changed` but not in `written` are certified by `observed` directly

def modified_since(project, name, started_ns, margin_ns=2_000_000_000):
    path = project.resolve() / name
    return not path.exists() or path.stat().st_ctime_ns >= started_ns - margin_ns
```

The margin covers coarse filesystem timestamps (FAT, some network mounts) and some
clock skew. Where a project's filesystem is known to be unreliable, a configuration
switch can restore today's always-recompile behaviour. Separately, the static scan
can cheaply find more of the usual candidates: graphicx's extension search, and a
local `\usepackage`/`\documentclass` `.sty`/`.cls`. Then most first builds would
discover nothing.

### F5 — Each input is hashed about 4 times per command (P2)

**Evidence.** I instrumented `latex.input_digest` and `latex.source_tree` with a
fixture document of 5 input names (one a 50 MB figure):

| Command | `input_digest` calls | `source_tree` scans |
|---|---|---|
| `build` | 10 | 7 |
| `document-check` | 20 (4 full passes) | 10 |
| `status` | 5 | 3 |

`build_inputs`, `input_roles` and `manuscript_dependencies` are each recomputed by
`prepare_build`, `receipt_matches`, `finish_build`, `verify` and `stale_reasons`.
Hashing runs at about 1 GB/s, so this is unnoticeable for papers. It is significant
for data-heavy documents that declare input globs over gigabytes.

**Proposal.** Add a per-invocation memo keyed by stat identity. No cache outlives the
process, which keeps the existing principle:

```python
_DIGESTS = {}
def input_digest(project, name, policy=False):
    path = project.resolve() / name
    if not path.is_file():
        return None
    st = path.stat()
    key = (str(path), policy, st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    if key not in _DIGESTS:
        _DIGESTS[key] = _hash(path, policy)
    return _DIGESTS[key]
```

A file rewritten in place changes its ctime, so the memo cannot hide a change. Also
compute the dependency set once per command, and pass it to `input_roles` and
`build_inputs` instead of rescanning.

### F6 — The installation manifest duplicates every managed file (P1)

**Evidence.** `.latex-ai/installation.json` is **536 KB**. For each managed file it
stores `installed` and `upstream` as full text. For the 11 runtime files of this reference (strategy
`full`) the two strings are identical, and the same code also exists in `.latex-ai/`
and in `workbench/`. Every upgrade therefore commits a diff of about 0.5 MB to the
user's repository. That diff cannot be reviewed, and it inflates Git history in every
installed project.

For `full` files, only the comparisons `current == base` and `current == upstream`
need the stored text (`bootstrap.py:531-543`, `diagnostics.py:135-137`). The three-way
merge needs text only for `block`/`json` files and for the extendable files
(`AGENTS.md`, `.gitignore`, the Makefile).

**Proposal.** Introduce manifest `schema_version: 2`:

```json
".latex-ai/latex.py": {"strategy": "full", "sha256": "…"},
"AGENTS.md":          {"strategy": "block", "installed": "…", "upstream": "…"}
```

The upgrader keeps a small reader for v1 and writes v2. This is a manifest format
with its own version, so it is not one of the retired configuration schemas. A
locally modified runtime file can no longer be shown as a diff against the manifest,
so `--diff` should show it against `git show HEAD:<path>` when Git is available, and
otherwise print the two hashes. The expected size is about 30 KB, a reduction of
about 95%.

### F7 — Inverted layering, circular imports, and an ambiguous `config` (P2)

**Evidence.**
- `core` is meant to be the bottom layer, but it imports `documents` in three places
  (`core.py:360, 395, 535`). `documents` imports `latex` and `guide`, `latex` imports
  `guide`, and all of them import `core`. Function-local imports keep the cycle from
  failing at import time, but the dependency graph has no layering.
- A parameter named `config` holds either the project configuration or a resolved
  document view. `core.document_settings` (`core.py:353-356`) accepts both and passes
  a view through unchanged. Almost every function in `latex.py` begins by calling it
  defensively. This is why F5's recomputation is easy to miss, and why
  `build_identity` must tolerate malformed input.

**Proposal.** Three explicit layers:

1. `util` (paths, `atomic_write`, `run`, locks, process identity): no project
   knowledge.
2. `config` (schema validation, defaults, `ProjectConfig`, `DocumentView` dataclasses,
   `documents.resolve`): depends on `util` only.
3. Backends (`latex`, `research`, `markdown`) and presentation (`guide`, `handbook`):
   they take typed objects.

Backend functions then take `DocumentView` and never re-resolve it.
`guide.command_name`, which hints use to name commands, should be passed in, or
computed once per command, rather than imported by `latex`.

### F8 — Command metadata in six places (P2)

**Evidence.** The knowledge "which action exists, which module it needs, whether it
takes `--document`, and how its output is shaped" is spread over:

- `runtime.ACTIONS`
- `runtime.DOCUMENT_ACTIONS`
- the `action_module` dict in `dispatch` (`runtime.py:646-648`)
- the `required` dict in the research branch (`runtime.py:706`)
- `guide.COMMANDS`, which describes itself as "the single source"
- the hard-coded `--document` set in `adapters.module_make_targets`
  (`adapters.py:224`)

These already disagree. `DOCUMENT_ACTIONS` includes `check`, `verify` and the
build-phase actions, while the adapter set does not. `dispatch` is a 190-line
`if/elif`. `runtime.py:23-30` also injects lazy backend wrappers through `globals()`.

**Proposal.** Use one registry and dispatch from it:

```python
@dataclass(frozen=True)
class Action:
    name: str
    handler: Callable[[Context], int]
    module: str | None = None        # require(...) before running
    document: bool = False           # accepts --document / DOC
    native_json: bool = False        # plan/modules/freshness
    make: Command | None = None      # short/reserved names for guide and adapters

ACTIONS = {a.name: a for a in (Action("build", build_cmd, "latex", document=True, make=...), ...)}
```

`guide.COMMANDS`, the adapter's recipe generation and `argparse` choices are then all
derived from this table. The existing test that every named command exists becomes a
property of the table.

### F9 — Duplicated primitives (P1 for locks, P2 for the rest)

| Primitive | Copies | Proposal |
|---|---|---|
| Locks | `core.operation_lock`, `research.task_lock`, (`diagnostics.fault_dir`) | One in-project lock (F1) |
| Atomic write | `core.atomic_write` (text), `markdown.render` (bytes, no `fsync`) | `atomic_write(path, data: str \| bytes)` |
| Markdown links | `runtime.file_checks` regex (`runtime.py:360-370`) and Pandoc in `markdown.py` | Keep the regex as the module-off fallback, behind one function with one documented scope |
| Excluded trees | `runtime.SKIPPED_TREES`, `markdown.EXCLUDED`, `bootstrap.EXCLUDED` (includes `workbench`, `build`, `out`), `task_graph` (`{.git,.latex-ai,.venv}`), two in `core.validate_config` | One `core.GENERATED_TREES` plus purpose-specific additions named at the call site |
| Planner suffix lists | `.csv`/`.tsv` appear both as manuscript-input and as ordinary suffixes (`runtime.py:261, 271`) | One table of suffix → route |

### F10 — The planner's suffix fallback selects every document (P2)

**Evidence.** In the three-document `tex-notes` example, `plan --files assets/logo.png
data/table.csv` selects `derivation, notebook, paper`, although no document
references either file (`runtime.py:261, 314-317`). In the reference repository, a
`workbench/docs/screenshot.png` selects the manuscript build.

**Proposal.** Locally, a document with a *verified* receipt has a complete, recorded
input set. Its sources would themselves change before it could start reading a new
file; the only exception is a computed file name, which `inputs` globs already cover.
So a file that matches only by suffix should select just the documents without a
verified receipt. CI has no receipts (artifacts are ignored by Git, and CI builds from
the repository only), so it keeps today's conservative behaviour automatically. Add
`validation.ignore` globs (for example `docs/**`) for files that are known not to be
manuscript inputs.

### F11 — Phased Make ownership is the riskiest area (P1)

**Evidence.** The adapter for `build_command: ["make", <goal>]` makes the project's
own recipe part of receipt ownership. It does this with `.EXTRA_PREREQS`,
target-specific `override SHELL/.SHELLFLAGS`, a `recipe-shell.sh` trampoline,
`build-prepare`/`build-finish` hooks keyed by `$$PPID`, fixed-point goal expansion
with `$(eval)`, and a lexical Make parser (`make_graph.py`). Releases 2.7.2, 2.7.3 and
3.0.1 each repaired defects here, and F2 is another one. The mechanism requires GNU
Make 4.3 and POSIX, and it refuses several ordinary Makefile shapes (custom
`.RECIPEPREFIX`, target-specific `SHELL`, shared prerequisites between documents).

**Assessment.** The design does what it sets out to do: keep the user's single Make
graph unchanged while still certifying the PDF. But that goal is expensive. Most
adopted projects need only "run `make pdf`, then certify what it produced".

**Proposal.**

- Make **opaque adoption** the default. `latex-ai-build` runs `$(MAKE) <goal>` as a
  child process under the receipt, exactly as any other `build_command` is run today.
  The generated `check` depends on `latex-ai-build`, not on `<goal>`.
- If the project's own `check` also reaches `<goal>`, the existing
  `project_check_rule` detection reports it. The second invocation is then an up-to-date
  no-op in Make, and the receipt still certifies the outputs.
- Keep phased ownership as an explicit opt-in (`"make_ownership": "phased"`) for
  projects that need one shared graph run.

This removes the 4.3 requirement, the shell trampoline and most of `make_graph`'s
load-bearing role from the default path.

### F12 — Process identity outside Linux (P2)

`processes.state` reads `/proc/<pid>/stat` (`processes.py:34-41`). Without `/proc`
(macOS), `token()` returns `None`, so the PID-reuse guard
(`birth == token(pid)`) compares `None == None` and always passes. If a build dies and
another process later reuses its PID, the receipt stays `running`, and
`assert_build_idle` blocks builds until that unrelated process exits.

**Proposal.** Fall back to `ps -o lstart= -p PID`, which POSIX `ps` supports on macOS
and the BSDs, as the birth token. Run it once per check; the cost is negligible.

### F13 — Scaling of the provenance archive (P2)

Every run copies all of its inputs and outputs into
`results/runs/<stamp>-<uuid>/` (`research.py:228-236, 291-297`). Every `status`,
`plan`, `validate`, `run` and `freshness` call parses **every** `record.json`
(`research.py:83`). There is no pruning, by design. So storage grows by the full input
size per run, and command latency grows linearly with history.

**Proposal.**

- *Content-addressed snapshots.* Store `results/runs/blobs/<sha256>` once, and let
  records reference digests (they already store them). Identical inputs, such as the
  script and configuration that rarely change, are then stored only once.
- *Layout by task.* Use `results/runs/<module>/<task>/<stamp>-<uuid>/record.json`, so
  the latest record for a task is one directory listing away. No second database is
  added; `history` still walks the tree. Keep a v1 reader for the flat layout.

### F14 — CI (P2)

- `adapters.document_workflow` emits **one `xu-cheng/texlive-action` step per
  document**, plus a project-check step. Each step starts the TeX Live container and
  runs `apt-get update && apt-get install python3 make` again. With N selected
  documents, that is N container start-ups and N package installs, one after another.
  Either use a job-level `container:` with a pinned TeX Live image, so the steps run
  in one container and install once, or fan out with a matrix over
  `fromJSON(needs.plan.outputs.document_ids)` so the documents build in parallel.
  Upload steps keep their per-document conditions.
- Pin third-party actions by commit SHA (`xu-cheng/texlive-action@<sha>`). The
  workflow has `contents: read`, which limits the damage, but it does run the action's
  code with the checkout.
- PR comparisons use `github.event.pull_request.base.sha` with a two-dot `git diff`,
  which also selects files that changed on the base branch after the fork point. This
  is conservative, not unsafe. `git merge-base` would select less.
- The generated `schema3-acceptance.yml` contains a portability step that can never
  run (`validation.package` is `null` there) and would `make -C workbench` from the
  wrong directory if it did. `generated_workflow()` should drop steps that cannot be
  selected.

### F15 — Tests and documentation (P3)

- Test modules are named after the events that produced them
  (`test_repairs_3_0_1`, `test_audit3_repairs`, `test_blind_repairs`,
  `test_review_fixes`, `test_simplification`, `test_guide_3_0_1`). To find the tests
  for receipts or locks you must know the project's history. Reorganise them by
  component (`test_receipts`, `test_locks`, `test_planner`, `test_installer`,
  `test_adapters_make`, …), and keep the reproduction origin in docstrings. The
  suite takes 154 s without TeX, almost entirely in subprocess-driven fixtures. A
  shared in-process fixture for the planner and receipts, plus a `slow` marker for the
  end-to-end cases, would give contributors a fast loop.
- The user guide is installed into every project as runtime code (`handbook.py`, 48 KB,
  stored twice in each manifest; see F6). That is acceptable, because it works
  offline and with a broken configuration. It is still the largest runtime file that
  is not part of the checking machinery, so it is a candidate for an optional module
  if runtime size becomes a concern.

## Proposed order of work

| Step | Findings | Effort | Risk | Notes |
|---|---|---|---|---|
| 1 | F1, the lock part of F9 | S | Low | Restores the safety property; a test with two users contending |
| 2 | F2 | S | Low | Install-time Make check; move the `$(error)` inside the build-goal condition |
| 3 | F3 | S | Low | Lenient decoding; errors name the file |
| 4 | F6 | M | Medium | Manifest v2 with a v1 reader; largest effect on user repositories |
| 5 | F4, F5 | M | Medium | Certify discovered inputs by ctime; per-invocation memo; regression: one compilation for `\includegraphics{fig}` |
| 6 | F11 | L | Medium | Opaque adoption by default, phased as opt-in; simplifies F2 permanently |
| 7 | F7, F8, the rest of F9 | L | Low | Pure refactor behind the existing 351 tests |
| 8 | F10, F12, F13, F14, F15 | M each | Low | Independent |

Following the repository's defect policy, each defect repair (F1–F3) should come with
a regression test that fails first, and should get an independent review before
approval.

## Not verified here

- Real TeX compilation and `make portability`: no TeX Live in this environment. F4's
  double compilation was measured with the suite's fixture compiler. The code path is
  the same for latexmk (`finish_build` → `regenerate_outputs` → `compile_document(force=True)`).
- F2 on an actual GNU Make 3.81. It was established by reading the generated adapter:
  the `$(error)` sits inside a condition that is true for every goal when `DOC` is
  unset.
- macOS and Windows behaviour (F12), and the hosted CI timings (F14).
