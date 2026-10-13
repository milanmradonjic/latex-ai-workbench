"""Receipt lifecycle across upgrades, failure, interruption and document state reporting."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from test_support import isolate_environment

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap
import core
import schema
import runtime

# A fake compiler: deterministic outputs, a failure marker and an optional slow mode
# that records its process ID, so interruption can be observed without TeX.
COMPILER = (
    "import os, sys, time\nfrom pathlib import Path\n"
    "root, out = Path(sys.argv[1]), Path(sys.argv[2])\n"
    "text = root.read_text()\n"
    "if 'SLOW' in text:\n"
    "    Path('compiler.pid').write_text(str(os.getpid()))\n"
    "    time.sleep(6)\n"
    "if 'BROKEN' in text: raise SystemExit(2)\n"
    "count = Path('compile-count')\n"
    "count.write_text(str(int(count.read_text()) + 1) if count.exists() else '1')\n"
    "out.mkdir(parents=True, exist_ok=True)\n"
    "(out/(root.stem+'.pdf')).write_bytes(b'%PDF-1.4\\n'+root.read_bytes())\n"
    "(out/(root.stem+'.log')).write_text('Clean compiler log\\n')\n")
SOURCE = "\\documentclass{article}\n\\begin{document}A note.\\end{document}\n"


class DocumentLifecycleTests(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-lifecycle-")
        self.project = Path(self.temp.name).resolve()
        (self.project / "compile.py").write_text(COMPILER)

    def tearDown(self):
        pid = self.project / "compiler.pid"
        if pid.exists():
            try:
                os.kill(int(pid.read_text()), signal.SIGKILL)
            except (OSError, ValueError):
                pass
        self.temp.cleanup()

    def install(self, *arguments, expected=0):
        result = subprocess.run([sys.executable, "-B", str(bootstrap.PACKAGE / "latex-ai-init"),
                                 *arguments, str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def command(self, *arguments, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"),
                                 *arguments], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def make(self, *arguments, expected=0):
        result = subprocess.run(["make", *arguments], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def states(self):
        return {row["id"]: row["state"] for row in json.loads(self.command("documents").stdout)}

    def make_paper(self, rules, goal="main.pdf"):
        """A paper whose own Make rule owns compilation: init first, then the project's rules after what init wrote."""
        (self.project / "main.tex").write_text(SOURCE)
        self.write_config({"schema_version": 3, "modules": {"latex": {"default_document": "manuscript", "documents": {"manuscript": {
            "root": "main.tex", "engine": "pdflatex", "lint": {"enabled": False}, "build_command": ["make", goal], "output_dir": "."}}}}})
        self.install("init", "--skip-editor")
        with (self.project / "Makefile").open("a") as stream:
            stream.write("\n" + rules)

    def adopted_paper(self, check_rule=""):
        """A paper whose own incremental Make rule owns compilation."""
        self.make_paper("main.pdf: main.tex compile.py\n\t" + sys.executable + " compile.py main.tex .\n" + check_rule)

    def named(self, **documents):
        for root in ("main.tex", "notes/main.tex"):
            path = self.project / root
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SOURCE)
        config = {"schema_version": 3, "modules": {"latex": {
            "default_document": "paper", "defaults": {"lint": {"enabled": False}}, "documents": {
                "paper": {"root": "main.tex", "build_command": [sys.executable, "compile.py", "main.tex", ".latex-ai/artifacts/documents/paper/build"]},
                "note": {"root": "notes/main.tex", "build_command": [sys.executable, "compile.py", "notes/main.tex", ".latex-ai/artifacts/documents/note/build"]}}}}}
        for name, values in documents.items():
            config["modules"]["latex"]["documents"][name].update(values)
        (self.project / core.CONFIG).write_text(json.dumps(config))
        return config

    def write_config(self, config):
        (self.project / core.CONFIG).write_text(json.dumps(config))

    def compiles(self):
        return int((self.project / "compile-count").read_text())

    def test_unverified_adopted_output_is_regenerated_not_certified(self):
        self.adopted_paper()
        self.make("main.pdf")  # the project's raw target, outside the workbench
        self.assertEqual(self.compiles(), 1)
        result = self.make("check")
        self.assertIn("regenerating", result.stdout)
        self.assertEqual(self.compiles(), 2)  # certified only after a real compilation
        self.assertEqual(self.states(), {"manuscript": "current"})
        self.make("check")
        self.assertEqual(self.compiles(), 2)  # and incremental again afterwards
        self.assertFalse(any((self.project / ".latex-ai/artifacts/unverified").rglob("*.pdf")))

    def test_makefile_edits_regenerate_once(self):
        self.adopted_paper()
        self.make("check")
        with (self.project / "Makefile").open("a") as stream:
            stream.write("# a comment changes no rule, but the receipt cannot know that\n")
        self.make("check")
        self.assertEqual(self.compiles(), 2)
        self.make("check")
        self.assertEqual(self.compiles(), 2)

    def test_failed_named_build_regenerates_instead_of_reviving_a_receipt(self):
        self.adopted_paper()
        self.make("check")
        source = self.project / "main.tex"
        source.write_text(SOURCE.replace("A note.", "BROKEN"))
        self.make("check", expected=2)
        self.assertEqual(self.states(), {"manuscript": "failed"})
        source.write_text(SOURCE)
        stamp = (self.project / "main.pdf").stat().st_mtime - 10
        os.utime(source, (stamp, stamp))  # Make now considers the old PDF current
        before = self.compiles()
        self.make("check")
        self.assertEqual(self.compiles(), before + 1)
        self.assertEqual(self.states(), {"manuscript": "current"})

    def test_build_that_cannot_regenerate_keeps_the_old_output_and_fails(self):
        self.make_paper(".PHONY: pdf\npdf:\n\t@true\n", goal="pdf")
        (self.project / "main.pdf").write_bytes(b"%PDF-old")
        (self.project / "main.log").write_text("old log\n")
        result = self.make("check", expected=2)
        self.assertIn("Build did not regenerate main.pdf", result.stderr)
        self.assertIn("Hint:", result.stderr)
        self.assertEqual((self.project / "main.pdf").read_bytes(), b"%PDF-old")
        self.assertEqual(self.states(), {"manuscript": "failed"})

    # F2: project-owned check rules keep running under change-aware validation.
    def test_schema_three_validate_runs_the_projects_own_check_rule(self):
        self.named()
        self.install("init")
        with (self.project / "Makefile").open("a") as stream:
            stream.write("\n.PHONY: project-tests\ncheck: project-tests\nproject-tests:\n\ttouch project-tests-ran\n")
        result = self.command("validate", "--files", "notes/main.tex")
        self.assertTrue((self.project / "project-tests-ran").exists(), result.stdout + result.stderr)

    def test_schema_three_validate_stays_selective_without_a_project_check_rule(self):
        self.named()
        self.install("init")
        (self.project / "main.tex").write_text("BROKEN\n")
        self.command("validate", "--files", "notes/main.tex")
        self.assertFalse((self.project / ".latex-ai/artifacts/documents/paper/build-receipt.json").exists())

    # F3: a failed document is reported and selected until it is rebuilt.
    def test_failed_document_is_reported_and_selected_after_its_source_is_restored(self):
        config = self.named()
        self.install("init")
        self.command("check")
        note = self.project / "notes/main.tex"
        note.write_text("BROKEN\n")
        self.command("validate", "--files", "notes/main.tex", expected=1)
        note.write_text(SOURCE)
        self.assertEqual(self.states(), {"paper": "current", "note": "failed"})
        plan = runtime.validation_plan(self.project, config, [])
        self.assertEqual(plan["documents"], ["note"])
        self.assertIn("last build failed", plan["document_reasons"]["note"][0])
        self.assertTrue(plan["manuscript"])
        status = self.command("status", "--files").stdout
        self.assertNotIn("Nothing pending", status)
        self.assertIn("DOC=note", status)
        self.command("validate", "--files")
        self.assertEqual(self.states(), {"paper": "current", "note": "current"})
        self.assertIn("Nothing pending", self.command("status", "--files").stdout)

    def test_plan_lists_selected_documents_for_people(self):
        self.named()
        self.install("init")
        output = self.command("plan", "--files", "notes/main.tex").stdout
        self.assertIn("Documents: note", output)

    # F4: interrupting the build owner ends its compiler or keeps ownership while it runs.
    @unittest.skipUnless(os.name == "posix", "process groups are POSIX")
    def test_terminated_build_owner_stops_its_compiler(self):
        self.named()
        self.install("init")
        (self.project / "notes/main.tex").write_text(SOURCE.replace("A note.", "SLOW"))
        owner = subprocess.Popen([sys.executable, "-B", ".latex-ai/workbench.py", "build", "--document", "note"],
                                 cwd=self.project, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pid = self.wait_for_compiler()
        owner.send_signal(signal.SIGTERM)
        owner.wait(timeout=20)
        time.sleep(0.5)
        self.assertFalse(self.alive(pid), "the compiler outlived its terminated owner")
        self.assertFalse((self.project / ".latex-ai/artifacts/active-build.json").exists())
        self.assertEqual(self.states()["note"], "failed")

    @unittest.skipUnless(os.name == "posix", "process groups are POSIX")
    def test_killed_build_owner_keeps_ownership_while_its_compiler_runs(self):
        self.named()
        self.install("init")
        (self.project / "notes/main.tex").write_text(SOURCE.replace("A note.", "SLOW"))
        owner = subprocess.Popen([sys.executable, "-B", ".latex-ai/workbench.py", "build", "--document", "note"],
                                 cwd=self.project, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pid = self.wait_for_compiler()
        owner.kill()
        owner.wait(timeout=20)
        self.assertTrue(self.alive(pid))
        result = self.command("build", "--document", "note", expected=1)
        self.assertIn("Another build is active", result.stderr)
        self.assertEqual(self.states()["note"], "running")
        deadline = time.time() + 30
        while self.alive(pid) and time.time() < deadline:
            time.sleep(0.2)
        (self.project / "notes/main.tex").write_text(SOURCE)
        self.command("build", "--document", "note")
        self.assertEqual(self.states()["note"], "current")

    def wait_for_compiler(self):
        deadline = time.time() + 20
        path = self.project / "compiler.pid"
        while time.time() < deadline:
            if path.exists() and path.read_text():
                return int(path.read_text())
            time.sleep(0.05)
        self.fail("the fake compiler did not start")

    @staticmethod
    def alive(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        try:  # a zombie child of this test process counts as gone
            return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
        except OSError:
            return True

    # F5: bibliography readiness covers each document's own declarations.
    def test_bibliography_check_covers_every_documents_own_files(self):
        config = self.named(note={"bibliography_files": ["notes/note.bib"]})
        (self.project / "notes/note.bib").write_text("@misc{dup, title={A}, year={2000}}\n@misc{dup, title={B}, year={2001}}\n")
        self.install("init")
        self.assertIn("Duplicate bibliography key", self.command("bib-check", expected=1).stderr)
        self.assertIn("Duplicate bibliography key", self.make("latex-ai-bib-check", "DOC=note", expected=2).stderr)
        self.make("latex-ai-bib-check", "DOC=paper")
        self.assertTrue(runtime.validation_plan(self.project, config, ["notes/note.bib"])["bibliography"])

    # F6: settings that do not affect compilation keep receipts current.
    def test_default_document_and_lint_settings_do_not_invalidate_receipts(self):
        config = self.named()
        self.install("init")
        self.command("check")
        config["modules"]["latex"]["default_document"] = "note"
        config["modules"]["latex"]["documents"]["paper"]["lint"] = {"args": ["-n8"]}
        self.write_config(config)
        self.assertEqual(self.states(), {"paper": "current", "note": "current"})
        config["modules"]["latex"]["documents"]["paper"]["engine"] = "xelatex"
        self.write_config(config)
        self.assertEqual(self.states(), {"paper": "stale", "note": "current"})

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "real TeX tools required")
    def test_compiler_failure_names_the_tex_error(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install("init", "--engine", "pdflatex", "--no-lint", "--skip-editor")
        (self.project / "notes").mkdir()
        (self.project / "notes/derivation.tex").write_text("\\documentclass{article}\n\\begin{document}\n\\undefinedfixturemacro\n\\end{document}\n")
        config = json.loads((self.project / core.CONFIG).read_text())
        config["modules"]["latex"]["documents"]["derivation"] = {"root": "notes/derivation.tex", "lint": {"enabled": False}}
        self.write_config(config)
        result = self.command("document-check", "--document", "derivation", expected=1)
        self.assertIn("derivation.tex:3: Undefined control sequence", result.stderr)
        self.assertIn("Hint:", result.stderr)


if __name__ == "__main__":
    unittest.main()
