"""Tests of build receipts and a document's state: what a build records, freshness, the output and its safety, the recorder, lint and the full check.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 13 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_audit3_repairs.py:
Independent audit 3 failures, exercised through installed workflows.

Compiler fixtures disable lint explicitly. Process/move tests isolate infrastructure;
the source-content and stdin tests use genuine TeX tools.

test_blind_repairs.py:
Installed-workflow regressions from the ten blind reviewers (current schema only).

test_document_lifecycle.py:
Receipt lifecycle across upgrades, failure, interruption and document state reporting.

test_documents.py:
Installed workflows for named TeX documents and mixed note organization.

test_modules.py:
(no docstring)

test_one_table_each.py:
Phase 3, F9: each fact the code spelled twice is now spelled once.

What each duplicate was, and what pins it: the Make goals that would make a project's build command call itself (derived from the
command registry), the folders no check treats as project sources (core.GENERATED_TREES), the suffixes the planner routes, the
Make names the template already defines, and the Markdown link check of the file checks.

test_repairs_3_0_1.py:
Regressions found by the independent 3.0.0 audit; each one failed before its repair.

The fixtures come from ``test_support.ProjectCase``; the genuine latexmk/GNU Make scenarios are
skipped when those tools are absent.

test_repairs_3_0_2.py:
Regressions from the architecture audit of 3.0.1 (docs/maintainers/architecture-audit-3.0.1.md).

Each test failed before its repair. Findings are named by their audit number (F1, F2, ...).

test_review_fixes.py:
Regressions for the architecture review's installed workflow failures.

test_scope_4_5_0.py:
Workbench 4.5.0, step 3.4 of docs/maintainers/plan-after-4.4.0.md: one engine (pdflatex), one bibliography program (BibTeX), no installer profiles.

`--engine`, `--backend` and `--profile` are gone from `init`, as are the lualatex, xelatex and biber paths behind them and the `biblatex` export format. A configuration that
says what stays (`engine: pdflatex`, `backend: none` or `bibtex`, export format `bibtex`) works as it did, and anything else is refused by name with a hint that points at
`build_command`. `--modules` chooses what a profile chose: `--modules ""` was `--profile core` and `--modules latex` was `--profile writing`.

test_scope_4_8_1.py:
4.8.1: independent-audit regressions, output safety, source integrity and bounded scans.

Every project is disposable; overwrite probes use only synthetic sentinel files.

test_simplification.py:
The one supported project model retains receipt and source safety.

test_workbench.py:
(no docstring)
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap
import bootstrap as boot
import commands
import core
import documents
import latex
import output_transaction
import runtime
import runtime as rt
import schema
from test_support import ProjectCase, fixture_env, isolate_environment


SOURCE = "\\documentclass{article}\n\\begin{document}Audit fixture.\\end{document}\n"


TEX = bool(shutil.which('latexmk') and shutil.which('pdflatex'))


SOURCE_blind_repairs = "\\documentclass{article}\n\\begin{document}A note.\\end{document}\n"


TEX_blind_repairs = shutil.which("latexmk") and shutil.which("pdflatex")


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


OLD_RECURSIVE_GOALS = {"latex-ai-build", "latex-ai-document-check", "latex-ai-validate", "check", "document-check", "validate"}


RECURSIVE_GOALS = OLD_RECURSIVE_GOALS | {"build", "latex-ai-build-all"}  # since 4.4 the short `build` is always the workbench's own alias; since 4.6 so is the whole package


GENERATED = "\\documentclass{article}\n\\begin{document}\\input{table}\\end{document}\n"


TEX_3_0_1 = bool(shutil.which("latexmk") and shutil.which("pdflatex") and shutil.which("make"))


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


BIBTEX_IDENTITY = {  # what 4.4.2 recorded for a default-layout document with BibTeX and a Zotero export
    "root": "main.tex", "engine": "pdflatex", "output": ".latex-ai/artifacts/documents/paper/build/main", "build_command": None,
    "bibliography": {"files": ["refs.bib"], "backend": "bibtex", "export": {"path": "refs.bib", "required": True, "format": "bibtex"}}}


BUILDER_FIXTURE = (  # the stand-in compiler that produced FROZEN_RECEIPT under 4.4.2, byte for byte
    "from pathlib import Path\n"
    "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
    "(out/'main.pdf').write_bytes(b'%PDF-fixture\\n'); (out/'main.log').write_text('Clean log\\n'); (out/'main.fls').write_text('PWD /fixture\\nINPUT main.tex\\n')\n")


FROZEN_RECEIPT = {  # a verified receipt exactly as 4.4.2 wrote it for a document with a build_command; 4.5.0 must judge it current
    "schema_version": 3, "status": "verified",
    "identity": {"root": "main.tex", "engine": "pdflatex", "output": "outputs/main", "build_command": ["python3", "builder.py"],
                 "bibliography": {"files": [], "backend": "none", "export": None}},
    "inputs": {"builder.py": "f12bee0fb7d77e4876bed8b7be1d18697a6491d4f3ebe34b299d28e217a9af11",
               "main.tex": "4bce36483fade5d4eb65a363da4155cb74744440dc9b9cc5e3f4f151659b6005"},
    "input_roles": {"builder.py": "source", "main.tex": "source"},
    "outputs": {".pdf": "6c8d22e47796a2cf56b46bf9aa0dba0f8c666f324080ad8fcdea4b1b3c5b65c2",
                ".log": "da1292e4af11a88d7215a8741c91830d33817b6ecc033653f243844a7cc33623"},
}


SOURCE_4_5_0 = "\\documentclass{article}\\begin{document}x\\end{document}\n"


def latex_module(document=None, defaults=None):
    values = {"default_document": "paper", "documents": {"paper": {"root": "main.tex", **(document or {})}}}
    if defaults:
        values["defaults"] = defaults
    return values


def configuration(document=None, defaults=None, **bibliography):
    modules = {"latex": latex_module(document, defaults)}
    if bibliography:
        modules["bibliography"] = {"files": [], **bibliography}
    return {"schema_version": 3, "modules": modules}


SOURCE_4_8_1 = '\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n'


def red_png():
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00')) + chunk(b'IEND', b''))


TEX_workbench = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


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

    def install(self, *args, expected=0):
        return self.run_command(sys.executable, '-B', str(bootstrap.PACKAGE / 'latex-ai-init'),
                                *args, str(self.project), expected=expected)

    def command(self, *args, **kwargs):
        return self.run_command(sys.executable, '-B', '.latex-ai/workbench.py', *args, **kwargs)

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
        config = {'schema_version': 3, 'modules': {'latex': {
            'default_document': 'paper', 'defaults': {'lint': {'enabled': False}},
            'documents': {name: {'root': root, 'build_command': [sys.executable, 'compile.py', root,
                f'.latex-ai/artifacts/documents/{name}/build']} for name, root in [('paper','main.tex'),('note','note.tex')]}}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install('init', '--skip-editor')
        if makefile is not None:  # the project's own Make text goes after what init wrote
            with (self.project / 'Makefile').open('a') as stream:
                stream.write('\n' + makefile)
        return config

    @unittest.skipUnless(TEX, 'real latexmk/pdflatex required')
    def test_a2_custom_output_symlink_cannot_escape(self):
        for output_dir in (".", "build"):
            for suffix in ('.pdf', '.log'):
                with self.subTest(output_dir=output_dir, suffix=suffix):
                    outside = self.project.parent / 'outside'
                    outside.write_bytes(b'Keep this outside-project sentinel')
                    (self.project / 'main.tex').write_text(SOURCE)
                    path = self.project / output_dir / ('main' + suffix)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.unlink(missing_ok=True)
                    path.symlink_to(outside)
                    view = {'root':'main.tex', 'engine':'pdflatex', 'lint':{'enabled':False}, 'output_dir':output_dir}
                    config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': view}}}}
                    with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(core.WorkbenchError):
                        latex.build(self.project, schema.document_settings(config))
                    self.assertEqual(outside.read_bytes(), b'Keep this outside-project sentinel')
                    path.unlink()

    @unittest.skipUnless(TEX, 'real latexmk/pdflatex required')
    def test_a5_custom_compiler_receives_supplied_stdin(self):
        (self.project / 'main.tex').write_text(SOURCE)
        (self.project / 'compile.py').write_text(
            "import subprocess,sys\n"
            "if sys.stdin.readline().strip()!='approve': raise SystemExit(3)\n"
            "subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],check=True)\n")
        self.install('init','--no-lint','--skip-editor',
                     '--build-command',json.dumps([sys.executable,'compile.py']))
        self.command('build', input='approve\n')
        self.command('verify')

    def test_a6_second_output_move_failure_restores_first(self):
        (self.project / 'main.tex').write_text(SOURCE)
        (self.project / 'main.pdf').write_bytes(b'%PDF-original')
        (self.project / 'main.log').write_text('Original log')
        config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'engine': 'pdflatex', 'build_command': [sys.executable, '-c', 'pass'], 'output_dir': '.'}}}}}
        original = shutil.move
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('second move failed')
            return original(*args, **kwargs)
        with patch.object(latex.shutil,'move',side_effect=fail_second), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(OSError):
            latex.regenerate_outputs(self.project,schema.document_settings(config))
        self.assertEqual((self.project / 'main.pdf').read_bytes(), b'%PDF-original')
        self.assertEqual((self.project / 'main.log').read_text(), 'Original log')

    def test_a7_malformed_receipt_identity_is_stale_and_recoverable(self):
        self.synthetic()
        self.command('build')
        receipt = self.project / '.latex-ai/artifacts/documents/paper/build-receipt.json'
        original = json.loads(receipt.read_text())
        for value in ([],None,'bad',4):
            with self.subTest(value=value):
                damaged = json.loads(json.dumps(original))
                damaged['identity']['bibliography'] = value
                receipt.write_text(json.dumps(damaged))
                rows = json.loads(self.command('documents').stdout)
                self.assertEqual(next(r for r in rows if r['id']=='paper')['state'],'stale')
                self.command('verify', expected=1)
                self.command('status','--files')
        self.command('build')
        self.command('verify')

    @unittest.skipUnless(TEX, 'real latexmk/pdflatex required')
    def test_a8_current_startup_failure_never_uses_prior_tex_log(self):
        (self.project / 'main.tex').write_text(SOURCE.replace('Audit fixture.','\\OLDMACRO'))
        self.install('init','--no-lint','--skip-editor')
        first = self.command('build',expected=1)
        self.assertIn('Undefined control sequence',first.stderr)
        (self.project / 'main.tex').write_text(SOURCE)
        (self.project / '.latexmkrc').write_text('die "CURRENT_RC_FAILURE before TeX starts\\n";\n')
        # Ensure the old log falls inside the previous implementation's one-second allowance.
        os.utime(Path(str(latex.output_paths(self.project, schema.document_settings(schema.load_config(self.project)))[2]) + '.log'), None)
        second = self.command('build',expected=1)
        self.assertIn('CURRENT_RC_FAILURE',second.stderr)
        self.assertNotIn('ERROR: main.tex:',second.stderr)

    def test_review_restored_journal_does_not_block_later_cleanup(self):
        pdf=self.project/'main.pdf'
        pdf.write_bytes(b'%PDF original')
        transaction=output_transaction.OutputTransaction(self.project,'paper',[pdf])
        transaction.displace()
        transaction.rollback()
        self.assertEqual(pdf.read_bytes(),b'%PDF original')
        pdf.unlink()  # a later successful build may be cleaned by the project
        output_transaction.recover(self.project,'paper')

    def test_review_interrupted_journal_is_recovered_only_once(self):
        pdf=self.project/'main.pdf'
        pdf.write_bytes(b'%PDF original')
        transaction=output_transaction.OutputTransaction(self.project,'paper',[pdf])
        transaction.displace()
        output_transaction.recover(self.project,'paper')
        self.assertEqual(pdf.read_bytes(),b'%PDF original')
        pdf.unlink()
        output_transaction.recover(self.project,'paper')

    def test_a12_lifecycle_fixture_ignores_callers_doc_and_makeflags(self):
        result=subprocess.run([sys.executable,'-B','-m','unittest',
            'test_receipts.DocumentLifecycleTests.test_failed_named_build_regenerates_instead_of_reviving_a_receipt'],
            cwd=bootstrap.PACKAGE/'tests',env={**self.env,'DOC':'external','MAKEFLAGS':'n'},
            capture_output=True,text=True,timeout=25)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


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

    def install(self, *args, expected=0):
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
        config = {"schema_version": 3, "modules": {"latex": {"default_document": "paper", "documents": {"paper": settings}}}}
        (project / core.CONFIG).write_text(json.dumps(config))
        self.install("init", str(project))
        return config

    @unittest.skipUnless(TEX_blind_repairs, "real compiler required; fixture lint deliberately disabled")
    def test_first_custom_nested_build_needs_no_retry(self):
        self.fixture()
        self.command("make", "latex-ai-build")
        self.assertEqual(documents.report(self.project, schema.load_config(self.project))[0]["state"], "current")

    @unittest.skipUnless(TEX_blind_repairs, "real compiler required; fixture lint deliberately disabled")
    def test_changed_compiler_recorded_input_refuses_verification_and_export(self):
        config = self.fixture(hidden=True)
        # Permit the old first-build retry here so the stale-certification failure
        # is independently demonstrated, rather than hidden by the first-run defect.
        first = subprocess.run(["make", "latex-ai-build"], cwd=self.project,
                               env=fixture_env(), capture_output=True, text=True, timeout=30)
        if first.returncode:
            self.command("make", "latex-ai-build")
        (self.project / "hidden.tex").write_text("Changed source.\n")
        result = self.command(sys.executable, ".latex-ai/workbench.py", "verify", "--json", expected=1)
        self.assertEqual(json.loads(result.stdout)["status"], "failed")
        self.command("make", "latex-ai-pdf-artifact", expected=2)
        self.assertEqual(documents.report(self.project, config)[0]["state"], "stale")

    @unittest.skipUnless(TEX_blind_repairs, "real compiler required; fixture lint deliberately disabled")
    def test_recorder_context_matrix_and_durable_dependencies(self):
        for custom in (False, True):
            for spelling in ("plain", "Project With Spaces"):
                with self.subTest(custom=custom, spelling=spelling):
                    project = self.project / str(custom) / spelling
                    config = self.fixture(project, custom, hidden=True)
                    self.command("make", "latex-ai-build", cwd=project)
                    view = schema.document_settings(config)
                    name = "hidden.tex" if custom else "tex/nested/hidden.tex"
                    receipt = latex.read_receipt(project, view)
                    self.assertIsNotNone(receipt["inputs"].get(name), receipt)
                    self.assertNotIn("tex/nested/tex/nested/paper.tex", receipt["inputs"])
                    Path(str(latex.output_paths(project, view)[2]) + ".fls").unlink()
                    self.assertEqual(documents.report(project, config)[0]["state"], "current")
                    self.assertIn(name, documents.dependency_index(project, config)["paper"])
                    (project / name).write_text("Changed hidden source.\n")
                    self.assertEqual(documents.report(project, config)[0]["state"], "stale")
                    self.command("make", "latex-ai-build", cwd=project)
                    self.command("make", "latex-ai-pdf-artifact", cwd=project)

    def test_recorder_pwd_is_authoritative_and_unresolvable_relative_inputs_fail(self):
        nested = self.project / "nested"
        nested.mkdir()
        (self.project / "source with spaces.txt").write_text("source")
        (nested / "alias.txt").symlink_to(self.project / "source with spaces.txt")
        fls = self.project / "paper.fls"
        fls.write_text(f"PWD {self.project}\nINPUT source with spaces.txt\nPWD {nested}\nINPUT alias.txt\nINPUT /outside/system.tex\n")
        self.assertEqual(latex.recorder_inputs(self.project, fls), {"source with spaces.txt"})
        fls.write_text("INPUT relative.txt\n")
        with self.assertRaises(core.WorkbenchError):
            latex.recorder_inputs(self.project, fls)

    @unittest.skipUnless(TEX_blind_repairs, "real compiler required; fixture lint deliberately disabled")
    def test_native_discovery_is_protected_before_certification(self):
        for mutate_again in (False, True):
            with self.subTest(mutate_again=mutate_again):
                project = self.project / str(mutate_again)
                config = self.fixture(project, custom=False, hidden=True)
                hidden = project / "tex/nested/hidden.tex"
                actual_run = latex.run_compiler
                calls = []

                def change_after_read(*args, **kwargs):
                    result = actual_run(*args, **kwargs)  # genuine TeX has consumed the source
                    calls.append(1)
                    if len(calls) == 1 or mutate_again:
                        hidden.write_text(f"Changed source {len(calls)}.\n")
                    return result

                with patch.object(latex, "run_compiler", side_effect=change_after_read):
                    if mutate_again:
                        with self.assertRaises(core.WorkbenchError):
                            latex.build(project, schema.document_settings(config))
                    else:
                        latex.build(project, schema.document_settings(config))
                self.assertEqual(len(calls), 2)
                self.assertEqual(documents.report(project, config)[0]["state"], "failed" if mutate_again else "current")
                if not mutate_again and shutil.which("pdftotext"):
                    pdf = Path(str(latex.output_paths(project, schema.document_settings(config))[2]) + ".pdf")
                    text = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True)
                    self.assertIn("Changed source 1.", text)
                    self.assertNotIn("Original source.", text)

    def test_discovery_rebuild_still_rejects_input_changes(self):
        config = self.fixture()
        settings = config["modules"]["latex"]["documents"]["paper"]
        settings["output_dir"] = "outputs"
        settings["build_command"] = [sys.executable, "builder.py"]
        (self.project / "hidden.txt").write_text("original")
        (self.project / "builder.py").write_text(
            "from pathlib import Path\n"
            "count=int(Path('count').read_text())+1 if Path('count').exists() else 1\n"
            "Path('count').write_text(str(count))\n"
            "out=Path('outputs');out.mkdir(exist_ok=True)\n"
            "(out/'paper.pdf').write_bytes(b'%PDF-fixture')\n"
            "(out/'paper.log').write_text('Clean log\\n')\n"
            "(out/'paper.fls').write_text('PWD '+str(Path.cwd())+'\\nINPUT hidden.txt\\nINPUT tex/nested/paper.tex\\n')\n"
            "if count==2: Path('hidden.txt').write_text('changed during protected rebuild')\n")
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.command("make", "latex-ai-build", expected=2)
        self.assertEqual((self.project / "count").read_text(), "2")
        self.assertEqual(documents.report(self.project, config)[0]["state"], "failed")

    def test_receipt_without_protected_discovery_guarantee_cannot_certify(self):
        config = self.fixture(custom=False, hidden=True)
        view = schema.document_settings(config)
        stem = latex.output_paths(self.project, view)[2]
        stem.parent.mkdir(parents=True, exist_ok=True)
        Path(str(stem) + ".pdf").write_bytes(b"%PDF-old")
        Path(str(stem) + ".log").write_text("Clean old log\n")
        # Format 2 allowed newly observed inputs to be hashed after compilation.
        # Its recorder may already be gone; do not reuse its certification or
        # its incomplete stored dependency list under the new guarantee.
        path = self.project / latex.receipt_path(view)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": 2, "status": "verified", "identity": latex.build_identity(self.project, view),
                                    "inputs": latex.build_inputs(self.project, view), "outputs": latex.build_outputs(self.project, view)}))
        self.assertEqual(documents.report(self.project, config)[0]["state"], "stale")
        with self.assertRaises(core.WorkbenchError):
            latex.verify(self.project, view)


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
        (self.project / "main.tex").write_text(SOURCE_blind_repairs)
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
            path.write_text(SOURCE_blind_repairs)
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
        source.write_text(SOURCE_blind_repairs.replace("A note.", "BROKEN"))
        self.make("check", expected=2)
        self.assertEqual(self.states(), {"manuscript": "failed"})
        source.write_text(SOURCE_blind_repairs)
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

    # F3: a failed document is reported and selected until it is rebuilt.
    def test_failed_document_is_reported_and_selected_after_its_source_is_restored(self):
        config = self.named()
        self.install("init")
        self.command("check")
        note = self.project / "notes/main.tex"
        note.write_text("BROKEN\n")
        self.command("validate", "--files", "notes/main.tex", expected=1)
        note.write_text(SOURCE_blind_repairs)
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

    # F6: settings that do not affect compilation keep receipts current.
    def test_default_document_and_lint_settings_do_not_invalidate_receipts(self):
        config = self.named()
        self.install("init")
        self.command("check")
        config["modules"]["latex"]["default_document"] = "note"
        config["modules"]["latex"]["documents"]["paper"]["lint"] = {"args": ["-n8"]}
        self.write_config(config)
        self.assertEqual(self.states(), {"paper": "current", "note": "current"})
        config["modules"]["latex"]["documents"]["paper"]["backend"] = "bibtex"
        self.write_config(config)
        self.assertEqual(self.states(), {"paper": "stale", "note": "current"})

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "real TeX tools required")
    def test_compiler_failure_names_the_tex_error(self):
        (self.project / "main.tex").write_text(SOURCE_blind_repairs)
        self.install("init", "--no-lint", "--skip-editor")
        (self.project / "notes").mkdir()
        (self.project / "notes/derivation.tex").write_text("\\documentclass{article}\n\\begin{document}\n\\undefinedfixturemacro\n\\end{document}\n")
        config = json.loads((self.project / core.CONFIG).read_text())
        config["modules"]["latex"]["documents"]["derivation"] = {"root": "notes/derivation.tex", "lint": {"enabled": False}}
        self.write_config(config)
        result = self.command("document-check", "--document", "derivation", expected=1)
        self.assertIn("derivation.tex:3: Undefined control sequence", result.stderr)
        self.assertIn("Hint:", result.stderr)


class DocumentTests(unittest.TestCase):
    """Origin: tests/test_documents.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-documents-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
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
        config = {"schema_version": 3, "modules": {"latex": {
            "default_document": "paper", "defaults": {"lint": {"enabled": False}}, "documents": {
                "paper": {"root": "main.tex", "build_command": [sys.executable, "compile.py", "main.tex", ".latex-ai/artifacts/documents/paper/build"]},
                "note": {"root": "notes/main.tex", "build_command": [sys.executable, "compile.py", "notes/main.tex", ".latex-ai/artifacts/documents/note/build"]}}}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        return config

    def test_rejects_output_directory_symlink_alias(self):
        config = self.configuration()
        (self.project / "output").mkdir()
        (self.project / "alias").symlink_to(self.project / "output", target_is_directory=True)
        targets = config["modules"]["latex"]["documents"]
        targets["paper"]["output_dir"] = "output"
        targets["note"]["output_dir"] = "alias"
        with self.assertRaisesRegex(core.WorkbenchError, "collision"):
            schema.validate_config(self.project, config)

    def test_build_outputs_cannot_overwrite_another_document_export(self):
        config = self.configuration()
        (self.project / "document.tex").write_text("\\documentclass{article}\n")
        config["modules"]["latex"]["documents"]["note"].update({"root": "document.tex", "output_dir": ".latex-ai/artifacts/documents/paper"})
        with self.assertRaisesRegex(core.WorkbenchError, "exported PDF"):
            schema.validate_config(self.project, config)

    def test_malformed_receipt_does_not_break_read_only_document_planning(self):
        config = self.configuration()
        self.install("init")
        receipt = self.project / latex.receipt_path(schema.resolve(config, "note").view)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({"schema_version": 1, "status": "verified", "configuration": None, "inputs": None}))
        before = self.snapshot()
        self.command("documents", "--json")
        report = json.loads(self.command("plan", "--files", "notes/main.tex", "--json").stdout)
        self.assertEqual(report["documents"], ["note"])
        self.assertEqual(self.snapshot(), before)

    def test_two_same_stem_documents_have_independent_receipts_and_exports(self):
        self.configuration()
        self.install("init")
        for name in ("paper", "note"):
            self.make("latex-ai-build", "DOC=" + name)
            self.make("latex-ai-pdf-artifact", "DOC=" + name)
        directory = self.project / ".latex-ai/artifacts/documents"
        paper = (directory / "paper/build-receipt.json").read_bytes()
        (self.project / "notes/main.tex").write_text("BROKEN\n")
        self.make("latex-ai-build", "DOC=note", expected=2)
        self.assertEqual(paper, (directory / "paper/build-receipt.json").read_bytes())
        self.make("latex-ai-pdf-artifact", "DOC=note", expected=2)
        self.make("latex-ai-pdf-artifact", "DOC=paper")
        self.assertTrue((directory / "paper/document.pdf").read_bytes().startswith(b"%PDF-"))
        self.assertFalse((self.project / ".latex-ai/artifacts/manuscript.pdf").exists())

    def test_receipt_configuration_changes_are_scoped(self):
        config = self.configuration()
        self.install("init")
        self.command("check")
        config["modules"]["latex"]["documents"]["note"]["backend"] = "bibtex"
        (self.project / core.CONFIG).write_text(json.dumps(config))
        states = {row["id"]: row["state"] for row in json.loads(self.command("documents").stdout)}
        self.assertEqual(states, {"paper": "current", "note": "stale"})

    def test_inspection_leaves_receipts_and_sources_unchanged(self):
        self.configuration()
        self.install("init")
        self.command("check")
        before = self.snapshot()
        self.command("documents")
        self.command("status", "--json")
        self.command("plan", "--files", "notes/main.tex", "--json")
        self.assertEqual(before, self.snapshot())

    def test_active_adopted_build_blocks_other_cleanup_and_export(self):
        config = self.configuration()
        config["modules"]["latex"]["documents"]["note"]["build_command"] = None
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        with contextlib.redirect_stdout(io.StringIO()):
            latex.prepare_build(self.project, schema.resolve(config, "paper").view, os.getpid())
        before = self.snapshot()
        for action in ("clean", "artifact"):
            result = self.command(action, "--document", "note", expected=1)
            self.assertIn("Another build is active", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_separate_adopted_graphs_allow_comments_with_make_symbols(self):
        config = self.configuration()
        (self.project / "Makefile").write_text("paper: main.tex # uses $< and 100%\nnote: notes/main.tex\n")
        for name in ("paper", "note"):
            config["modules"]["latex"]["documents"][name]["build_command"] = ["make", name]
        schema.validate_config(self.project, config)


class ModuleTests(unittest.TestCase):
    """Origin: tests/test_modules.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-modules-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return boot.main([*args, str(self.project)])

    def run_main(self, *arguments):
        errors = io.StringIO()
        with patch.object(sys, "argv", ["workbench", *arguments, "--project", str(self.project)]), contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            return rt.main(), errors.getvalue()

    PAPER = "\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n"

    def test_full_check_builds_before_linting_and_a_lint_failure_says_what_can_be_done(self):
        import latex
        (self.project / "main.tex").write_text(self.PAPER)
        self.assertEqual(self.cli("init", "--modules", "latex"), 0)
        config = schema.load_config(self.project)
        order = []
        with patch.object(rt, "build", side_effect=lambda *a: order.append("build")), patch.object(rt, "verify", side_effect=lambda *a: order.append("verify")), \
                patch.object(rt, "lint", side_effect=lambda *a: order.append("lint")), contextlib.redirect_stdout(io.StringIO()):
            rt.full_check(self.project, config)
        self.assertEqual(order, ["build", "verify", "lint"])  # a TeX error is reported even when the style checker also objects
        with patch.object(latex, "chktex_warnings", return_value=[dict(self.ROWS[0])]), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(core.WorkbenchError) as raised:
                latex.lint(self.project, schema.document_settings(config))
        for phrase in ("lint", "args", ".chktexrc", "enabled", "baseline"):
            self.assertIn(phrase, raised.exception.hint)

    ROWS = [{"file": "main.tex", "line": 3, "warning": 2, "message": "Non-breaking space (`~') should have been used.", "text": "See Fig. \\ref{f}."},
            {"file": "main.tex", "line": 3, "warning": 12, "message": "Interword spacing (`\\ ') should perhaps be used.", "text": "See Fig. \\ref{f}."},
            {"file": "sections/a.tex", "line": 9, "warning": 8, "message": "Wrong length of dash may have been used.", "text": "Runge--Kutta"}]

    def test_lint_baseline_accepts_recorded_warnings_and_fails_only_on_new_ones(self):
        import latex
        (self.project / "main.tex").write_text(self.PAPER)
        self.assertEqual(self.cli("init", "--modules", "latex"), 0)
        config = schema.load_config(self.project)
        baseline = self.project / latex.baseline_path(schema.document_settings(config))

        def lint(rows):
            out = io.StringIO()
            with patch.object(latex, "chktex_warnings", return_value=[dict(row) for row in rows]), contextlib.redirect_stdout(out):
                try:
                    latex.lint(self.project, schema.document_settings(config))
                    return None, out.getvalue()
                except core.WorkbenchError as error:
                    return error, out.getvalue()

        error, _ = lint(self.ROWS)  # no baseline yet: every warning fails, and the hint names the way out
        self.assertIsNotNone(error)
        self.assertIn("lint-baseline", error.hint)
        with patch.object(latex, "chktex_warnings", return_value=[dict(row) for row in self.ROWS]):
            status, errors = self.run_main("lint-baseline")
        self.assertEqual(status, 0, errors)
        data = json.loads(baseline.read_text())
        self.assertEqual(sum(entry["count"] for entry in data["accepted"]), 3)
        error, text = lint(self.ROWS)
        self.assertIsNone(error)
        self.assertIn("3 warning(s) accepted", text)
        moved = [dict(row, line=row["line"] + 40) for row in self.ROWS]  # the same lines further down the file are still the same warnings
        self.assertIsNone(lint(moved)[0])
        added = self.ROWS + [{"file": "main.tex", "line": 7, "warning": 18, "message": "Use either `` or '' as an alternative to `\"'.", "text": 'A "new" sentence.'}]
        error, text = lint(added)
        self.assertIn("1 new warning", str(error))
        self.assertIn("main.tex:7", text)
        self.assertNotIn("Runge--Kutta", text)  # accepted warnings are not listed again
        edited = [dict(self.ROWS[0], text="See also Fig. \\ref{f}.")] + self.ROWS[1:]  # touching an accepted line means cleaning it
        self.assertIn("1 new warning", str(lint(edited)[0]))
        error, text = lint(self.ROWS[:1])  # fixed warnings never fail; the leftover entries are reported
        self.assertIsNone(error)
        self.assertIn("2 accepted warning(s) no longer occur", text)
        self.assertIsNone(lint([])[0])
        plan = rt.validation_plan(self.project, config, paths=[".chktex-baseline.json"])
        self.assertTrue(plan["manuscript"])  # changing the baseline is a change to what is checked
        policy = (boot.PACKAGE / "templates/AGENTS.md").read_text()
        self.assertIn("make latex-ai-lint-baseline", policy)
        self.assertRegex(policy, r"(?s)baseline.*owner")

    def test_lint_output_that_cannot_be_read_fails_instead_of_passing(self):
        import latex
        (self.project / "main.tex").write_text(self.PAPER)
        self.assertEqual(self.cli("init", "--modules", "latex"), 0)
        config = schema.load_config(self.project)
        for returncode, stdout in ((2, "something this version prints differently\n"), (1, "")):
            done = argparse.Namespace(returncode=returncode, stdout=stdout, stderr="chktex: complaint\n")
            with self.subTest(returncode=returncode), patch.object(latex.shutil, "which", return_value="/usr/bin/chktex"), \
                    patch.object(latex.subprocess, "run", return_value=done), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(core.WorkbenchError):
                    latex.chktex_warnings(self.project, schema.document_settings(config))
        fmt = "\x1f".join(("main.tex", "3", "2", "Non-breaking space", "See Fig. \\ref{f}.  ")) + "\n"
        with patch.object(latex.shutil, "which", return_value="/usr/bin/chktex"), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(latex.subprocess, "run", return_value=argparse.Namespace(returncode=2, stdout=fmt, stderr="")):
            rows = latex.chktex_warnings(self.project, schema.document_settings(config))
        self.assertEqual(rows, [{"file": "main.tex", "line": 3, "warning": 2, "message": "Non-breaking space", "text": "See Fig. \\ref{f}."}])


class RecursionGuard(ProjectCase):
    """Origin: tests/test_one_table_each.py."""

    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")

    def test_the_goals_that_run_the_build_again_come_from_the_registry(self):
        self.assertEqual(set(commands.RECURSIVE_GOALS), RECURSIVE_GOALS)
        names = {name for command in commands.COMMANDS for name in (command.short, command.reserved)}
        self.assertLessEqual(commands.RECURSIVE_GOALS, names | {"latex-ai-build"})
        self.assertTrue(all(goal.startswith(commands.RESERVED_PREFIX) or goal in {"build", "check", "validate", "document-check"}
                            for goal in commands.RECURSIVE_GOALS))
        self.assertTrue(all(command.reserved.startswith(commands.RESERVED_PREFIX) for command in commands.COMMANDS if command.reserved))

    def test_a_build_command_naming_any_of_them_is_refused(self):
        for goal in sorted(commands.RECURSIVE_GOALS) + ["latex-ai-plan", "latex-ai-anything"]:
            with self.subTest(goal=goal):
                config = self.configure(documents_={"paper": {"root": "main.tex", "build_command": ["make", goal]}})
                with self.assertRaisesRegex(schema.WorkbenchError, "Recursive build_command"):
                    schema.validate_config(self.project, config)

    def test_the_project_s_own_targets_are_not_refused(self):
        for goal in ("lint", "paper", "all"):
            with self.subTest(goal=goal):
                config = self.configure(documents_={"paper": {"root": "main.tex", "build_command": ["make", goal]}})
                schema.validate_config(self.project, config)

    def test_the_closure_check_forbids_the_same_goals(self):
        source = (PACKAGE / "schema.py").read_text(encoding="utf-8")
        self.assertNotIn('"latex-ai-document-check"', source, "the goals are the registry's, not a second list")
        self.assertNotIn('"document-check", "validate"', source)


class Repairs(ProjectCase):

    # --- build-produced inputs -------------------------------------------------------------------------

    """Origin: tests/test_repairs_3_0_1.py, workbench 3.0.1."""

    def generated_project(self, deterministic=True):
        (self.project / "main.tex").write_text(GENERATED)
        (self.project / "data.txt").write_text("1\n")
        text = "'sum ' + data" if deterministic else "'sum ' + data + ' run ' + count.read_text()"
        self.builder("data = Path('data.txt').read_text().strip()\n"
                     "table = Path('table.tex')\n"
                     f"text = {text}\n"
                     "if not table.exists() or table.read_text() != text:\n"
                     "    table.write_text(text)\n", inputs=("main.tex", "data.txt", "table.tex"))
        self.configure()
        self.install("init", "--skip-editor")

    def test_generated_input_is_certified_on_the_first_build_and_after_data_changes(self):
        self.generated_project()
        self.command("build")  # table.tex is written by the build that includes it
        self.assertEqual(self.state(), "current")
        self.assertEqual(self.receipt()["inputs"]["table.tex"], digest("sum 1"))
        (self.project / "data.txt").write_text("2\n")
        self.assertEqual(self.state(), "stale")
        self.command("build")
        self.assertEqual(self.state(), "current")
        self.assertEqual(self.receipt()["inputs"]["table.tex"], digest("sum 2"))

    def test_generator_that_cannot_settle_names_the_unstable_input(self):
        self.generated_project(deterministic=False)
        result = self.command("build", expected=1)
        self.assertIn("table.tex", result.stderr)
        self.assertIn("changed during execution", result.stderr)
        self.assertEqual(self.state(), "failed")

    @unittest.skipUnless(TEX_3_0_1, "real latexmk, pdflatex and GNU Make required")
    def test_adopted_make_with_generated_table_and_figure_builds_once(self):
        (self.project / "data.csv").write_text("1\n2\n3\n4\n")
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}\n"
                                               "Sum of data: \\input{table}\n\\includegraphics[width=2cm]{figure.pdf}\n\\end{document}\n")
        self.run_command("pdflatex", "-interaction=nonstopmode", "-jobname=base", "\\documentclass{article}\\begin{document}x\\end{document}")
        self.configure({"paper": {"root": "main.tex", "lint": {"enabled": False}, "backend": "none", "build_command": ["make", "pdf"], "output_dir": "."}})
        self.install("init", "--skip-editor")
        with (self.project / "Makefile").open("a") as stream:  # the project's own rules, after what init wrote
            stream.write(
                ".PHONY: pdf\npdf: main.pdf\n"
                "table.tex: data.csv\n\tawk '{s+=$$1} END {printf \"%d\", s}' data.csv > table.tex\n"
                "figure.pdf: data.csv base.pdf\n\tcp base.pdf figure.pdf\n"
                "main.pdf: main.tex table.tex figure.pdf\n\tlatexmk -pdf -interaction=nonstopmode -recorder main.tex\n")
        self.run_command("make", "check")
        self.assertEqual(self.state(), "current")
        (self.project / "data.csv").write_text("5\n5\n")
        self.run_command("make", "check")
        self.assertEqual(self.state(), "current")
        text = subprocess.run(["pdftotext", "main.pdf", "-"], cwd=self.project, capture_output=True, text=True).stdout if shutil.which("pdftotext") else "Sum of data: 10"
        self.assertIn("Sum of data: 10", text)

    def linked_project(self):
        outside = self.root / "shared-figures"
        outside.mkdir()
        (outside / "plot.txt").write_text("one")
        (self.project / "shared").symlink_to(outside, target_is_directory=True)
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\\includegraphics{shared/plot.pdf}\\end{document}\n")
        self.builder(inputs=("main.tex", "shared/plot.txt", "/outside/system.sty"))
        self.configure()
        self.install("init", "--skip-editor")
        return outside

    def test_link_leaving_the_project_is_a_tracked_input(self):
        outside = self.linked_project()
        self.command("build")
        self.assertEqual(self.state(), "current")
        self.assertIn("shared/plot.txt", self.receipt()["inputs"])
        self.assertNotIn("/outside/system.sty", "".join(self.receipt()["inputs"]))
        (outside / "plot.txt").write_text("two")
        self.assertEqual(self.state(), "stale")
        self.command("verify", expected=1)
        self.command("build")
        self.assertEqual(self.state(), "current")

    def test_link_target_named_in_source_is_tracked_on_a_fresh_checkout(self):
        outside = self.linked_project()
        (outside / "plot.pdf").write_bytes(b"%PDF-figure")
        view = schema.document_settings(schema.load_config(self.project))
        self.assertIn("shared/plot.pdf", latex.manuscript_dependencies(self.project, view, include_receipt=False))

    def test_names_that_are_not_project_spellings_still_invalidate_a_receipt(self):
        self.linked_project()
        self.command("build")
        path = self.project / ".latex-ai/artifacts/documents/paper/build-receipt.json"
        for bad in ("../shared-figures/plot.txt", "shared/../main.tex", "/etc/hostname"):
            with self.subTest(name=bad):
                receipt = json.loads(path.read_text())
                receipt["inputs"][bad] = None
                self.assertEqual(latex.recorded_inputs(self.project, schema.document_settings(schema.load_config(self.project)), receipt), {})

    def test_bibliography_style_beside_the_document_is_an_input(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Cite.\\bibliographystyle{house}\\bibliography{refs}\\end{document}\n")
        (self.project / "house.bst").write_text("% local style\n")
        (self.project / "refs.bib").write_text("@article{a,title={A}}\n")
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")
        view = schema.document_settings(schema.load_config(self.project))
        self.assertIn("house.bst", latex.manuscript_dependencies(self.project, view, include_receipt=False))
        self.assertIn("house.bst", latex.build_inputs(self.project, view))
        self.command("build")
        self.assertEqual(self.state(), "current")
        (self.project / "house.bst").write_text("% edited local style\n")
        self.assertEqual(self.state(), "stale")

    def test_system_bibliography_style_adds_no_input(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Cite.\\bibliographystyle{plain}\\end{document}\n")
        self.builder()
        self.configure()
        self.install("init", "--skip-editor")
        view = schema.document_settings(schema.load_config(self.project))
        self.assertNotIn("plain.bst", latex.build_inputs(self.project, view))
        (self.project / "plain.bst").write_text("% a local style shadows the system one\n")
        self.assertIn("plain.bst", latex.build_inputs(self.project, view))

    def test_a_clean_build_reports_its_integrity_once(self):
        self.configure()
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.install("init", "--skip-editor")
        result = self.run_command("make", "check")
        self.assertEqual(result.stdout.count("Citation/reference integrity checks passed"), 1, result.stdout)


class Repairs_3_0_2(ProjectCase):

    # --- F1: one lock per project, shared by everyone who works in it ----------------------------------

    """Origin: tests/test_repairs_3_0_2.py, workbench 3.0.2."""

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
        original = Path.open
        def counted(path, *arguments, **keywords):
            reads.append(path.name)
            return original(path, *arguments, **keywords)
        with patch.object(latex, "SETTLED_NS", 0), patch.object(Path, "open", counted):
            first = latex.build_inputs(self.project, config)
            latex.build_inputs(self.project, config)
        self.assertEqual(reads.count("data.bin"), 1)
        (self.project / "data.bin").write_bytes(b"y" * 1000)  # same size: the change of ctime is what counts
        with patch.object(latex, "SETTLED_NS", 0):
            self.assertNotEqual(latex.build_inputs(self.project, config)["data.bin"], first["data.bin"])

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


class ReviewFixes(unittest.TestCase):
    """Origin: tests/test_review_fixes.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-review-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def install(self, *arguments, env=None):
        return subprocess.run([sys.executable, "-B", str(bootstrap.PACKAGE / "latex-ai-init"),
                               "init", str(self.project), *arguments], env=env, capture_output=True, text=True)

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "needs pdfLaTeX")
    def test_default_build_receipt_rejects_stale_verify_and_export(self):
        p = self.project
        source = p / "main.tex"
        source.write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'lint': {'enabled': False}, 'output_dir': '.'}}}}, 'integrations': {'ci': {'pdf_artifact': True}}}
        with contextlib.redirect_stdout(io.StringIO()):
            latex.build(p, schema.document_settings(config))
            latex.build(p, schema.document_settings(config))
            source.write_text(source.read_text().replace("Fixture", "\\undefinedcommand"))
            for action in (latex.verify, latex.artifact):
                with self.subTest(action=action.__name__), self.assertRaisesRegex(core.WorkbenchError, "freshness|receipt"):
                    action(p, schema.document_settings(config))
            with self.assertRaises(core.WorkbenchError):
                latex.build(p, schema.document_settings(config))
            source.write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
            with self.assertRaises(core.WorkbenchError):
                latex.verify(p, schema.document_settings(config))

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "needs pdfLaTeX")
    def test_existing_make_target_and_custom_build_work_together(self):
        p = self.project
        (p / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        result = self.install("--build-command", '["make","pdf"]', "--no-lint", "--skip-editor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with (p / "Makefile").open("a") as stream:  # the project's own rule goes after what init wrote
            stream.write("\npdf:\n\t@echo compiler >> calls\n\tlatexmk -pdf -recorder -interaction=nonstopmode -halt-on-error main.tex\n")
        for count in range(1, 3):
            result = subprocess.run(["make", "-j4", "check"], cwd=p, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len((p / "calls").read_text().splitlines()), count)
        self.assertEqual(latex.read_receipt(p, schema.document_settings(schema.load_config(p)))["status"], "verified")
        # An unchanged raw project build retains its valid receipt. The reserved
        # wrapper is what establishes a new one after inputs or outputs change.
        receipt = (p / latex.receipt_path(schema.document_settings(schema.load_config(p)))).read_bytes()
        result = subprocess.run(["make", "pdf"], cwd=p, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((p / latex.receipt_path(schema.document_settings(schema.load_config(p)))).read_bytes(), receipt)


class Receipts(ProjectCase):
    """The plan's criterion for this step: the receipts of projects that use only what stays do not change.

    Origin: tests/test_scope_4_5_0.py, workbench 4.5.0.
    """

    def test_a_receipt_written_by_4_4_2_is_still_current(self):
        (self.project / "main.tex").write_text(SOURCE_4_5_0)
        (self.project / "builder.py").write_text(BUILDER_FIXTURE)
        (self.project / "outputs").mkdir()
        (self.project / "outputs/main.pdf").write_bytes(b"%PDF-fixture\n")
        (self.project / "outputs/main.log").write_text("Clean log\n")
        (self.project / core.CONFIG).write_text(json.dumps({"schema_version": 3, "modules": {"latex": {"default_document": "paper", "documents": {
            "paper": {"root": "main.tex", "lint": {"enabled": False}, "output_dir": "outputs", "build_command": ["python3", "builder.py"]}}}}}))
        receipt = self.project / ".latex-ai/artifacts/documents/paper/build-receipt.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps(FROZEN_RECEIPT, indent=2) + "\n")
        self.assertEqual(self.state(), "current")

    def test_the_build_identity_keeps_the_shape_and_values_4_4_2_recorded(self):
        (self.project / "main.tex").write_text(SOURCE_4_5_0)
        config = configuration({"backend": "bibtex"}, files=["refs.bib"], export={"path": "refs.bib", "required": True, "format": "bibtex"})
        view = schema.document_settings(core.effective_config(config))
        self.assertEqual(latex.build_identity(self.project, view), BIBTEX_IDENTITY)


class ExportSafetyAudit(ProjectCase):
    """4.10.2: export must preserve source aliases and the previous complete export."""

    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE_4_8_1)
        self.configure()
        self.builder()
        self.install('init', '--skip-editor')
        self.command('build')
        self.destination = self.project / '.latex-ai/artifacts/documents/paper/document.pdf'

    def linked_export(self, symbolic):
        source = self.project / 'main.tex'
        before = source.read_bytes()
        if symbolic:
            self.destination.symlink_to(source)
        else:
            self.destination.hardlink_to(source)
        result = self.command('artifact', expected=1)
        self.assertIn('linked PDF export', result.stderr)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(self.state(), 'current')

    def test_export_refuses_a_symlink_to_source(self):
        self.linked_export(symbolic=True)

    def test_export_refuses_a_hard_link_to_source(self):
        self.linked_export(symbolic=False)

    def test_export_refuses_a_redirected_parent_directory(self):
        original = self.destination.parent
        redirected = self.project / 'authored'
        original.rename(redirected)
        original.symlink_to(redirected, target_is_directory=True)
        source = redirected / 'document.pdf'
        source.write_bytes(b'%PDF-authored figure')
        result = self.command('artifact', expected=1)
        self.assertIn('linked PDF export', result.stderr)
        self.assertEqual(source.read_bytes(), b'%PDF-authored figure')

    def test_failed_export_preserves_the_previous_complete_pdf(self):
        self.destination.write_bytes(b'%PDF-previous complete export')

        def interrupted(source, destination):
            Path(destination).write_bytes(b'partial copy')
            raise OSError('simulated full disk')

        view = schema.document_settings(schema.load_config(self.project))
        with patch.object(latex.shutil, 'copyfile', side_effect=interrupted), self.assertRaises(OSError):
            latex.artifact(self.project, view)
        self.assertEqual(self.destination.read_bytes(), b'%PDF-previous complete export')
        self.assertFalse(list(self.destination.parent.glob('.latex-ai-tmp-*')))

    def test_a_pdf_changed_during_copy_is_not_published_as_verified(self):
        self.destination.write_bytes(b'%PDF-previous complete export')
        copy = shutil.copyfile

        def changed(source, destination):
            Path(source).write_bytes(b'%PDF-unverified replacement')
            return copy(source, destination)

        view = schema.document_settings(schema.load_config(self.project))
        with patch.object(latex.shutil, 'copyfile', side_effect=changed), self.assertRaises(core.WorkbenchError):
            latex.artifact(self.project, view)
        self.assertEqual(self.destination.read_bytes(), b'%PDF-previous complete export')
        self.assertFalse(list(self.destination.parent.glob('.latex-ai-tmp-*')))


class DigestMemoryAudit(ProjectCase):
    def test_hashing_a_large_input_uses_bounded_memory_and_preserves_the_digest(self):
        import hashlib
        import tracemalloc
        path = self.project / 'large-data.bin'
        data = b'12345678' * (1024 * 1024)
        path.write_bytes(data)
        expected = hashlib.sha256(data).hexdigest()
        del data
        tracemalloc.start()
        try:
            digest = latex.file_digest(path)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(digest, expected)
        self.assertLess(peak, 3 * 1024 * 1024)
        path.write_bytes(b'changed data')
        self.assertEqual(latex.file_digest(path), hashlib.sha256(b'changed data').hexdigest())


class AuditRepairs(ProjectCase):
    """Origin: tests/test_scope_4_8_1.py, workbench 4.8.1."""

    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE_4_8_1)

    def native(self, source=SOURCE_4_8_1):
        (self.project / 'main.tex').write_text(source)
        self.install('init', '--no-lint', '--skip-editor')
        return schema.document_settings(schema.load_config(self.project))

    def test_f1_standard_auxiliary_output_links_cannot_escape(self):
        outside = self.root / 'outside.txt'
        outside.write_text('keep')
        for suffix in ('.lof', '.lot', '.lol', '.loe', '.idx', '.ind', '.ilg', '.glo', '.gls', '.glg', '.acn', '.acr', '.alg', '.nav', '.snm', '.vrb'):
            with self.subTest(suffix=suffix):
                child = self.project / ('main' + suffix)
                child.symlink_to(outside)
                try:
                    with self.assertRaises(core.WorkbenchError):
                        core.document_paths(self.project, 'main.tex', '.')
                    self.assertEqual(outside.read_text(), 'keep')
                finally:
                    child.unlink()

    def test_f2_outputs_cannot_alias_any_declared_root_in_either_order(self):
        (self.project / 'notes.tex').write_text(SOURCE_4_8_1 + '% notes\n')
        for kind in ('hard', 'symbolic'):
            for default in ('paper', 'notes'):
                with self.subTest(kind=kind, default=default):
                    alias = self.project / 'main.log'
                    alias.hardlink_to(self.project / 'notes.tex') if kind == 'hard' else alias.symlink_to('notes.tex')
                    config = self.configure(documents_={
                        'paper': {'root': 'main.tex', 'output_dir': '.'},
                        'notes': {'root': 'notes.tex', 'output_dir': '.'}})
                    config['modules']['latex']['default_document'] = default
                    try:
                        with self.assertRaisesRegex(core.WorkbenchError, 'collision|overlap|aliases'):
                            schema.validate_config(self.project, config)
                        self.assertEqual((self.project / 'notes.tex').read_text(), SOURCE_4_8_1 + '% notes\n')
                    finally:
                        alias.unlink()

    def test_f2_output_cannot_alias_its_own_root(self):
        (self.project / 'main.aux').hardlink_to(self.project / 'main.tex')
        config = self.configure(documents_={'paper': {'root': 'main.tex', 'output_dir': '.'}})
        with self.assertRaises(core.WorkbenchError):
            schema.validate_config(self.project, config)

    def test_f2_build_protects_known_nonroot_source_from_output_alias(self):
        (self.project / 'fragment.tex').write_text('Valuable fragment.\n')
        (self.project / 'main.tex').write_text(SOURCE_4_8_1.replace('Fixture.', '\\input{fragment}'))
        (self.project / 'main.log').hardlink_to(self.project / 'fragment.tex')
        self.configure(documents_={'paper': {'root': 'main.tex', 'output_dir': '.',
            'lint': {'enabled': False}, 'build_command': [sys.executable, '-c', 'raise SystemExit(99)']}})
        self.install('init', '--skip-editor')
        result = self.command('build', expected=1)
        self.assertRegex(result.stderr, 'aliases|overlap|collision')
        self.assertEqual((self.project / 'fragment.tex').read_text(), 'Valuable fragment.\n')

    def test_f2_generated_suffix_does_not_hide_an_authored_listing(self):
        (self.project / 'example.idx').write_text('Keep the authored listing.\n')
        (self.project / 'main.tex').write_text(SOURCE_4_8_1.replace('Fixture.', '\\lstinputlisting{example.idx}'))
        self.builder(inputs=('main.tex', 'example.idx'))
        with (self.project / 'builder.py').open('a') as stream:
            stream.write("(out / 'main.idx').write_text('would overwrite the source')\n")
        self.configure()
        (self.project / 'outputs').mkdir()
        (self.project / 'outputs/main.idx').hardlink_to(self.project / 'example.idx')
        self.install('init', '--skip-editor')
        result = self.command('build', expected=1)
        self.assertIn('aliases a source input', result.stderr)
        self.assertEqual((self.project / 'example.idx').read_text(), 'Keep the authored listing.\n')

    def test_f2_recorder_only_same_suffix_data_still_invalidates_receipts(self):
        (self.project / 'train.log').write_text('first')
        self.builder(inputs=('main.tex', 'train.log'))
        self.configure()
        self.install('init', '--skip-editor')
        self.command('build')
        self.assertIn('train.log', self.receipt()['inputs'])
        (self.project / 'train.log').write_text('changed')
        self.assertEqual(self.state(), 'stale')

    def test_f2_explicit_listing_at_an_output_path_is_protected(self):
        (self.project / 'main.tex').write_text(SOURCE_4_8_1.replace('Fixture.', '\\lstinputlisting{outputs/main.idx}'))
        self.builder(inputs=('main.tex', 'outputs/main.idx'))
        with (self.project / 'builder.py').open('a') as stream:
            stream.write("(out / 'main.idx').write_text('would overwrite the source')\n")
        self.configure()
        (self.project / 'outputs').mkdir()
        (self.project / 'outputs/main.idx').write_text('Keep the authored listing.\n')
        self.install('init', '--skip-editor')
        result = self.command('build', expected=1)
        self.assertIn('aliases a source input', result.stderr)
        self.assertEqual((self.project / 'outputs/main.idx').read_text(), 'Keep the authored listing.\n')

    def test_f2_a_build_script_at_an_output_path_is_protected(self):
        self.builder()
        self.configure()
        (self.project / 'outputs').mkdir()
        script = self.project / 'outputs/main.log'
        original = (self.project / 'builder.py').read_text()
        script.write_text(original)
        self.edit_config(lambda data: data['modules']['latex']['documents']['paper'].update(
            build_command=[sys.executable, 'outputs/main.log']))
        self.install('init', '--skip-editor')
        self.assertIn('aliases a source input', self.command('build', expected=1).stderr)
        self.assertEqual(script.read_text(), original)

    def test_f2_mentioning_an_output_filename_is_not_reading_it(self):
        (self.project / 'main.tex').write_text(SOURCE_4_8_1.replace('Fixture.', '\\texttt{outputs/main.log}'))
        self.builder()
        self.configure()
        self.install('init', '--skip-editor')
        self.command('build')
        self.command('build')
        self.assertEqual(self.state(), 'current')

    def test_f2_output_command_arguments_are_not_treated_as_source_scripts(self):
        self.builder()
        config = self.configure()
        config['modules']['latex']['documents']['paper']['build_command'] += ['--output', 'outputs/main.pdf']
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install('init', '--skip-editor')
        self.command('build')
        self.command('build')
        self.assertNotIn('outputs/main.pdf', self.receipt()['inputs'])
        self.assertEqual(self.state(), 'current')

    def test_f2_makefiles_at_an_output_path_are_protected(self):
        self.builder()
        self.configure()
        self.install('init', '--skip-editor')
        original = 'raw:\n\t' + sys.executable + ' builder.py\n'
        for stem, directory in (('main', 'outputs'), ('-paper', '.'), ('-file', '.')):
            (self.project / (stem + '.tex')).write_text(SOURCE_4_8_1)
            name = (Path(directory) / (stem + '.log')).as_posix()
            script = self.project / name
            script.parent.mkdir(exist_ok=True)
            (self.project / 'builder.py').write_text('from pathlib import Path\n'
                + 'Path(' + repr(str(Path(directory) / (stem + '.pdf'))) + ").write_bytes(b'%PDF-fixture')\n"
                + 'Path(' + repr(name) + ").write_text('would overwrite the makefile')\n")
            for arguments in (['-f', name], ['--file', name], ['--makefile', name],
                              ['-f' + name], ['--file=' + name], ['--makefile=' + name]):
                with self.subTest(arguments=arguments):
                    script.write_text(original)
                    (self.project / '.latex-ai/artifacts/documents/paper/build-receipt.json').unlink(missing_ok=True)
                    self.edit_config(lambda data: data['modules']['latex']['documents']['paper'].update(
                        root=stem + '.tex', output_dir=directory, build_command=['make', *arguments, 'raw']))
                    self.assertIn('aliases a source input', self.command('build', expected=1).stderr)
                    self.assertEqual(script.read_text(), original)

    def test_f2_actual_generated_auxiliary_is_not_treated_as_authored(self):
        self.builder("Path('outputs').mkdir(exist_ok=True)\nPath('outputs/main.aux').write_text('generated')\n",
                     inputs=('main.tex', 'outputs/main.aux'))
        self.configure()
        self.install('init', '--skip-editor')
        self.command('build')
        self.assertNotIn('outputs/main.aux', self.receipt()['inputs'])
        self.assertEqual(self.state(), 'current')

    def test_f2_dash_named_makefile_does_not_turn_an_output_goal_into_source(self):
        self.builder()
        self.configure()
        self.install('init', '--skip-editor')
        (self.project / '-f').write_text('outputs/main.pdf: main.tex builder.py\n\t' + sys.executable + ' builder.py\n')
        for arguments in (['-f', '-f'], ['--file', '-f'], ['--makefile', '-f'],
                          ['-f-f'], ['--file=-f'], ['--makefile=-f']):
            with self.subTest(arguments=arguments):
                (self.project / '.latex-ai/artifacts/documents/paper/build-receipt.json').unlink(missing_ok=True)
                self.edit_config(lambda data: data['modules']['latex']['documents']['paper'].update(
                    build_command=['make', *arguments, 'outputs/main.pdf']))
                self.command('build')
                self.command('build')
                self.assertIn('-f', self.receipt()['inputs'])
                self.assertNotIn('outputs/main.pdf', self.receipt()['inputs'])
                self.assertEqual(self.state(), 'current')

    def test_f2_known_script_roles_preserve_dash_named_source_scripts(self):
        self.builder()
        self.configure()
        self.install('init', '--skip-editor')
        (self.project / '-paper.tex').write_text(SOURCE_4_8_1)
        builder = "from pathlib import Path\nPath('-paper.pdf').write_bytes(b'%PDF-fixture')\nPath('-paper.log').write_text('would overwrite the script')\n"
        (self.project / 'builder.py').write_text(builder)
        self.env['PATH'] = str(self.project) + os.pathsep + self.env['PATH']
        for executable, options, original in (
                (sys.executable, ['--'], builder), (sys.executable, ['-u', '--'], builder),
                ('bash', ['--'], sys.executable + ' builder.py\n'),
                ('bash', ['-eu', '--'], sys.executable + ' builder.py\n'),
                ('-paper.log', [], '#!' + sys.executable + '\n' + builder)):
            with self.subTest(executable=executable, options=options):
                script = self.project / '-paper.log'
                script.write_text(original)
                script.chmod(0o700)
                if not shutil.which(executable, path=self.env['PATH']):
                    self.skipTest(executable + ' required')
                (self.project / '.latex-ai/artifacts/documents/paper/build-receipt.json').unlink(missing_ok=True)
                self.edit_config(lambda data: data['modules']['latex']['documents']['paper'].update(
                    root='-paper.tex', output_dir='.', build_command=[executable, *options, '-paper.log']))
                self.assertIn('aliases a source input', self.command('build', expected=1).stderr)
                self.assertEqual(script.read_text(), original)

    @unittest.skipUnless(TEX, 'real latexmk and pdflatex required')
    def test_f1_listings_auxiliary_cannot_overwrite_an_external_file(self):
        view = self.native('\\documentclass{article}\n\\usepackage{listings}\n\\begin{document}\n\\lstlistoflistings\n'
                           '\\begin{lstlisting}[caption=Demo]\nexample\n\\end{lstlisting}\n\\end{document}\n')
        stem = latex.output_paths(self.project, view)[2]
        stem.parent.mkdir(parents=True, exist_ok=True)
        outside = self.root / 'outside.txt'
        outside.write_text('keep')
        Path(str(stem) + '.lol').symlink_to(outside)
        self.command('build', expected=1)
        self.assertEqual(outside.read_text(), 'keep')

    def test_f3_graphics_search_paths_in_fragments_add_all_candidates(self):
        (self.project / 'figures').mkdir()
        (self.project / 'other').mkdir()
        (self.project / 'paths.tex').write_text('\\graphicspath{\n {figures/} {other/}\n}\n')
        (self.project / 'main.tex').write_text(SOURCE_4_8_1.replace('Fixture.', '\\input{paths}\\includegraphics*{plot}\\includegraphics{fixed.png}'))
        for name in ('figures/plot.png', 'other/plot.pdf', 'figures/fixed.png', 'other/fixed.png'):
            (self.project / name).write_bytes(b'fixture')
        view = schema.document_settings(self.configure())
        dependencies = latex.manuscript_dependencies(self.project, view)
        for name in ('figures/plot.png', 'other/plot.pdf', 'figures/fixed.png', 'other/fixed.png'):
            self.assertIn(name, dependencies)

    @unittest.skipUnless(TEX, 'real latexmk and pdflatex required')
    def test_f3_preferred_graphic_invalidates_and_rebuilds_the_pdf(self):
        (self.project / 'figures').mkdir()
        (self.project / 'figures/plot.png').write_bytes(red_png())
        view = self.native('\\documentclass{article}\n\\usepackage{graphicx}\n\\graphicspath{{figures/}}\n'
                           '\\begin{document}\\includegraphics[width=1cm]{plot}\\end{document}\n')
        self.command('build')
        stem = latex.output_paths(self.project, view)[2]
        before = Path(str(stem) + '.pdf').read_bytes()
        self.run_command('pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-jobname=plot',
                         '-output-directory=figures', SOURCE_4_8_1.replace('Fixture.', 'New preferred figure.').replace('\n', ' '))
        self.assertEqual(latex.receipt_state(self.project, view), 'stale')
        self.command('build')
        self.assertEqual(latex.receipt_state(self.project, view), 'current')
        self.assertIn('figures/plot.pdf', Path(str(stem) + '.fls').read_text())
        self.assertNotEqual(before, Path(str(stem) + '.pdf').read_bytes())


class SimplificationTests(unittest.TestCase):
    """Origin: tests/test_simplification.py."""

    def setUp(self):
        isolate_environment(self)
        self.directory = tempfile.TemporaryDirectory(prefix="workbench-3-")
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name).resolve()

    def config(self):
        return {"schema_version": 3, "modules": {"latex": {
            "default_document": "paper", "documents": {"paper": {
                "root": "./main.tex", "lint": {"enabled": False}}}}}}

    def test_old_project_schemas_refuse_installation_without_writes(self):
        for version in (1, 2):
            config = {"schema_version": version, "modules": {}}
            (self.project / core.CONFIG).write_text(json.dumps(config))
            before = {p.name: p.read_bytes() for p in self.project.iterdir()}
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(bootstrap.main(["init", str(self.project)]), 2)
            self.assertEqual(before, {p.name: p.read_bytes() for p in self.project.iterdir()})

    def test_project_commands_reject_document_selector_without_skipping_checks(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n")
        (self.project / core.CONFIG).write_text(json.dumps(self.config()))
        for action in ("plan", "validate", "modules", "doctor", "documents"):
            with self.subTest(action=action), patch.object(sys, "argv", ["workbench", action, "--document", "paper", "--project", str(self.project)]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runtime.main(), 1)

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "real TeX compiler required")
    def test_canonical_receipt_inputs_survive_recorder_removal(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\n\\def\\partname{hidden}\n\\input{\\partname}\n\\end{document}\n")
        (self.project / "hidden.tex").write_text("A hidden source.\n")
        config = self.config()
        schema.validate_config(self.project, config)
        with contextlib.redirect_stdout(io.StringIO()):
            latex.build(self.project, schema.document_settings(config))
        self.assertEqual(documents.report(self.project, config)[0]["state"], "current")
        stem = latex.output_paths(self.project, schema.document_settings(config))[2]
        Path(str(stem) + ".fls").unlink()
        self.assertIn("hidden.tex", documents.dependency_index(self.project, config)["paper"])
        self.assertEqual(documents.report(self.project, config)[0]["state"], "current")
        (self.project / "hidden.tex").write_text("Changed hidden source.\n")
        self.assertEqual(documents.report(self.project, config)[0]["state"], "stale")

    def test_malformed_receipt_dependencies_are_stale_without_breaking_inspection(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n")
        config = self.config()
        config["modules"]["latex"]["documents"]["paper"]["root"] = "main.tex"
        path = self.project / latex.receipt_path(schema.document_settings(config))
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": latex.RECEIPT_SCHEMA, "status": "verified",
            "identity": latex.build_identity(self.project, config), "inputs": {"../outside": None}, "outputs": {}}))
        self.assertEqual(documents.report(self.project, config)[0]["state"], "stale")
        documents.dependency_index(self.project, config)


class WorkbenchTests(unittest.TestCase):
    """Origin: tests/test_workbench.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="latex-ai-unit-")
        self.project = Path(self.temp.name).resolve()
        (self.project / "paper.tex").write_text(TEX_workbench)

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return boot.main([*args, str(self.project)])

    def init(self):
        self.assertEqual(self.cli("init"), 0)

    def selection(self, *names):
        return rt.validation_plan(self.project, rt.load_config(self.project), list(names))

    def test_recursion_guard_blocks_same_project_but_allows_synthetic_children(self):
        self.init()
        plan = self.selection("paper.tex")
        with patch.dict(rt.os.environ, {"LATEX_AI_VALIDATE_ACTIVE": str(self.project)}), self.assertRaisesRegex(rt.WorkbenchError, "Recursive"), contextlib.redirect_stdout(io.StringIO()):
            rt.validate_changes(self.project, plan)
        with patch.dict(rt.os.environ, {"LATEX_AI_VALIDATE_ACTIVE": str(self.project.parent / "different-project")}), patch.object(rt, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            rt.validate_changes(self.project, plan)
        self.assertEqual(run.call_count, 1)


class ReadTheLog(ProjectCase):
    """Workbench 4.10.1, after the readers of the manual used it: a failure whose details are in the compiler's log says where the log is,
    and a message that TeX wrapped in its log is given whole.

    Origin: workbench 4.10.1 (the reader findings recorded in verification-4.9.1.md).
    """

    def fixture(self, log, code=0):
        """A project whose stand-in compiler writes this log and exits with this code."""
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}x\\end{document}\n")
        self.configure()
        self.install("init", "--skip-editor")
        self.compiler(log, code)

    def compiler(self, log, code=0):
        (self.project / "builder.py").write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
            "(out / 'main.pdf').write_bytes(b'%PDF-fixture')\n"
            f"(out / 'main.log').write_text({log!r})\n"
            "(out / 'main.fls').write_text('PWD ' + str(Path.cwd()) + '\\nINPUT main.tex\\n')\n"
            f"sys.exit({code})\n")

    def tex_failing(self, log):
        """A project built by the default `latexmk`, which here is a stand-in that writes this log and fails."""
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}x\\end{document}\n")
        self.configure({"paper": {"root": "main.tex", "lint": {"enabled": False}, "output_dir": "outputs"}})
        self.install("init", "--skip-editor")
        shim = self.root / "bin"
        shim.mkdir()
        (shim / "latexmk").write_text(
            f"#!{sys.executable}\n"
            "import pathlib, sys\n"
            "args = sys.argv[1:]\n"
            "out = pathlib.Path(next(a.split('=', 1)[1] for a in args if a.startswith('-outdir=')))\n"
            "out.mkdir(parents=True, exist_ok=True)\n"
            f"(out / (pathlib.Path(args[-1]).stem + '.log')).write_text({log!r})\n"
            "sys.exit(1)\n")
        (shim / "latexmk").chmod(0o755)
        self.env["PATH"] = f"{shim}:{self.env['PATH']}"

    def test_an_undefined_reference_says_where_the_log_is_and_what_to_run(self):
        self.fixture("LaTeX Warning: Reference `fig:one' on page 1 undefined on input line 3.\nLaTeX Warning: There were undefined references.\n")
        result = self.command("build", expected=1)
        self.assertIn("Unresolved manuscript integrity errors", result.stderr)
        hint = next(line for line in result.stderr.splitlines() if line.startswith("Hint:"))
        self.assertIn("outputs/main.log", hint)
        self.assertIn("document-check", hint)

    def test_a_message_that_tex_wrapped_at_79_characters_is_given_whole(self):
        message = "./main.tex:8: LaTeX Error: \\begin{itemize} on input line 4 ended by \\end{document}."
        first, rest = message[:79], message[79:]
        self.assertEqual(len(first), 79)
        self.tex_failing(first + "\n" + rest + "\nl.8 \\end{document}\n")
        result = self.command("build", expected=1)
        self.assertIn(message, result.stderr)
        self.assertNotIn("l.8", next(line for line in result.stderr.splitlines() if line.startswith("ERROR")))

    def test_a_short_message_is_not_joined_with_the_line_after_it(self):
        self.tex_failing("! Undefined control sequence.\nl.3 \\undefinedfixturemacro\n")
        result = self.command("build", expected=1)
        error = next(line for line in result.stderr.splitlines() if line.startswith("ERROR"))
        self.assertIn("Undefined control sequence.", error)
        self.assertNotIn("l.3", error)
        self.assertIn("outputs/main.log", result.stderr)


if __name__ == "__main__":
    unittest.main()
