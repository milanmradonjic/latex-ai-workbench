"""Adapter regressions; run from this folder with python3 -m unittest discover -p 'test_*.py'."""
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("build_documents", Path(__file__).with_name("build_documents.py"))
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class CoupledBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.build = Path(temporary.name)
        for key, value in (("BUILD", self.build), ("STAMP", self.build / "state.json")):
            context = patch.object(adapter, key, value)
            context.start()
            self.addCleanup(context.stop)
        self.source = self.build / "source.tex"
        self.source.write_text("original source")
        context = patch.object(adapter, "sources", lambda: {"source": adapter.digest(self.source)})
        context.start()
        self.addCleanup(context.stop)
        for name in adapter.DOCUMENTS:
            self.write_outputs(name)
            (self.build / (name + ".aux")).write_text(name)
        aux = adapter.auxiliaries()
        adapter.STAMP.write_text(json.dumps({"consumed": {"paper": aux["supplement"], "supplement": aux["paper"]}}))
        self.log = self.build / "compiler.log"

    def write_outputs(self, name):
        for suffix in (".pdf", ".log"):
            (self.build / (name + suffix)).write_text("rebuilt " + name)

    def settle(self, compile_one, document="paper"):
        with patch.object(adapter, "compile_one", side_effect=compile_one) as compiler:
            adapter.settle(document, log=self.log)
        return [(call.args[0], call.kwargs["force"]) for call in compiler.call_args_list]

    def test_current_outputs_are_not_forced(self):
        before = {name: adapter.output_identities(name) for name in adapter.DOCUMENTS}
        self.assertEqual(self.settle(lambda *args, **kwargs: None), [("paper", False), ("supplement", False)])
        self.assertEqual(before, {name: adapter.output_identities(name) for name in adapter.DOCUMENTS})

    def test_prose_build_is_not_repeated(self):
        calls = self.settle(lambda name, **kwargs: self.write_outputs(name) if name == "paper" else None)
        self.assertEqual(calls, [("paper", False), ("supplement", False)])

    def test_reference_changes_propagate_in_both_directions(self):
        for requested in adapter.DOCUMENTS:
            with self.subTest(requested=requested):
                companion = next(name for name in adapter.DOCUMENTS if name != requested)
                changed = set()

                def compile_one(name, **kwargs):
                    self.write_outputs(name)
                    if name not in changed:
                        path = self.build / (name + ".aux")
                        path.write_text(path.read_text() + " new page")
                        changed.add(name)

                calls = self.settle(compile_one, document=requested)
                self.assertEqual(calls, [(requested, False), (companion, False), (requested, False)])
                saved = json.loads(adapter.STAMP.read_text())
                self.assertEqual(saved["consumed"][requested], adapter.auxiliaries()[companion])

    def test_external_aux_ignored_by_latexmk_forces_the_consumer(self):
        (self.build / "paper.aux").write_text("changed exported page")

        def compile_one(name, force, **kwargs):
            if force:
                self.write_outputs(name)

        self.assertEqual(self.settle(compile_one), [("paper", False), ("supplement", False), ("supplement", True)])

    def test_missing_output_is_regenerated(self):
        (self.build / "paper.log").unlink()
        calls = self.settle(lambda name, **kwargs: self.write_outputs(name))
        self.assertEqual(calls, [("paper", True), ("supplement", False)])

    def test_nonconvergence_is_bounded_and_drops_cache(self):
        def compile_one(name, **kwargs):
            self.write_outputs(name)
            path = self.build / (name + ".aux")
            path.write_text(path.read_text() + " unstable")

        with patch.object(adapter, "compile_one", side_effect=compile_one) as compiler:
            with self.assertRaisesRegex(RuntimeError, "did not converge"):
                adapter.settle("paper", log=self.log)
            self.assertLessEqual(compiler.call_count, 2 * adapter.MAX_ROUNDS)
        self.assertFalse(adapter.STAMP.exists())

    def test_failure_drops_cache(self):
        with self.assertRaisesRegex(RuntimeError, "compiler failure"):
            self.settle(lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("compiler failure")))
        self.assertFalse(adapter.STAMP.exists())

    def test_changed_source_is_rejected(self):
        def compile_one(*args, **kwargs):
            self.source.write_text("edited while compiling")

        with self.assertRaisesRegex(RuntimeError, "Source inputs changed"):
            self.settle(compile_one)
        self.assertFalse(adapter.STAMP.exists())

    def test_malformed_cache_does_not_establish_consumed_state(self):
        for saved in ([], {"consumed": []}, {"consumed": None}):
            with self.subTest(saved=saved):
                adapter.STAMP.write_text(json.dumps(saved))
                calls = self.settle(lambda name, force, **kwargs: self.write_outputs(name) if force else None)
                self.assertEqual(calls, [("paper", False), ("paper", True), ("supplement", False), ("supplement", True)])

    def test_failed_compiler_preserves_log_and_exit_status(self):
        def fail(command, **kwargs):
            kwargs["stdout"].write("specific TeX error\n")
            return subprocess.CompletedProcess(command, 12)

        with patch.object(adapter.subprocess, "run", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "exit 12.*Full output"):
                adapter.compile_one("paper", log=self.log)
        self.assertIn("specific TeX error", self.log.read_text())

    def test_missing_aux_is_recreated_before_running_bibtex(self):
        (self.build / "paper.aux").unlink()
        database = self.build / "paper.fdb_latexmk"
        database.write_text("stale bibliography scheduling")
        with patch.object(adapter.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as compiler:
            adapter.compile_one("paper", log=self.log)
        self.assertEqual(compiler.call_count, 2)
        self.assertIn("-bibtex-", compiler.call_args_list[0].args[0])
        self.assertIn("-g", compiler.call_args_list[0].args[0])
        self.assertNotIn("-bibtex-", compiler.call_args_list[1].args[0])
        self.assertEqual(database.read_text(), "stale bibliography scheduling")

    def test_required_receipt_regeneration_is_done_within_one_invocation(self):
        def compile_one(name, force, **kwargs):
            if force:
                self.write_outputs(name)

        with patch.object(adapter, "compile_one", side_effect=compile_one) as compiler:
            adapter.settle("paper", log=self.log, force=True)
        calls = [(call.args[0], call.kwargs["force"]) for call in compiler.call_args_list]
        self.assertEqual(calls, [("paper", False), ("paper", True), ("supplement", False)])

    def test_required_receipt_does_not_repeat_an_incremental_rebuild(self):
        with patch.object(adapter, "compile_one", side_effect=lambda name, **kwargs: self.write_outputs(name)) as compiler:
            adapter.settle("paper", log=self.log, force=True)
        self.assertEqual(compiler.call_count, 2)
        self.assertTrue(all(not call.kwargs["force"] for call in compiler.call_args_list))


@unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex") and shutil.which("bibtex"), "TeX tools required")
class RealAuxRecoveryTests(unittest.TestCase):
    def test_missing_and_failed_aux_recover_with_the_real_bibliography_backend(self):
        with tempfile.TemporaryDirectory() as temporary:
            revision = Path(temporary)
            build = revision / "build"
            build.mkdir()
            source = revision / "paper.tex"
            good = ("\\documentclass{article}\n\\begin{document}\nSynthetic fixture.\\cite{fixture}\n"
                    "\\bibliographystyle{plain}\\bibliography{fixture}\n\\end{document}\n")
            source.write_text(good)
            (revision / "fixture.bib").write_text("@article{fixture,author={Fixture, A.},title={Synthetic},journal={Journal},year={2026}}\n")
            with patch.object(adapter, "BUILD", build), patch.object(adapter, "SOURCES", revision):
                log = build / "adapter.log"
                adapter.compile_one("paper", log=log)
                (build / "paper.aux").unlink()
                adapter.compile_one("paper", log=log)
                source.write_text(good.replace("Synthetic fixture.", "\\UndefinedWorkbenchCommand"))
                with self.assertRaises(RuntimeError):
                    adapter.compile_one("paper", log=log)
                source.write_text(good)
                # An interrupted TeX run can leave an AUX header without its
                # bibliography records, as the manuscript recovery probe did.
                (build / "paper.aux").write_text("\\relax\n")
                adapter.compile_one("paper", force=True, log=log)
                self.assertIn("\\bibdata{fixture}", (build / "paper.aux").read_text())
                self.assertIn("Output written on", (build / "paper.log").read_text())


if __name__ == "__main__":
    unittest.main()
