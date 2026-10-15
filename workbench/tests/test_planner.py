"""Tests of the validation plan: which checks a change needs, change discovery, the lightweight file checks and what routes to the manuscript build.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 10 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_audit3_repairs.py:
Independent audit 3 failures, exercised through installed workflows.

Compiler fixtures disable lint explicitly. Process/move tests isolate infrastructure;
the source-content and stdin tests use genuine TeX tools.

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

test_scope_4_8_1.py:
4.8.1: independent-audit regressions, output safety, source integrity and bounded scans.

Every project is disposable; overwrite probes use only synthetic sentinel files.

test_validation_ignore.py:
`validation.ignore`: paths the owner declares are never routed to the manuscript build.

The patterns are validated like `validation.manuscript_inputs`. They never exempt what the build reads, build or
configuration files, or the agent's policy files: those keep their routing whatever is declared.

test_workbench.py:
(no docstring)
"""

import ast
import contextlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap
import bootstrap as boot
import core
import guide
import latex
import runtime
import runtime as rt
import schema
from test_support import ProjectCase, fixture_env, isolate_environment, prepare_config


SOURCE = "\\documentclass{article}\n\\begin{document}Audit fixture.\\end{document}\n"


TEX = bool(shutil.which('latexmk') and shutil.which('pdflatex'))


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


SOURCE_document_lifecycle = "\\documentclass{article}\n\\begin{document}A note.\\end{document}\n"


def set_literals(path):
    """Every set display in a module, as the set of its string members."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [{node.value for node in display.elts if isinstance(node, ast.Constant) and isinstance(node.value, str)}
            for display in ast.walk(tree) if isinstance(display, ast.Set)]


REASON = {"M": "manuscript input or potential figure", "O": "ordinary documentation/data/code: file checks; use task-specific tests when relevant",
          "U": "unclassified input: conservative manuscript validation"}


# How 3.6.0 routed each file name, recorded from its code before this change: M manuscript input or potential figure,
# O ordinary documentation/data/code, U unclassified (conservative manuscript validation).
ROUTING = dict(
    zip(".tex .bib .sty .cls .bst .bbx .cbx .lbx .tikz .png .jpg .jpeg .pdf .svg .eps .ps .webp .tif .tiff .csv .tsv .PNG .CSV".split(), "M" * 24),
    **dict(zip(".md .markdown .txt .rst .adoc .json .yaml .yml .toml .py .MD".split(), "O" * 11)),
    **{".rules": "U", ".xyz": "U", ".log": "U", ".ipynb": "U"})


SOURCE_4_8_1 = '\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n'


IGNORED = "ignored by validation.ignore: file checks only"


LEFT_ALONE = ("docs/figure.png", "docs/table.csv", "docs/blob.xyz", "docs/deeper/still/plot.pdf")


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

    def install(self, *args, expected=0, **choices):
        prepare_config(self.project, **choices)
        return self.run_command(sys.executable, '-B', str(bootstrap.PACKAGE / 'latex-ai-init'),
                                *args, str(self.project), expected=expected)

    def command(self, *args, **kwargs):
        return self.run_command(sys.executable, '-B', '.latex-ai/workbench.py', *args, **kwargs)

    def named(self, makefile=None):
        for name in ('main.tex', 'note.tex'):
            (self.project / name).write_text(SOURCE)
        config = {'schema_version': 4, 'default_document': 'paper', 'defaults': {'lint': {'enabled': False}}, 'documents': {'paper': {'root': 'main.tex'}, 'note': {'root': 'note.tex'}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install('init', editor=False)
        if makefile is not None:  # the project's own Make text goes after what init wrote
            with (self.project / 'Makefile').open('a') as stream:
                stream.write('\n' + makefile)
        return config

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

    @unittest.skipUnless(TEX, 'real latexmk/pdflatex required')
    def test_a1_observed_makefile_source_is_not_policy_only(self):
        self.named('# First displayed line\n')
        (self.project / 'main.tex').write_text(
            '\\documentclass{article}\n\\usepackage{verbatim}\n\\begin{document}\\verbatiminput{Makefile}\\end{document}\n')
        self.command('document-check', '--document', 'paper')
        with (self.project / 'Makefile').open('a') as stream:
            stream.write('# Added displayed manuscript content\n')
        self.command('verify', '--document', 'paper', expected=1)
        self.command('artifact', '--document', 'paper', expected=1)

    def test_a4_project_check_syntax_is_preserved_by_selected_validation(self):
        cases = {'blank':'check:\n\n\ttouch project-check-ran\n',
                 'comment':'check:\n# comment between rule and recipe\n\ttouch project-check-ran\n',
                 'conditional':'check:\nifeq (1,1)\n\ttouch project-check-ran\nendif\n',
                 'eval':'LOCAL_CHECK := $(eval check: local-test)\nlocal-test:\n\ttouch project-check-ran\n',
                 'variable':'CHECK_NAME := check\n$(CHECK_NAME): local-test\nlocal-test:\n\ttouch project-check-ran\n',
                 'prefix':'check: latex-ai-local-test\nlatex-ai-local-test:\n\ttouch project-check-ran\n'}
        for name, makefile in cases.items():
            with self.subTest(name=name):
                old = self.project
                self.project = old / name
                self.project.mkdir()
                try:
                    self.synthetic(makefile)
                    self.command('validate', '--files', 'note.tex')
                    self.assertTrue((self.project / 'project-check-ran').is_file())
                finally:
                    self.project = old

    def test_review_missing_optional_make_include_selects_project_check(self):
        self.synthetic('-include generated.mk\ngenerated.mk:\n'
            '\t@echo "check: generated-check" > $@\n'
            '\t@echo "generated-check: ; touch generated-check-ran" >> $@\n')
        plan=json.loads(self.command('plan','--files','note.tex','--json').stdout)
        self.assertTrue(plan['project_check'],plan)
        self.command('validate','--files','note.tex')
        self.assertTrue((self.project/'generated-check-ran').is_file())


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

    def named(self, **documents):
        for root in ("main.tex", "notes/main.tex"):
            path = self.project / root
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SOURCE_document_lifecycle)
        config = {'schema_version': 4, 'default_document': 'paper', 'defaults': {'lint': {'enabled': False}}, 'documents': {'paper': {'root': 'main.tex', 'build_command': [sys.executable, 'compile.py', 'main.tex', '.latex-ai/artifacts/documents/paper/build']}, 'note': {'root': 'notes/main.tex', 'build_command': [sys.executable, 'compile.py', 'notes/main.tex', '.latex-ai/artifacts/documents/note/build']}}}
        for name, values in documents.items():
            config["documents"][name].update(values)
        (self.project / core.CONFIG).write_text(json.dumps(config))
        return config

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

    def test_plan_lists_selected_documents_for_people(self):
        self.named()
        self.install("init")
        output = self.command("plan", "--files", "notes/main.tex").stdout
        self.assertIn("Documents: note", output)


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
        config = {'schema_version': 4, 'default_document': 'paper', 'defaults': {'lint': {'enabled': False}}, 'documents': {'paper': {'root': 'main.tex', 'build_command': [sys.executable, 'compile.py', 'main.tex', '.latex-ai/artifacts/documents/paper/build']}, 'note': {'root': 'notes/main.tex', 'build_command': [sys.executable, 'compile.py', 'notes/main.tex', '.latex-ai/artifacts/documents/note/build']}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        return config

    def test_failed_full_check_reports_document_and_checks_remaining_target(self):
        self.configuration()
        self.install("init")
        (self.project / "main.tex").write_text("BROKEN\n")
        result = self.command("check", "--json", expected=1)
        report = json.loads(result.stdout)
        self.assertEqual([row["status"] for row in report["result"]["documents"]], ["failed", "passed"])
        self.assertIn("paper", report["stderr"])

    def test_note_change_selects_only_its_document(self):
        config = self.configuration()
        plan = runtime.validation_plan(self.project, config, ["notes/main.tex"])
        self.assertEqual(plan["documents"], ["note"])
        self.assertTrue(plan["manuscript"])
        self.assertEqual(runtime.validation_plan(self.project, config, ["notes/readme.md"])["documents"], [])

    def test_shared_and_deleted_fragments_select_all_consumers(self):
        config = self.configuration()
        (self.project / "shared.tex").write_text("Shared definitions\n")
        for root, include in (("main.tex", "shared"), ("notes/main.tex", "../shared")):
            path = self.project / root
            path.write_text("\\input{" + include + "}\n" + path.read_text())
        self.assertEqual(runtime.validation_plan(self.project, config, ["shared.tex"])["documents"], ["note", "paper"])
        (self.project / "shared.tex").unlink()
        self.assertEqual(runtime.validation_plan(self.project, config, ["shared.tex"])["documents"], ["note", "paper"])

    def test_hard_link_alias_selects_the_declared_document_input(self):
        config = self.configuration()
        (self.project / "resource.md").write_text("Resource\n")
        os.link(self.project / "resource.md", self.project / "alias.md")
        config["documents"]["paper"]["inputs"] = ["resource.md"]
        self.assertEqual(runtime.validation_plan(self.project, config, ["alias.md"])["documents"], ["paper"])

    def test_uncertain_tex_and_build_policy_select_all_documents(self):
        config = self.configuration()
        for path in ("unclassified.tex", "Makefile", core.CONFIG):
            with self.subTest(path=path):
                self.assertEqual(runtime.validation_plan(self.project, config, [path])["documents"], ["note", "paper"])

    def test_selected_validation_does_not_build_unrelated_paper(self):
        self.configuration()
        self.install("init")
        (self.project / "main.tex").write_text("BROKEN\n")
        self.command("validate", "--files", "notes/main.tex")
        self.assertFalse((self.project / ".latex-ai/artifacts/documents/paper/build-receipt.json").exists())
        self.assertTrue((self.project / ".latex-ai/artifacts/documents/note/build-receipt.json").exists())

    def test_deleted_explicit_input_selects_target_before_first_build(self):
        config = self.configuration()
        config["documents"]["note"]["inputs"] = ["notes/context.md"]
        self.assertEqual(runtime.validation_plan(self.project, config, ["notes/context.md"])["documents"], ["note"])
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install("init")
        result = self.command("build", "--document", "note", expected=1)
        self.assertIn("Missing declared document input", result.stderr)

    def test_selected_validation_reports_all_failing_documents(self):
        self.configuration()
        self.install("init")
        for path in ("main.tex", "notes/main.tex"):
            (self.project / path).write_text("BROKEN\n")
        report = json.loads(self.command("validate", "--files", "unknown.tex", "--json", expected=1).stdout)
        self.assertEqual({row["id"] for row in report["result"]["documents"]}, {"paper", "note"})
        self.assertTrue(all(row["status"] == "failed" for row in report["result"]["documents"]))


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

    def snapshot(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}

    def command(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), *args],
                                cwd=self.project, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_saving_a_text_file_validates_without_a_compiler(self):
        self.assertEqual(self.cli('init'), 0)
        notes = self.project / "notes/session.md"
        notes.parent.mkdir()
        notes.write_text("A question about physics.\n")
        self.command("validate", "--files", "notes/session.md")
        before = self.snapshot()
        self.assertEqual(self.cli("diff"), 0)  # read-only, and the runtime is this release's
        self.assertEqual(before, self.snapshot())

    def make_result(self, *arguments):
        # Run as the user would in a fresh shell: not as a child of the package's own `make test` (which sets
        # MAKEFLAGS and makes Make announce directories), and without the caller's TASK or the comparison
        # revision hosted CI exports for the outer repository (LATEX_AI_BASE names a commit these fixtures lack).
        env = {name: value for name, value in os.environ.items() if name not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "TASK", "LATEX_AI_BASE"}}
        return subprocess.run(["make", "-s", "--no-print-directory", *arguments], cwd=self.project, capture_output=True, text=True, env=env)

    def make_output(self, *arguments, expected=0):
        done = self.make_result(*arguments)
        self.assertEqual(done.returncode, expected, done.stdout + done.stderr)
        return done.stdout

    def test_validation_without_git_history_says_so_in_plain_words(self):
        self.assertEqual(self.cli('init'), 0)
        text = self.make_output("validation-plan")
        self.assertIn("full validation selected", text)
        self.assertIn("not a Git repository", text)
        self.assertNotIn("fatal:", text)
        self.assertRegex((boot.PACKAGE / "docs/quickstart.md").read_text(), r"Git repository")
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
            text = self.make_output("validation-plan")
            self.assertIn("no commit", text)
            self.assertNotIn("fatal:", text)


class GeneratedTrees(unittest.TestCase):
    """Origin: tests/test_one_table_each.py."""

    def test_one_constant_holds_the_folders_no_check_treats_as_sources(self):
        self.assertEqual(core.GENERATED_TREES, {".git", ".latex-ai", ".venv", "__pycache__", "node_modules", "site-packages", "dist-packages"})


    def test_no_module_but_core_lists_them_again(self):
        for path in sorted(PACKAGE.glob("*.py")):
            if path.name == "core.py":
                continue
            for members in set_literals(path):
                with self.subTest(module=path.name, members=sorted(members)):
                    self.assertFalse({".git", ".venv"} <= members or {".latex-ai", "node_modules"} <= members)

    def test_a_walk_without_git_skips_them(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            for folder in ("notes", *sorted(core.GENERATED_TREES)):
                (project / folder).mkdir()
                (project / folder / "page.md").write_text("# Page\n")
            with patch.object(runtime, "git_names", side_effect=OSError):
                self.assertEqual(runtime.project_files(project), ["notes/page.md"])


class PlannerSuffixes(ProjectCase):
    """Origin: tests/test_one_table_each.py."""

    def test_every_suffix_is_routed_as_it_was(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\\begin{document}x\\end{document}\n")
        self.configure()
        config = runtime.load_config(self.project)
        for suffix, route in ROUTING.items():
            name = "data/file" + suffix
            with self.subTest(name=name):
                self.assertEqual(runtime.validation_plan(self.project, config, [name])["reasons"][name], REASON[route])
        for name, route in (("data/.gitignore", "O"), ("data/LICENSE", "O"), ("data/noext", "U")):
            with self.subTest(name=name):
                self.assertEqual(runtime.validation_plan(self.project, config, [name])["reasons"][name], REASON[route])

    def test_the_tables_name_each_suffix_once(self):
        self.assertEqual(runtime.DATA_SUFFIXES, {".csv", ".tsv"})
        self.assertTrue(runtime.DATA_SUFFIXES <= runtime.MANUSCRIPT_SUFFIXES)
        self.assertFalse(runtime.DATA_SUFFIXES & runtime.DOCUMENT_SUFFIXES)
        self.assertEqual(runtime.CHECKED_SUFFIXES,
                         {".md", ".markdown", ".txt", ".rst", ".adoc", ".json", ".yaml", ".yml", ".toml", ".py", ".rules", ".tex", ".bib", ".csv", ".tsv"})
        literals = [members for members in set_literals(PACKAGE / "runtime.py") if members & {".csv", ".tsv"}]
        self.assertEqual(literals, [{".csv", ".tsv"}], "a suffix list in runtime.py repeats the data suffixes")


class MarkdownLinks(unittest.TestCase):
    """Origin: tests/test_one_table_each.py."""

    def check(self, files, name, text):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            for file in files:
                (project / file).parent.mkdir(parents=True, exist_ok=True)
                (project / file).write_text("x\n")
            (project / name).parent.mkdir(parents=True, exist_ok=True)
            return runtime.broken_markdown_link(project, project / name, text)

    def test_a_missing_local_target_is_reported_as_written(self):
        self.assertEqual(self.check([], "notes.md", "See [it](gone.md) and ![fig](img/gone.png)."), "gone.md")

    def test_existing_and_non_local_targets_are_fine(self):
        text = ("[a](here.md) [b](here.md#part) [c](here.md?x=1) [d](<here.md>) [e](sub/there%20now.md) [f](https://example.org/x) "
                "[g](mailto:a@b.c) [h](#anchor) [i](/absolute) [j](here.md \"title\") [k](../outside.md)")
        self.assertIsNone(self.check(["here.md", "sub/there now.md"], "notes.md", text))

    def test_code_fences_are_not_links(self):
        self.assertIsNone(self.check([], "notes.md", "```\n[x](gone.md)\n```\n~~~\n[y](gone2.md)\n~~~\n"))

    def test_the_target_is_resolved_beside_the_file(self):
        self.assertIsNone(self.check(["docs/here.md"], "docs/notes.md", "[a](here.md)"))
        self.assertEqual(self.check(["docs/here.md"], "notes.md", "[a](here.md)"), "here.md")


class Repairs(ProjectCase):

    # --- build-produced inputs -------------------------------------------------------------------------

    """Origin: tests/test_repairs_3_0_1.py, workbench 3.0.1."""

    def linked_project(self):
        outside = self.root / "shared-figures"
        outside.mkdir()
        (outside / "plot.txt").write_text("one")
        (self.project / "shared").symlink_to(outside, target_is_directory=True)
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\\includegraphics{shared/plot.pdf}\\end{document}\n")
        self.builder(inputs=("main.tex", "shared/plot.txt", "/outside/system.sty"))
        self.configure()
        self.install('init', editor=False)
        return outside

    def test_planning_accepts_a_changed_link_that_leaves_the_project(self):
        self.linked_project()
        self.command("build")
        plan = runtime.validation_plan(self.project, schema.load_config(self.project), ["shared/plot.txt"])
        self.assertEqual(plan["documents"], ["paper"])

    def test_every_installed_runtime_file_is_a_full_validation_trigger(self):
        everything = self.configure()
        shipped = set(core.runtime_sources(everything)) | {"bootstrap.py", "latex-ai-init"}
        self.assertLessEqual(shipped, set(core.RUNTIME_FILES))
        self.configure()
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.install('init', editor=False)
        (self.project / "workbench").mkdir()
        (self.project / "workbench/Makefile").write_text("test:\n\ttrue\n")
        (self.project / "workbench/latex-ai-init").write_text("#!/usr/bin/env python3\n")
        config = schema.load_config(self.project)
        for name in sorted(core.RUNTIME_FILES):
            with self.subTest(name):
                plan = runtime.validation_plan(self.project, config, [f"workbench/{name}"])
                self.assertTrue(plan["manuscript"] and plan["unit"] and plan["portability"], plan["reasons"])

    def test_plan_says_when_a_document_selector_is_ignored(self):
        self.configure()
        (self.project / "main.tex").write_text(SOURCE)
        self.builder()
        self.install('init', editor=False)
        result = self.command("plan", "--files", "main.tex", env=fixture_env(DOC="paper"))
        self.assertIn("DOC=paper", result.stdout)
        self.assertIn("ignored", result.stdout)
        quiet = self.command("plan", "--files", "main.tex")
        self.assertNotIn("DOC", quiet.stdout)


class Repairs_3_0_2(ProjectCase):

    # --- F1: one lock per project, shared by everyone who works in it ----------------------------------

    """Origin: tests/test_repairs_3_0_2.py, workbench 3.0.2."""

    def test_latin1_sources_install_plan_and_pass_file_checks(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\usepackage[latin1]{inputenc}\n"
                                               "\\begin{document}\n\\input{chap}\n\\end{document}\n")
        (self.project / "chap.tex").write_bytes("Caf\u00e9 na\u00efve\n".encode("latin-1"))
        (self.project / "other.tex").write_bytes("\u00e9t\u00e9\n".encode("latin-1"))
        self.install('init', editor=False)
        plan = json.loads(self.command("plan", "--files", "chap.tex", "--json").stdout)
        self.assertEqual(plan["documents"], ["manuscript"])
        self.command("validate", "--files-only", "--files", "chap.tex")


class AuditRepairs(ProjectCase):
    """Origin: tests/test_scope_4_8_1.py, workbench 4.8.1."""

    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE_4_8_1)

    def native(self, source=SOURCE_4_8_1):
        (self.project / 'main.tex').write_text(source)
        self.install('init', lint=False, editor=False)
        return schema.document_settings(schema.load_config(self.project))

    def test_f4_recipeprefix_selects_the_projects_own_check(self):
        # This fixture uses a GNU Make 3.82 feature; macOS ships 3.81. Prefer gmake when installed.
        make = shutil.which('gmake') or shutil.which('make')
        probe = subprocess.run([make, '-f', '-', 'probe'], input='.RECIPEPREFIX := >\nprobe:\n> @:\n',
                               env=self.env, capture_output=True, text=True)
        if probe.returncode:
            self.skipTest('GNU Make with .RECIPEPREFIX support required (3.82+)')
        tools = self.root / 'tools'
        tools.mkdir()
        (tools / 'make').symlink_to(make)
        self.env['PATH'] = str(tools) + os.pathsep + self.env.get('PATH', '')
        self.native()
        makefile = self.project / 'Makefile'
        makefile.write_text(makefile.read_text().replace('check:\n\t@$(PYTHON) .latex-ai/workbench.py check\n',
            '.RECIPEPREFIX := >\ncheck:\n> @touch custom-check-ran\n.RECIPEPREFIX :=\n'))
        plan = json.loads(self.command('plan', '--files', 'main.tex', '--json').stdout)
        self.assertTrue(plan['project_check'])
        self.command('validate', '--files', 'main.tex')
        self.assertTrue((self.project / 'custom-check-ran').is_file())

    def test_f4_computed_recipeprefix_is_conservative(self):
        for assignment in ('.RECIPEPREFIX = $(PREFIX)', '.RECIPEPREFIX :=', 'export .RECIPEPREFIX ?= >'):
            with self.subTest(assignment=assignment):
                (self.project / 'Makefile').write_text(assignment + '\ncheck:\n> @false\n')
                self.assertTrue(guide.project_check_rule(self.project))

    def test_f5_full_check_rejects_conflicts_without_a_compiler_failure(self):
        (self.project / 'main.tex').write_text(SOURCE_4_8_1.replace('Fixture.', '<<<<<<< HEAD\nOld\n=======\nNew\n>>>>>>> topic\n'))
        self.builder()
        self.configure()
        self.install('init', editor=False)
        result = self.command('check', expected=1)
        self.assertIn('conflict marker', result.stderr)

    def test_f5_full_check_covers_inputs_first_discovered_by_the_compiler(self):
        (self.project / 'hidden.txt').write_text('<<<<<<< HEAD\nOld\n>>>>>>> topic\n')
        self.builder(inputs=('main.tex', 'hidden.txt'))
        self.configure()
        self.install('init', editor=False)
        result = self.command('document-check', expected=1)
        self.assertIn('hidden.txt', result.stderr)

    def test_f6_comment_stripping_counts_backslash_parity(self):
        for count in range(6):
            source = 'prefix ' + '\\' * count + '% comment'
            expected = source if count % 2 else source[:source.index('%')]
            with self.subTest(backslashes=count):
                self.assertEqual(latex.tex_without_comments(source), expected)

    def test_o1_project_listing_checks_each_environment_directory_once(self):
        (self.project / 'docs').mkdir()
        names = sorted(f'docs/{number}.md' for number in range(100))
        for name in names:
            (self.project / name).write_text('Fixture')
        with patch.object(runtime, 'git_names', side_effect=[names, []]), \
                patch.object(runtime, 'environment_root', wraps=runtime.environment_root) as check:
            self.assertEqual(runtime.project_files(self.project), names)
        self.assertEqual(check.call_count, 1)

    def test_o2_planning_scans_each_document_once(self):
        (self.project / 'notes.tex').write_text(SOURCE_4_8_1)
        config = self.configure(documents_={'paper': {'root': 'main.tex'}, 'notes': {'root': 'notes.tex'}})
        with patch.object(latex, 'manuscript_dependencies', wraps=latex.manuscript_dependencies) as scan:
            runtime.validation_plan(self.project, config, ['main.tex'])
        self.assertEqual(scan.call_count, 2)


class ValidationIgnore(ProjectCase):

    """Origin: tests/test_validation_ignore.py."""

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
                          (".latex-ai/guide.py", "manuscript")):
            with self.subTest(name=name):
                plan = self.plan(name, ignore=["docs/**", ".latex-ai/**"])
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


class WorkbenchTests(unittest.TestCase):
    """Origin: tests/test_workbench.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="latex-ai-unit-")
        self.project = Path(self.temp.name).resolve()
        (self.project / "paper.tex").write_text(TEX_workbench)
        prepare_config(self.project, root="paper.tex", output_dir=".")

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, **choices):
        prepare_config(self.project, **{"root": "paper.tex", "output_dir": ".", **choices})
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return boot.main([*args, str(self.project)])

    def snapshot(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}

    def init(self):
        self.assertEqual(self.cli("init"), 0)

    def selection(self, *names):
        return rt.validation_plan(self.project, rt.load_config(self.project), list(names))

    def test_docs_and_ordinary_files_never_invoke_manuscript_tools(self):
        self.init()
        (self.project / "README.md").write_text("Notes about [the source](paper.tex).\n")
        (self.project / "helper.py").write_text("value = 1\n")
        (self.project / "notes.json").write_text('{"note": true}\n')
        plan = self.selection("README.md", "helper.py", "notes.json", "notes.yaml")
        self.assertFalse(plan["manuscript"] or plan["unit"] or plan["portability"])
        before = self.snapshot()
        with patch.object(rt, "run", side_effect=AssertionError("Build tool invoked")), contextlib.redirect_stdout(io.StringIO()):
            rt.validate_changes(self.project, plan)
        self.assertEqual(before, self.snapshot())

    def test_policy_checks_without_a_manuscript_build(self):
        self.init()
        plan = self.selection("AGENTS.md", "CLAUDE.md", ".claude/settings.json", "workbench/skills/latex-ai-workbench/SKILL.md")
        self.assertTrue(plan["policy"])
        self.assertFalse(plan["manuscript"])
        with patch.object(rt, "run", side_effect=AssertionError("Build tool invoked")), contextlib.redirect_stdout(io.StringIO()):
            rt.validate_changes(self.project, plan)
        (self.project / "CLAUDE.md").write_text("Competing policy\n")
        with self.assertRaisesRegex(rt.WorkbenchError, "delegate"):
            rt.file_checks(self.project, plan)

    def test_workbench_python_selects_regressions_and_build_controls_select_full(self):
        self.init()
        (self.project / "workbench").mkdir()
        (self.project / "workbench/Makefile").write_text("test:\n\ttrue\n")
        (self.project / "workbench/latex-ai-init").write_text("#!/usr/bin/env python3\n")  # the distribution's entry point
        for name in ("workbench/tests/test_workbench.py", "workbench/utility.py"):
            plan = self.selection(name)
            self.assertTrue(plan["unit"])
            self.assertFalse(plan["manuscript"] or plan["portability"])
        for name in ("Makefile", rt.CONFIG, "workbench/runtime.py", "workbench/bootstrap.py"):
            plan = self.selection(name)
            self.assertTrue(plan["manuscript"] and plan["unit"] and plan["portability"])

    def test_hosted_distribution_is_recognised_by_its_entry_point_or_configuration(self):
        self.init()
        config = rt.load_config(self.project)

        def plan(*names, cfg=None):
            return rt.validation_plan(self.project, cfg or config, list(names))
        # An unrelated directory that happens to be called workbench and has a Makefile is not the distribution.
        (self.project / "workbench").mkdir()
        (self.project / "workbench/Makefile").write_text("test:\n\ttrue\n")
        for name in ("workbench/analysis.py", "workbench/runtime.py", "workbench/templates/AGENTS.md"):
            with self.subTest(unrelated=name):
                found = plan(name)
                self.assertFalse(found["unit"] or found["portability"] or found["manuscript"])
                self.assertIsNone(found["package"])
        (self.project / "workbench/latex-ai-init").write_text("#!/usr/bin/env python3\n")
        self.assertEqual(plan("workbench/analysis.py")["package"], "workbench")
        self.assertTrue(plan("workbench/analysis.py")["unit"])
        self.assertTrue(plan("workbench/runtime.py")["manuscript"])
        # validation.package relocates it, and null switches package routing off.
        (self.project / "tools/kit").mkdir(parents=True)
        (self.project / "tools/kit/Makefile").write_text("test:\n\ttrue\n")
        relocated = {**config, "validation": {"package": "tools/kit"}}
        schema.validate_config(self.project, relocated)
        self.assertEqual(plan("tools/kit/analysis.py", cfg=relocated)["package"], "tools/kit")
        self.assertTrue(plan("tools/kit/analysis.py", cfg=relocated)["unit"])
        self.assertTrue(plan("tools/kit/templates/AGENTS.md", cfg=relocated)["manuscript"])
        self.assertTrue(plan("tools/kit/skills/latex-ai-workbench/SKILL.md", cfg=relocated)["policy"])
        self.assertFalse(plan("workbench/analysis.py", cfg=relocated)["unit"])
        disabled = {**config, "validation": {"package": None}}
        schema.validate_config(self.project, disabled)
        self.assertFalse(plan("workbench/analysis.py", cfg=disabled)["unit"])
        for bad in ("../kit", "/abs/kit", "", 7):
            with self.subTest(bad=bad), self.assertRaises(rt.WorkbenchError):
                schema.validate_config(self.project, {**config, "validation": {"package": bad}})

    def test_tex_bib_and_unknown_inputs_select_manuscript(self):
        self.init()
        for name in ("paper.tex", "references.bib", "figures/plot.svg", "custom.buildinput"):
            with self.subTest(name=name):
                self.assertTrue(self.selection(name)["manuscript"])

    def test_included_and_deleted_markdown_is_a_manuscript_dependency(self):
        self.init()
        (self.project / "paper.tex").write_text(TEX_workbench.replace("Hello.", "\\input{notes.md}\n\\lstinputlisting{helper.py}"))
        for name in ("notes.md", "helper.py"):
            with self.subTest(name=name):
                self.assertTrue(self.selection(name)["manuscript"])

    def test_files_named_in_braces_are_inputs_without_a_recorder_file(self):
        self.init()
        body = ("\\verbatiminput{data/results.txt}\n\\pgfplotstableread[col sep=comma]{data/table.json}\\loadedtable\n\\directlua{dofile(\"x.lua\")}\n"
                "\\verbatiminput{data/result file.txt}\n\\input{\"data/quoted name.txt\"}")
        (self.project / "paper.tex").write_text(TEX_workbench.replace("Hello.", body))
        stem = latex.output_paths(self.project, schema.document_settings(rt.load_config(self.project)))[2]
        self.assertFalse(Path(str(stem) + ".fls").exists())  # CI checkouts never have the recorder file
        for name in ("data/results.txt", "data/table.json", "data/result file.txt", "data/quoted name.txt"):  # none exists, so deletion is covered too
            with self.subTest(name=name):
                self.assertTrue(self.selection(name)["manuscript"])
        for name in ("README.md", "data/unreferenced.txt", "data/result file two.txt", "notes/other.md", "analysis.json"):
            with self.subTest(name=name):
                self.assertFalse(self.selection(name)["manuscript"])

    def test_recorder_dependencies_and_custom_build_scripts_are_recognized(self):
        self.init()
        self.assertFalse(self.selection("data/values.txt")["manuscript"])
        stem = latex.output_paths(self.project, schema.document_settings(rt.load_config(self.project)))[2]
        stem.parent.mkdir(parents=True, exist_ok=True)
        Path(str(stem) + ".fls").write_text(f"PWD {self.project}\nINPUT data/values.txt\nINPUT /external/package.tex\n")
        self.assertTrue(self.selection("data/values.txt")["manuscript"])
        (self.project / "helper.py").write_text("print('build')\n")
        config = rt.load_config(self.project)
        config["documents"]["manuscript"]["build_command"] = ["python3", "helper.py"]
        self.assertTrue(rt.validation_plan(self.project, config, ["helper.py"])["manuscript"])

    def test_git_discovery_includes_all_working_changes_without_mutation(self):
        index = self.project / "fake-index"
        index.write_bytes(b"index")
        outputs = [SimpleNamespace(returncode=0, stdout=str(index).encode() + b"\n", stderr=b""),
                   SimpleNamespace(returncode=0, stdout=b"old.tex\0draft notes.md\0", stderr=b""),
                   SimpleNamespace(returncode=0, stdout=b"new.md\0", stderr=b"")]
        with patch.object(rt.subprocess, "run", side_effect=outputs) as call:
            names, fallback = rt.changed_files(self.project)
        self.assertEqual(names, ["draft notes.md", "new.md", "old.tex"])
        self.assertIsNone(fallback)
        self.assertEqual([item.args[0][3] for item in call.call_args_list], ["rev-parse", "diff", "ls-files"])
        self.assertIn("--no-renames", call.call_args_list[1].args[0])
        self.assertNotEqual(call.call_args_list[1].kwargs["env"]["GIT_INDEX_FILE"], str(index))  # diff refreshes a copy, never the real index

    def test_missing_history_and_zero_base_select_full_validation(self):
        self.init()
        failed = SimpleNamespace(returncode=128, stdout=b"", stderr=b"unknown revision")
        listed = SimpleNamespace(returncode=0, stdout=b"README.md\0", stderr=b"")
        for base in ("missing", "0" * 40, ""):
            with patch.object(rt.subprocess, "run", side_effect=lambda *args, **kwargs: failed if "diff" in args[0] else listed):
                plan = rt.validation_plan(self.project, rt.load_config(self.project), base=base)
            self.assertTrue(plan["manuscript"])
            self.assertIn("full validation", plan["fallback"])

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_queries_leave_a_stale_git_index_byte_identical(self):
        # A throwaway repository inside the temp directory: the only way to observe a real
        # index rewrite (git diff refreshes stale stat data and ignores GIT_OPTIONAL_LOCKS).
        def git(*args):
            subprocess.run(["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-C", str(self.project), *args],
                           check=True, capture_output=True)
        git("init", "-q")
        git("add", "paper.tex", ".latex-ai.json")
        git("commit", "-q", "-m", "fixture")
        paper = self.project / "paper.tex"
        stamp = paper.stat().st_mtime + 100
        os.utime(paper, (stamp, stamp))  # identical bytes, new mtime: the index stat data is now stale
        index = self.project / ".git/index"
        before = index.read_bytes()
        self.assertEqual(rt.changed_files(self.project), ([], None))  # a touched file is not a change
        rt.project_files(self.project)
        boot.git_snapshot(self.project)
        self.assertEqual(index.read_bytes(), before)

    def throwaway_git(self, *args):
        subprocess.run(["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-C", str(self.project), *args],
                       check=True, capture_output=True)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_environment_whose_marker_is_ignored_is_still_skipped(self):
        self.throwaway_git("init", "-q")
        (self.project / ".gitignore").write_text("*.cfg\n")  # pyvenv.cfg never appears in Git's listing
        environment = self.project / "analysis-env"
        (environment / "lib").mkdir(parents=True)
        (environment / "pyvenv.cfg").write_text("home = /usr/bin\n")
        (environment / "lib/bad.py").write_text("print 'python-2 code in an environment'\n")
        (self.project / "ok.py").write_text("x = 1\n")
        names = rt.project_files(self.project)
        self.assertNotIn("analysis-env/lib/bad.py", names)
        self.assertIn("ok.py", names)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_split_index_contents_stay_byte_identical(self):
        # With a split index Git refreshes the shared-index file's mtime on any read, which no query can
        # avoid; what is guaranteed, and checked here, is that neither index file's contents change.
        self.throwaway_git("init", "-q")
        self.throwaway_git("add", "paper.tex", ".latex-ai.json")
        self.throwaway_git("commit", "-q", "-m", "one")
        self.throwaway_git("update-index", "--split-index")
        paper = self.project / "paper.tex"
        paper.write_text(paper.read_text() + "% second revision\n")
        self.throwaway_git("add", "paper.tex", ".latex-ai.json")
        self.throwaway_git("commit", "-q", "-m", "two")
        stamp = paper.stat().st_mtime + 100
        os.utime(paper, (stamp, stamp))  # stale stat data again
        git_dir = self.project / ".git"
        tracked = [git_dir / "index", git_dir / "HEAD", *git_dir.glob("sharedindex.*"), *git_dir.glob("refs/heads/*")]
        self.assertTrue(list(git_dir.glob("sharedindex.*")), "fixture did not produce a split index")
        before = {path: path.read_bytes() for path in tracked}
        self.assertEqual(rt.changed_files(self.project), ([], None))
        rt.project_files(self.project)
        boot.git_snapshot(self.project)
        self.assertEqual({path: path.read_bytes() for path in tracked}, before)

    def test_every_git_query_runs_with_optional_locks_disabled(self):
        import diagnostics
        seen = []
        index = self.project / "fake-index"
        index.write_bytes(b"index")

        def fake(*args, **kwargs):
            seen.append((args[0][3], kwargs.get("env", {}).get("GIT_OPTIONAL_LOCKS")))
            return SimpleNamespace(returncode=0, stdout=str(index).encode() if args[0][3] == "rev-parse" else b"", stderr="")
        with patch.object(rt.subprocess, "run", side_effect=fake):
            rt.changed_files(self.project)
            rt.project_files(self.project)
            boot.git_snapshot(self.project)
            diagnostics.git_state(self.project)
        self.assertGreaterEqual({command for command, _ in seen}, {"diff", "ls-files", "status", "rev-parse", "config", "branch"})
        self.assertEqual({lock for _, lock in seen}, {"0"})  # git status/diff would otherwise rewrite a stale .git/index

    def test_changed_paths_cannot_escape_project(self):
        self.init()
        with self.assertRaises(rt.WorkbenchError):
            self.selection("../notes.md")

    def test_declared_custom_inputs_override_documentation_classification(self):
        self.init()
        config = rt.load_config(self.project)
        config["validation"] = {"manuscript_inputs": ["analysis/*.json", "generated/*.md"]}
        schema.validate_config(self.project, config)
        for name in ("analysis/results.json", "generated/result.md"):
            self.assertTrue(rt.validation_plan(self.project, config, [name])["manuscript"])
        self.assertFalse(rt.validation_plan(self.project, config, ["notes.md"])["manuscript"])

    def test_invalid_custom_input_patterns_are_rejected(self):
        self.init()
        config = rt.load_config(self.project)
        for patterns in ("*.md", ["../*.md"], ["/external/*.md"], ["bad\nname"]):
            config["validation"] = {"manuscript_inputs": patterns}
            with self.subTest(patterns=patterns), self.assertRaises(rt.WorkbenchError):
                schema.validate_config(self.project, config)

    def test_lightweight_checks_catch_real_file_errors(self):
        self.init()
        for name, contents, exception in [("notes.json", "{invalid}", rt.WorkbenchError),  # reported with the file's name
                                          ("helper.py", "def broken(\n", SyntaxError),
                                          ("notes.md", "[missing](missing.md)\n", rt.WorkbenchError),
                                          ("notes.yaml", "<<<<<<< mine\n", rt.WorkbenchError)]:
            (self.project / name).write_text(contents)
            with self.subTest(name=name), self.assertRaises(exception) as raised:
                rt.file_checks(self.project, self.selection(name))
            self.assertIn(name, str(raised.exception))  # every one of these says which file it is about

    def test_setext_underline_is_not_a_conflict_but_real_markers_are(self):
        self.init()
        (self.project / "notes.md").write_text("Summary\n=======\n\nProse.\n")
        (self.project / "notes.rst").write_text("Summary\n=======\n\nProse.\n")
        with contextlib.redirect_stdout(io.StringIO()):
            rt.file_checks(self.project, self.selection("notes.md", "notes.rst"))  # a real check, before any helper is consulted
        import core
        for text in ("Summary\n=======\n\nProse.\n", "Title\n=====\n", "Heading\n=======  \n"):
            with self.subTest(text=text):
                self.assertFalse(core.damaged_text(text))
        for text in ("<<<<<<< mine\nx\n=======\ny\n>>>>>>> theirs\n", ">>>>>>> theirs\n", "a\n<<<<<<< HEAD\n", "nul\0"):
            with self.subTest(text=text):
                self.assertTrue(core.damaged_text(text))
        self.assertEqual(rt.bib_keys("% =======\n=======\n@book{k, title={T}}\n", "x.bib"), ["k"])

    def test_full_check_files_skip_environments_and_honour_git_listing(self):
        for name, text in (("src/ok.py", "x = 1\n"), ("venv/pyvenv.cfg", "home = /x\n"), ("venv/lib/legacy.py", "print 'x'\n"),
                           ("env/lib/python3.12/site-packages/p/legacy.py", "print 'x'\n"), ("node_modules/p/x.json", "{bad"),
                           (".venv/lib/legacy.py", "print 'x'\n"), ("conda/conda-meta/p.json", "{bad")):
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        with patch.object(rt.subprocess, "run", return_value=SimpleNamespace(returncode=128, stdout=b"", stderr=b"not a repository")):
            walked = rt.project_files(self.project)
        self.assertIn("src/ok.py", walked)
        self.assertIn("paper.tex", walked)
        for name in ("venv/lib/legacy.py", "env/lib/python3.12/site-packages/p/legacy.py", "node_modules/p/x.json", ".venv/lib/legacy.py", "conda/conda-meta/p.json"):
            self.assertNotIn(name, walked)
        listing = SimpleNamespace(returncode=0, stdout=b"src/ok.py\0venv/pyvenv.cfg\0venv/lib/legacy.py\0docs/a.md\0conda/conda-meta/p.json\0pkg/site-packages/x.py\0", stderr=b"")
        with patch.object(rt.subprocess, "run", return_value=listing):
            self.assertEqual(rt.project_files(self.project), ["docs/a.md", "src/ok.py"])

    def test_markdown_examples_and_deleted_docs_do_not_fail_link_checks(self):
        self.init()
        (self.project / "notes.md").write_text('Example:\n```markdown\n[example](future.md)\n```\n[web](https://example.com)\n')
        with contextlib.redirect_stdout(io.StringIO()):
            rt.file_checks(self.project, self.selection("notes.md", "deleted.md"))

    def test_selected_checks_use_canonical_make_and_files_only_never_builds(self):
        self.init()
        (self.project / "workbench").mkdir()
        (self.project / "workbench/Makefile").write_text("test:\n\ttrue\n")
        (self.project / "workbench/latex-ai-init").write_text("#!/usr/bin/env python3\n")  # the distribution's entry point
        plan = self.selection(rt.CONFIG)
        with patch.object(rt, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            rt.validate_changes(self.project, plan)
        self.assertEqual([item.args[0] for item in run.call_args_list], [["make", "-C", "workbench", "test"], ["make", "-C", "workbench", "portability"], ["make", "document-check", "DOC=manuscript"]])
        with patch.object(rt, "run", side_effect=AssertionError("Build tool invoked")), contextlib.redirect_stdout(io.StringIO()):
            rt.validate_changes(self.project, plan, files_only=True)


if __name__ == "__main__":
    unittest.main()
