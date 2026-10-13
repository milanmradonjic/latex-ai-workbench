"""The guide: pictures, how-tos and a glossary, written once and shown as terminal text, a web page or Markdown.

``make guide`` prints it, ``make guide-html`` writes it as one self-contained page, and ``docs/handbook.md`` and
``docs/handbook.html`` in the package are generated copies (``make -C workbench handbook``; a test keeps them equal).
Commands in the text are written as ``make build`` and shown with the names that work in the reader's project
(``localize``): where a Makefile keeps its own ``build``, the guide says ``make latex-ai-build``.
"""
import html
import re
import sys
from typing import NamedTuple, Tuple

import guide
from core import VERSION, WorkbenchError

WIDTH = 78


class Topic(NamedTuple):
    id: str
    title: str
    summary: str                  # one line, shown in the index
    blocks: tuple                 # ("p", text) ("diagram", art, caption) ("steps", items) ("defs", pairs) ("note", text)
    kind: str = "picture"         # start, picture, howto or reference
    needs: Tuple[str, ...] = ()   # modules, any of which makes it useful; empty: always


def flow(steps, width=20):
    """Boxes joined by arrows, each with a note to its right. The borders are computed, so they line up."""
    middle, lines = width // 2, []
    for index, (label, note) in enumerate(steps):
        last = index == len(steps) - 1
        assert len(label) <= width and width + 4 + len(note) <= WIDTH - 2, label
        lines += ["┌" + "─" * width + "┐", "│" + label.center(width) + "│  " + note,
                  "└" + "─" * middle + ("─" if last else "┬") + "─" * (width - middle - 1) + "┘"]
        if not last:
            lines.append(" " * (middle + 1) + "▼")
    return "\n".join(lines)


def frame(title, sections, width=72):
    """One box in titled sections: ``sections`` is a list of (heading, [lines])."""
    def row(text):
        assert len(text) <= width - 2 and width + 4 <= WIDTH, text
        return "│ " + text.ljust(width - 2) + " │"
    lines = [title, "┌" + "─" * width + "┐"]
    for index, (heading, body) in enumerate(sections):
        if index:
            lines.append("├" + "─" * width + "┤")
        lines += [row(heading)] + [row("  " + text) for text in body]
    return "\n".join(lines + ["└" + "─" * width + "┘"])


def routes(left, right, rows, width=(30, 36)):
    """Rows of (what changed, what runs) joined by arrows."""
    a, b = width
    assert a + b + 8 <= WIDTH - 2 and all(len(s) <= a - 2 and len(r) <= b - 2 for s, r in rows), rows
    lines = [f" {left:<{a + 1}}    {right}", "┌" + "─" * a + "┐   ┌" + "─" * b + "┐"]
    lines += [f"│ {source:<{a - 1}}│──▶│ {action:<{b - 1}}│" for source, action in rows]
    return "\n".join(lines + ["└" + "─" * a + "┘   └" + "─" * b + "┘"])


MAP = frame("your project folder", [
    ("YOURS: the workbench never overwrites these",
     ["main.tex  refs.bib  notes/  data  scripts  your own Makefile rules"]),
    ("SETTINGS: you edit them, or `latex-ai-init configure` does",
     [".latex-ai.json   which modules are on, which documents exist",
      "Makefile         your rules, plus one marked block of workbench ones",
      "AGENTS.md        the rules an AI assistant follows here"]),
    ("THE WORKBENCH: an installed copy; never edit it by hand",
     [".latex-ai/*.py             the code that `make ...` runs",
      ".latex-ai/installation.json  what was installed; keep it in Git"]),
    ("WHAT IT RECORDS: written by the commands",
     [".latex-ai/artifacts/   build receipts, exported PDFs, reports",
      "                       (Git ignores this folder)"]),
])

LOOP = flow([
    ("make status", "where do things stand, and what comes next?"),
    ("edit your files", "TeX, notes, data: as you always do"),
    ("make validation-plan", "which checks do my changes need? (runs nothing)"),
    ("make validate", "run exactly those checks; repeat until they pass"),
    ("make check", "everything, once, before you share the work"),
    ("git diff", "you review; committing is your decision"),
], width=22)

CHECKS = routes("you changed", "make validate runs", [
    ("notes, Markdown, scripts", "quick file checks, no TeX build"),
    ("AGENTS.md, permissions", "structure checks; you review meaning"),
    (".tex, .bib, figures, data", "build and check documents using them"),
    ("Makefile, settings, CI", "file checks, then a full check"),
    ("no Git, or unknown files", "everything, to be safe"),
], width=(28, 40))

LIFE = """\
┌─────────┐ make document-check ┌─────────┐ you edit a source ┌───────┐
│ missing ├────────────────────▶│ current ├──────────────────▶│ stale │
└─────────┘   (build succeeds)  └─────────┘ or a build setting└───┬───┘
                                     ▲                            │
                                     └────────────────────────────┘
                                    make document-check (succeeds)

A build that fails or is interrupted leaves the document   failed
A build that is in progress shows as                       running"""

NAMES = """\
make build ──▶ does your Makefile already have a `build` target?
                    │ no                       │ yes
                    ▼                          ▼
      the workbench's build       your recipe runs, unchanged.
      (a short alias)             The workbench's own is
                                  `make latex-ai-build`"""


def p(text):
    return ("p", text)


def note(text):
    return ("note", text)


def steps(*items):
    return ("steps", items)


def defs(*pairs):
    return ("defs", pairs)


def diagram(art, caption):
    return ("diagram", art, caption)


INSTALLER = "python3 /path/to/workbench/latex-ai-init"

TOPICS = (
    Topic("overview", "What this is", "The workbench in one page", (
        p("The workbench is a set of `make` commands that live inside your project. They check your files, build your PDF, "
          "remember what was built from what, and tell you when something is out of date. It never edits your writing, and it "
          "never changes Git: committing is always your decision."),
        p("You do not have to learn all of it. Five commands cover most days:"),
        defs(("`make status`", "Where the project stands, and what to do next. Start here whenever you are unsure."),
             ("`make validate`", "After editing: run only the checks your changes need. `make validation-plan` previews them."),
             ("`make check`", "The full check of everything. Run it before you share the work."),
             ("`make build`", "Build the PDF of a LaTeX document, when LaTeX is on."),
             ("`make guide`", "This guide. `make guide-html` writes it as a web page.")),
        p("Type commands in the project folder, the one that holds `.latex-ai.json`. If a command is not found, or does something "
          "you did not expect, your own Makefile may already use that name: see the topic `names`."),
    ), kind="start"),

    Topic("map", "What lives where", "The folders and files, and who owns each", (
        diagram(MAP, "Four kinds of file: yours, settings, the installed workbench, and what it records."),
        p("Rule of thumb: edit YOURS and SETTINGS, and only read the rest. If something in the workbench part looks wrong, "
          "do not repair it by hand: report it (topic `defect`)."),
    )),

    Topic("loop", "The everyday loop", "What to run, in what order, while you work", (
        diagram(LOOP, "The loop for a normal working session. Only the last step before sharing is `make check`."),
        note("Choosing checks by what changed compares your files with the last Git commit. Without a Git repository, or "
             "before the first commit, every check is selected and `make status` says so."),
    )),

    Topic("checks", "What runs when", "Why `make validate` runs less than `make check`", (
        diagram(CHECKS, "How the files you changed decide what `make validate` runs."),
        p("`make validate` is the quick one: it asks Git which files changed and runs only the checks they need. "
          "`make check` always covers everything, though it may reuse a build whose verified record is still current."),
        p("`make validation-plan` shows the selection and the reason for each choice without running anything."),
        note("If your own Makefile gives `check` rules of its own, `make validate` runs `make check` so that they are never "
             "skipped."),
    )),

    Topic("states", "Document states", "What current, stale, failed, running and missing mean", (
        diagram(LIFE, "The life of a LaTeX document's build. Only `current` means its PDF can be trusted."),
        defs(("current", "The last verified build matches the sources and settings as they are now. Nothing to do."),
             ("stale", "A source or a build setting changed since the verified build. `make status` lists what changed under "
                       "the document; rebuild with `make document-check DOC=name`."),
             ("failed", "The last build failed or was interrupted. Read the first compiler error it printed, fix the source, "
                        "rebuild. Restoring the old text does not clear it; only a successful build does."),
             ("running", "A build is in progress. Wait for it; `make status` shows its owner and compiler. "
                         "docs/troubleshooting.md in the workbench package explains how to inspect it safely."),
             ("missing", "Never built, so there is no PDF to trust yet. `make document-check DOC=name` builds and checks it.")),
        note("An exported PDF (`make pdf-artifact`) is a copy. Rebuilding does not update it; export again."),
    ), needs=("latex",)),

    Topic("names", "Command names", "Why a command can have two names, and the variables it takes", (
        diagram(NAMES, "A short name is only an alias; your own rule always wins."),
        p("Every workbench command has a long name that starts with `latex-ai-` and always reaches the workbench. The short "
          "name (`build`, `help`, `doctor`) is added only where your Makefile has no target of that name. "
          "`make help` and this guide show the names that work in your project."),
        p("Some commands take a variable after the command, for example `make build DOC=notes`:"),
        defs(("`DOC=name`", "Choose a document. Without it, the default document is used."),
             ("`TOPIC=name`", "Choose a part of this guide, for example `make guide TOPIC=loop`."),
             ("`ISSUE_NOTE=\"...\"`", "What you saw and what you expected, for `make latex-ai-issue`.")),
        p(f"`latex-ai-init` is not a Make target. It is a file in the workbench package that installs, upgrades, audits and "
          f"reconfigures a project, so you run it as `{INSTALLER}`."),
    )),

    Topic("install", "I want to put the workbench into a project", "Preview, apply, then look around", (
        steps(("Look first. This writes nothing and lists what would be added:",
               f"{INSTALLER} init /path/to/project \\\n    --dry-run --diff"),
              "A folder with one main `.tex` file needs nothing more (with several, add `--root thesis.tex`). For an empty folder, "
              "or one without a manuscript, say what it is for: add `--profile core` (the other is "
              "`writing`).",
              "If the preview is right, run the same command without `--dry-run --diff`.",
              ("Then, in the project folder:", "make help")),
        note("The installer never overwrites your files, never touches Git, and backs up the files it manages before replacing "
             "them. A paper that has its own Makefile also needs the command that builds it (`--build-command`); the installer "
             "says so. Run it as `python3 /path/to/workbench/latex-ai-init`: it is a file in the workbench package, not a "
             "command on your PATH."),
    ), kind="howto"),

    Topic("first-day", "I just installed it. What do I do first?", "Look around, then run the first check", (
        p("Run these in the project folder, one at a time."),
        steps(("See which commands this project has:", "make help"),
              ("See where things stand and what to do next:", "make status"),
              ("Confirm that the tools it needs are installed (LaTeX projects need a TeX distribution):", "make doctor"),
              ("Run the first full check:", "make check")),
        note("A paper you already had usually has some ChkTeX warnings, and they fail the check: see the topic `baseline`. "
             "If you see `INTERNAL ERROR`, see `defect`. Nothing here changes Git."),
    ), kind="howto"),

    Topic("edit", "I changed something. What do I run?", "Preview the checks, run them, check everything before sharing", (
        steps(("Preview which checks your changes need. This runs nothing:", "make validation-plan"),
              ("Run those checks:", "make validate"),
              "Fix what it reports and repeat.",
              ("Before you share the work, check everything:", "make check"),
              ("Review the changes yourself. Committing is your decision:", "git diff")),
        note("Choosing checks by what changed needs a Git repository with at least one commit. Without one, every check runs "
             "and `make status` says so. The topic `checks` explains the choice."),
    ), kind="howto"),

    Topic("pdf", "I want a PDF I can send", "Build it, check it, copy out the verified file", (
        steps(("Build it. `DOC=name` picks a document other than the default:", "make build"),
              ("Check it, including bibliography and ChkTeX:", "make check"),
              ("Copy the verified PDF out:", "make pdf-artifact")),
        p("The copy lands under `.latex-ai/artifacts/`; for a named document it is "
          "`.latex-ai/artifacts/documents/NAME/document.pdf`."),
        note("Export refuses a PDF whose build is not `current` (topic `states`). Rebuilding does not update an earlier copy, "
             "so export again after a rebuild."),
    ), kind="howto", needs=("latex",)),

    Topic("stale", "I see stale, failed or missing in the status. What now?", "Find out why, rebuild that one document", (
        p("Each document has a state (topic `states`). Only `current` means its PDF can be trusted."),
        steps(("Read the lines under the document in the status. They name what changed:", "make status"),
              ("Rebuild and check that one document:", "make document-check DOC=name"),
              "If it fails, read the first error it prints (it names the compiler log), fix the source, and run the same "
              "command again.",
              "If it says another build is active, wait. `make status` shows who owns it. Do not delete lock or receipt files."),
    ), kind="howto", needs=("latex",)),

    Topic("baseline", "I already had a paper, and ChkTeX warnings fail the check", "Fix them, or record today's as accepted", (
        p("ChkTeX warnings fail `make check`, and a paper that already exists usually has some. There are two honest choices."),
        steps(("Fix the warnings one by one. List them with:", "make lint"),
              ("Or accept today's warnings as a recorded baseline. From then on only new warnings fail:",
               "make lint-baseline"),
              "Run `make check` again."),
        note("Accepting a baseline is the owner's decision, not a routine step: an assistant should ask you first. The list is "
             "saved under `.latex-ai/lint-baselines/` unless the configuration says otherwise, and belongs in version control."),
    ), kind="howto", needs=("latex",)),

    Topic("document", "I want a second TeX document next to my paper", "Register another root file as a named document", (
        steps("Write the new document as a complete `.tex` file, for example `notes/derivation.tex`.",
              ("Preview the registration, then apply it by running the same command without `--dry-run --diff`:",
               f"{INSTALLER} configure . \\\n    --document derivation --root notes/derivation.tex --dry-run --diff"),
              ("Build and check the new document:", "make document-check DOC=derivation"),
              ("Export its PDF:", "make pdf-artifact DOC=derivation"),
              ("List every document and its state:", "make documents")),
        note("Each document has its own build record and PDF. `make check` covers all of them, and `make build` without `DOC` "
             "uses the default document."),
    ), kind="howto", needs=("latex",)),

    Topic("module", "I want to turn a module on or off", "Modules are optional capabilities; switch them with the installer", (
        p("`make help` lists the modules that are not enabled here and prints the command that enables one."),
        steps(("Preview the change, with a module's name instead of NAME (for example `markdown`):",
               f"{INSTALLER} configure . \\\n    --enable NAME --dry-run --diff"),
              "If the preview is what you want, run the same command without `--dry-run --diff`.",
              "To turn one off, use `--disable NAME` the same way. Your files are kept."),
        note(f"`latex-ai-init` is a file in the workbench package, not a command on your PATH: run it as `{INSTALLER}`."),
    ), kind="howto"),

    Topic("upgrade", "I want to move to a newer release", "Preview with the new package, read the plan, apply", (
        steps(("Run the NEW package's installer in preview mode:",
               f"{INSTALLER.replace('workbench', 'new-workbench')} upgrade . --dry-run --diff"),
              "Read the plan. Conflicts are reported by name and there is no overwrite switch: reconcile them deliberately.",
              "Apply it by running the same command without `--dry-run`. Files that change get a backup first.",
              ("Then confirm the tools and the project:", "make doctor"),
              ("And check everything:", "make check")),
        note("Never delete `.latex-ai/installation.json` to force an upgrade. It is what makes merging safe."),
    ), kind="howto"),

    Topic("agent", "I want an AI assistant to work on this project", "What to tell it, and what it will ask you", (
        steps("Point it at `AGENTS.md` in the project root. That is the policy it follows, and the installer put it there.",
              "Ask it to start with `make status`, to run `make validate` after its edits and `make check` before it "
              "says it is done.",
              "Expect a question before any Git change: staging, committing, pushing, switching branches and the like need "
              "your approval. Answer deliberately; these prompts are guardrails, not a security boundary.",
              "It must not edit `.latex-ai/` or loosen a check to get a pass. If it believes the workbench is wrong, "
              "it should write a report (topic `defect`) and tell you."),
        note("For a second opinion, ask another assistant to review the diff under the same `AGENTS.md`. "
             "docs/agents.md describes the writer and reviewer roles."),
    ), kind="howto"),

    Topic("defect", "I think the workbench itself is wrong", "Write a local report instead of working around it", (
        p("An ordinary failure prints `ERROR:`; your file or tool is at fault and the message says which. `INTERNAL ERROR` "
          "means the workbench itself failed. A check that passes when it plainly should not is the other case worth reporting."),
        steps(("Write a local report:", "make latex-ai-issue ISSUE_NOTE=\"observed ... expected ...\""),
              "It is saved as `.latex-ai/artifacts/issues/report-*.json`. Nothing is sent anywhere, so read it first if you "
              "like.",
              "Pass it to whoever maintains the workbench, and do not trust the verdict that looked wrong until it has been "
              "looked at."),
        note("Do not edit the installed files in `.latex-ai/`. A repair belongs in the workbench package, with a test."),
    ), kind="howto"),

    Topic("trouble", "Reading a message", "What the messages the workbench prints are telling you", (
        defs(("`ERROR: ...`", "An ordinary failure with a cause you can fix. Read the file or tool it names. A `Hint:` line "
                              "below it, when present, is the next action."),
             ("`INTERNAL ERROR`", "A fault inside the workbench, not in your project. Report it (topic `defect`)."),
             ("`Configuration problem`", "`.latex-ai.json` is missing or cannot be read. `make help`, `make status`, "
                                         "`make guide` and `make latex-ai-issue` still work, and the message says how to fix it."),
             ("`Module is disabled: NAME`", "The command belongs to a module that is off here. The hint prints the command "
                                            "that turns it on (topic `module`)."),
             ("`Another build is active`", "A build is already running, or its compiler still is. Wait; `make status` shows "
                                           "the owner."),
             ("`Build inputs changed during execution`", "A generator rewrote a file the document reads while it was being "
                                                         "built. The message names the files; docs/troubleshooting.md in the "
                                                         "workbench package explains the fix.")),
        p("docs/troubleshooting.md in the workbench package has a table of symptoms and the next action for each."),
    ), kind="reference"),

    Topic("glossary", "Glossary", "The words this tool uses", (
        defs(("AGENTS.md", "The rules file an AI assistant reads first. Among them: Git changes need your approval."),
             ("Alias", "A short command name such as `build` that points to the long `latex-ai-` name. It exists only where "
                       "your Makefile has no target of that name."),
             ("Artifact", "A file the workbench writes under `.latex-ai/artifacts/`: build receipts, exported PDFs, reports "
                          "and the web version of this guide. Git ignores them."),
             ("Baseline (lint)", "A recorded list of ChkTeX warnings you chose to accept. Only new warnings fail."),
             ("Build receipt", "The record of one build: what was compiled, with which settings, from which file contents, "
                               "producing which outputs. It is what lets the workbench say a PDF is current."),
             ("Check and validate", "`make check` runs everything. `make validate` runs only what your changed files need."),
             ("Configuration", "`.latex-ai.json`: which modules are on and which documents exist."),
             ("Document", "A LaTeX file the workbench builds under a name of its own, with its own receipt and PDF. "
                          "Your paper is one; a supplement or notes can be more."),
             ("Doctor", "`make doctor` checks that the tools the project needs are installed."),
             ("Evidence", "What the commands record about what happened: build receipts. It does not prove "
                          "that your science is right."),
             ("Installer", f"`latex-ai-init`, a file in the workbench package that installs, upgrades, audits and "
                           f"reconfigures a project. Run it as `{INSTALLER}`."),
             ("Manifest", "The installation manifest `.latex-ai/installation.json` records what was installed."),
             ("Module", "An optional capability: latex, bibliography, markdown."),
             ("Plan", "The preview of which checks your changes need (`make validation-plan`)."),
             ("Profile", "A starting choice of modules made at install time. It is not a lasting policy."),
             ("Reserved name", "The long `latex-ai-` name of a command, which works in every project."),
             ("Root", "The main `.tex` file of a document."),
             ("Runtime", "The workbench code installed in `.latex-ai/`. It belongs to the workbench: do not edit it."),
             ("Schema", "The version of the configuration format. Workbench 3 reads schema 3 only."),
             ("Stale", "Out of date: a document whose sources or settings changed since its verified build."),
             ("Verified", "Said of a PDF whose build receipt matches the sources and settings as they are now."),
             ("Workbench", "This tool: the commands, their checks and the records they keep.")),
    ), kind="reference"),
)

KINDS = (("picture", "Understand it"), ("howto", "Do something"), ("reference", "Look something up"))
BY_ID = {topic.id: topic for topic in TOPICS}
# One character for one: the plain form of a picture keeps its layout. A new non-ASCII character fails a test until it is listed.
ASCII = str.maketrans({"─": "-", "│": "|", "┌": "+", "┐": "+", "└": "+", "┘": "+", "├": "+", "┤": "+", "┬": "+", "▼": "v", "▲": "^", "▶": ">"})


def topic_ids():
    return [topic.id for topic in TOPICS]


def to_ascii(text):
    return text.translate(ASCII)


def fit_terminal(text, stream=None):
    """The text as the terminal can show it: box drawing where its encoding allows, plain characters where not."""
    encoding = getattr(stream or sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(encoding)
        return text
    except (UnicodeEncodeError, LookupError):
        return to_ascii(text)


def localize(text, names):
    """Commands written as ``make build`` shown under the name that works here (None or equal: unchanged)."""
    def name(match):
        actual = (names or {}).get(match.group(1))
        return "make " + (actual if actual else match.group(1))
    return re.sub(r"\bmake ([a-z][\w-]*)", name, text)


def context(project, config, problem=None, documents=None):
    """What the guide needs to know about the reader's project (None for the generic copy)."""
    return {"name": project.name, "modules": guide.enabled_modules(config), "names": guide.available(project, config),
            "problem": problem, "documents": documents or []}


def differing_names(ctx):
    return [(short, actual) for short, actual in (ctx or {}).get("names", {}).items() if actual and actual != short]


def unavailable(topic, ctx):
    """The topic needs a module that is off in this project."""
    return bool(ctx and topic.needs and ctx.get("modules") is not None and not set(topic.needs) & set(ctx["modules"])
                and ctx.get("problem") is None)


def project_rows(ctx):
    """(label, [lines]) for the part of the guide that is about this very project."""
    rows = []
    if ctx["problem"]:
        rows.append(("Problem", [f"Configuration problem: {ctx['problem'][0]}", f"To fix it: {ctx['problem'][1]}"]))
    else:
        rows.append(("Modules", [", ".join(ctx["modules"]) or "none (core only)"]))
    if ctx["documents"]:
        lines = []
        for document in ctx["documents"]:
            lines.append(f"{document['id']}{' (default)' if document.get('default') else ''}: {document['state']}")
            lines += ["  " + reason for reason in document.get("reasons", ())]
        rows.append(("Documents", lines))
    differ = differing_names(ctx)
    if differ:
        rows.append(("Names", ["Your Makefile keeps its own target for " + ", ".join(f"`{short}`" for short, _ in differ) +
                               "; the workbench's commands are " + ", ".join(f"`make {actual}`" for _, actual in differ) + "."]))
    rows.append(("Next", ["`make status` says what to do next."]))
    return rows


def wrap(text, first="", rest=None, width=WIDTH):
    """Fill lines to the width; a `code span` is never split across two lines."""
    rest = first if rest is None else rest
    lines, line = [], first
    for word in re.findall(r"(?:[^\s`]|`[^`]*`)+|\S+", text):
        if line.strip() and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = rest
        line += ("" if not line.strip() or line.endswith(" ") else " ") + word
    return lines + [line]


def text_blocks(blocks, ctx):
    names = (ctx or {}).get("names")
    out = []
    for block in blocks:
        kind = block[0]
        if kind == "p":
            out += wrap(localize(block[1], names)) + [""]
        elif kind == "note":
            out += wrap("Note: " + localize(block[1], names)) + [""]
        elif kind == "diagram":
            out += ["  " + line if line else "" for line in block[1].splitlines()] + [""]
            out += wrap(localize(block[2], names), "  ") + [""]
        elif kind == "steps":
            for number, item in enumerate(block[1], 1):
                body, code = (item, None) if isinstance(item, str) else item
                out += wrap(localize(body, names), f"  {number}. ", "     ")
                if code:
                    out += ["       " + line for line in localize(code, names).splitlines()]
            out.append("")
        elif kind == "defs":
            for term, meaning in block[1]:
                out += [f"  {localize(term, names).strip('`')}"] + wrap(localize(meaning, names), "      ")
            out.append("")
    return out


def heading(title, mark="-"):
    return [title, mark * len(title)]


def index_lines(ctx):
    names = (ctx or {}).get("names")
    command = localize("make guide", names)
    lines = []
    for kind, title in KINDS:
        lines += [title]
        for topic in TOPICS:
            if topic.kind == kind:
                tag = " (not enabled here)" if unavailable(topic, ctx) else ""
                lines += wrap(topic.title + tag, f"  {command} TOPIC={topic.id:<10}", " " * (len(command) + 20))
        lines.append("")
    return lines


def render_text(topic=None, ctx=None, ascii_only=False):
    """The guide as terminal text: the front page, one topic by id, or everything (``all``)."""
    if topic and topic not in BY_ID and topic != "all":
        raise WorkbenchError(f"Unknown guide topic: {topic}", hint="topics: " + ", ".join(topic_ids()) + ", all")
    names = (ctx or {}).get("names")
    if topic in BY_ID and topic != "overview":
        chosen = BY_ID[topic]
        lines = heading(chosen.title) + [""] + text_blocks(chosen.blocks, ctx)
    else:
        lines = heading(f"LaTeX AI Workbench {VERSION}: guide", "=") + [""] + text_blocks(BY_ID["overview"].blocks, ctx)
        if ctx:
            lines += heading("Your project right now") + [f"  {'Project':<11}{ctx['name']}"]
            for label, body in project_rows(ctx):
                lines += wrap(localize(body[0], names), f"  {label:<11}", " " * 13)
                for more in body[1:]:
                    indent = 13 + len(more) - len(more.lstrip())
                    lines += wrap(localize(more.lstrip(), names), " " * indent, " " * (indent + 2))
            lines.append("")
        if topic == "all":
            for chosen in TOPICS[1:]:
                lines += heading(chosen.title) + [""] + text_blocks(chosen.blocks, ctx)
        else:
            lines += index_lines(ctx)
            lines += wrap(localize("`make guide TOPIC=all` prints everything; `make guide-html` writes the same guide as a web "
                                   "page, `.latex-ai/artifacts/guide.html`, that you can open in a browser.", names))
    text = "\n".join(lines).rstrip("\n") + "\n"
    return to_ascii(text) if ascii_only else text


# --- Markdown ---------------------------------------------------------------------------------------------------

GENERATED = "Generated from handbook.py by `make -C workbench handbook`; do not edit it by hand."


def slug(title):
    return re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")


def markdown_blocks(blocks):
    out = []
    for block in blocks:
        kind = block[0]
        if kind == "p":
            out += [block[1], ""]
        elif kind == "note":
            out += [f"> **Note.** {block[1]}", ""]
        elif kind == "diagram":
            out += ["```text", *block[1].splitlines(), "```", "", f"*{block[2]}*", ""]
        elif kind == "steps":
            for number, item in enumerate(block[1], 1):
                body, code = (item, None) if isinstance(item, str) else item
                out.append(f"{number}. {body}")
                if code:
                    out += ["", "   ```sh", *["   " + line for line in code.splitlines()], "   ```"]
            out.append("")
        elif kind == "defs":
            out += [f"- **{term}**: {meaning}" for term, meaning in block[1]]
            out.append("")
    return out


def render_markdown():
    """The guide as a Markdown page for the package's docs (generic: no project in it)."""
    lines = [f"<!-- {GENERATED} -->", f"# LaTeX AI Workbench {VERSION}: guide", ""]
    lines += ["This is the printable copy of the guide that `make guide` shows in a project and `make guide-html` writes as a "
             "web page. In a project the commands are shown under the names that work there.", ""]
    lines += [f"## {BY_ID['overview'].title}", ""] + markdown_blocks(BY_ID["overview"].blocks)
    lines += ["## Contents", ""]
    for kind, title in KINDS:
        lines += [f"**{title}**", ""]
        lines += [f"- [{topic.title}](#{slug(topic.title)}): {topic.summary}" for topic in TOPICS if topic.kind == kind]
        lines.append("")
    for topic in TOPICS[1:]:
        lines += [f"## {topic.title}", ""] + markdown_blocks(topic.blocks)
    return "\n".join(lines).rstrip("\n") + "\n"


# --- HTML -------------------------------------------------------------------------------------------------------

CSS = """
:root{--bg:#fbfbf8;--fg:#1d2024;--muted:#5b626b;--accent:#1f5fbf;--panel:#f1f2ee;--border:#d9dbd3;--code:#ebece6;
--current:#1c7a3d;--stale:#a35d00;--failed:#b3261e;--running:#1f5fbf;--missing:#5b626b}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15181b;--fg:#e3e5e8;--muted:#98a0a9;--accent:#8ab4f8;
--panel:#1d2125;--border:#32383e;--code:#232830;--current:#6fcf8c;--stale:#f0b35a;--failed:#ff8a80;--running:#8ab4f8;--missing:#98a0a9}}
:root[data-theme="dark"]{--bg:#15181b;--fg:#e3e5e8;--muted:#98a0a9;--accent:#8ab4f8;--panel:#1d2125;--border:#32383e;--code:#232830;
--current:#6fcf8c;--stale:#f0b35a;--failed:#ff8a80;--running:#8ab4f8;--missing:#98a0a9}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:var(--panel);padding:.4rem .6rem;z-index:2}
header{padding:1.5rem 16px 1rem;max-width:62rem;margin:0 auto}
h1{font-size:1.6rem;margin:0 0 .3rem}.lede{color:var(--muted);margin:0}
.layout{display:grid;grid-template-columns:15rem minmax(0,1fr);gap:2rem;max-width:62rem;margin:0 auto;padding:0 16px 3rem}
nav{position:sticky;top:1rem;align-self:start;font-size:.92rem;max-height:calc(100vh - 2rem);overflow:auto}
nav h2{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:1rem 0 .3rem}
nav ul{list-style:none;margin:0;padding:0}nav li{margin:.15rem 0}
main{min-width:0;max-width:46rem}
section{margin:0 0 2.4rem;scroll-margin-top:1rem}
h2{font-size:1.3rem;margin:0 0 .5rem;border-bottom:1px solid var(--border);padding-bottom:.25rem}
code{background:var(--code);padding:.05em .3em;border-radius:4px;font:.9em ui-monospace,"SF Mono",Menlo,Consolas,"DejaVu Sans Mono",monospace}
pre{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:.7rem .9rem;overflow-x:auto;margin:.6rem 0;
font:.84rem/1.3 ui-monospace,"SF Mono",Menlo,Consolas,"DejaVu Sans Mono",monospace}
pre code{background:none;padding:0;font:inherit}
figure{margin:.8rem 0}figure pre{line-height:1.12}figcaption{color:var(--muted);font-size:.9rem}
dl{margin:.6rem 0}dt{font-weight:600;margin-top:.55rem}dd{margin:.1rem 0 0 1.2rem}
.note{border-left:4px solid var(--accent);background:var(--panel);padding:.5rem .8rem;margin:.8rem 0;border-radius:0 6px 6px 0}
.project{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem}
.project dt{margin-top:.4rem}.project ul{margin:.1rem 0;padding-left:1.1rem;color:var(--muted)}
.state{font-weight:600;white-space:nowrap}.state::before{content:"\\25CF  "}
.state-current{color:var(--current)}.state-stale{color:var(--stale)}.state-failed{color:var(--failed)}
.state-running{color:var(--running)}.state-missing{color:var(--missing)}
.soon{color:var(--muted);font-size:.85em}
footer{max-width:62rem;margin:0 auto;padding:1rem 16px 2rem;color:var(--muted);font-size:.88rem}
@media (max-width:820px){.layout{grid-template-columns:1fr}nav{position:static;max-height:12rem;border:1px solid var(--border);border-radius:8px;padding:0 .8rem .6rem}}
@media print{nav,.skip{display:none}.layout{display:block}pre,figure,.note{break-inside:avoid}body{font-size:11pt}a{color:inherit}}
"""


def escape(text):
    return html.escape(text, quote=True)


def inline(text, names=None):
    """Escaped text with `code spans`; commands are shown under the names that work in the project."""
    parts = re.split(r"(`[^`]*`)", localize(text, names))
    return "".join(f"<code>{escape(part[1:-1])}</code>" if len(part) > 1 and part[0] == part[-1] == "`" else escape(part)
                   for part in parts)


def html_blocks(blocks, names):
    out = []
    for block in blocks:
        kind = block[0]
        if kind == "p":
            out.append(f"<p>{inline(block[1], names)}</p>")
        elif kind == "note":
            out.append(f'<p class="note"><strong>Note.</strong> {inline(block[1], names)}</p>')
        elif kind == "diagram":
            out.append(f'<figure><pre role="img" aria-label="{escape(block[2])}">{escape(block[1])}</pre>'
                       f"<figcaption>{inline(block[2], names)}</figcaption></figure>")
        elif kind == "steps":
            out.append("<ol>")
            for item in block[1]:
                body, code = (item, None) if isinstance(item, str) else item
                out.append(f"<li>{inline(body, names)}" + (f"<pre>{escape(localize(code, names))}</pre>" if code else "") + "</li>")
            out.append("</ol>")
        elif kind == "defs":
            out.append("<dl>" + "".join(f"<dt>{inline(term, names)}</dt><dd>{inline(meaning, names)}</dd>" for term, meaning in block[1]) + "</dl>")
    return out


def project_html(ctx):
    names = ctx.get("names")
    out = ['<section id="project"><h2>Your project right now</h2><dl class="project">',
           f"<dt>Project</dt><dd>{escape(ctx['name'])}</dd>"]
    for label, body in project_rows(ctx):
        if label == "Documents":
            items = []
            for document in ctx["documents"]:
                state = escape(document["state"])
                reasons = "".join(f"<li>{escape(reason)}</li>" for reason in document.get("reasons", ()))
                items.append(f"<li>{escape(document['id'])}{' (default)' if document.get('default') else ''}: "
                             f'<span class="state state-{state}">{state}</span>' + (f"<ul>{reasons}</ul>" if reasons else "") + "</li>")
            out.append("<dt>Documents</dt><dd><ul>" + "".join(items) + "</ul></dd>")
        else:
            out.append(f"<dt>{escape(label)}</dt><dd>" + "<br>".join(inline(line, names) for line in body) + "</dd>")
    return out + ["</dl></section>"]


def render_html(ctx=None):
    """The guide as one self-contained page: no script, no font, no request to anything outside it."""
    names = (ctx or {}).get("names")
    nav = ["<ul>" + ('<li><a href="#project">Your project</a></li>' if ctx else "") + '<li><a href="#overview">What this is</a></li></ul>']
    for kind, title in KINDS:
        nav.append(f"<h2>{title}</h2><ul>")
        for topic in TOPICS:
            if topic.kind == kind:
                soon = ' <span class="soon">(not enabled here)</span>' if unavailable(topic, ctx) else ""
                nav.append(f'<li><a href="#{topic.id}">{escape(topic.title)}</a>{soon}</li>')
        nav.append("</ul>")
    body = []
    if ctx:
        body += project_html(ctx)
    for topic in TOPICS:
        body.append(f'<section id="{topic.id}"><h2>{escape(topic.title)}</h2>')
        body += html_blocks(topic.blocks, names)
        body.append("</section>")
    where = (f"This copy is about the project {escape(ctx['name'])} and shows its command names." if ctx else
             "This copy is generic. <code>make guide-html</code> in a project adds that project's state and command names.")
    return "\n".join([
        "<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Workbench guide{' - ' + escape(ctx['name']) if ctx else ''}</title>", f"<style>{CSS}</style>", "</head>", "<body>",
        '<a class="skip" href="#main">Skip to the guide</a>',
        f"<header><h1>LaTeX AI Workbench {VERSION}: guide</h1>"
        f'<p class="lede">What it is, how the parts fit, and how to do the common things.</p></header>',
        '<div class="layout">', '<nav aria-label="Guide topics">', *nav, "</nav>", '<main id="main">', *body, "</main>", "</div>",
        f"<footer>{where} {inline(GENERATED)}</footer>", "</body>", "</html>", ""])
