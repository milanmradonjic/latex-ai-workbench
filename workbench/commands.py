"""The command registry: the one table of every workbench action and how a person or a Makefile reaches it.

An action is what ``workbench.py NAME`` runs. This table says, once per action, which module it needs, whether it takes
``--document``, whether its ``--json`` output is its own, which Make names reach it and how they are described.
``runtime`` derives its argument choices, its checks and its dispatch from it, ``guide`` derives ``COMMANDS`` (every name
shown to readers) and ``adapters`` derives the Makefile recipes. The handler of an action is the function ``do_<name>``
in ``runtime`` (``-`` written ``_``); a test keeps the two in step. The order is the order ``make help`` lists commands.
"""
from typing import NamedTuple, Optional, Tuple

# What a recipe takes from Make variables, by the ``selects`` of a target (DOC and the issue
# variables reach recipes through the environment, never as Make text spliced into a shell line).
RECIPE_ARGUMENTS = {"": "", "document": ' --document "$$DOC"',
                    "note": ' --note "$$ISSUE_NOTE" --command "$$ISSUE_COMMAND"'}


RESERVED_PREFIX = "latex-ai-"  # every Make name the installer reserves starts with it


class Target(NamedTuple):
    """A Make name that reaches an action. ``short`` is the everyday alias, and only where the project has no target
    of that name; ``reserved`` is the name the installer always provides (None for check and lint, whose recipe
    belongs to the project's Makefile)."""
    short: str
    reserved: Optional[str]
    group: str
    description: str
    selects: str = ""     # what the recipe takes from Make variables: "document" or "note"
    usage: str = ""       # the assignment `make help` shows after the name: DOC=NAME


class Action(NamedTuple):
    name: str
    targets: Tuple[Target, ...] = ()
    module: Optional[str] = None               # the module that must be enabled, or the action refuses
    needs: Optional[Tuple[str, ...]] = None    # modules whose presence makes its Make names available; default: (module,)
    document: bool = False                     # accepts --document (DOC)
    view: bool = False                         # works on one document's view of the configuration (the default document when none is named)
    native_json: bool = False                  # --json prints its own JSON rather than the generic envelope
    standalone: bool = False                   # runs without reading .latex-ai.json

    @property
    def handler(self):
        return "do_" + self.name.replace("-", "_")


class Command(NamedTuple):
    """One Make name of an action, as the names shown to readers and the Makefile recipes use it."""
    short: str
    reserved: Optional[str]
    group: str
    description: str
    action: Optional[str] = None   # runtime arguments of its recipe; None: the recipe belongs to the Makefile template
    needs: Tuple[str, ...] = ()    # enabled when any of these modules is on; empty: always
    selects: str = ""
    usage: str = ""


ACTIONS = (
    Action("check", document=True, targets=(
        Target("check", None, "Everyday", "Full check of the enabled modules (builds the manuscript when LaTeX is on)"),)),
    Action("validate", targets=(
        Target("validate", "latex-ai-validate", "Everyday", "Run only the checks your changed files need"),)),
    Action("plan", native_json=True, targets=(
        Target("validation-plan", "latex-ai-plan", "Everyday", "Preview which checks that would be, without running anything"),)),
    Action("status", standalone=True, targets=(
        Target("status", "latex-ai-status", "Everyday", "Where the project stands and what to do next"),)),
    Action("doctor", targets=(
        Target("doctor", "latex-ai-doctor", "Everyday", "Check that the required tools are installed"),)),
    Action("help", standalone=True, targets=(
        Target("help", "latex-ai-help", "Everyday", "This list"),)),
    Action("guide", standalone=True, targets=(
        Target("guide", "latex-ai-guide", "Everyday", "A short manual for this project"),)),
    Action("build", module="latex", document=True, view=True, targets=(
        Target("build", "latex-ai-build", "Manuscript", "Build the PDF and record its input/output validity", selects="document", usage="DOC=NAME"),)),
    Action("build-prepare", module="latex", document=True, view=True),    # internal transaction hooks of an adopted build
    Action("build-finish", module="latex", document=True, view=True),
    Action("build-shell", module="latex", view=True),
    Action("lint", module="latex", document=True, view=True, targets=(
        Target("lint", None, "Manuscript", "Run the configured static checks (ChkTeX)"),
        Target("document-lint", "latex-ai-lint", "Documents", "Run the selected document's static checks (ChkTeX)", selects="document", usage="DOC=NAME"))),
    Action("documents", module="latex", targets=(
        Target("documents", "latex-ai-documents", "Documents", "List declared documents and their build validity"),)),
    Action("document-check", module="latex", document=True, targets=(
        Target("document-check", "latex-ai-document-check", "Documents", "Build, verify and lint one document; DOC=name selects it", selects="document", usage="DOC=NAME"),)),
    Action("lint-baseline", module="latex", document=True, view=True, targets=(
        Target("lint-baseline", "latex-ai-lint-baseline", "Manuscript", "Accept today's ChkTeX warnings as a recorded baseline; new ones still fail (owner's decision)", selects="document", usage="DOC=NAME"),)),
    Action("verify", module="latex", document=True, view=True),
    Action("bib-check", needs=("latex", "bibliography"), document=True, targets=(
        Target("bib-check", "latex-ai-bib-check", "Manuscript", "Check bibliography files, entries and duplicate keys (the full check finds undefined citations)", selects="document"),)),
    Action("artifact", module="latex", document=True, view=True, targets=(
        Target("pdf-artifact", "latex-ai-pdf-artifact", "Manuscript", "Copy the verified current PDF to .latex-ai/artifacts/", selects="document", usage="DOC=NAME"),)),
    Action("clean", module="latex", document=True, view=True, targets=(
        Target("clean", "latex-ai-clean", "Manuscript", "Remove build files", selects="document", usage="DOC=NAME"),)),
    Action("modules", native_json=True, targets=(
        Target("modules", "latex-ai-modules", "Inspect and report", "Show which modules are enabled (JSON)"),)),
    Action("issue", standalone=True, targets=(
        Target("issue", "latex-ai-issue", "Inspect and report", 'Write a local report on a suspected workbench defect: ISSUE_NOTE="observed ... expected ..."', selects="note"),)),
)

NAMES = tuple(action.name for action in ACTIONS)
BY_NAME = {action.name: action for action in ACTIONS}

# The Make goals that run the project's own build command again: the check, validate and document-check actions under every name,
# and the reserved build goal. A build command that reaches one of them would call itself. (The short `build` is not among them:
# where the project has a target of that name it is the project's own.)
RECURSIVE_GOALS = frozenset(
    [target.short for name in ("check", "validate", "document-check") for target in BY_NAME[name].targets]
    + [target.reserved for name in ("check", "validate", "document-check", "build") for target in BY_NAME[name].targets if target.reserved])


def _commands():
    rows = []
    for action in ACTIONS:
        needs = action.needs if action.needs is not None else ((action.module,) if action.module else ())
        for target in action.targets:
            recipe = None if target.reserved is None else action.name
            rows.append(Command(target.short, target.reserved, target.group, target.description, recipe, needs, target.selects, target.usage))
    return rows


COMMANDS = _commands()
