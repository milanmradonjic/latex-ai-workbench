"""Guard: the Makefile block, editor files and CI workflow an installed project carries stay byte-identical.

Upgrading must not churn an installed project, so a refactor of the code that renders these files (Phase 1 of
the plan after 3.0.2 replaces the command tables behind them) must leave them exactly as they are. Each fixture
configuration below is rendered and compared, byte for byte, with the copy stored in ``tests/fixtures/generated/``.

A failure means generated text changed. Undo the change, or, when the release announces it, refresh the copies
with ``python3 -B tests/test_generated_files_guard.py --generate`` and review the diff of the stored files.
"""
import copy
import difflib
import shutil
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import adapters
import bootstrap
import core

STORED = Path(__file__).resolve().parent / "fixtures" / "generated"
SUFFIX = ".txt"  # so no tool mistakes a stored copy for a live Makefile, workflow or editor file, and the planner files it as plain text
WORKFLOW = ".github/workflows/latex-ai.yml"
GUARDED = {"Makefile": "Makefile", ".vscode/settings.json": "vscode-settings.json",
           ".vscode/tasks.json": "vscode-tasks.json", WORKFLOW: "workflow.yml"}  # generated path -> stored name


def profile(name, editor=True, ci=True, build_command=None):
    """The configuration `init --profile NAME` starts from (bootstrap.detect_config), with an optional build command."""
    modules = core.PROFILES[name]
    config = {"schema_version": 3, "modules": {n: copy.deepcopy(core.MODULES[n]["defaults"]) for n in modules},
              "integrations": {"editor": editor, "ci": {"enabled": ci, "pdf_artifact": "latex" in modules, "texlive_version": "2026"}}}
    if build_command:
        config["modules"]["latex"]["documents"]["manuscript"].update(build_command=build_command, output_dir=".")
    return config


# The multi-document example (examples/tex-notes), with the editor files and CI switched on.
MULTI_DOCUMENT = {
    "schema_version": 3,
    "modules": {"latex": {"default_document": "paper", "documents": {
                    "paper": {"root": "main.tex"}, "derivation": {"root": "notes/derivation.tex"},
                    "notebook": {"root": "notes/notebook.tex"}}},
                "notes": {"path": "notes", "index": "index.md", "session_state": "state.tex"}},
    "integrations": {"editor": True, "ci": {"enabled": True, "pdf_artifact": True, "texlive_version": "2026"}},
}

# A project's own Makefile that the installer adopts: the managed block is merged into it, never written whole.
PHASED = ".PHONY: pdf\npdf:\n\t@echo project pdf rule\n"
CHECK_REACHES_GOAL = ".PHONY: pdf check\npdf:\n\t@echo project pdf rule\ncheck: pdf\n\t@echo project check\n"
OWN_SHORT_NAMES = "".join(f"{name}:\n\t@echo project {name}\n" for name in ("pdf", "doctor", "status", "help", "validate", "clean"))
OTHER_BUILD = "all:\n\t@echo project build\n"
OWN_CHECK = "check:\n\t@echo project check\n"

# name -> (configuration, the project's existing Makefile, or None for a fresh install)
FIXTURES = {
    **{f"profile-{name}": (profile(name), None) for name in core.PROFILES},
    "profile-writing-no-editor-no-ci": (profile("writing", editor=False, ci=False), None),
    "multi-document": (MULTI_DOCUMENT, None),
    "adopted-make-goal": (profile("writing", build_command=["make", "pdf"]), PHASED),
    "adopted-make-goal-reached-by-check": (profile("writing", build_command=["make", "pdf"]), CHECK_REACHES_GOAL),
    "adopted-make-own-short-names": (profile("writing", build_command=["make", "pdf"]), OWN_SHORT_NAMES),
    "adopted-other-build-command": (profile("writing", build_command=["python3", "build.py"]), OTHER_BUILD),
    "adopted-no-tex": (profile("numerical"), OWN_CHECK),
}


def render(config, makefile=None):
    """What the installer would carry into a project for this configuration, keyed by the stored file name."""
    files = {name: text for name, text in bootstrap.desired_files(config).items() if name in GUARDED}
    if makefile is not None:
        files["Makefile"] = adapters.make_adapter(makefile, config)  # the block merged into the project's Makefile
    files[WORKFLOW] = adapters.workflow(config)  # with CI off the installer still keeps an existing workflow, disabled
    return {GUARDED[name]: text for name, text in files.items()}


def generate():
    """Write the stored copies from the current code. A deliberate act: review the diff before committing it."""
    for name, (config, makefile) in FIXTURES.items():
        directory = STORED / name
        directory.mkdir(parents=True, exist_ok=True)
        rendered = {filename + SUFFIX: text for filename, text in render(config, makefile).items()}
        for filename, text in rendered.items():
            (directory / filename).write_bytes(text.encode("utf-8"))
        for stale in directory.iterdir():
            if stale.name not in rendered:
                stale.unlink()
    for orphan in STORED.iterdir():
        if orphan.name not in FIXTURES:
            shutil.rmtree(orphan) if orphan.is_dir() else orphan.unlink()


class GeneratedFilesGuard(unittest.TestCase):
    def test_every_fixture_renders_exactly_its_stored_copies(self):
        for name, (config, makefile) in FIXTURES.items():
            rendered = render(config, makefile)
            directory = STORED / name
            with self.subTest(fixture=name):
                stored = sorted(path.name for path in directory.glob("*")) if directory.is_dir() else []
                self.assertEqual(stored, sorted(filename + SUFFIX for filename in rendered),
                                 f"{name}: the files generated no longer match the stored copies (see the module docstring)")
            for filename, text in rendered.items():
                with self.subTest(fixture=name, file=filename):
                    path = directory / (filename + SUFFIX)
                    self.assertTrue(path.is_file(), f"{path} is missing; see the module docstring")
                    expected = path.read_bytes()
                    if text.encode("utf-8") != expected:
                        change = "".join(list(difflib.unified_diff(expected.decode("utf-8").splitlines(True), text.splitlines(True),
                                                                   "stored", "generated", n=1))[:60])
                        self.fail(f"{name}/{filename} changed. An installed project would change on upgrade.\n{change}")

    def test_no_stored_fixture_is_left_without_a_fixture(self):
        self.assertEqual(sorted(path.name for path in STORED.iterdir()) if STORED.is_dir() else [], sorted(FIXTURES))


if __name__ == "__main__":
    generate() if "--generate" in sys.argv else unittest.main()
