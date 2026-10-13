"""Project Make and editor-policy adapters generated from shared command contracts."""
import re
import shlex
import os
import make_graph
import guide
from commands import RECIPE_ARGUMENTS, RESERVED_PREFIX
from guide import make_targets
from core import WorkbenchError, has_module
from schema import document_settings, specifications

BEGIN = "# BEGIN LATEX AI WORKBENCH"
END = "# END LATEX AI WORKBENCH"

def block(content):
    return BEGIN + "\n" + content.rstrip() + "\n" + END + "\n"


def merge_block(current, desired, previous=None):
    if BEGIN not in current and END not in current:
        if previous is not None and (BEGIN in previous or END in previous):
            raise WorkbenchError("Previously managed block was removed locally; reconcile explicitly")
        return current.rstrip() + "\n\n" + block(desired)
    pattern = re.compile(re.escape(BEGIN) + r"\n(.*?)\n" + re.escape(END) + r"(?:\n|$)", re.S)
    matches = list(pattern.finditer(current))
    if len(matches) != 1 or current.count(BEGIN) != 1 or current.count(END) != 1:
        raise WorkbenchError("Malformed or repeated managed block")
    managed = matches[0][1] + "\n"
    if previous is not None:
        old = pattern.search(previous)
        if old and managed != old[1] + "\n" and managed != desired.rstrip() + "\n":
            raise WorkbenchError("Local changes inside managed block; reconcile manually")
    elif managed != desired.rstrip() + "\n":
        raise WorkbenchError("Unregistered managed block differs; reconcile manually")
    return current[:matches[0].start()] + block(desired) + current[matches[0].end():]


def prerequisite_expression(value):
    """Keep Make variable expressions, excluding comments and inline recipes."""
    return make_graph.partition(value, '#;')[0]


def make_edges(outside, project=None):
    """(target, prerequisite expression) for each literal rule of the project's own makefiles."""
    return [(name, deps) for name, deps in make_graph.read(outside, project).edges
            if re.fullmatch(r'[A-Za-z][\w.-]*', name)]


def matching_check_rules(generated, graph):
    """Do not mix single- and double-colon rules when extending the user's check."""
    if graph.recipe_prefix:
        raise WorkbenchError('Custom Make recipe prefix requires an explicit project adapter',
                             hint='automatic integration emits tab-prefixed recipes; preserve this Makefile and integrate manually')
    if graph.separator('check') == '::':
        return re.sub(r'^check:(?!:)', 'check::', generated, flags=re.M)
    return generated


def make_adapter(current, config, project=None):
    if not has_module(config, "latex"):
        return core_make_adapter(current, config, project)
    original_config = config
    config = document_settings(config)
    # Ignore the managed block when learning local targets during upgrades. Targets of makefiles the
    # project includes by name count as its own too.
    outside = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", current, flags=re.S)
    graph = make_graph.read(outside, project)
    targets = make_targets(outside, project)
    if not config.get("build_command"):
        return core_make_adapter(current, original_config, project)
    command = config["build_command"]
    phased = (len(command) == 2 and command[0] in {"make", "gmake"}
              and re.fullmatch(r"[A-Za-z][\w.-]*", command[1]) and command[1] in targets
              and command[1] not in {"check", "lint"} and not command[1].startswith(RESERVED_PREFIX))
    result = ["PYTHON ?= python3", ".PHONY: latex-ai-integrity latex-ai-check-passed build lint check"]
    if phased:
        goal = command[1]
        if os.name != 'posix' or any(set(rule.variables) & {'SHELL', '.SHELLFLAGS'} for rule in graph.rules):
            raise WorkbenchError('Phased Make ownership requires POSIX and a shared recipe shell',
                                 hint='target-specific SHELL/.SHELLFLAGS overrides require an explicit project build adapter')
        # One outer Make graph shares the original target with existing check
        # prerequisites. An order-only barrier covers implicit/generated
        # dependencies without forcing recompilation or changing automatic $^.
        goals = {"check", "latex-ai-build", "latex-ai-integrity", "latex-ai-check-passed"}
        if "build" not in targets:
            goals.add("build")  # generated alias reaches the receipt's finish phase
        edges = make_edges(outside, project)
        # Expand prerequisite variables with Make's own evaluator. A bounded
        # fixed point discovers parent/default goals without executing recipes.
        parents = " ".join("$(if $(filter $(LATEX_AI_BUILD_GOALS),$(LATEX_AI_BUILD_DEPS_"
                           + str(index) + "))," + name + ")" for index, (name, _) in enumerate(edges))
        result.extend([
            "LATEX_AI_BUILD_GOALS := " + " ".join(sorted(goals)),
            *[f"LATEX_AI_BUILD_DEPS_{index} := {deps}" for index, (_, deps) in enumerate(edges)],
            "LATEX_AI_BUILD_PARENTS = " + parents,
            "$(foreach LATEX_AI_GRAPH_STEP," + " ".join(str(i) for i in range(len(edges) + 1))
            + ",$(eval LATEX_AI_BUILD_GOALS := $(sort $(LATEX_AI_BUILD_GOALS) $(LATEX_AI_BUILD_PARENTS))))",
            'LATEX_AI_RECIPE_SHELL := $(SHELL)',
            'LATEX_AI_RECIPE_FLAGS := $(.SHELLFLAGS)',
            "ifneq ($(filter $(LATEX_AI_BUILD_GOALS),$(or $(MAKECMDGOALS),$(.DEFAULT_GOAL))),)",
            # Only the goals that need the phase hooks refuse an older Make: the project's own
            # targets and the read-only commands keep working with it.
            "ifeq ($(filter extra-prereqs,$(.FEATURES)),)",
            "$(error Adopted build receipts require GNU Make 4.3 or later with extra-prereqs)", "endif",
            ".EXTRA_PREREQS += | latex-ai-build-prepare",
            goal + graph.separator(goal) + ' .EXTRA_PREREQS += | latex-ai-build-prepare',
            # Make 4.3 splits .SHELLFLAGS on whitespace under .ONESHELL, so an
            # inline quoted -c trampoline is not portable. A script forwards the
            # expanded recipe as one argument without nested shell quoting or
            # needing its execute bit. override preserves receipt ownership.
            goal + graph.separator(goal) + ' override SHELL := /bin/sh',
            goal + graph.separator(goal) + ' override .SHELLFLAGS = .latex-ai/recipe-shell.sh $(PYTHON) .latex-ai/workbench.py build-shell --shell-arguments $(LATEX_AI_RECIPE_SHELL) $(LATEX_AI_RECIPE_FLAGS)',
            'endif',
            ".PHONY: latex-ai-build-prepare latex-ai-build",
            # GNU Make 3.81 cannot parse `private`, even for unrelated goals. These shell
            # overrides are needed only by phased builds, which require extra-prereqs.
            'ifneq ($(filter extra-prereqs,$(.FEATURES)),)',
            'latex-ai-build-prepare: private override SHELL := $(LATEX_AI_RECIPE_SHELL)',
            'latex-ai-build-prepare: private override .SHELLFLAGS := $(LATEX_AI_RECIPE_FLAGS)',
            'endif',
            "latex-ai-build-prepare: .EXTRA_PREREQS =",
            "latex-ai-build-prepare:",
            '\t+@$(PYTHON) .latex-ai/workbench.py build-prepare --build-owner "$$PPID"',
            f"latex-ai-build: {goal} latex-ai-build-prepare",
            '\t+@$(PYTHON) .latex-ai/workbench.py build-finish --build-owner "$$PPID"'])
    if "build" not in targets:
        result.extend(["build: latex-ai-build"])
    if "lint" not in targets:
        result.extend(["lint:", "\t@$(PYTHON) .latex-ai/workbench.py lint"])
    # The build is verified before the style checker runs; one closing line says the workbench's part passed,
    # since an adapted `check` is assembled from Make prerequisites and may be followed by the project's own recipe.
    parts = ["latex-ai-integrity", "lint"]
    result.extend(["latex-ai-integrity: latex-ai-build", "\t@$(PYTHON) .latex-ai/workbench.py verify",
                   "latex-ai-check-passed: " + " ".join(parts),
                   '\t@echo "Workbench checks passed: build, integrity, lint"',
                   "check: latex-ai-check-passed"])
    if not phased:
        result.extend([".PHONY: latex-ai-build", "latex-ai-build:",
                       f'\t@$(PYTHON) .latex-ai/workbench.py build --document {config["name"]}'])
    others = [document for document in specifications(original_config) if not document.default]
    if others:
        result.extend([".PHONY: latex-ai-other-documents", "latex-ai-other-documents: latex-ai-check-passed"])
        for document in others:
            result.append(f'\t@$(PYTHON) .latex-ai/workbench.py document-check --document {document.name}')
        result.append("check: latex-ai-other-documents")
        result = [line.replace("Workbench checks passed:", "Default document checks passed:") for line in result]
    # Full check goals always share the adopted default's outer Make graph,
    # even with DOC set. Document-specific build goals select their target.
    edges = make_edges(outside, project)
    parents = " ".join("$(if $(filter $(LATEX_AI_CHECK_GOALS),$(LATEX_AI_CHECK_DEPS_"
                       + str(index) + "))," + name + ")" for index, (name, _) in enumerate(edges))
    check_graph = ["LATEX_AI_CHECK_GOALS := check",
                   *[f"LATEX_AI_CHECK_DEPS_{index} := {deps}" for index, (_, deps) in enumerate(edges)],
                   "LATEX_AI_CHECK_PARENTS = " + parents,
                   "$(foreach LATEX_AI_GRAPH_STEP," + " ".join(str(i) for i in range(len(edges) + 1))
                   + ",$(eval LATEX_AI_CHECK_GOALS := $(sort $(LATEX_AI_CHECK_GOALS) $(LATEX_AI_CHECK_PARENTS))))"]
    result = ["PYTHON ?= python3", "export DOC", *check_graph,
              "ifneq ($(filter " + config["name"] + ",$(or $(DOC)," + config["name"]
              + "))$(filter $(LATEX_AI_CHECK_GOALS),$(or $(MAKECMDGOALS),$(.DEFAULT_GOAL))),)",
              *[line for line in result if line != "PYTHON ?= python3"]]
    result.extend(["else", ".PHONY: latex-ai-build latex-ai-named-check", "latex-ai-build:",
                   '\t@$(PYTHON) .latex-ai/workbench.py build --document "$$DOC"',
                   "latex-ai-named-check:", '\t@$(PYTHON) .latex-ai/workbench.py check',
                   "check: latex-ai-named-check", "endif"])
    generated = "\n".join(result) + "\n" + module_make_targets(original_config, targets | {"build"},
                                                             omitted={"latex-ai-build"})
    return matching_check_rules(generated, graph)


def integration_text(name, upstream):
    if name == "AGENTS.md":
        return "## Workbench integration\n\nRead `.latex-ai.json` for enabled modules and project commands. The Makefile is canonical.\nChoose validation by changed files: `make latex-ai-plan` previews the selection;\n`make latex-ai-validate` runs it. Ordinary docs, notes and policy edits do not\nneed a manuscript build unless consumed by LaTeX. Use task-specific tests for\nunrelated code; `make check` checks enabled modules, including full manuscript\nvalidation when LaTeX is enabled.\n`make latex-ai-help` lists this project's commands by the names that work here: where the\nMakefile already had a target of a short name, that recipe was kept and the workbench\ncommand is the `latex-ai-` form. `make latex-ai-status` says where the project stands.\nA lint baseline (`.chktex-baseline.json`, written by `make latex-ai-lint-baseline`) lists style\nwarnings the owner accepted; creating or refreshing that baseline is the owner's decision.\nRespect stricter local validation policy. Inspect `git diff` / `git status`.\nGit mutations require explicit user approval; preserve all user changes.\nChanges reach the default branch (`main` or `master`) only through a pull request\nfrom a topic branch; never push, merge or fast-forward to it directly.\nAgents open pull requests; only the owner merges them.\nNever invent bibliography metadata or edit declared Zotero exports by hand.\nSuspected workbench defects (`INTERNAL ERROR`, or a result that\ncontradicts its inputs): do not edit `.latex-ai/` or weaken a check; capture\nevidence with `make latex-ai-issue ISSUE_NOTE=\"observed ... expected ...\"` and tell the user.\n"
    if name == "CLAUDE.md":
        return "Read and follow `AGENTS.md`, the canonical semantic policy.\n"
    return upstream


def module_make_targets(config, existing=(), omitted=()):
    """Every command of the registry (commands.py, as guide.COMMANDS) that this configuration enables, under its reserved ``latex-ai-``
    name, plus the short alias where the project has no target of that name. Guidance and hints can therefore
    always name a command that reaches the workbench, and no command is named in a second place."""
    commands = [command for command in guide.COMMANDS if command.reserved and command.reserved not in omitted and guide.enabled(command, config)]
    # DOC reaches recipes through the environment ("$$DOC"), never as Make text
    # spliced into a shell line, so its value cannot be interpreted as shell syntax.
    result = ["export ISSUE_NOTE ISSUE_COMMAND"]  # the same rule for the issue report's free text
    result.append("export DOC")  # the document selector
    for command in commands:
        result.extend([f".PHONY: {command.reserved}", f"{command.reserved}:"])
        result.append(f"\t@$(PYTHON) .latex-ai/workbench.py {command.action}{RECIPE_ARGUMENTS[command.selects]}")
        if command.short not in existing:
            result.extend([f".PHONY: {command.short}", f"{command.short}: {command.reserved}"])
    return "\n".join(result) + "\n"


def core_makefile(config):
    return "# Project-local core checks.\nPYTHON ?= python3\n.DEFAULT_GOAL := check\n.PHONY: check\ncheck:\n\t@$(PYTHON) .latex-ai/workbench.py check\n"


def core_make_adapter(current, config, project=None):
    outside = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", current, flags=re.S)
    targets = make_targets(outside, project)
    result = ["PYTHON ?= python3", ".PHONY: latex-ai-core-check",
              "latex-ai-core-check:", "\t@$(PYTHON) .latex-ai/workbench.py check", "check: latex-ai-core-check"]
    return matching_check_rules("\n".join(result) + "\n" + module_make_targets(config, targets), make_graph.read(outside, project))
