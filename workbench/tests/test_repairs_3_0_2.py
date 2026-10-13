"""Regressions from the architecture audit of 3.0.1 (docs/maintainers/architecture-audit-3.0.1.md).

Each test failed before its repair. Findings are named by their audit number (F1, F2, ...).
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
import schema
import diagnostics
import latex
import processes
from test_support import ProjectCase

PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = "\\documentclass{article}\n\\begin{document}Audit fixture.\\end{document}\n"
HOLD = ("import sys, time\nsys.path.insert(0, {package!r})\nfrom pathlib import Path\nimport core\n"
        "with {lock}:\n    print('held', flush=True)\n    time.sleep(60)\n")


class Repairs(ProjectCase):

    # --- F1: one lock per project, shared by everyone who works in it ----------------------------------

    def hold(self, lock, temporary):
        """A second process holding ``lock`` with its own temporary directory."""
        script = HOLD.format(package=str(PACKAGE), lock=lock)
        holder = subprocess.Popen([sys.executable, "-B", "-c", script], env={**self.env, "TMPDIR": str(temporary)},
                                  stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        return holder

    def test_operation_lock_excludes_a_process_with_another_temporary_directory(self):
        (self.root / "a").mkdir(); (self.root / "b").mkdir()
        self.hold(f"core.operation_lock(Path({str(self.project)!r}), 'build')", self.root / "a")
        with patch.object(tempfile, "tempdir", str(self.root / "b")), self.assertRaises(core.WorkbenchError):
            with core.operation_lock(self.project, "build"):
                pass
        self.assertTrue((self.project / ".latex-ai/artifacts/locks/build.lock").is_file())

    def test_a_lock_that_cannot_be_created_fails_closed(self):
        # Before 3.0.2 a lock that could not be created was skipped, and the work ran without any lock.
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")), self.assertRaises(core.WorkbenchError):
            with core.operation_lock(self.project, "build"):
                self.fail("ran without a lock")

    def test_fault_records_are_kept_per_user(self):
        if hasattr(os, "getuid"):
            self.assertIn(str(os.getuid()), str(diagnostics.fault_dir(self.project)))

    # --- F3: TeX sources that are not UTF-8 --------------------------------------------------------------

    def test_latin1_sources_install_plan_and_pass_file_checks(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\usepackage[latin1]{inputenc}\n"
                                               "\\begin{document}\n\\input{chap}\n\\end{document}\n")
        (self.project / "chap.tex").write_bytes("Caf\u00e9 na\u00efve\n".encode("latin-1"))
        (self.project / "other.tex").write_bytes("\u00e9t\u00e9\n".encode("latin-1"))
        self.install("init", "--skip-editor")
        plan = json.loads(self.command("plan", "--files", "chap.tex", "--json").stdout)
        self.assertEqual(plan["documents"], ["manuscript"])
        self.command("validate", "--files-only", "--files", "chap.tex")

    # --- F5: an input is hashed once per command -----------------------------------------------------------

    def built(self, source, inputs, older=()):
        (self.project / "main.tex").write_text(source)
        for name in older:  # existing well before the build starts
            (self.project / name).write_bytes(b"x" * 1000)
        self.configure()
        self.builder(inputs=inputs)
        self.install("init", "--skip-editor")

    def test_unchanged_inputs_are_hashed_once_per_invocation(self):
        self.built(SOURCE, ("main.tex",), older=("data.bin",))
        changed = schema.document_settings(schema.load_config(self.project)).to_json()  # a view is read-only
        changed["validation"]["manuscript_inputs"] = ["data.bin"]
        config = schema.DocumentView(changed)
        reads = []
        original = Path.read_bytes
        def counted(path):
            reads.append(path.name)
            return original(path)
        with patch.object(latex, "SETTLED_NS", 0), patch.object(Path, "read_bytes", counted):
            first = latex.build_inputs(self.project, config)
            latex.build_inputs(self.project, config)
        self.assertEqual(reads.count("data.bin"), 1)
        (self.project / "data.bin").write_bytes(b"y" * 1000)  # same size: the change of ctime is what counts
        with patch.object(latex, "SETTLED_NS", 0):
            self.assertNotEqual(latex.build_inputs(self.project, config)["data.bin"], first["data.bin"])

    # --- F4: inputs the compiler discovers but nobody wrote during the build ---------------------------

    def test_discovered_input_that_predates_the_build_needs_no_second_compilation(self):
        (self.project / "hidden.dat").write_text("read by a macro the static scan cannot see\n")
        time.sleep(2.2)  # older than the build by more than the timestamp margin
        self.built(SOURCE, ("main.tex", "hidden.dat"))
        result = self.command("build")
        self.assertEqual((self.project / "count").read_text(), "1", result.stdout)
        self.assertEqual(self.state(), "current")
        self.assertIn("hidden.dat", self.receipt()["inputs"])
        (self.project / "hidden.dat").write_text("changed\n")
        self.assertEqual(self.state(), "stale")

    def test_graphics_without_extension_track_every_file_graphicx_could_choose(self):
        source = "\\documentclass{article}\n\\usepackage{graphicx}\n\\usepackage{mystyle}\n\\begin{document}\\includegraphics{fig}\\end{document}\n"
        (self.project / "fig.png").write_bytes(b"png")
        (self.project / "mystyle.sty").write_text("% local style\n")
        self.built(source, ("main.tex", "fig.png", "mystyle.sty"))
        names = latex.manuscript_dependencies(self.project, schema.document_settings(schema.load_config(self.project)), include_receipt=False)
        self.assertIn("fig.png", names)
        self.assertIn("mystyle.sty", names)
        self.command("build")
        self.assertEqual(self.state(), "current")
        (self.project / "fig.pdf").write_bytes(b"%PDF-1.5")  # graphicx now prefers it over fig.png
        self.assertEqual(self.state(), "stale")

    # --- F12: process identity without /proc --------------------------------------------------------

    def test_process_identity_without_proc_still_detects_a_reused_pid(self):
        if os.name != "posix" or not shutil.which("ps"):
            self.skipTest("POSIX ps required")
        with patch.object(processes, "state", return_value=None):
            token = processes.token(os.getpid())
            self.assertTrue(token)
            self.assertTrue(processes.alive(os.getpid(), token))
            self.assertFalse(processes.alive(os.getpid(), token + " earlier"))

    # --- F6: the installation record keeps text only where a merge needs it -----------------------------

    def test_the_record_keeps_a_digest_for_each_runtime_file_and_nothing_else(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--skip-editor")
        record = json.loads((self.project / ".latex-ai/installation.json").read_text())
        self.assertEqual(set(record), {"schema_version", "version", "files"})
        digest = record["files"][".latex-ai/core.py"]
        self.assertEqual(digest, diagnostics.sha256_text((self.project / ".latex-ai/core.py").read_text()))
        self.assertTrue(all(name.startswith(".latex-ai/") for name in record["files"]))
        self.assertLess(len(json.dumps(record)), 4_000)

    # --- F14: CI steps that can never be selected are not generated ---------------------------------


if __name__ == "__main__":
    unittest.main()
