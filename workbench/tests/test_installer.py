"""Tests of the installer and the files it writes: init, diff and runtime, the configuration and its errors, the generated Makefile, editor and policy files.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 20 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_audit3_repairs.py:
Independent audit 3 failures, exercised through installed workflows.

Compiler fixtures disable lint explicitly. Process/move tests isolate infrastructure;
the source-content and stdin tests use genuine TeX tools.

test_documents.py:
Installed workflows for named TeX documents and mixed note organization.

test_generated_files_guard.py:
Guard: the Makefile block and the editor files an installed project carries stay byte-identical.

Upgrading must not churn an installed project, so a refactor of the code that renders these files (Phase 1 of
the plan after 3.0.2 replaces the command tables behind them) must leave them exactly as they are. Each fixture
configuration below is rendered and compared, byte for byte, with the copy stored in ``tests/fixtures/generated/``.

A failure means generated text changed. Undo the change, or, when the release announces it, refresh the copies
with ``python3 -B tests/test_installer.py --generate`` and review the diff of the stored files.

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

test_repairs_3_0_3.py:
Phase 0 macOS verification: regressions against the actual older GNU Make parser.

test_repairs_3_4_1.py:
3.4.1: LaTeX Workshop's View PDF looks where each document is built.

Before, the generated .vscode/settings.json never set latex-workshop.latex.outDir, so the viewer looked beside the root
file while the build wrote elsewhere (revision/main.tex built into revision/build/): a blank viewer that reported a
zero-byte PDF. outDir is one string whose placeholders expand per root file, so the workbench derives the first value that
gives every document its real output directory, and says so when none does.

test_review_fixes.py:
Regressions for the architecture review's installed workflow failures.

test_scope_4_3_0.py:
Workbench 4.3.0 removes the installer's upgrade machinery (see docs/maintainers/minimal-scope.md): the installer creates a
project (`init`), says how a project differs from this release (`diff`) and refreshes its vendored runtime (`runtime`). There is no
audit, upgrade, configure or recovery; a project is updated by an agent following docs/upgrading.md, with a diff and `make check`.

These tests pin what is gone (the modes, the three-way merge, the manifest of every managed file, the disabled-module memory) and what the
three modes promise: `init` never touches an installed project, `diff` never writes, `runtime` never overwrites an edited file unasked.

test_scope_4_4_0.py:
Workbench 4.4.0 removes the adoption of a project's own Makefile (see docs/maintainers/minimal-scope.md): the workbench no longer merges
into, parses or wraps a Makefile it did not write. `init` creates a project and refuses to touch a file of the project's that differs
from what it would write; an existing project is migrated to the workbench's layout by an agent following docs/migrating.md.

These tests pin what is gone (the Make parser, the adapter, the build hooks, the Make version requirement), what `init` now promises
(it writes only files that are absent or already identical, and says what to do about the rest) and what stays (a project's own Make
targets run as an ordinary build command, and `validate` still runs a project's own `check`).

test_scope_4_4_1.py:
Workbench 4.4.1, step 3.1 of docs/maintainers/plan-after-4.4.0.md: refreshing a project's runtime no longer renders its policy, Makefile
and editor files, and `diff` renders what it compares once.

`runtime_files(config)` is the runtime half of `desired_files(config)`, which now builds on it. These tests pin that the two agree (in content and in order,
since `init` and `diff` print in that order), that `runtime` and `diff` keep their behaviour, and that the schema's errors name this workbench.

test_scope_4_4_2.py:
Workbench 4.4.2, step 3.2 of docs/maintainers/plan-after-4.4.0.md: a module declares what something reads, and no more.

The module table had a `tools` list, a `requires` list and a `check_group` that nothing used: both lists were empty for both modules, and no caller passed a group
to `module_names`. These tests pin that they are gone, and that what they stood for did not change: the order of the modules, the tools a project needs, what the schema
says about a module or a field it does not know, and what `modules` reports (minus the `requires` that was always empty).

test_scope_4_5_0.py:
Workbench 4.5.0, step 3.4 of docs/maintainers/plan-after-4.4.0.md: one engine (pdflatex), one bibliography program (BibTeX), no installer profiles.

`--engine`, `--backend` and `--profile` are gone from `init`, as are the lualatex, xelatex and biber paths behind them and the `biblatex` export format. A configuration that
says what stays (`engine: pdflatex`, `backend: none` or `bibtex`, export format `bibtex`) works as it did, and anything else is refused by name with a hint that points at
`build_command`. `--modules` chooses what a profile chose: `--modules ""` was `--profile core` and `--modules latex` was `--profile writing`.

test_scope_4_5_1.py:
Workbench 4.5.1: `init` stops at a paper that needs a toolchain the workbench does not build, and says what to declare.

4.5.0 stopped reading the source for lualatex, xelatex or biber, so `init` on such a paper succeeded as pdflatex and the first build failed with the compiler's
own message. The guard reads the source for the few signs that it needs another engine or biber, refuses before writing anything, and prints the `--build-command`
to run `init` again with, which is the whole fix. A `--build-command` takes the guard away, since the project then builds itself; a project that has its own
configuration is not second-guessed. The hint is tested by following it with the real tools where they are installed.

test_scope_4_6_0.py:
Workbench 4.6.0, step 3.5 of docs/maintainers/plan-after-4.4.0.md: `make all`, and `make NAME` for each document of a project that has several.

`make all` builds every document, one after another (one runtime action, `build --all`, because the project's build lock refuses two builds at once and so
`make -j all` must not start them side by side). `make notes` builds that document, as `make build DOC=notes` does. The generated Makefile gains the targets on purpose:
`all` for every project with LaTeX, and a target per document when there are two or more, written only where the name is free. The bare `make` still builds the
default document. `make guide` names the targets, and `diff` shows an existing project the lines it lacks.

test_scope_4_8_1.py:
4.8.1: independent-audit regressions, output safety, source integrity and bounded scans.

Every project is disposable; overwrite probes use only synthetic sentinel files.

test_scope_4_9_0.py:
Workbench 4.9.0, step 3.7 of docs/maintainers/plan-after-4.4.0.md: the doctor's stamp report, and the update recipe in the skill file.

`make doctor` has always checked the tools. It now also reports the project's stamp: what `.latex-ai/installation.json` records, what the vendored runtime is, and which runtime
files were edited or are missing. Given the folder of a release (`LATEX_AI_TEMPLATE=/path/to/workbench`, or `--template`) it adds the template's side by running that
release's own `latex-ai-init diff`, so there is one rule for what differs, and writes nothing. The update recipe an agent follows is in the skill file; `docs/upgrading.md` points to it.

test_workbench.py:
(no docstring)
"""

import contextlib
import copy
import difflib
import io
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap
import bootstrap as boot
import commands
import core
import diagnostics
import guide
import latex
import runtime as rt
import schema
from test_support import ProjectCase, fixture_env, isolate_environment, prepare_config


SOURCE = "\\documentclass{article}\n\\begin{document}Audit fixture.\\end{document}\n"


# The multi-document example (examples/tex-notes), with the editor files switched on.
MULTI_DOCUMENT = {'schema_version': 4, 'default_document': 'paper', 'documents': {'paper': {'root': 'main.tex'}, 'derivation': {'root': 'notes/derivation.tex'}, 'notebook': {'root': 'notes/notebook.tex'}}, 'integrations': {'editor': True}}


def starting(editor=True):
    return {"schema_version": 4, "default_document": "manuscript", "documents": {"manuscript": {"root": "main.tex"}},
            "integrations": {"editor": editor}}


# name -> configuration
FIXTURES = {
    "latex": starting(),
    "latex-no-editor": starting(editor=False),
    "multi-document": MULTI_DOCUMENT,
}


STORED = Path(__file__).resolve().parent / "fixtures" / "generated"


SUFFIX = ".txt"  # so no tool mistakes a stored copy for a live Makefile, workflow or editor file, and the planner files it as plain text


GUARDED = {"Makefile": "Makefile", ".vscode/settings.json": "vscode-settings.json",
           ".vscode/tasks.json": "vscode-tasks.json"}  # generated path -> stored name


def render(config):
    """What the installer would carry into a project for this configuration, keyed by the stored file name."""
    return {GUARDED[name]: text for name, text in bootstrap.desired_files(config).items() if name in GUARDED}


OLD_MAKE = Path('/usr/bin/make')


HAS_OLD_MAKE = OLD_MAKE.is_file() and subprocess.run(
    [str(OLD_MAKE), '--version'], capture_output=True, text=True
).stdout.startswith('GNU Make 3.81')


def documents(*pairs):
    return [{"root": root, "output_dir": output, "name": root.rsplit("/", 1)[-1].removesuffix(".tex")} for root, output in pairs]


TEX = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


SOURCE_4_3_0 = "\\documentclass{article}\\begin{document}x\\end{document}\n"


REMOVED_WORDS = re.compile(r"latex-ai-init (?:upgrade|audit|configure)\b|\bconfigure (?:--enable|--disable)|--enable (?:bibliography|latex)\b"
                           r"|\bdisabled_modules\b|installation\.py|\.latex-ai/installation\.json.{0,40}manifest|three-way")


OWN_FILES = {"AGENTS.md": "Mine.\n", ".gitignore": "*.tmp\n", "Makefile": "pdf:\n\ttrue\n", ".vscode/settings.json": '{"editor.tabSize": 3}\n',
             ".claude/settings.json": '{"permissions": {"allow": ["Bash(ls)"]}}\n'}


CONFIGS = (starting(), starting(editor=False), MULTI_DOCUMENT)




def paper(**fields):
    return {"root": "main.tex", "engine": "pdflatex", **fields}




def latex_module(document=None, defaults=None):
    values = {"default_document": "paper", "documents": {"paper": {"root": "main.tex", **(document or {})}}}
    if defaults:
        values["defaults"] = defaults
    return values


def configuration(document=None, defaults=None, **bibliography):
    config = {"schema_version": 4, **latex_module(document, defaults)}
    if bibliography:
        config["bibliography"] = {"files": [], **bibliography}
    return config


ACCEPTED = (  # what stays, and worked before
    configuration({"engine": "pdflatex", "backend": "none"}),
    configuration({"engine": "pdflatex", "backend": "bibtex"}),
    configuration(defaults={"engine": "pdflatex", "backend": "bibtex"}),
    configuration({"backend": "bibtex"}, files=["refs.bib"], export={"path": "refs.bib", "format": "bibtex"}),
)


REFUSED = (  # what 4.4.2 accepted and 4.5.0 refuses: the word the message must name, and the word the hint must hold
    ("a document's engine, lualatex", configuration({"engine": "lualatex"}), "lualatex", "build_command"),
    ("a document's engine, xelatex", configuration({"engine": "xelatex"}), "xelatex", "build_command"),
    ("the default engine", configuration(defaults={"engine": "xelatex"}), "xelatex", "build_command"),
    ("a document's backend", configuration({"backend": "biber"}), "biber", "build_command"),
    ("the default backend", configuration(defaults={"backend": "biber"}), "biber", "build_command"),
    ("a default engine every document overrides", configuration({"engine": "pdflatex"}, defaults={"engine": "xelatex"}), "xelatex", "build_command"),
    ("a default backend every document overrides", configuration({"backend": "none"}, defaults={"backend": "biber"}), "biber", "build_command"),
    ("the export format", configuration(export={"path": "refs.bib", "format": "biblatex"}), "biblatex", "Better BibTeX"),
    ("an export without a format", configuration(export={"path": "refs.bib"}), "is missing", "Better BibTeX"),
)


BIB = "@misc{fixture, title={Synthetic fixture}, year={2000}}\n"


DOCUMENT = "\\documentclass{article}\n%s\\begin{document}\n%s\\end{document}\n"


FINE = (  # sources that mention them without needing them
    ("a magic comment for pdflatex", "% !TeX program = pdflatex\n" + DOCUMENT % ("", "x\n")),
    ("fontspec in a comment", DOCUMENT % ("% \\usepackage{fontspec}\n", "x\n")),
    ("biblatex processed by BibTeX", DOCUMENT % ("\\usepackage[backend=bibtex]{biblatex}\n\\addbibresource{refs.bib}\n", "x\\printbibliography\n")),
    ("plain BibTeX", DOCUMENT % ("", "x\\bibliographystyle{plain}\\bibliography{refs}\n")),
)


NEEDS = (  # source, what the message must name, latexmk's flag the hint must carry
    ("magic comment, lualatex", "% !TeX program = lualatex\n" + DOCUMENT % ("", "x\n"), "lualatex", "-lualatex"),
    ("magic comment, xelatex", "% !TeX TS-program = xelatex\n" + DOCUMENT % ("", "x\n"), "xelatex", "-xelatex"),
    ("directlua", DOCUMENT % ("", "\\directlua{tex.print('x')}\n"), "lualatex", "-lualatex"),
    ("luacode", DOCUMENT % ("\\usepackage{luacode}\n", "x\n"), "lualatex", "-lualatex"),
    ("xeCJK", DOCUMENT % ("\\usepackage{xeCJK}\n", "x\n"), "xelatex", "-xelatex"),
    ("fontspec", DOCUMENT % ("\\usepackage{fontspec}\n", "x\n"), "fontspec", "-lualatex"),
    ("biblatex", DOCUMENT % ("\\usepackage{biblatex}\n\\addbibresource{refs.bib}\n", "x\\printbibliography\n"), "biblatex", "-pdf"),
    ("biblatex with biber named", DOCUMENT % ("\\usepackage[backend=biber]{biblatex}\n", "x\n"), "biblatex", "-pdf"),
)


def document(name, **fields):
    return {"root": f"{name}.tex", "lint": {"enabled": False}, "output_dir": "outputs", "build_command": [sys.executable, "builder.py", name], **fields}


def configuration_4_6_0(*names, default=None, **fields):
    return {'schema_version': 4, 'default_document': default or names[0], 'documents': {name: document(name, **fields) for name in names}, 'integrations': {'editor': False}}


def makefile(config):
    return bootstrap.desired_files(config)["Makefile"]


def rules(text):
    """{target: its recipe lines} for the plain rules of a Makefile text."""
    found, current = {}, None
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z][\w-]*):(?!=)\s*(.*)$", line)
        if match:
            current = found.setdefault(match[1], [])
            if match[2]:
                current.append("prerequisites: " + match[2])
        elif line.startswith("\t") and current is not None:
            current.append(line.strip())
        elif line.strip():
            current = None
    return found


SOURCE_4_8_1 = '\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n'


SKILL = PACKAGE / "skills/latex-ai-workbench/references/installation.md"


def generate():
    """Write the stored copies from the current code. A deliberate act: review the diff before committing it."""
    for name, config in FIXTURES.items():
        directory = STORED / name
        directory.mkdir(parents=True, exist_ok=True)
        rendered = {filename + SUFFIX: text for filename, text in render(config).items()}
        for filename, text in rendered.items():
            (directory / filename).write_bytes(text.encode("utf-8"))
        for stale in directory.iterdir():
            if stale.name not in rendered:
                stale.unlink()
    for orphan in STORED.iterdir():
        if orphan.name not in FIXTURES:
            shutil.rmtree(orphan) if orphan.is_dir() else orphan.unlink()


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

    def test_a11_double_colon_installation_never_produces_invalid_make(self):
        makefile='check:: local-test\nlocal-test:\n\ttouch project-check-ran\n'
        (self.project/'Makefile').write_text(makefile)
        (self.project/'main.tex').write_text(SOURCE)
        result=self.install('init', expected=None, lint=False, editor=False, build_command=json.loads(json.dumps([sys.executable, '-c', 'pass'])))
        if result.returncode==0:
            parsed=self.run_command('make','-n','check')
            self.assertIn('local-test',(self.project/'Makefile').read_text())
        else:
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertEqual((self.project/'Makefile').read_text(),makefile)
            self.assertFalse((self.project/'.latex-ai/installation.json').exists())


class DocumentTests(unittest.TestCase):
    """Origin: tests/test_documents.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-documents-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

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

    def test_invalid_defaults_and_recursive_commands_fail_before_installation(self):
        for change in ("default", "recursive", "malformed"):
            config = self.configuration()
            values = config
            if change == "default":
                values["defaults"]["engine"] = "bogus"
                for fields in values["documents"].values():
                    fields["engine"] = "pdflatex"
            else:
                values["documents"]["note"]["build_command"] = ["make", "check" if change == "recursive" else {}]
            with self.subTest(change=change), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, config)


class GeneratedFilesGuard(unittest.TestCase):
    """Origin: tests/test_generated_files_guard.py."""

    def test_every_fixture_renders_exactly_its_stored_copies(self):
        for name, config in FIXTURES.items():
            rendered = render(config)
            directory = STORED / name
            with self.subTest(fixture=name):
                stored = sorted(path.name for path in directory.glob("*")) if directory.is_dir() else []
                self.assertEqual(stored, sorted(filename + SUFFIX for filename in rendered),
                                 f"{name}: the files generated no longer match the stored copies (see the module docstring)")
            for filename, text in rendered.items():
                with self.subTest(fixture=name, file=filename):
                    path = directory / (filename + SUFFIX)
                    self.assertTrue(path.is_file(), f"{path} is missing; see the module docstring")
                    expected = path.read_bytes()
                    if text.encode("utf-8") != expected:
                        change = "".join(list(difflib.unified_diff(expected.decode("utf-8").splitlines(True), text.splitlines(True),
                                                                   "stored", "generated", n=1))[:60])
                        self.fail(f"{name}/{filename} changed. An installed project would change on upgrade.\n{change}")

    def test_no_stored_fixture_is_left_without_a_fixture(self):
        self.assertEqual(sorted(path.name for path in STORED.iterdir()) if STORED.is_dir() else [], sorted(FIXTURES))


class ModuleTests(unittest.TestCase):
    """Origin: tests/test_modules.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-modules-")
        self.project = Path(self.temp.name).resolve()
        prepare_config(self.project, lint=False, editor=True)

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

    def example(self):
        """A small LaTeX project with the workbench installed."""
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nExample.\n\\end{document}\n")
        self.assertEqual(self.cli('init', lint=False, editor=False), 0)
        return schema.load_config(self.project)


    def test_unknown_modules_and_settings_are_rejected(self):
        for modules in ({"magic": {}}, {"notes": {}}, {"numerics": {}}, {"bibliography": {"unknown_key": 1}}):
            with self.subTest(modules=modules), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, {'schema_version': 3, 'modules': modules})

    def run_main(self, *arguments):
        errors = io.StringIO()
        with patch.object(sys, "argv", ["workbench", *arguments, "--project", str(self.project)]), contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            return rt.main(), errors.getvalue()

    def cli_result(self, *args):
        out, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errors):
            status = boot.main([*args, str(self.project)])
        return status, out.getvalue(), errors.getvalue()

    def cli_output(self, *args):
        return self.cli_result(*args)[:2]

    def test_installer_summarises_in_plain_words_and_says_what_comes_next(self):
        (self.project / "main.tex").write_text(self.PAPER)
        status, text = self.cli_output("init", "--dry-run")
        self.assertIn("Dry run: nothing was changed", text)
        self.assertFalse((self.project / ".latex-ai/workbench.py").exists())
        status, text = self.cli_output("init")
        self.assertEqual(status, 0)
        self.assertRegex(text, r"Done: \d+ file\(s\) added")
        for command in ("make doctor", "make help", "make check"):
            self.assertIn(command, text)
        status, _, errors = self.cli_result("init")
        self.assertEqual(status, 2)
        self.assertIn("already has the workbench installed", errors)
        self.assertRegex(errors, r"Hint: .*runtime.*diff")


    PAPER = "\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n"

    def test_a_broken_json_file_is_named_in_the_error(self):
        self.example()
        path = self.project / core.CONFIG
        original = path.read_text()
        path.write_text('{"schema_version": 1,,}')
        status, errors = self.run_main("check")
        path.write_text(original)
        self.assertEqual(status, 1)
        self.assertIn(f"ERROR: {core.CONFIG} is not valid JSON", errors)
        self.assertIn("Hint:", errors)
        (self.project / "data.json").write_text("{broken")  # an ordinary project file, found by the file checks
        status, errors = self.run_main("validate", "--files", "data.json")
        self.assertEqual(status, 1)
        self.assertIn("data.json", errors)

    def test_the_look_first_output_is_short_and_ends_with_the_summary(self):
        (self.project / "main.tex").write_text(self.PAPER)
        status, text = self.cli_output("init", "--dry-run", "--diff")
        lines = text.rstrip().splitlines()
        self.assertEqual(status, 0)
        self.assertLess(len(lines), 700, "the first command a newcomer runs must stay readable")
        self.assertIn("Dry run: nothing was changed", "\n".join(lines[-3:]))
        self.assertRegex(text, r"(?m)^new file: \.latex-ai/workbench\.py \(\d+ lines")
        self.assertNotIn("+def main():", text)
        self.assertIn("+.DEFAULT_GOAL := build", text)  # files the project will own or read are still shown in full

    def test_installation_uses_the_explicit_editor_preference(self):
        config = json.loads((self.project / core.CONFIG).read_text())
        config["integrations"]["editor"] = False
        (self.project / core.CONFIG).write_text(json.dumps(config))
        status, text = self.cli_output("init")
        self.assertEqual(status, 0, text)
        self.assertFalse((self.project / ".vscode").exists())
        self.assertIn("make status", text.split("Next:")[1])


    def test_dry_runs_and_diff_never_write(self):
        before = self.snapshot()
        self.assertEqual(self.cli('init', '--dry-run'), 0)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.cli('init'), 0)
        before = self.snapshot()
        self.assertEqual(self.cli("diff"), 0)
        self.assertEqual(self.cli("runtime", "--dry-run"), 0)
        self.assertEqual(before, self.snapshot())


class Repairs(ProjectCase):

    # --- build-produced inputs -------------------------------------------------------------------------

    """Origin: tests/test_repairs_3_0_1.py, workbench 3.0.1."""

    def test_configuration_errors_name_the_offending_key(self):
        base = {'schema_version': 4, 'default_document': 'paper', 'documents': {'paper': {'root': 'main.tex'}}}
        (self.project / "main.tex").write_text(SOURCE)
        cases = {
            "document": lambda c: c["documents"]["paper"].update(rooot="main.tex"),
            "latex": lambda c: c.update(documnts={}),
            "core": lambda c: c.update(moduls={}),
            "integrations": lambda c: c.update(integrations={"cii": {}}),
            "module": lambda c: c.update(bibliography={"pth": "refs.bib"}),
            "validation": lambda c: c.update(validation={"manuscript_input": []}),
        }
        for label, edit in cases.items():
            config = json.loads(json.dumps(base))
            edit(config)
            with self.subTest(label), self.assertRaises(core.WorkbenchError) as caught:
                schema.validate_config(self.project, config)
            self.assertRegex(str(caught.exception), r"rooot|documnts|moduls|cii|pth|manuscript_input", label)

    def test_invalid_schema_hint_says_what_to_do(self):
        with self.assertRaises(core.WorkbenchError) as caught:
            schema.validate_config(self.project, {'schema_version': 2})
        self.assertIn("examples/minimal", caught.exception.hint)
        self.assertIn(str(2), str(caught.exception))


class Repairs_3_0_2(ProjectCase):

    # --- F1: one lock per project, shared by everyone who works in it ----------------------------------

    """Origin: tests/test_repairs_3_0_2.py, workbench 3.0.2."""

    def test_the_record_keeps_a_digest_for_each_runtime_file_and_nothing_else(self):
        (self.project / "main.tex").write_text(SOURCE)
        self.install('init', editor=False)
        record = json.loads((self.project / ".latex-ai/installation.json").read_text())
        self.assertEqual(set(record), {"schema_version", "version", "files"})
        digest = record["files"][".latex-ai/core.py"]
        self.assertEqual(digest, diagnostics.sha256_text((self.project / ".latex-ai/core.py").read_text()))
        self.assertTrue(all(name.startswith(".latex-ai/") for name in record["files"]))
        self.assertLess(len(json.dumps(record)), 4_000)


class Repairs_3_0_3(ProjectCase):
    """Origin: tests/test_repairs_3_0_3.py, workbench 3.0.3."""

    @unittest.skipUnless(HAS_OLD_MAKE, 'Actual GNU Make 3.81 required')
    def test_actual_make_3_81_runs_the_generated_makefile(self):
        """3.0.2 F2, now simpler: the Makefile init writes asks nothing of the Make version, so the one macOS ships runs it."""
        (self.project / 'main.tex').write_text('\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n')
        self.builder()
        self.configure()
        # Select old Make without accidentally selecting stock macOS Python (<3.10).
        env = {**self.env, 'PATH': str(OLD_MAKE.parent) + os.pathsep + self.env.get('PATH', ''), 'PYTHON': sys.executable}
        package = Path(__file__).resolve().parents[1]
        self.run_command(sys.executable, '-B', str(package / 'latex-ai-init'), 'init', str(self.project), env=env)
        for goal in ('help', 'status', 'doctor', 'check'):
            with self.subTest(goal=goal):
                self.run_command(str(OLD_MAKE), goal, env=env)
        self.assertEqual(self.state(), 'current')


class ViewerOutputDirectory(unittest.TestCase):
    """Origin: tests/test_repairs_3_4_1.py, workbench 3.4.1."""

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
    """Origin: tests/test_repairs_3_4_1.py, workbench 3.4.1."""

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


class ReviewFixes(unittest.TestCase):
    """Origin: tests/test_review_fixes.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-review-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def install(self, *arguments, env=None, **choices):
        (self.project / "builder.py").write_text("from pathlib import Path\nPath('main.pdf').write_bytes(b'%PDF-fixture')\nPath('main.log').write_text('Clean log\\n')\n")
        prepare_config(self.project, lint=False, output_dir=".", build_command=[sys.executable, "builder.py"], **choices)
        return subprocess.run([sys.executable, "-B", str(bootstrap.PACKAGE / "latex-ai-init"),
                               "init", str(self.project), *arguments], env=env, capture_output=True, text=True)

    def test_installation_and_diff_without_git(self):
        tools = self.project / "tools"; tools.mkdir()
        for name in ("make", "python3"):
            (tools / name).symlink_to(shutil.which(name))
        # Hermetic: CI exports LATEX_AI_BASE, all zeros on a new branch, which would replace the Git diagnosis.
        env = {**{k: v for k, v in os.environ.items() if k != "LATEX_AI_BASE"}, "PATH": str(tools)}
        result = self.install(env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([sys.executable, str(bootstrap.PACKAGE / "latex-ai-init"), "diff", str(self.project)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([sys.executable, str(self.project / ".latex-ai/workbench.py"), "validate", "--project", str(self.project)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Git is not installed", result.stdout)

    def test_json_results_wrap_the_output_and_preserve_exit_status(self):
        p = self.project
        self.assertEqual(self.install().returncode, 0)
        for action in ("status", "check"):
            result = subprocess.run([sys.executable, str(p / ".latex-ai/workbench.py"), action, "--project", str(p), "--json"],
                                    capture_output=True, text=True)
            data = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, data)
            self.assertEqual(data["exit_status"], 0)
            self.assertEqual(data["status"], "success")
            self.assertIsInstance(data["result"], dict)
        (p / "broken.json").write_text("{invalid}")
        result = subprocess.run([sys.executable, str(p / ".latex-ai/workbench.py"), "validate", "--project", str(p), "--json", "--files", "broken.json"],
                                capture_output=True, text=True)
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["exit_status"], 1)
        self.assertIn("broken.json", data["stderr"])


class Init(ProjectCase):
    """Origin: tests/test_scope_4_3_0.py, workbench 4.3.0."""

    def test_init_creates_a_project_and_records_a_digest_of_each_runtime_file_and_nothing_else(self):
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        self.install('init', lint=False, editor=False)
        record = json.loads((self.project / ".latex-ai/installation.json").read_text(encoding="utf-8"))
        self.assertEqual(set(record), {"schema_version", "version", "files"})
        self.assertEqual(record["version"], core.VERSION)
        self.assertTrue(record["files"] and all(name.startswith(".latex-ai/") for name in record["files"]))
        for name, digest in record["files"].items():
            self.assertEqual(digest, diagnostics.sha256_text((self.project / name).read_text(encoding="utf-8")), name)

    def test_init_refuses_a_project_that_is_installed_and_writes_nothing(self):
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        self.install('init', lint=False, editor=False)
        before = {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        done = self.install("init", expected=2)
        self.assertIn("already has the workbench installed", done.stdout + done.stderr)
        self.assertIn("runtime", done.stdout + done.stderr)  # the hint names what to do instead
        self.assertEqual(before, {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()})

    def test_init_builds_a_project_from_the_configuration_it_already_has_and_does_not_change_it(self):
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        config = self.configure()
        text = (self.project / core.CONFIG).read_text(encoding="utf-8")
        self.install('init', editor=False)
        self.assertEqual((self.project / core.CONFIG).read_text(encoding="utf-8"), text)
        self.assertEqual(json.loads(text), config)
        self.assertTrue((self.project / ".latex-ai/workbench.py").is_file())

    def test_an_init_that_dies_half_way_is_finished_by_running_it_again_without_the_starting_options(self):
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        written = []
        real = bootstrap.publish

        def dies_on_the_sixth_file(project, name, text):
            written.append(name)
            if len(written) == 6:
                raise OSError("simulated power cut")
            return real(project, name, text)

        prepare_config(self.project)
        with patch.object(bootstrap, "publish", dies_on_the_sixth_file), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bootstrap.main(["init", str(self.project)]), 2)
        self.assertTrue((self.project / core.CONFIG).is_file())
        self.assertFalse((self.project / ".latex-ai/installation.json").exists(), "the record is written last")
        self.install("init")
        self.assertEqual(self.install("diff").returncode, 0)


class Diff(ProjectCase):
    """Origin: tests/test_scope_4_3_0.py, workbench 4.3.0."""

    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        self.install('init', lint=False, editor=False)

    def snapshot(self):
        return {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()}

    def test_diff_is_silent_about_a_current_project_and_never_writes(self):
        before = self.snapshot()
        done = self.install("diff")
        self.assertIn("runtime files are identical", done.stdout)
        self.assertEqual(before, self.snapshot())

    def test_diff_exits_1_for_an_edited_or_missing_runtime_file_and_still_never_writes(self):
        (self.project / ".latex-ai/core.py").write_text("# local\n")
        (self.project / ".latex-ai/guide.py").unlink()
        before = self.snapshot()
        done = self.install("diff", "--diff", expected=1)
        self.assertIn("RUNTIME differs: .latex-ai/core.py", done.stdout)
        self.assertIn("RUNTIME missing: .latex-ai/guide.py", done.stdout)
        self.assertIn("-# local", done.stdout)
        self.assertEqual(before, self.snapshot())

    def test_diff_names_a_missing_policy_file_and_marks_one_you_extended_as_not_to_be_overwritten(self):
        (self.project / "AGENTS.md").write_text("Mine.\n")
        (self.project / ".gitignore").unlink(missing_ok=True)
        done = self.install("diff")
        self.assertIn("DIFFERS (a file you may have added to; read, do not overwrite): AGENTS.md", done.stdout)

    def test_the_options_only_init_reads_are_refused_not_ignored(self):
        for option in ("--json", "--force"):
            with self.subTest(option=option):
                done = self.install("diff", option, expected=2)
                self.assertIn("does not take", done.stdout + done.stderr)


class Runtime(ProjectCase):
    """Origin: tests/test_scope_4_3_0.py, workbench 4.3.0."""

    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        self.install('init', lint=False, editor=False)
        self.core = self.project / ".latex-ai/core.py"
        self.original = self.core.read_text(encoding="utf-8")

    def snapshot(self):
        return {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()}

    def test_runtime_restores_a_missing_runtime_file_and_records_it(self):
        self.core.unlink()
        self.install("runtime")
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)
        self.assertEqual(self.install("diff").returncode, 0)

    def test_runtime_replaces_a_file_the_record_says_the_workbench_wrote_and_backs_up_the_old_one(self):
        # Simulate an older release: its file and the record agree; this release's file differs.
        old = "# an older release\n"
        self.core.write_text(old)
        record = self.project / ".latex-ai/installation.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        data["files"][".latex-ai/core.py"] = diagnostics.sha256_text(old)
        record.write_text(json.dumps(data), encoding="utf-8")
        self.install("runtime")
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)
        backups = list((self.project / ".latex-ai/backups").glob("*/.latex-ai/core.py"))
        self.assertEqual([path.read_text(encoding="utf-8") for path in backups], [old])

    def test_runtime_reads_the_record_an_older_release_wrote(self):
        # 4.2 recorded a digest per file inside an object, with a strategy; a project made by it must not look edited.
        old = "# an older release\n"
        self.core.write_text(old)
        record = self.project / ".latex-ai/installation.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        data["files"] = {name: {"strategy": "full", "installed_sha256": digest} for name, digest in data["files"].items()}
        data["files"][".latex-ai/core.py"]["installed_sha256"] = diagnostics.sha256_text(old)
        record.write_text(json.dumps({**data, "schema_version": 2}), encoding="utf-8")
        self.install("runtime")
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)

    def test_runtime_refuses_to_overwrite_an_edited_file_unless_forced(self):
        self.core.write_text(self.original + "# local edit\n")
        before = self.snapshot()
        done = self.install("runtime", expected=2)
        self.assertIn("modified locally", done.stdout)
        self.assertIn("--force", done.stdout)
        self.assertEqual(before, self.snapshot(), "a refusal changes nothing")
        self.install("runtime", "--force")
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)
        kept = list((self.project / ".latex-ai/backups").glob("*/.latex-ai/core.py"))
        self.assertEqual([path.read_text(encoding="utf-8") for path in kept], [self.original + "# local edit\n"])

    def test_a_runtime_that_dies_half_way_is_finished_by_running_it_again(self):
        # The record is written last, so a refresh that stops after some files leaves the old record, and the files not yet
        # replaced still match it: nothing looks edited, and the second run only does what is left.
        for name in ("core.py", "guide.py", "schema.py"):
            (self.project / ".latex-ai" / name).write_text("# an older release\n")
        record = self.project / ".latex-ai/installation.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        for name in ("core.py", "guide.py", "schema.py"):
            data["files"][".latex-ai/" + name] = diagnostics.sha256_text("# an older release\n")
        record.write_text(json.dumps(data), encoding="utf-8")
        written = []

        def dies_on_the_second_file(project, name, text):
            written.append(name)
            if len(written) == 2:
                raise OSError("simulated power cut")
            return real(project, name, text)

        real = bootstrap.publish
        with patch.object(bootstrap, "publish", dies_on_the_second_file), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bootstrap.main(["runtime", str(self.project)]), 2)
        self.assertEqual(json.loads(record.read_text(encoding="utf-8")), data, "the record is written last")
        self.assertEqual(self.install("diff", expected=1).returncode, 1)
        self.install("runtime")
        self.assertEqual(self.install("diff").returncode, 0)
        self.assertEqual(self.core.read_text(encoding="utf-8"), self.original)

    def test_runtime_dry_run_writes_nothing(self):
        self.core.unlink()
        before = self.snapshot()
        done = self.install("runtime", "--dry-run")
        self.assertIn("Dry run", done.stdout)
        self.assertEqual(before, self.snapshot())

    def test_runtime_leaves_every_file_that_is_not_runtime_alone(self):
        (self.project / "AGENTS.md").write_text("Mine.\n")
        (self.project / "Makefile").write_text("pdf:\n\ttrue\n")
        (self.project / ".vscode").mkdir(exist_ok=True)
        (self.project / ".vscode/settings.json").write_text('{"editor.tabSize": 3}\n')
        self.core.unlink()
        self.install("runtime")
        self.assertEqual((self.project / "AGENTS.md").read_text(), "Mine.\n")
        self.assertEqual((self.project / "Makefile").read_text(), "pdf:\n\ttrue\n")
        self.assertEqual((self.project / ".vscode/settings.json").read_text(), '{"editor.tabSize": 3}\n')

    def test_runtime_in_a_folder_that_is_not_a_project_is_a_clean_error(self):
        empty = self.root / "empty"
        empty.mkdir()
        done = self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), "runtime", str(empty), expected=2)
        self.assertNotIn("INTERNAL ERROR", done.stdout + done.stderr)
        self.assertEqual(list(empty.iterdir()), [])

    def test_a_status_that_finds_a_changed_runtime_points_to_diff(self):
        self.core.write_text(self.original + "# local edit\n")
        text = self.command("status", expected=None).stdout
        self.assertRegex(text, r"latex-ai-init diff \. --diff")
        self.assertNotRegex(text, REMOVED_WORDS)


class Init_4_4_0(ProjectCase):
    """Origin: tests/test_scope_4_4_0.py, workbench 4.4.0."""

    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        prepare_config(self.project, lint=False, editor=True)

    def init(self, *extra, expected=0):
        return self.install('init', *extra, expected=expected, lint=False)

    def put(self, files):
        for name, text in files.items():
            (self.project / name).parent.mkdir(parents=True, exist_ok=True)
            (self.project / name).write_text(text)

    def test_init_refuses_each_file_of_the_project_that_differs_and_writes_nothing(self):
        for name, text in OWN_FILES.items():
            with self.subTest(file=name):
                self.put({name: text})
                before = self.snapshot()
                done = self.init(expected=2)
                self.assertIn(name, done.stdout)
                self.assertIn("resolve", done.stdout + done.stderr)
                self.assertEqual(before, self.snapshot())
                (self.project / name).unlink()

    def test_init_lists_every_collision_at_once(self):
        self.put(OWN_FILES)
        done = self.init(expected=2)
        for name in OWN_FILES:
            self.assertRegex(done.stdout, rf"CONFLICT: {re.escape(name)}")

    def test_init_refuses_the_other_spellings_of_a_makefile(self):
        for name in ("GNUmakefile", "makefile"):
            with self.subTest(file=name):
                self.put({name: "pdf:\n\ttrue\n"})
                before = self.snapshot()
                done = self.init(expected=2)
                self.assertIn(name, done.stdout)
                self.assertEqual(before, self.snapshot())
                (self.project / name).unlink()

    def test_a_file_that_is_already_what_init_writes_is_no_collision(self):
        self.init()
        installed = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file() and ".latex-ai/" not in p.as_posix()}
        (self.project / ".latex-ai/installation.json").unlink()
        self.init()
        self.assertEqual(installed, {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file() and ".latex-ai/" not in p.as_posix()})

    def test_the_other_files_of_a_project_are_never_touched(self):
        own = {"latexmkrc": "$pdf_mode = 1;\n", "scripts/figure.py": "print('x')\n", "README.md": "# Paper\n", "refs.bib": "@misc{k,title={T}}\n"}
        self.put(own)
        self.init()
        for name, text in own.items():
            self.assertEqual((self.project / name).read_text(), text)

    def test_a_project_s_own_make_targets_are_added_after_init_not_merged_by_it(self):
        self.init()
        makefile = self.project / "Makefile"
        text = makefile.read_text()
        makefile.write_text(text + "\n.PHONY: figures\nfigures:\n\t@echo figures\n")
        done = self.run_command("make", "figures")
        self.assertIn("figures", done.stdout)
        self.run_command("make", "help")  # and the workbench's own targets still work beside it


class ProjectMake(ProjectCase):
    """Origin: tests/test_scope_4_4_0.py, workbench 4.4.0."""

    def test_a_project_target_runs_as_an_ordinary_build_command_and_stays_incremental(self):
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        self.builder()
        self.configure({"paper": {"root": "main.tex", "lint": {"enabled": False}, "output_dir": "outputs", "build_command": ["make", "outputs/main.pdf"]}})
        self.install('init', editor=False)
        makefile = self.project / "Makefile"
        makefile.write_text(makefile.read_text() + f"\noutputs/main.pdf: main.tex builder.py\n\t@{sys.executable} builder.py\n")
        for _ in range(3):
            self.run_command("make", "check")
        self.assertEqual((self.project / "count").read_text(), "1", "Make compiled once; the receipt vouches for the runs that changed nothing")
        self.assertEqual(self.state(), "current")
        makefile.write_text(makefile.read_text() + "# the project's Make policy changed\n")
        self.assertEqual(self.state(), "stale", "the Makefile is an input of a build that runs through it")

    def test_make_s_dry_run_question_and_touch_modes_run_nothing(self):
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        self.builder()
        self.configure()
        self.install('init', editor=False)
        for mode in ("-n", "-q", "-t"):
            with self.subTest(mode=mode):
                self.run_command("make", mode, "check", expected=None)
                self.assertFalse((self.project / "count").exists())
                self.assertFalse((self.project / ".latex-ai/artifacts/documents").exists())

    def test_validate_still_runs_the_project_s_own_check(self):
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        self.configure()
        self.install('init', editor=False)
        makefile = self.project / "Makefile"
        template = makefile.read_text()
        self.assertFalse(guide.project_check_rule(self.project), "the Makefile as init wrote it has no check of the project's")
        for label, extra in (("a prerequisite", "\ncheck: my-tests\nmy-tests:\n\t@true\n"), ("a second recipe", "\ncheck::\n\t@echo mine\n"),
                             ("an include", "\n-include extra.mk\n")):
            with self.subTest(label):
                makefile.write_text(template + extra)
                self.assertTrue(guide.project_check_rule(self.project))
        makefile.write_text(template + "\n.PHONY: figures\nfigures:\n\t@true\n")
        self.assertFalse(guide.project_check_rule(self.project), "a target that is not check does not make validate conservative")


class RuntimeApartFromProjectFiles(ProjectCase):
    """Origin: tests/test_scope_4_4_1.py, workbench 4.4.1."""

    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE_4_3_0)
        self.configure()
        self.install("init")

    def cli(self, *args, **choices):
        prepare_config(self.project, **choices)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = bootstrap.main([*args, str(self.project)])
        return status, out.getvalue()

    def test_the_runtime_files_are_the_packages_own_files_for_the_modules_in_use(self):
        for config in CONFIGS:
            with self.subTest(config=config):
                expected = {".latex-ai/" + target: (PACKAGE / source).read_text(encoding="utf-8")
                            for source, target in core.runtime_sources(core.effective_config(config)).items()}
                self.assertTrue(expected)
                self.assertEqual(bootstrap.runtime_files(config), expected)
                self.assertEqual(list(bootstrap.runtime_files(config)), list(expected))  # init and diff print in this order
                self.assertEqual({name: text for name, text in bootstrap.desired_files(config).items() if name.startswith(".latex-ai/")}, expected)

    def test_refreshing_the_runtime_renders_no_project_file(self):
        (self.project / ".latex-ai/guide.py").unlink()
        render = AssertionError("runtime must not render the policy, Makefile and editor files")
        with patch.object(bootstrap, "desired_files", side_effect=render):
            status, text = self.cli("runtime")
        self.assertEqual(status, 0, text)
        self.assertIn("CREATE: .latex-ai/guide.py", text)
        self.assertEqual((self.project / ".latex-ai/guide.py").read_text(), (PACKAGE / "guide.py").read_text())
        self.assertEqual(self.cli("diff")[0], 0)

    def test_diff_renders_once(self):
        with patch.object(bootstrap, "desired_files", wraps=bootstrap.desired_files) as spy:
            status, text = self.cli("diff")
        self.assertEqual(status, 0, text)
        self.assertEqual(spy.call_count, 1)

    def test_diff_still_reports_a_missing_and_a_changed_runtime_file(self):
        (self.project / ".latex-ai/guide.py").unlink()
        changed = self.project / ".latex-ai/core.py"
        changed.write_text(changed.read_text() + "# edited\n")
        status, text = self.cli("diff", "--diff")
        self.assertEqual(status, 1, text)
        lines = text.splitlines()
        self.assertEqual([line for line in lines if line.startswith("RUNTIME")],
                         ["RUNTIME differs: .latex-ai/core.py", "RUNTIME missing: .latex-ai/guide.py"] if lines.index("RUNTIME differs: .latex-ai/core.py") < lines.index("RUNTIME missing: .latex-ai/guide.py")
                         else ["RUNTIME missing: .latex-ai/guide.py", "RUNTIME differs: .latex-ai/core.py"])
        self.assertTrue(lines[-1].endswith("2 runtime file(s) differ."), lines[-1])
        self.assertIn("-# edited", text)

    def test_the_schema_errors_name_the_current_workbench(self):
        with self.assertRaisesRegex(core.WorkbenchError, r"^Workbench 5 supports only project configuration schema 4 \(this file declares 2\)"):
            schema.validate_config(self.project, {'schema_version': 2})
        with self.assertRaisesRegex(core.WorkbenchError, r"^Workbench 5 supports only project configuration schema 4$"):
            schema.document_settings({'schema_version': 2})


class WhatStays(ProjectCase):
    """Origin: tests/test_scope_4_5_0.py, workbench 4.5.0."""

    def setUp(self):
        super().setUp()
        (self.project / "main.tex").write_text(SOURCE_4_3_0)

    def test_only_pdflatex_and_bibtex_are_accepted_and_the_refusal_says_where_to_go(self):
        for name, config, word, in_hint in REFUSED:
            with self.subTest(refused=name):
                with self.assertRaises(core.WorkbenchError) as raised:
                    schema.validate_config(self.project, config)
                self.assertIn(word, str(raised.exception))
                self.assertIn(in_hint, raised.exception.hint or "")
        for config in ACCEPTED:
            with self.subTest(accepted=json.dumps(config)):
                schema.validate_config(self.project, config)

    def test_the_installed_runtime_refuses_such_a_configuration_by_name(self):
        self.install('init', editor=False)
        self.edit_config(lambda data: data["documents"]["manuscript"].update(engine="xelatex"))
        result = self.command("check", expected=1)
        self.assertIn("xelatex", result.stderr)
        self.assertIn("build_command", result.stderr)

    def test_status_and_help_say_what_to_edit_when_the_configuration_is_refused(self):
        """After an upgrade the first command is `make status`; it must carry the hint, not point at a last good copy that is the same configuration."""
        self.install('init', editor=False)
        self.edit_config(lambda data: data["documents"]["manuscript"].update(engine="xelatex"))
        for action in ("status", "help", "guide"):
            with self.subTest(action=action):
                text = self.command(action).stdout
                self.assertIn("engine 'xelatex' is not supported", text)
                self.assertIn("edit .latex-ai.json: remove the engine setting", text)
        (self.project / core.CONFIG).write_text("{")  # a problem that carries no hint of its own keeps the old advice
        self.assertIn("version control has the last good copy", self.command("status").stdout)

    def init_project(self, name, source, *options):
        """`init` in a fresh folder holding one manuscript; returns the folder's configuration."""
        folder = self.root / name
        folder.mkdir()
        (folder / "main.tex").write_text(source)
        (folder / "refs.bib").write_text("@misc{fixture, title={Synthetic fixture}}\n")
        self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), "init", *options, str(folder))
        return json.loads((folder / core.CONFIG).read_text())


    def test_the_default_build_asks_latexmk_for_pdf_output(self):
        self.install('init', editor=False)
        view = schema.document_settings(schema.load_config(self.project))
        commands = []
        with patch.object(latex, "run_compiler", lambda project, config, command, **kw: commands.append(command)):
            latex.compile_document(self.project, view)
        self.assertEqual(commands[0][:2], ["latexmk", "-pdf"])


class Generated(ProjectCase):
    """Origin: tests/test_scope_4_6_0.py, workbench 4.6.0."""

    def test_every_project_gets_the_fixed_all_recipe(self):
        for names in (("paper",), ("paper", "notes")):
            text = makefile(configuration_4_6_0(*names))
            self.assertEqual(rules(text)["all"], ['@$(PYTHON) .latex-ai/workbench.py build --all'])

    def test_bare_make_still_builds_the_default_document(self):
        self.assertIn(".DEFAULT_GOAL := build", makefile(configuration_4_6_0("paper", "notes", default="notes")))


    def test_a_project_with_one_document_gets_none(self):
        self.assertEqual(set(rules(makefile(configuration_4_6_0("manuscript")))) & {"manuscript"}, set())


    def test_the_registry_knows_all(self):
        target = next(t for t in commands.BY_NAME["build"].targets if t.short == "all")
        self.assertEqual(target.selects, "all")
        self.assertIn("all", commands.RECURSIVE_GOALS)


class AuditRepairs(ProjectCase):
    """Origin: tests/test_scope_4_8_1.py, workbench 4.8.1."""

    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE_4_8_1)

    def test_f6_commented_bibliography_after_linebreak_does_not_block_init(self):
        (self.project / 'main.tex').write_text(SOURCE_4_8_1.replace('Fixture.', 'Text.\\\\% \\bibliography{missing}\nMore.'))
        self.install('init', lint=False, editor=False)
        self.assertEqual(schema.document_settings(schema.load_config(self.project)).bibliography['backend'], 'none')


class Recipe(unittest.TestCase):
    """Origin: tests/test_scope_4_9_0.py, workbench 4.9.0."""

    def recipe(self):
        return re.search(r"^## Update\n(.*?)(?=^## |\Z)", SKILL.read_text(encoding="utf-8"), re.S | re.M)[1]

    def test_the_skill_holds_the_whole_recipe_in_order_and_starts_with_a_snapshot(self):
        text = self.recipe()
        steps = dict(re.findall(r"^(\d)\. (.*?)(?=^\d\. |^Never delete|\Z)", text, re.S | re.M))
        self.assertEqual(sorted(steps), list("1234567"))
        for number, words in {"1": ["make snapshot"], "2": ["make doctor", "releases.md"], "3": ["latex-ai-init diff", "LATEX_AI_TEMPLATE"], "4": ["latex-ai-init runtime", "--dry-run"],
                              "5": ["AGENTS.md", "stricter"], "6": [".latex-ai.json"], "7": ["make doctor LATEX_AI_TEMPLATE", "make check", "git diff"]}.items():
            for word in words:
                self.assertIn(word, steps[number], f"step {number} lacks {word}")

    def test_upgrading_md_points_at_the_recipe_and_keeps_to_what_a_person_needs(self):
        text = (PACKAGE / "docs/upgrading.md").read_text(encoding="utf-8")
        self.assertIn("skills/latex-ai-workbench/references/installation.md", text)
        for word in ("diff", "runtime", "releases.md", "make check", "snapshot", "make doctor"):
            self.assertIn(word, text)
        self.assertLessEqual(len(text.splitlines()), 45)


class WorkbenchTests(unittest.TestCase):
    """Origin: tests/test_workbench.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="latex-ai-unit-")
        self.project = Path(self.temp.name).resolve()
        (self.project / "paper.tex").write_text(TEX)
        prepare_config(self.project, root="paper.tex", output_dir=".", editor=True)

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

    def test_dry_run_never_writes(self):
        before = self.snapshot()
        self.assertEqual(self.cli("init", "--dry-run"), 0)
        self.assertEqual(before, self.snapshot())

    def test_a_second_init_is_refused_and_writes_nothing(self):
        self.init()
        before = self.snapshot()
        self.assertEqual(self.cli("init"), 2)
        self.assertEqual(before, self.snapshot())


    def test_backup_symlink_escape_refused(self):
        self.init()
        with tempfile.TemporaryDirectory(prefix="latex-ai-external-") as directory:
            (self.project / ".latex-ai/backups").symlink_to(directory)
            with self.assertRaises(rt.WorkbenchError):
                boot.apply(self.project, [{"path": "AGENTS.md", "before": (self.project / "AGENTS.md").read_text(), "after": "New"}])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_conflicting_editor_item_refuses_all_writes(self):
        path = self.project / ".vscode/tasks.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"tasks": [{"label": "Build: manuscript", "command": "custom"}]}))
        before = self.snapshot()
        self.assertEqual(self.cli("init"), 2)
        self.assertEqual(before, self.snapshot())
        config = rt.load_config(self.project)
        config["integrations"]["editor"] = False
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.assertEqual(self.cli("init"), 0)

    def test_jsonc_preserved(self):
        path = self.project / ".vscode/settings.json"
        path.parent.mkdir()
        content = '{\n// Local comment\n"editor.tabSize": 4,\n}\n'
        path.write_text(content)
        self.assertEqual(self.cli("init"), 2)
        config = rt.load_config(self.project)
        config["integrations"]["editor"] = False
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.assertEqual(self.cli("init"), 0)
        self.assertEqual(path.read_text(), content)

    def test_modified_runtime_is_not_overwritten_without_force(self):
        self.init()
        path = self.project / ".latex-ai/workbench.py"
        original = path.read_text()
        path.write_text(original + "\n# user edit\n")
        before = self.snapshot()
        self.assertEqual(self.cli("runtime"), 2)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.cli("diff"), 1)  # and diff says so
        self.assertEqual(self.cli("runtime", "--force"), 0)
        self.assertEqual(path.read_text(), original)
        self.assertEqual(self.cli("diff"), 0)

    def test_malformed_document_configuration_is_reported_never_crashes(self):
        self.init()
        base = rt.load_config(self.project)
        base["bibliography"] = {"files": [], "export": {"path": "zotero.bib", "required": False, "format": "bibtex"}}
        gone = object()
        tex = ("documents", "manuscript")
        bib = ("bibliography",)
        cases = [(tex + ("root",), gone), (tex + ("engine",), []), (tex + ("engine",), {}),
                 (tex + ("backend",), []), (tex + ("backend",), {}),
                 (bib + ("export",), {}), (bib + ("export", "format"), []),
                 (bib + ("export", "format"), {}), (bib + ("export", "path"), gone)]
        for path, value in cases:
            config = json.loads(json.dumps(base))
            parent = config
            for step in path[:-1]:
                parent = parent[step]
            if value is gone:
                del parent[path[-1]]
            else:
                parent[path[-1]] = value
            with self.subTest(path=path, value=value), self.assertRaises(rt.WorkbenchError):
                schema.validate_config(self.project, config)

    def test_changed_guardrail_preserved(self):
        path = self.project / ".claude/settings.json"
        path.parent.mkdir()
        path.write_text('{"permissions":{"deny":["Bash(*)"]}}')
        before = self.snapshot()
        self.assertEqual(self.cli("init"), 2)
        self.assertEqual(before, self.snapshot())

    def test_symlink_destination_refused(self):
        target = self.project / "own-policy.md"
        target.write_text("Policy")
        (self.project / "AGENTS.md").symlink_to(target)
        before = target.read_text()
        self.assertEqual(self.cli("init"), 2)
        self.assertEqual(target.read_text(), before)

    def test_path_escape_refused(self):
        with self.assertRaises(rt.WorkbenchError):
            rt.local_path(self.project, "../outside.tex")

    def test_concurrent_edit_refuses_writes(self):
        path = self.project / "AGENTS.md"
        path.write_text("User changed this")
        with self.assertRaises(rt.WorkbenchError):
            boot.apply(self.project, [{"path": "AGENTS.md", "before": "Old", "after": "New"}])
        self.assertEqual(path.read_text(), "User changed this")


if __name__ == "__main__":
    generate() if "--generate" in sys.argv else unittest.main()
