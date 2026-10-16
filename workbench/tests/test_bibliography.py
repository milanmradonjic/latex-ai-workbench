"""Tests of the bibliography checks: parsing, duplicate keys, the export and the backend logs.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 6 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_blind_repairs.py:
Installed-workflow regressions from the ten blind reviewers (current schema only).

test_document_lifecycle.py:
Receipt lifecycle across upgrades, failure, interruption and document state reporting.

test_documents.py:
Installed workflows for named TeX documents and mixed note organization.

test_modules.py:
(no docstring)

test_scope_4_8_1.py:
4.8.1: independent-audit regressions, output safety, source integrity and bounded scans.

Every project is disposable; overwrite probes use only synthetic sentinel files.

test_workbench.py:
(no docstring)
"""

import argparse
import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap
import bootstrap as boot
import core
import runtime
import runtime as rt
import schema
from test_support import ProjectCase, fixture_env, isolate_environment, prepare_config


SOURCE = "\\documentclass{article}\n\\begin{document}A note.\\end{document}\n"


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


SOURCE_4_8_1 = '\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n'


TEX = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


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
        text = SOURCE if not hidden else SOURCE.replace("A note.", "\\def\\partname{hidden}\\input{\\partname}")
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

    def test_bibliography_success_names_actual_documents_and_files(self):
        config = self.fixture()
        (self.project / "note.tex").write_text(SOURCE)
        (self.project / "paper.bib").write_text("@misc{paper, title={Paper}}\n")
        (self.project / "note.bib").write_text("@misc{note, title={Note}}\n")
        config["documents"]["paper"]["bibliography_files"] = ["paper.bib"]
        config["documents"]["note"] = {"root": "note.tex", "bibliography_files": ["note.bib"], "lint": {"enabled": False}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        result = self.command(sys.executable, ".latex-ai/workbench.py", "bib-check", "--document", "note", "--json")
        data = json.loads(result.stdout)
        self.assertEqual(data["result"]["bibliographies"], [{"document": "note", "files": ["note.bib"]}])
        result = self.command("make", "bib-check")
        self.assertIn("paper: paper.bib", result.stdout)
        self.assertIn("note: note.bib", result.stdout)


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

    def make(self, *arguments, expected=0):
        result = subprocess.run(["make", *arguments], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def named(self, **documents):
        for root in ("main.tex", "notes/main.tex"):
            path = self.project / root
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SOURCE)
        config = {'schema_version': 4, 'default_document': 'paper', 'defaults': {'lint': {'enabled': False}}, 'documents': {'paper': {'root': 'main.tex', 'build_command': [sys.executable, 'compile.py', 'main.tex', '.latex-ai/artifacts/documents/paper/build']}, 'note': {'root': 'notes/main.tex', 'build_command': [sys.executable, 'compile.py', 'notes/main.tex', '.latex-ai/artifacts/documents/note/build']}}}
        for name, values in documents.items():
            config["documents"][name].update(values)
        (self.project / core.CONFIG).write_text(json.dumps(config))
        return config

    # F5: bibliography readiness covers each document's own declarations.
    def test_bibliography_check_covers_every_documents_own_files(self):
        config = self.named(note={"bibliography_files": ["notes/note.bib"]})
        (self.project / "notes/note.bib").write_text("@misc{dup, title={A}, year={2000}}\n@misc{dup, title={B}, year={2001}}\n")
        self.install("init", expected=2)  # preflight catches the malformed secondary bibliography
        (self.project / "notes/note.bib").write_text("@misc{dup, title={A}}\n")
        self.install("init")
        (self.project / "notes/note.bib").write_text("@misc{dup, title={A}}\n@misc{dup, title={B}}\n")
        self.assertIn("Duplicate bibliography key", self.command("bib-check", expected=1).stderr)
        self.assertIn("Duplicate bibliography key", self.make("bib-check", "DOC=note", expected=2).stderr)
        self.make("bib-check", "DOC=paper")
        self.assertTrue(runtime.validation_plan(self.project, config, ["notes/note.bib"])["level"] == "full")


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

    def command(self, *arguments, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"),
                                 *arguments], cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_validation_checks_shared_bibliography(self):
        config = {'schema_version': 4, 'default_document': 'paper', 'documents': {'paper': {'root': 'main.tex', 'lint': {'enabled': False}}}, 'bibliography': {'files': ['refs.bib']}}
        (self.project / 'main.tex').write_text(TEX)
        (self.project / core.CONFIG).write_text(json.dumps(config))
        (self.project / "refs.bib").write_text("@misc{fixture, title={Synthetic fixture}}\n")
        self.install("init")
        (self.project / "refs.bib").write_text("@misc{fixture, title={One}}\n@misc{fixture, title={Two}}\n")
        self.assertIn("Duplicate bibliography key", self.command("validate", expected=1).stderr)


class ModuleTests(unittest.TestCase):
    """Origin: tests/test_modules.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-modules-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, **choices):
        prepare_config(self.project, **choices)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return boot.main([*args, str(self.project)])

    def command(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), *args],
                                cwd=self.project, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result


class AuditRepairs(ProjectCase):
    """Origin: tests/test_scope_4_8_1.py, workbench 4.8.1."""

    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE_4_8_1)

    def test_bibliography_scanning_accepts_whitespace_with_explicit_declarations(self):
        (self.project / 'refs.bib').write_text('@misc{fixture,title={Synthetic fixture}}\n')
        config = self.configure(documents_={"paper": {"root": "main.tex", "backend": "bibtex"}})
        config["bibliography"] = {"files": ["refs.bib"]}
        for whitespace in (' ', '\n', '\t'):
            with self.subTest(whitespace=repr(whitespace)):
                (self.project / 'main.tex').write_text(SOURCE_4_8_1.replace('Fixture.', '\\bibliography' + whitespace + '{refs}'))
                view = schema.document_settings(schema.validate_config(self.project, config))
                self.assertEqual(view.bibliography['backend'], 'bibtex')
                self.assertEqual([p.name for p in rt.bibliography_check(self.project, view)], ['refs.bib'])


class WorkbenchTests(unittest.TestCase):
    """Origin: tests/test_workbench.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="latex-ai-unit-")
        self.project = Path(self.temp.name).resolve()
        (self.project / "paper.tex").write_text(TEX)
        prepare_config(self.project, root="paper.tex", output_dir=".")

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, **choices):
        prepare_config(self.project, **{"root": "paper.tex", "output_dir": ".", **choices})
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return boot.main([*args, str(self.project)])

    def init(self):
        self.assertEqual(self.cli("init"), 0)

    def test_bib_nested_values_and_string_macros(self):
        bib = '@string{journal = "A"}\n@article(key, title={A {nested} "quote" (test) 50%}, journal=journal # " B")\n'
        self.assertEqual(rt.bib_keys(bib, "test.bib"), ["key"])

    def test_bib_truncation_merge_conflict_and_nul(self):
        for bib in ['@article{k,title={truncated}', '<<<<<<< mine\n@book{k,title={T}}', '\0@book{k,title={T}}']:
            with self.subTest(bib=bib), self.assertRaises(rt.WorkbenchError):
                rt.bib_keys(bib, "test.bib")

    def test_duplicate_keys_across_bibliographies(self):
        self.init()
        config = rt.load_config(self.project)
        config.setdefault("bibliography", {"files": [], "export": None})["files"] = ["one.bib", "two.bib"]
        for name in config.setdefault("bibliography", {"files": [], "export": None})["files"]:
            (self.project / name).write_text('@book{same, title={T}}')
        with self.assertRaisesRegex(rt.WorkbenchError, "Duplicate"):
            rt.bibliography_check(self.project, schema.document_settings(config))

    def test_case_variant_duplicate_keys_follow_the_backend(self):
        self.init()
        config = rt.load_config(self.project)
        config.setdefault("bibliography", {"files": [], "export": None})["files"] = ["one.bib", "two.bib"]
        (self.project / "one.bib").write_text('@book{Smith2020, title={T}}')
        (self.project / "two.bib").write_text('@book{smith2020, title={U}}')
        config["documents"]["manuscript"]["backend"] = "bibtex"
        with self.assertRaisesRegex(rt.WorkbenchError, r"Duplicate bibliography key 'smith2020' \(same key as 'Smith2020'; BibTeX ignores case\)"):
            rt.bibliography_check(self.project, schema.document_settings(config))
        config["documents"]["manuscript"]["backend"] = "none"  # unprocessed exports keep case-variant keys distinct
        self.assertEqual(len(rt.bibliography_check(self.project, schema.document_settings(config))), 2)
        (self.project / "two.bib").write_text('@book{Smith2020, title={U}}')  # exact duplicates stay errors everywhere
        for backend in ("bibtex", "none"):
            config["documents"]["manuscript"]["backend"] = backend
            with self.subTest(backend=backend, exact=True), self.assertRaisesRegex(rt.WorkbenchError, "Duplicate bibliography key 'Smith2020': "):
                rt.bibliography_check(self.project, schema.document_settings(config))

    def test_optional_then_required_export(self):
        self.init()
        config = rt.load_config(self.project)
        config.setdefault("bibliography", {"files": [], "export": None})["export"] = {"path": "zotero.bib", "required": False, "format": "bibtex"}
        self.assertEqual(rt.bibliography_check(self.project, schema.document_settings(config)), {})
        config.setdefault("bibliography", {"files": [], "export": None})["export"]["required"] = True
        with self.assertRaisesRegex(rt.WorkbenchError, "Missing"):
            rt.bibliography_check(self.project, schema.document_settings(config))
        (self.project / "zotero.bib").write_text("% Empty export\n")
        with self.assertRaisesRegex(rt.WorkbenchError, "no entries"):
            rt.bibliography_check(self.project, schema.document_settings(config))

    def test_log_failures_and_advisory_warnings(self):
        self.init()
        config = rt.load_config(self.project)
        config["documents"]["manuscript"]["output_dir"] = "."
        (self.project / "paper.pdf").write_bytes(b"%PDF-1.5\n")
        for warning in ["LaTeX Warning: There were undefined references.", "LaTeX Warning: There were undefined citations.",
                        "LaTeX Warning: Label `same' multiply defined.", "LaTeX Warning: Please (re)run BibTeX on the file(s)."]:
            (self.project / "paper.log").write_text(warning)
            with self.subTest(warning=warning), self.assertRaises(rt.WorkbenchError):
                rt.verify(self.project, schema.document_settings(config), check_receipt=False)
        (self.project / "paper.log").write_text("Overfull \\hbox (1pt too wide)\n")
        with contextlib.redirect_stdout(io.StringIO()):
            rt.verify(self.project, schema.document_settings(config), check_receipt=False)

    def test_stale_backend_log_ignored_when_bibliography_disabled(self):
        self.init()
        config = rt.load_config(self.project)
        config["documents"]["manuscript"]["output_dir"] = "."
        (self.project / "paper.pdf").write_bytes(b"%PDF-1.5\n")
        (self.project / "paper.log").write_text("Output written on paper.pdf.\n")
        (self.project / "paper.blg").write_text("I couldn't open database file obsolete.bib\n")
        with contextlib.redirect_stdout(io.StringIO()):
            rt.verify(self.project, schema.document_settings(config), check_receipt=False)
        config["documents"]["manuscript"]["backend"] = "bibtex"
        with self.assertRaisesRegex(rt.WorkbenchError, "integrity"):
            rt.verify(self.project, schema.document_settings(config), check_receipt=False)


if __name__ == "__main__":
    unittest.main()
