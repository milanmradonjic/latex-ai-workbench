"""`validation.ignore`: paths the owner declares are never routed to the manuscript build.

The patterns are validated like `validation.manuscript_inputs`. They never exempt what the build reads, build or
configuration files, or the agent's policy files: those keep their routing whatever is declared.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime
import schema
from test_support import ProjectCase

IGNORED = "ignored by validation.ignore: file checks only"
LEFT_ALONE = ("docs/figure.png", "docs/table.csv", "docs/blob.xyz", "docs/deeper/still/plot.pdf")


class ValidationIgnore(ProjectCase):

    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\\input{docs/part.tex}\\end{document}\n")
        (self.project / "docs").mkdir()
        (self.project / "docs" / "part.tex").write_text("Part.\n")

    def plan(self, *names, ignore=None, **validation):
        if ignore is not None:
            validation["ignore"] = ignore
        config = self.configure(**({"validation": validation} if validation else {}))
        schema.validate_config(self.project, config)
        return runtime.validation_plan(self.project, runtime.load_config(self.project), list(names))

    def test_without_the_setting_these_paths_reach_the_manuscript_build(self):
        for name in LEFT_ALONE:
            with self.subTest(name=name):
                self.assertTrue(self.plan(name)["manuscript"])

    def test_ignored_paths_are_not_routed_to_the_manuscript_build(self):
        for name in LEFT_ALONE:
            with self.subTest(name=name):
                plan = self.plan(name, ignore=["docs/**"])
                self.assertFalse(plan["manuscript"])
                self.assertEqual(plan["reasons"][name], IGNORED)
                self.assertTrue(plan["files"], "an ignored file still gets the file checks")

    def test_other_paths_keep_their_routing(self):
        plan = self.plan("figures/plot.png", "docs/figure.png", ignore=["docs/**"])
        self.assertTrue(plan["manuscript"])
        self.assertNotEqual(plan["reasons"]["figures/plot.png"], IGNORED)
        self.assertEqual(plan["reasons"]["docs/figure.png"], IGNORED)

    def test_a_path_the_build_reads_is_never_ignored(self):
        plan = self.plan("docs/part.tex", ignore=["docs/**"])
        self.assertTrue(plan["manuscript"])
        self.assertNotEqual(plan["reasons"]["docs/part.tex"], IGNORED)

    def test_a_declared_manuscript_input_is_never_ignored(self):
        plan = self.plan("docs/generated.json", ignore=["docs/**"], manuscript_inputs=["docs/generated.*"])
        self.assertTrue(plan["manuscript"])
        self.assertNotEqual(plan["reasons"]["docs/generated.json"], IGNORED)

    def test_build_configuration_and_policy_files_are_never_ignored(self):
        for name, key in (("docs/Makefile", "manuscript"), ("docs/latexmkrc", "manuscript"), ("docs/AGENTS.md", "policy"),
                          (".github/workflows/latex-ai.yml", "manuscript")):
            with self.subTest(name=name):
                plan = self.plan(name, ignore=["docs/**", ".github/**"])
                self.assertNotEqual(plan["reasons"][name], IGNORED)
                self.assertTrue(plan[key])

    def test_a_leading_dot_slash_does_not_stop_a_pattern_from_matching(self):
        plan = self.plan("docs/figure.png", ignore=["./docs/*"])
        self.assertEqual(plan["reasons"]["docs/figure.png"], IGNORED)

    def test_a_manuscript_input_with_a_leading_dot_slash_still_routes_to_the_manuscript(self):
        plan = self.plan("docs/generated.json", manuscript_inputs=["./docs/*.json"])
        self.assertTrue(plan["manuscript"])

    def test_a_pattern_that_matches_nothing_changes_nothing(self):
        for ignore in ([], ["elsewhere/**"]):
            with self.subTest(ignore=ignore):
                self.assertEqual(self.plan("docs/figure.png", ignore=ignore)["reasons"], self.plan("docs/figure.png")["reasons"])

    def test_the_patterns_are_validated_like_manuscript_inputs(self):
        for bad in ("docs/**", ["../x/*"], ["/abs/*"], ["bad\nname"], [""], [1], [None]):
            with self.subTest(ignore=bad), self.assertRaises(runtime.WorkbenchError) as raised:
                self.plan("docs/figure.png", ignore=bad)
            self.assertIn("validation.ignore", str(raised.exception))

    def test_other_validation_keys_are_still_rejected(self):
        with self.assertRaises(runtime.WorkbenchError):
            self.plan("docs/figure.png", ignores=["docs/**"])


if __name__ == "__main__":
    unittest.main()
