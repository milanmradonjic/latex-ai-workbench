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
import adapters
import core
import schema
import diagnostics
import latex
import processes
import research
from test_support import ProjectCase

PACKAGE = Path(__file__).resolve().parents[1]
MAKE = bool(shutil.which("make"))
SOURCE = "\\documentclass{article}\n\\begin{document}Audit fixture.\\end{document}\n"
HOLD = ("import sys, time\nsys.path.insert(0, {package!r})\nfrom pathlib import Path\nimport core, research\n"
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

    def test_research_task_lock_is_the_project_lock(self):
        (self.root / "a").mkdir(); (self.root / "b").mkdir()
        self.hold(f"research.task_lock(Path({str(self.project)!r}), 'numerics', 'solve')", self.root / "a")
        with patch.object(tempfile, "tempdir", str(self.root / "b")), self.assertRaises(core.WorkbenchError):
            with research.task_lock(self.project, "numerics", "solve"):
                pass

    def test_a_lock_that_cannot_be_created_fails_closed(self):
        # Before: research.task_lock caught the error and ran the task without any lock.
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")), self.assertRaises(core.WorkbenchError):
            with research.task_lock(self.project, "numerics", "solve"):
                self.fail("ran without a lock")

    def test_fault_records_are_kept_per_user(self):
        if hasattr(os, "getuid"):
            self.assertIn(str(os.getuid()), str(diagnostics.fault_dir(self.project)))

    # --- F2: an old GNU Make keeps the project's own targets ---------------------------------------------

    def adopted(self):
        (self.project / "main.tex").write_text(SOURCE)
        (self.project / "Makefile").write_text(".PHONY: pdf\npdf:\n\t@echo project pdf rule\n")
        self.configure({"paper": {"root": "main.tex", "lint": {"enabled": False}, "build_command": ["make", "pdf"], "output_dir": "."}})

    @unittest.skipUnless(MAKE, "GNU Make required")
    def test_make_without_extra_prereqs_still_runs_project_targets_and_help(self):
        self.adopted()
        self.install("init", "--skip-editor")
        old = ".FEATURES="  # what GNU Make before 4.3 reports: no extra-prereqs
        self.assertIn("project pdf rule", self.run_command("make", "pdf", old).stdout)
        self.run_command("make", "latex-ai-help", old)
        refused = self.run_command("make", "latex-ai-build", old, expected=None)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("GNU Make 4.3", refused.stdout + refused.stderr)

    def fake_make(self):
        """A `make` first on PATH that runs the real one but reports the features of GNU Make 3.81."""
        directory = self.root / "old-make"
        directory.mkdir()
        (directory / "make").write_text(f"#!/bin/sh\nexec {shutil.which('make')} \"$@\" .FEATURES=\n")
        (directory / "make").chmod(0o755)
        return {**self.env, "PATH": f"{directory}{os.pathsep}{self.env.get('PATH', '')}"}

    @unittest.skipUnless(MAKE, "GNU Make required")
    def test_installer_and_doctor_name_the_make_requirement(self):
        self.adopted()
        env = self.fake_make()
        installed = self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), "init", "--skip-editor", str(self.project), env=env)
        self.assertIn("GNU Make 4.3", installed.stdout)
        doctor = self.command("doctor", expected=1, env=env)
        self.assertIn("GNU Make 4.3", doctor.stdout + doctor.stderr)

    # --- F3: TeX sources that are not UTF-8 --------------------------------------------------------------

    def test_latin1_sources_install_plan_and_pass_file_checks(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\usepackage[latin1]{inputenc}\n"
                                               "\\begin{document}\n\\input{chap}\n\\end{document}\n")
        (self.project / "chap.tex").write_bytes("Caf\u00e9 na\u00efve\n".encode("latin-1"))
        (self.project / "other.tex").write_bytes("\u00e9t\u00e9\n".encode("latin-1"))
        self.install("init", "--skip-editor", "--no-ci")
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

    def test_manifest_keeps_digests_for_files_installed_whole(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--skip-editor")
        manifest = json.loads((self.project / ".latex-ai/installation.json").read_text())
        self.assertEqual(manifest["schema_version"], 2)
        runtime = manifest["files"][".latex-ai/core.py"]
        self.assertNotIn("installed", runtime)
        self.assertNotIn("upstream", runtime)
        self.assertEqual(runtime["installed_sha256"], diagnostics.sha256_text((self.project / ".latex-ai/core.py").read_text()))
        self.assertIn("upstream", manifest["files"]["AGENTS.md"])  # extendable: the text is what is searched for
        self.assertLess(len(json.dumps(manifest)), 60_000)

    def test_upgrade_reads_a_version_1_manifest(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--skip-editor")
        path = self.project / ".latex-ai/installation.json"
        manifest = json.loads(path.read_text())
        for name, record in manifest["files"].items():
            text = (self.project / name).read_text() if (self.project / name).is_file() else ""
            manifest["files"][name] = {"strategy": record["strategy"], "installed": record.get("installed", text),
                                       "upstream": record.get("upstream", text)}
        path.write_text(json.dumps({**manifest, "schema_version": 1}, indent=2) + "\n")
        self.assertIn("unmodified", json.dumps(diagnostics.installation(self.project)))
        self.install("upgrade")
        self.assertEqual(json.loads(path.read_text())["schema_version"], 2)
        (self.project / ".latex-ai/core.py").write_text((self.project / ".latex-ai/core.py").read_text() + "# local\n")
        self.assertEqual(diagnostics.installation(self.project)["differing"], [".latex-ai/core.py"])
        conflict = self.install("upgrade", "--diff", expected=2)
        self.assertIn("Locally modified managed file", conflict.stdout)
        self.assertIn("+# local", conflict.stdout)

    # --- F14: CI steps that can never be selected are not generated ---------------------------------

    def test_workflow_omits_package_steps_when_package_routing_is_off(self):
        config = {"schema_version": 3, "validation": {"package": None},
                  "modules": {"latex": {"default_document": "paper", "documents": {"paper": {"root": "main.tex"}}}},
                  "integrations": {"ci": {"enabled": True, "pdf_artifact": True}}}
        text = adapters.workflow(config)
        self.assertNotIn("Test workbench", text)
        self.assertNotIn("Test compiler portability", text)
        self.assertIn("Test workbench", adapters.workflow({**config, "validation": {}}))


if __name__ == "__main__":
    unittest.main()
