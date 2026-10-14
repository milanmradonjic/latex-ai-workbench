"""Guard: the Makefile block and the editor files an installed project carries stay byte-identical.

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
import bootstrap
import core

STORED = Path(__file__).resolve().parent / "fixtures" / "generated"
SUFFIX = ".txt"  # so no tool mistakes a stored copy for a live Makefile, workflow or editor file, and the planner files it as plain text
GUARDED = {"Makefile": "Makefile", ".vscode/settings.json": "vscode-settings.json",
           ".vscode/tasks.json": "vscode-tasks.json"}  # generated path -> stored name


def starting(modules, editor=True):
    """The configuration `init --modules ...` starts from (bootstrap.detect_config)."""
    return {"schema_version": 3, "modules": {n: copy.deepcopy(core.MODULES[n]["defaults"]) for n in modules},
            "integrations": {"editor": editor}}


# The multi-document example (examples/tex-notes), with the editor files switched on.
MULTI_DOCUMENT = {
    "schema_version": 3,
    "modules": {"latex": {"default_document": "paper", "documents": {
                    "paper": {"root": "main.tex"}, "derivation": {"root": "notes/derivation.tex"},
                    "notebook": {"root": "notes/notebook.tex"}}}},
    "integrations": {"editor": True},
}

# name -> configuration
FIXTURES = {
    "core-only": starting([]),
    "latex": starting(["latex"]),
    "latex-no-editor": starting(["latex"], editor=False),
    "multi-document": MULTI_DOCUMENT,
}


def render(config):
    """What the installer would carry into a project for this configuration, keyed by the stored file name."""
    return {GUARDED[name]: text for name, text in bootstrap.desired_files(config).items() if name in GUARDED}


def generate():
    """Write the stored copies from the current code. A deliberate act: review the diff before committing it."""
    for name, config in FIXTURES.items():
        directory = STORED / name
        directory.mkdir(parents=True, exist_ok=True)
        rendered = {filename + SUFFIX: text for filename, text in render(config).items()}
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
        for name, config in FIXTURES.items():
            rendered = render(config)
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
