"""The command registry: the one table of every workbench action and how a person or a Makefile reaches it.

An action is what ``workbench.py NAME`` runs. This table says, once per action, whether it takes
``--document``, whether its ``--json`` output is its own, which Make names reach it and how they are described.
``runtime`` derives its argument choices, its checks and its dispatch from it, ``guide`` derives ``COMMANDS`` (every name
shown to readers) and ``bootstrap`` derives the Makefile recipes. The handler of an action is the function ``do_<name>``
in ``runtime`` (``-`` written ``_``); a test keeps the two in step. The order is the order ``make help`` lists commands.
"""
from typing import NamedTuple, Tuple

# What a recipe takes from Make variables, by the ``selects`` of a target (DOC and the issue
# variables reach recipes through the environment, never as Make text spliced into a shell line).
RECIPE_ARGUMENTS = {"": "", "document": ' --document "$$DOC"', "all": " --all",
                    "note": ' --note "$$ISSUE_NOTE" --command "$$ISSUE_COMMAND"', "label": ' --note="$$SNAPSHOT_NOTE"'}


class Target(NamedTuple):
    """One fixed public Make name."""
    short: str
    group: str
    description: str
    selects: str = ""     # what the recipe takes from Make variables: "document", "all", "note" or "label"
    usage: str = ""       # the assignment `make help` shows after the name: DOC=NAME


class Action(NamedTuple):
    name: str
    targets: Tuple[Target, ...] = ()
    document: bool = False                     # accepts --document (DOC)
    batch: bool = False                        # accepts --all: the action for every document in turn
    view: bool = False                         # works on one document's view of the configuration (the default document when none is named)
    native_json: bool = False                  # --json prints its own JSON rather than the generic envelope
    standalone: bool = False                   # runs without reading .latex-ai.json

    @property
    def handler(self):
        return "do_" + self.name.replace("-", "_")


class Command(NamedTuple):
    """One Make name of an action, as the names shown to readers and the Makefile recipes use it."""
    short: str
    group: str
    description: str
    action: str = ""   # runtime action for the generated recipe
    selects: str = ""
    usage: str = ""


ACTIONS = (
    Action("check", document=True, targets=(
        Target("check", "Everyday", "Build, verify and lint every declared document"),)),
    Action("validate", targets=(
        Target("validate", "Everyday", "Run file checks, then check every document when full validation is selected"),)),
    Action("plan", native_json=True, targets=(
        Target("validation-plan", "Everyday", "Explain file or full validation without running checks"),)),
    Action("status", standalone=True, targets=(
        Target("status", "Everyday", "Where the project stands and what to do next"),)),
    Action("doctor", targets=(
        Target("doctor", "Everyday", "Check the required tools and the version stamp; LATEX_AI_TEMPLATE=/path/to/workbench compares it with a release"),)),
    Action("help", standalone=True, targets=(
        Target("help", "Everyday", "This list"),)),
    Action("guide", standalone=True, targets=(
        Target("guide", "Everyday", "A short manual for this project"),)),
    Action("build", document=True, view=True, batch=True, targets=(
        Target("build", "Manuscript", "Build the PDF and record its input/output validity", selects="document", usage="DOC=NAME"),
        Target("all", "Documents", "Build every document, one after another", selects="all"))),
    Action("lint", document=True, view=True, targets=(
        Target("lint", "Manuscript", "Run the selected document's static checks (ChkTeX)", selects="document", usage="DOC=NAME"),)),
    Action("documents", targets=(
        Target("documents", "Documents", "List declared documents and their build validity"),)),
    Action("document-check", document=True, targets=(
        Target("document-check", "Documents", "Build, verify and lint one document; DOC=name selects it", selects="document", usage="DOC=NAME"),)),
    Action("lint-baseline", document=True, view=True, targets=(
        Target("lint-baseline", "Manuscript", "Accept today's ChkTeX warnings as a recorded baseline; new ones still fail (owner's decision)", selects="document", usage="DOC=NAME"),)),
    Action("verify", document=True, view=True),
    Action("bib-check", document=True, targets=(
        Target("bib-check", "Manuscript", "Check bibliography files, entries and duplicate keys (the full check finds undefined citations)", selects="document"),)),
    Action("artifact", document=True, view=True, targets=(
        Target("pdf-artifact", "Manuscript", "Copy the verified current PDF to .latex-ai/artifacts/", selects="document", usage="DOC=NAME"),)),
    Action("clean", document=True, view=True, targets=(
        Target("clean", "Manuscript", "Remove build files", selects="document", usage="DOC=NAME"),)),
    Action("issue", standalone=True, targets=(
        Target("issue", "Inspect and report", 'Write a local report on a suspected workbench defect: ISSUE_NOTE="observed ... expected ..."', selects="note"),)),
    Action("snapshot", standalone=True, targets=(
        Target("snapshot", "Snapshots", 'Keep a copy of every file outside the project, to restore from (yours: never deleted): SNAPSHOT_NOTE="why" labels it', selects="label"),)),
    Action("snapshots", standalone=True, targets=(
        Target("snapshots", "Snapshots", "List the snapshots and the Git command that restores from one"),)),
)

NAMES = tuple(action.name for action in ACTIONS)
BY_NAME = {action.name: action for action in ACTIONS}

# Any generated target that re-enters a custom build would recurse, including `all`.
RECURSIVE_GOALS = frozenset(target.short for name in ("build", "check", "validate", "document-check")
                            for target in BY_NAME[name].targets)

COMMANDS = tuple(Command(target.short, target.group, target.description, action.name, target.selects, target.usage)
                 for action in ACTIONS for target in action.targets)
