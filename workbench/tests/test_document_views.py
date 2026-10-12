"""Resolved document views are immutable, typed mappings whose JSON is exactly what 3.2.0 stored.

The build record keeps a view as JSON ("configuration") and compares it with the view of the build that finishes it, so
the shape must not change while a build runs across an upgrade. `fixtures/views.json` pins it, for every configuration
of the generated-files guard and one that sets every key a document can carry. Refresh it only with
`python3 -B tests/test_document_views.py --generate`, and only when a release announces a change of shape.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import core
import schema
from test_generated_files_guard import FIXTURES

STORED = Path(__file__).resolve().parent / "fixtures" / "views.json"

# One configuration that sets every key a document or the shared settings can carry.
EVERY_KEY = {
    "schema_version": 3,
    "modules": {
        "latex": {"default_document": "paper",
                  "defaults": {"engine": "lualatex", "backend": "biber", "lint": {"enabled": True, "args": ["-n8"]}, "output_dir": "out"},
                  "documents": {"paper": {"root": "main.tex", "inputs": ["data/*.csv"], "bibliography_files": ["extra.bib"]},
                                "note": {"root": "notes/note.tex", "engine": "xelatex", "backend": "bibtex", "build_command": ["make", "note"],
                                         "output_dir": "note-out", "lint": {"enabled": False, "baseline": "note.baseline.json"}}}},
        "bibliography": {"files": ["refs.bib"], "export": {"path": "refs.bib", "required": True, "format": "biblatex"}},
    },
    "integrations": {"editor": False, "ci": {"enabled": True, "pdf_artifact": True, "texlive_version": "2026"}},
    "validation": {"manuscript_inputs": ["figures/*.pdf"], "package": None},
}
CONFIGURATIONS = {**{name: config for name, (config, makefile) in FIXTURES.items()}, "every-key": EVERY_KEY}


def rendered():
    """For every configuration, each declared document with its view as the JSON a build record stores."""
    return {name: [{"name": document.name, "default": document.default, "view": json.loads(document.configuration)}
                   for document in schema.specifications(core.effective_config(config))]
            for name, config in CONFIGURATIONS.items()}


def generate():
    STORED.parent.mkdir(parents=True, exist_ok=True)
    STORED.write_text(json.dumps(rendered(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ViewShapeIsPinned(unittest.TestCase):
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
        self.assertEqual((view.name, view.root, view.engine, view.output_dir), ("note", "notes/note.tex", "xelatex", "note-out"))
        self.assertEqual(list(view.build_command), ["make", "note"])
        self.assertEqual(view.lint["enabled"], False)
        self.assertEqual(view.bibliography["backend"], "bibtex")
        self.assertEqual(view.ci["texlive_version"], "2026")
        self.assertEqual(list(self.view("paper").inputs), ["data/*.csv"])
        self.assertEqual(view.validation["manuscript_inputs"], ["figures/*.pdf"])

    def test_to_json_and_deep_copies_are_plain_mutable_data(self):
        view = self.view()
        for copy_ in (view.to_json(), copy.deepcopy(view)):
            self.assertIs(type(copy_), dict)
            self.assertIs(type(copy_["lint"]), dict)
            self.assertIs(type(copy_["lint"]["args"]), list)
            self.assertEqual(copy_, view)
            copy_["lint"]["args"].append("-n9")  # a copy is the caller's to change
        self.assertEqual(list(view.lint["args"]), ["-n8"])

    def test_a_project_without_latex_gets_shared_settings_not_a_document(self):
        config = core.effective_config({"schema_version": 3, "modules": {"bibliography": {"files": ["refs.bib"], "export": None}}})
        settings = schema.document_settings(config)
        self.assertIsInstance(settings, schema.SharedSettings)
        self.assertNotIsInstance(settings, schema.DocumentView)
        self.assertEqual(list(settings.bibliography["files"]), ["refs.bib"])
        self.assertEqual(set(settings), {"bibliography", "validation", "ci"})

    def test_document_settings_resolves_a_project_configuration_and_refuses_a_view(self):
        config = core.effective_config(EVERY_KEY)
        view = schema.document_settings(config, "note")
        self.assertIsInstance(view, schema.DocumentView)
        with self.assertRaises(TypeError):
            schema.document_settings(view)  # already resolved: the caller that holds it uses it as it is


class BackendsTakeResolvedViews(unittest.TestCase):
    def test_the_latex_backend_never_resolves_a_configuration(self):
        source = (Path(schema.__file__).resolve().parent / "latex.py").read_text(encoding="utf-8")
        self.assertNotIn("document_settings", source)

    def test_a_backend_refuses_a_project_configuration_instead_of_checking_nothing(self):
        import latex
        config = core.effective_config({"schema_version": 3, "modules": {"bibliography": {"files": ["refs.bib"], "export": None}}})
        for call in (latex.bibliography_check, latex.declared_bibs):
            with self.subTest(call=call.__name__), self.assertRaises(AttributeError):
                call(Path("."), config)  # a project configuration has no bibliography settings of its own; resolve it first
        settings = schema.document_settings(config)
        self.assertEqual([path.name for path in latex.declared_bibs(Path("."), settings)], ["refs.bib"])

if __name__ == "__main__":
    generate() if "--generate" in sys.argv else unittest.main()
