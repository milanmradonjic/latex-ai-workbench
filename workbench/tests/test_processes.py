"""Tests of the processes a build starts: locks, ownership of a build, interruption and the compiler's cleanup.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 4 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_audit3_repairs.py:
Independent audit 3 failures, exercised through installed workflows.

Compiler fixtures disable lint explicitly. Process/move tests isolate infrastructure;
the source-content and stdin tests use genuine TeX tools.

test_blind_repairs.py:
Installed-workflow regressions from the ten blind reviewers (current schema only).

test_document_lifecycle.py:
Receipt lifecycle across upgrades, failure, interruption and document state reporting.

test_repairs_3_0_2.py:
Regressions from the architecture audit of 3.0.1 (docs/maintainers/architecture-audit-3.0.1.md).

Each test failed before its repair. Findings are named by their audit number (F1, F2, ...).
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap
import core
import documents
import latex
import processes
import schema
from test_support import ProjectCase, fixture_env, isolate_environment, prepare_config


SOURCE = "\\documentclass{article}\n\\begin{document}Audit fixture.\\end{document}\n"


TEX = bool(shutil.which('latexmk') and shutil.which('pdflatex'))


SOURCE_blind_repairs = "\\documentclass{article}\n\\begin{document}A note.\\end{document}\n"


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


HOLD = ("import sys, time\nsys.path.insert(0, {package!r})\nfrom pathlib import Path\nimport core\n"
        "with {lock}:\n    print('held', flush=True)\n    time.sleep(60)\n")


class Audit3Repairs(unittest.TestCase):
    """Origin: tests/test_audit3_repairs.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix='workbench-audit3-')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve() / 'project'
        self.project.mkdir()
        self.env = fixture_env()
        self.children = []
        self.addCleanup(self.stop_children)

    def stop_children(self):
        for pid in self.children:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                pass

    def run_command(self, *args, expected=0, input=None, env=None):
        result = subprocess.run(args, cwd=self.project, env=env or self.env,
                                input=input, capture_output=True, text=True, timeout=20)
        if expected is not None:
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def install(self, *args, expected=0, **choices):
        prepare_config(self.project, **choices)
        return self.run_command(sys.executable, '-B', str(bootstrap.PACKAGE / 'latex-ai-init'),
                                *args, str(self.project), expected=expected)

    def synthetic(self, makefile=None):
        """Use deterministic output bytes only for process/validation infrastructure."""
        (self.project / 'compile.py').write_text(
            "from pathlib import Path\nimport sys\n"
            "root, out = Path(sys.argv[1]), Path(sys.argv[2])\n"
            "out.mkdir(parents=True,exist_ok=True)\n"
            "(out/(root.stem+'.pdf')).write_bytes(b'%PDF-1.4\\n'+root.read_bytes())\n"
            "(out/(root.stem+'.log')).write_text('Clean fixture log\\n')\n")
        for name in ('main.tex', 'note.tex'):
            (self.project / name).write_text(SOURCE)
        config = {'schema_version': 4, 'default_document': 'paper', 'defaults': {'lint': {'enabled': False}}, 'documents': {name: {'root': root, 'build_command': [sys.executable, 'compile.py', root, f'.latex-ai/artifacts/documents/{name}/build']} for name, root in [('paper', 'main.tex'), ('note', 'note.tex')]}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install('init', editor=False)
        if makefile is not None:  # the project's own Make text goes after what init wrote
            with (self.project / 'Makefile').open('a') as stream:
                stream.write('\n' + makefile)
        return config

    def wait_file(self, name):
        deadline = time.monotonic() + 8
        path = self.project / name
        while time.monotonic() < deadline:
            if path.is_file() and path.read_text().strip():
                return path.read_text().strip()
            time.sleep(.03)
        self.fail(f'{name} was not written')

    @unittest.skipUnless(os.name=='posix','POSIX signals required')
    def test_a9_interruptions_emit_one_structured_result(self):
        self.synthetic()
        compiler = self.project/'compile.py'
        compiler.write_text("import os,time\nfrom pathlib import Path\nPath('compiler.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n")
        for number in (signal.SIGTERM,signal.SIGINT):
            with self.subTest(signal=number):
                (self.project/'compiler.pid').unlink(missing_ok=True)
                owner = subprocess.Popen([sys.executable,'-B','.latex-ai/workbench.py','build','--json'],
                    cwd=self.project,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                pid = int(self.wait_file('compiler.pid'))
                self.children.append(pid)
                owner.send_signal(number)
                stdout,stderr = owner.communicate(timeout=10)
                self.assertEqual(owner.returncode,128+number,stderr)
                result = json.loads(stdout)
                self.assertEqual(result['status'],'interrupted')
                self.assertEqual(result['exit_status'],128+number)
                self.assertNotIn('Traceback',stderr)
                self.assertEqual(latex.read_receipt(self.project,schema.resolve(schema.load_config(self.project)).view)['status'],'failed')

    @unittest.skipUnless(Path('/proc').is_dir(),'Linux process state required')
    def test_a10_zombie_owner_is_not_running(self):
        child = subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        try:
            token = latex.process_token(child.pid)
            child.kill()
            deadline = time.monotonic()+5
            while time.monotonic()<deadline:
                fields = Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split()
                if fields[0]=='Z': break
                time.sleep(.01)
            self.assertEqual(fields[0],'Z')
            self.assertFalse(latex.owner_alive({'owner_pid':child.pid,'owner_token':token}))
        finally:
            child.wait(timeout=5)

    @unittest.skipUnless(os.name=='posix','POSIX signals required')
    def test_review_repeated_interrupt_waits_for_stubborn_compiler_cleanup(self):
        self.synthetic()
        (self.project/'compile.py').write_text('import os,time,signal\nfrom pathlib import Path\n'
            'signal.signal(signal.SIGTERM,signal.SIG_IGN)\nsignal.signal(signal.SIGINT,signal.SIG_IGN)\n'
            "Path('compiler.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n")
        owner=subprocess.Popen([sys.executable,'-B','.latex-ai/workbench.py','build','--json'],
            cwd=self.project,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        pid=int(self.wait_file('compiler.pid'))
        self.children.append(pid)
        owner.send_signal(signal.SIGINT)
        time.sleep(.15)
        owner.send_signal(signal.SIGINT)
        stdout,stderr=owner.communicate(timeout=12)
        self.assertEqual(owner.returncode,130,stderr)
        self.assertEqual(json.loads(stdout)['status'],'interrupted')
        self.assertFalse(latex.group_alive(pid))

    @unittest.skipUnless(os.name=='posix' and TEX,'POSIX and real compiler required')
    def test_review_owner_death_before_publication_never_executes_compiler(self):
        (self.project/'main.tex').write_text(SOURCE)
        launcher=self.project/'owner.py'
        launcher.write_text('import sys,os\nfrom pathlib import Path\n'
            'sys.path.insert(0,'+repr(str(bootstrap.PACKAGE))+')\nimport core\n'
            "def started(pid):\n Path('compiler.pid').write_text(str(pid))\n os._exit(97)\n"
            "core.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],Path.cwd(),started=started)\n")
        self.run_command(sys.executable,'-B',str(launcher),expected=97)
        pid=int(self.wait_file('compiler.pid'))
        self.children.append(pid)
        deadline=time.monotonic()+3
        while latex.group_alive(pid) and time.monotonic()<deadline:
            time.sleep(.03)
        self.assertFalse(latex.group_alive(pid))
        self.assertFalse((self.project/'main.pdf').exists())


class BlindRepairTests(unittest.TestCase):
    """Origin: tests/test_blind_repairs.py."""

    def setUp(self):
        isolate_environment(self)
        self.directory = tempfile.TemporaryDirectory(prefix="workbench-blind-fix-")
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name).resolve()

    def command(self, *argv, cwd=None, expected=0):
        result = subprocess.run(argv, cwd=cwd or self.project, env=fixture_env(),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def install(self, *args, expected=0, **choices):
        prepare_config(self.project, **choices)
        return self.command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"),
                            *args, expected=expected)

    def fixture(self, project=None, custom=True, hidden=False):
        project = project or self.project
        (project / "tex/nested").mkdir(parents=True)
        text = SOURCE_blind_repairs if not hidden else SOURCE_blind_repairs.replace("A note.", "\\def\\partname{hidden}\\input{\\partname}")
        (project / "tex/nested/paper.tex").write_text(text)
        if hidden:
            (project / ("hidden.tex" if custom else "tex/nested/hidden.tex")).write_text("Original source.\n")
        settings = {"root": "tex/nested/paper.tex", "lint": {"enabled": False}, "output_dir": "custom/output with spaces"}
        if custom:
            settings["build_command"] = ["latexmk", "-pdf", "-recorder", "-interaction=nonstopmode",
                                         "-halt-on-error", "-outdir=custom/output with spaces", "tex/nested/paper.tex"]
        config = {'schema_version': 4, 'default_document': 'paper', 'documents': {'paper': settings}}
        (project / core.CONFIG).write_text(json.dumps(config))
        self.install("init", str(project))
        return config

    def test_live_orphan_compiler_is_visible_in_document_status(self):
        config = self.fixture()
        view = schema.document_settings(config)
        receipt = {"status": "running", "owner_pid": 101, "owner_token": "owner", "compiler_groups": [{"pid": 202, "token": "compiler"}]}
        with patch.object(latex, "read_receipt", return_value=receipt), patch.object(latex, "process_alive", return_value=False), patch.object(latex, "group_alive", return_value=True):
            row = documents.report(self.project, config)[0]
        self.assertEqual(row["state"], "running")
        self.assertEqual(row["ownership"], {"owner_pid": 101, "owner_alive": False, "compiler_groups": [202]})


class DocumentLifecycleTests(unittest.TestCase):
    """Origin: tests/test_document_lifecycle.py."""

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

    def install(self, *arguments, expected=0, **choices):
        prepare_config(self.project, **choices)
        result = subprocess.run([sys.executable, "-B", str(bootstrap.PACKAGE / "latex-ai-init"),
                                 *arguments, str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def command(self, *arguments, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"),
                                 *arguments], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def states(self):
        return {row["id"]: row["state"] for row in json.loads(self.command("documents").stdout)}

    def named(self, **documents):
        for root in ("main.tex", "notes/main.tex"):
            path = self.project / root
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SOURCE_blind_repairs)
        config = {'schema_version': 4, 'default_document': 'paper', 'defaults': {'lint': {'enabled': False}}, 'documents': {'paper': {'root': 'main.tex', 'build_command': [sys.executable, 'compile.py', 'main.tex', '.latex-ai/artifacts/documents/paper/build']}, 'note': {'root': 'notes/main.tex', 'build_command': [sys.executable, 'compile.py', 'notes/main.tex', '.latex-ai/artifacts/documents/note/build']}}}
        for name, values in documents.items():
            config["documents"][name].update(values)
        (self.project / core.CONFIG).write_text(json.dumps(config))
        return config

    # F4: interrupting the build owner ends its compiler or keeps ownership while it runs.
    @unittest.skipUnless(os.name == "posix", "process groups are POSIX")
    def test_terminated_build_owner_stops_its_compiler(self):
        self.named()
        self.install("init")
        (self.project / "notes/main.tex").write_text(SOURCE_blind_repairs.replace("A note.", "SLOW"))
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
        (self.project / "notes/main.tex").write_text(SOURCE_blind_repairs.replace("A note.", "SLOW"))
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
        (self.project / "notes/main.tex").write_text(SOURCE_blind_repairs)
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


class Repairs(ProjectCase):

    # --- F1: one lock per project, shared by everyone who works in it ----------------------------------

    """Origin: tests/test_repairs_3_0_2.py, workbench 3.0.2."""

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

    def test_process_identity_without_proc_still_detects_a_reused_pid(self):
        if os.name != "posix" or not shutil.which("ps"):
            self.skipTest("POSIX ps required")
        with patch.object(processes, "state", return_value=None):
            token = processes.token(os.getpid())
            self.assertTrue(token)
            self.assertTrue(processes.alive(os.getpid(), token))
            self.assertFalse(processes.alive(os.getpid(), token + " earlier"))


if __name__ == "__main__":
    unittest.main()
