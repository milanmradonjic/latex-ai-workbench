"""Tests of named documents and their views: defaults, selectors, notes, `make all` and a target for each.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 5 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_document_views.py:
Resolved document views are immutable, typed mappings whose JSON is exactly what 3.2.0 stored.

The build record keeps a view as JSON ("configuration") and compares it with the view of the build that finishes it, so
the shape must not change while a build runs across an upgrade. `fixtures/views.json` pins it, for every configuration
of the generated-files guard and one that sets every key a document can carry. Refresh it only with
`python3 -B tests/test_documents.py --generate`, and only when a release announces a change of shape.

test_documents.py:
Installed workflows for named TeX documents and mixed note organization.

test_repairs_3_2_0.py:
3.2.0: --document names a LaTeX document, so a project without LaTeX refuses it and says how to turn LaTeX on.

Before, `check --document X` and `bib-check --document X` in a project created without LaTeX stopped with an internal
error (`documents.py` was not installed there). Once the configuration code moved into `schema.py`, which every
project has, they refused, but without the hint `build --document X` gives; where LaTeX had been disabled they
never gave one.

test_scope_4_4_0.py:
Workbench 4.4.0 removes the adoption of a project's own Makefile (see docs/maintainers/minimal-scope.md): the workbench no longer merges
into, parses or wraps a Makefile it did not write. `init` creates a project and refuses to touch a file of the project's that differs
from what it would write; an existing project is migrated to the workbench's layout by an agent following docs/migrating.md.

These tests pin what is gone (the Make parser, the adapter, the build hooks, the Make version requirement), what `init` now promises
(it writes only files that are absent or already identical, and says what to do about the rest) and what stays (a project's own Make
targets run as an ordinary build command, and `validate` still runs a project's own `check`).

test_scope_4_6_0.py:
Workbench 4.6.0, step 3.5 of docs/maintainers/plan-after-4.4.0.md: `make all`, and `make NAME` for each document of a project that has several.

`make all` builds every document, one after another (one runtime action, `build --all`, because the project's build lock refuses two builds at once and so
`make -j all` must not start them side by side). `make notes` builds that document, as `make build DOC=notes` does. The generated Makefile gains the targets on purpose:
`all` for every project with LaTeX, and a target per document when there are two or more, written only where the name is free. The bare `make` still builds the
default document. `make guide` names the targets, and `diff` shows an existing project the lines it lacks.
"""

import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap
import core
import documents
import latex
import schema
from test_installer import FIXTURES
from test_support import ProjectCase, isolate_environment, prepare_config


# One configuration that sets every key a document or the shared settings can carry.
EVERY_KEY = {'schema_version': 4, 'default_document': 'paper', 'defaults': {'engine': 'pdflatex', 'backend': 'bibtex', 'lint': {'enabled': True, 'args': ['-n8']}, 'output_dir': 'out'}, 'documents': {'paper': {'root': 'main.tex', 'inputs': ['data/*.csv'], 'bibliography_files': ['extra.bib']}, 'note': {'root': 'notes/note.tex', 'engine': 'pdflatex', 'backend': 'none', 'build_command': ['make', 'note'], 'output_dir': 'note-out', 'lint': {'enabled': False, 'baseline': 'note.baseline.json'}}}, 'bibliography': {'files': ['refs.bib'], 'export': {'path': 'refs.bib', 'required': True, 'format': 'bibtex'}}, 'integrations': {'editor': False}}


CONFIGURATIONS = {**dict(FIXTURES), "every-key": EVERY_KEY}


STORED = Path(__file__).resolve().parent / "fixtures" / "views.json"


def rendered():
    """For every configuration, each declared document with its view as the JSON a build record stores."""
    return {name: [{"name": document.name, "default": document.default, "view": json.loads(document.configuration)}
                   for document in schema.specifications(core.effective_config(config))]
            for name, config in CONFIGURATIONS.items()}


TEX = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


REMOVED_WORDS = re.compile(r"(?i)adopted (?:make|single-target|build|command|goal|document)|EXTRA_PREREQS|GNU Make 4\.3|build-shell|build-prepare"
                           r"|kept your Makefile target|explicit (?:project )?adapter|phased (?:Make|build)|shared adopted|Make adoption")


BUILDER = ("import sys\nfrom pathlib import Path\nname = sys.argv[1]\n"
           "if Path('fail-' + name).exists():\n    sys.exit('simulated compiler failure for ' + name)\n"
           "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
           "(out / (name + '.pdf')).write_bytes(b'%PDF-fixture ' + name.encode())\n"
           "(out / (name + '.log')).write_text('Clean log\\n')\n"
           "(out / (name + '.fls')).write_text('PWD ' + str(Path.cwd()) + '\\nINPUT ' + name + '.tex\\n')\n")


SOURCE = "\\documentclass{article}\\begin{document}x\\end{document}\n"


def document(name, **fields):
    return {"root": f"{name}.tex", "lint": {"enabled": False}, "output_dir": "outputs", "build_command": [sys.executable, "builder.py", name], **fields}


def configuration(*names, default=None, **fields):
    return {'schema_version': 4, 'default_document': default or names[0], 'documents': {name: document(name, **fields) for name in names}, 'integrations': {'editor': False}}


def generate():
    STORED.parent.mkdir(parents=True, exist_ok=True)
    STORED.write_text(json.dumps(rendered(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ViewShapeIsPinned(unittest.TestCase):
    """Origin: tests/test_document_views.py."""

    def test_every_view_has_exactly_the_json_stored_for_it(self):
        self.assertEqual(rendered(), json.loads(STORED.read_text(encoding="utf-8")),
                         "a view changed shape: a build running across an upgrade would fail (see the module docstring)")

    def test_the_stored_text_of_a_build_record_is_the_canonical_json_of_the_view(self):
        for name, config in CONFIGURATIONS.items():
            for document in schema.specifications(core.effective_config(config)):
                with self.subTest(configuration=name, document=document.name):
                    self.assertEqual(json.dumps(document.view, sort_keys=True), document.configuration)
                    self.assertEqual(json.dumps(document.view.to_json(), sort_keys=True), document.configuration)


class ViewTypes(unittest.TestCase):
    """Origin: tests/test_document_views.py."""

    def view(self, name="paper"):
        return schema.resolve(core.effective_config(EVERY_KEY), name).view

    def test_a_view_is_a_document_view_and_compares_equal_to_the_dict_a_build_record_was_loaded_into(self):
        view = self.view()
        self.assertIsInstance(view, schema.DocumentView)
        self.assertIsInstance(view, dict)
        loaded = json.loads(json.dumps({"configuration": view}))["configuration"]
        self.assertEqual(loaded, view)
        self.assertEqual(view, loaded)
        self.assertFalse(loaded != view)

    def test_a_view_refuses_every_change_at_every_depth(self):
        view = self.view()
        for attempt in (lambda: view.__setitem__("root", "x"), lambda: view.pop("root"), lambda: view.update(root="x"),
                        lambda: view.setdefault("new", 1), lambda: view.clear(), lambda: view.popitem(), lambda: view.__delitem__("root"),
                        lambda: view["lint"].__setitem__("enabled", False), lambda: view["lint"]["args"].append("-n9"),
                        lambda: view["inputs"].sort(), lambda: view["bibliography"]["files"].extend(["x.bib"]),
                        lambda: view["bibliography"].update(backend="none")):
            with self.subTest(attempt=attempt), self.assertRaises(TypeError):
                attempt()

    def test_typed_properties_read_the_keys_the_backends_use(self):
        view = self.view("note")
        self.assertEqual((view.name, view.root, view.engine, view.output_dir), ("note", "notes/note.tex", "pdflatex", "note-out"))
        self.assertEqual(list(view.build_command), ["make", "note"])
        self.assertEqual(view.lint["enabled"], False)
        self.assertEqual(view.bibliography["backend"], "none")
        self.assertEqual(list(self.view("paper").inputs), ["data/*.csv"])
        self.assertEqual(self.view("paper").validation["manuscript_inputs"], ["data/*.csv"])

    def test_to_json_and_deep_copies_are_plain_mutable_data(self):
        view = self.view()
        for copy_ in (view.to_json(), copy.deepcopy(view)):
            self.assertIs(type(copy_), dict)
            self.assertIs(type(copy_["lint"]), dict)
            self.assertIs(type(copy_["lint"]["args"]), list)
            self.assertEqual(copy_, view)
            copy_["lint"]["args"].append("-n9")  # a copy is the caller's to change
        self.assertEqual(list(view.lint["args"]), ["-n8"])


    def test_document_settings_resolves_a_project_configuration_and_refuses_a_view(self):
        config = core.effective_config(EVERY_KEY)
        view = schema.document_settings(config, "note")
        self.assertIsInstance(view, schema.DocumentView)
        with self.assertRaises(TypeError):
            schema.document_settings(view)  # already resolved: the caller that holds it uses it as it is


class BackendsTakeResolvedViews(unittest.TestCase):
    """Origin: tests/test_document_views.py."""

    def test_the_latex_backend_never_resolves_a_configuration(self):
        source = (Path(schema.__file__).resolve().parent / "latex.py").read_text(encoding="utf-8")
        self.assertNotIn("document_settings", source)

    def test_a_backend_refuses_a_project_configuration_instead_of_checking_nothing(self):
        import latex
        config = core.effective_config({'schema_version': 4, 'default_document': 'paper', 'documents': {'paper': {'root': 'main.tex'}}, 'bibliography': {'files': ['refs.bib'], 'export': None}})
        for call in (latex.bibliography_check, latex.declared_bibs):
            with self.subTest(call=call.__name__), self.assertRaises(AttributeError):
                call(Path("."), config)  # a project configuration has no bibliography settings of its own; resolve it first
        settings = schema.document_settings(config)
        self.assertEqual([path.name for path in latex.declared_bibs(Path("."), settings)], ["refs.bib"])


class DocumentTests(unittest.TestCase):
    """Origin: tests/test_documents.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-documents-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def install(self, *arguments, expected=0, **choices):
        prepare_config(self.project, **choices)
        result = subprocess.run([sys.executable, "-B", str(bootstrap.PACKAGE / "latex-ai-init"),
                                 *arguments, str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def make(self, *arguments, expected=0):
        result = subprocess.run(["make", *arguments], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def snapshot(self):
        """Every project file's bytes, except the empty lock files a refused operation leaves in the ignored artifacts."""
        locks = self.project / core.LOCKS
        return {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*")
                if p.is_file() and not p.is_relative_to(locks)}

    def configuration(self):
        for root in ("main.tex", "notes/main.tex"):
            path = self.project / root
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\\documentclass{article}\n\\begin{document}A note.\\end{document}\n")
        (self.project / "compile.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "root, out = Path(sys.argv[1]), Path(sys.argv[2])\n"
            "if 'BROKEN' in root.read_text(): raise SystemExit(2)\n"
            "out.mkdir(parents=True, exist_ok=True)\n"
            "(out/(root.stem+'.pdf')).write_bytes(b'%PDF-1.4\\n'+root.read_bytes())\n"
            "(out/(root.stem+'.log')).write_text('Clean compiler log\\n')\n")
        config = {'schema_version': 4, 'default_document': 'paper', 'defaults': {'lint': {'enabled': False}}, 'documents': {'paper': {'root': 'main.tex', 'build_command': [sys.executable, 'compile.py', 'main.tex', '.latex-ai/artifacts/documents/paper/build']}, 'note': {'root': 'notes/main.tex', 'build_command': [sys.executable, 'compile.py', 'notes/main.tex', '.latex-ai/artifacts/documents/note/build']}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        return config

    def test_per_document_defaults_are_independent(self):
        config = self.configuration()
        config["defaults"]["lint"]["args"] = ["-n8"]
        config["documents"]["note"]["lint"] = {"enabled": True}
        config["documents"]["note"]["backend"] = "bibtex"
        schema.validate_config(self.project, config)
        note = schema.resolve(config, "note").view
        self.assertEqual(note["lint"], {"enabled": True, "args": ["-n8"], "baseline": ".latex-ai/lint-baselines/note.json"})
        changed = note.to_json()  # a view is read-only; a copy is the caller's to change
        changed["lint"]["args"].append("-n9")
        self.assertEqual(note["lint"]["args"], ["-n8"])
        self.assertEqual(schema.resolve(config, "paper").view["lint"]["args"], ["-n8"])
        self.assertIn("bibtex", schema.required_tools(config))

    def test_rejects_duplicate_roots_and_output_stems(self):
        config = self.configuration()
        targets = config["documents"]
        targets["note"]["root"] = "./main.tex"
        with self.assertRaisesRegex(core.WorkbenchError, "collision"):
            schema.validate_config(self.project, config)
        targets["note"]["root"] = "notes/main.tex"
        for target in targets.values():
            target["output_dir"] = "output"
        with self.assertRaisesRegex(core.WorkbenchError, "collision"):
            schema.validate_config(self.project, config)

    def test_malformed_document_values_are_expected_configuration_errors(self):
        for field, value in (("bibliography_files", [{}]), ("root", []), ("lint", []), ("inputs", [{}])):
            config = self.configuration()
            config["documents"]["note"][field] = value
            with self.subTest(field=field), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, config)

    def test_invalid_selector_does_not_mutate_project(self):
        self.configuration()
        self.install("init")
        before = self.snapshot()
        result = self.make("build", "DOC=../../paper", expected=2)
        self.assertIn("Unknown document", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_notes_paths_cannot_escape_the_notes_directory(self):
        for name in ("../state.tex", "/tmp/state.tex", "", "../../.latex-ai/state.tex"):
            config = {'schema_version': 4}
            with self.subTest(name=name), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, config)

    def test_editor_tasks_use_named_make_commands(self):
        config = self.configuration()
        config["integrations"] = {"editor": True}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        tasks = json.loads((self.project / ".vscode/tasks.json").read_text())["tasks"]
        self.assertIn(["build", "DOC=note"], [task["args"] for task in tasks])

    def test_symlink_root_uses_named_output_directory(self):
        (self.project / "src").mkdir()
        (self.project / "alias").mkdir()
        (self.project / "src/main.tex").write_text("\\documentclass{article}\n")
        (self.project / "alias/paper.tex").symlink_to(self.project / "src/main.tex")
        self.install('init', root='alias/paper.tex', lint=False, editor=False)
        original = latex.output_paths(self.project, schema.document_settings(schema.load_config(self.project)))[2]
        self.assertIn("/.latex-ai/artifacts/documents/manuscript/build/", str(original).replace("\\", "/"))
        self.assertIn("/.latex-ai/artifacts/documents/manuscript/build/main.pdf", (self.project / ".gitignore").read_text())


class Documents(unittest.TestCase):
    """Origin: tests/test_scope_4_4_0.py, workbench 4.4.0."""

    def test_no_live_document_or_guide_describes_what_is_gone(self):
        paths = [PACKAGE / name for name in ("README.md", "templates/AGENTS.md", "skills/latex-ai-workbench/SKILL.md", "skills/latex-ai-workbench/references/installation.md",
                                             "runtime.py", "schema.py", "bootstrap.py", "core.py", "latex.py", "Makefile")]
        paths += sorted(path for path in (PACKAGE / "docs").glob("*.md") if path.name != "migrating.md")  # the recipe names the old adapter, to recognize it
        for path in paths:
            with self.subTest(file=path.name):
                found = REMOVED_WORDS.search(path.read_text(encoding="utf-8"))
                self.assertIsNone(found, found and found.group(0))

    def test_the_explicit_installation_recipe_is_written_down(self):
        text = (PACKAGE / "docs/installing.md").read_text()
        self.assertIn("Prepare `.latex-ai.json`", text)
        self.assertIn("does not", text)
        self.assertFalse((PACKAGE / "docs/migrating.md").exists())


class Running(ProjectCase):
    """Origin: tests/test_scope_4_6_0.py, workbench 4.6.0."""

    def setUp(self):
        super().setUp()
        for name in ("paper", "notes"):
            (self.project / f"{name}.tex").write_text(SOURCE)
        (self.project / "builder.py").write_text(BUILDER)
        (self.project / core.CONFIG).write_text(json.dumps(configuration("paper", "notes")))
        self.install('init', editor=False)

    def states(self):
        return {row["id"]: row["state"] for row in documents.report(self.project, schema.load_config(self.project))}

    def test_make_with_an_explicit_selector_builds_that_document_only(self):
        self.run_command("make", "build", "DOC=notes")
        self.assertEqual(self.states(), {"paper": "missing", "notes": "current"})

    def test_bare_make_builds_the_default_document_only(self):
        self.run_command("make")
        self.assertEqual(self.states(), {"paper": "current", "notes": "missing"})

    def test_make_all_builds_every_document_even_when_make_is_asked_for_parallel_jobs(self):
        result = self.run_command("make", "-j4", "all")
        self.assertEqual(self.states(), {"paper": "current", "notes": "current"})
        self.assertNotIn("Cannot lock", result.stdout + result.stderr)

    def test_all_stops_at_the_first_failure_and_names_the_document(self):
        (self.project / "fail-notes").write_text("")
        result = self.run_command("make", "all", expected=2)
        self.assertEqual(self.states()["paper"], "current")
        self.assertIn("notes", result.stdout + result.stderr)

    def test_all_does_not_try_the_documents_after_a_failure(self):
        (self.project / "fail-paper").write_text("")
        self.run_command("make", "all", expected=2)
        self.assertEqual(self.states(), {"paper": "failed", "notes": "missing"})

    def test_all_refuses_a_named_document_and_belongs_to_build_only(self):
        self.command("build", "--all", "--document", "paper", expected=1)
        self.command("lint", "--all", expected=1)


if __name__ == "__main__":
    generate() if "--generate" in sys.argv else unittest.main()
