"""3.4.1: LaTeX Workshop's View PDF looks where each document is built.

Before, the generated .vscode/settings.json never set latex-workshop.latex.outDir, so the viewer looked beside the root
file while the build wrote elsewhere (revision/main.tex built into revision/build/): a blank viewer that reported a
zero-byte PDF. outDir is one string whose placeholders expand per root file, so the workbench derives the first value that
gives every document its real output directory, and says so when none does.
"""
import json
import sys
import unittest

from test_support import ProjectCase

import bootstrap

TEX = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


def documents(*pairs):
    return [{"root": root, "output_dir": output, "name": root.rsplit("/", 1)[-1].removesuffix(".tex")} for root, output in pairs]


class ViewerOutputDirectory(unittest.TestCase):
    def out_dir(self, *pairs):
        return bootstrap.viewer_out_dir(documents(*pairs))

    def test_a_document_built_beside_its_root_needs_no_setting(self):
        self.assertEqual(self.out_dir(("main.tex", ".")), (None, None))
        self.assertEqual(self.out_dir(("paper/main.tex", "paper"), ("paper/note.tex", "./paper/")), (None, None))

    def test_the_reported_layout_gets_the_value_that_aligns_the_viewer(self):
        # revision/main.tex and revision/supplementary.tex, both built into revision/build/
        self.assertEqual(self.out_dir(("revision/main.tex", "revision/build"), ("revision/supplementary.tex", "revision/build")),
                         ("%DIR%/build", None))

    def test_the_default_layout_of_a_single_document(self):
        self.assertEqual(self.out_dir(("main.tex", ".latex-ai/artifacts/documents/manuscript/build")),
                         ("%DIR%/.latex-ai/artifacts/documents/manuscript/build", None))

    def test_documents_in_different_folders_each_with_the_same_subfolder(self):
        self.assertEqual(self.out_dir(("a/main.tex", "a/build"), ("b/main.tex", "b/build")), ("%DIR%/build", None))

    def test_documents_sharing_one_folder_outside_their_own(self):
        self.assertEqual(self.out_dir(("a/x.tex", "out"), ("b/y.tex", "out")), ("%WORKSPACE_FOLDER%/out", None))
        self.assertEqual(self.out_dir(("paper/main.tex", ".")), ("%WORKSPACE_FOLDER%", None))

    def test_the_spelling_of_the_output_directory_does_not_matter(self):
        self.assertEqual(self.out_dir(("revision/main.tex", "./revision/./build/")), ("%DIR%/build", None))

    def test_documents_that_build_in_different_places_get_no_value_and_a_reason_naming_them(self):
        value, reason = self.out_dir(("main.tex", ".latex-ai/artifacts/documents/paper/build"),
                                     ("notes/derivation.tex", ".latex-ai/artifacts/documents/derivation/build"))
        self.assertIsNone(value)
        for text in ("main", "derivation", ".latex-ai/artifacts/documents/paper/build", "output_dir"):
            self.assertIn(text, reason)


class GeneratedEditorSettings(ProjectCase):
    def project_with(self, documents_):
        (self.project / "revision").mkdir()
        for name in ("main", "supplementary"):
            (self.project / "revision" / f"{name}.tex").write_text(TEX)
        self.configure(documents_, integrations={"editor": True})
        return self.install("init")

    def settings(self):
        return json.loads((self.project / ".vscode/settings.json").read_text())

    def document(self, root, **fields):
        return {"root": root, "lint": {"enabled": False}, "build_command": [sys.executable, "builder.py"], **fields}

    def test_the_reported_project_gets_outdir_beside_its_build_output(self):
        self.project_with({"paper": self.document("revision/main.tex", output_dir="revision/build"),
                           "supplement": self.document("revision/supplementary.tex", output_dir="revision/build")})
        self.assertEqual(self.settings()["latex-workshop.latex.outDir"], "%DIR%/build")

    def test_a_project_built_beside_its_sources_gets_no_outdir(self):
        self.project_with({"paper": self.document("revision/main.tex", output_dir="revision"),
                           "supplement": self.document("revision/supplementary.tex", output_dir="revision")})
        self.assertNotIn("latex-workshop.latex.outDir", self.settings())

    def test_documents_that_build_in_different_places_are_told_why_the_viewer_cannot_follow(self):
        result = self.project_with({"paper": self.document("revision/main.tex", output_dir="revision/one"),
                                    "supplement": self.document("revision/supplementary.tex", output_dir="revision/two")})
        self.assertNotIn("latex-workshop.latex.outDir", self.settings())
        shown = result.stdout + result.stderr
        self.assertIn("LaTeX Workshop", shown)
        self.assertIn("output_dir", shown)


if __name__ == "__main__":
    unittest.main()
