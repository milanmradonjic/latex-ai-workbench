"""Tests of contracts between components: the command registry, import layering, one table for each fact, the repository's own workflows.

Regrouped by component in step 3.8 of docs/maintainers/plan-after-4.4.0.md from 5 older test files; each class says which one, and the release it came with.
What each of those files said of itself:

test_architecture.py:
Cross-component contracts: identities, evidence, execution and recovery.

test_commands_registry.py:
Phase 1 of the plan after 3.0.2: one registry (commands.py) holds what six tables used to say about each action.

test_modules.py:
(no docstring)

test_repairs_3_5_0.py:
3.5.0, kept in 4.1.0: the GitHub actions this repository's workflows run are pinned to the commit their tag pointed to,
with the tag in a comment.

A tag such as `actions/checkout@v7` is resolved again on every run, so a moved or hijacked tag would change what CI
executes, with the repository's checkout and its token in reach. A commit cannot move. (Until 4.0 the workbench also
generated workflows for the projects it installed, and pinned those; it no longer does.)

test_review_fixes.py:
Regressions for the architecture review's installed workflow failures.
"""

import ast
import contextlib
import inspect
import io
import json
import os
import re
import shutil
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
import commands
import core
import guide
import latex
import runtime
import runtime as rt
import schema
from test_support import isolate_environment


REPOSITORY = Path(__file__).resolve().parents[2]


PINNED = re.compile(r"^\s*(?:- )?uses: [A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40} # v\d+(?:\.\d+)*$")


USES = re.compile(r"^\s*(?:- )?uses: (?!\./)")


def unpinned(text):
    return [line.strip() for line in text.split("\n") if USES.match(line) and not PINNED.match(line)]


class ArchitectureTests(unittest.TestCase):
    """Origin: tests/test_architecture.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-contract-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def test_custom_noop_cannot_validate_old_artifacts(self):
        p = self.project
        (p / "main.tex").write_text("\\undefinedcommand")
        (p / "main.pdf").write_bytes(b"%PDF-old")
        (p / "main.log").write_text("old successful log")
        config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'build_command': [sys.executable, '-c', 'pass'], 'lint': {'enabled': False}, 'output_dir': '.'}}}}}
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(core.WorkbenchError, "freshness|rewrit|receipt"):
            rt.full_check(p, config)

    def test_verified_custom_build_reuse_and_invalidation(self):
        p = self.project
        (p / "main.tex").write_text("source")
        (p / "builder.py").write_text("from pathlib import Path\nimport sys\nif 'broken' in Path('main.tex').read_text(): sys.exit(1)\n"
                                      "if not Path('main.pdf').exists():\n Path('main.pdf').write_bytes(b'%PDF-' + Path('main.tex').read_bytes())\n Path('main.log').write_text('successful fixture')\n")
        config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'build_command': [sys.executable, 'builder.py'], 'lint': {'enabled': False}, 'output_dir': '.'}}}}}
        with contextlib.redirect_stdout(io.StringIO()):
            latex.build(p, schema.document_settings(config))
            latex.build(p, schema.document_settings(config))  # a verified incremental no-op is legitimate
            (p / "main.tex").write_text("changed source")
            with self.assertRaises(core.WorkbenchError):
                latex.verify(p, schema.document_settings(config))
            # The incremental builder keeps its stale PDF; the workbench certifies only a regenerated one.
            latex.build(p, schema.document_settings(config))
            self.assertEqual((p / "main.pdf").read_bytes(), b"%PDF-changed source")
            latex.verify(p, schema.document_settings(config))
            (p / "main.tex").write_text("broken")
            with self.assertRaises(core.WorkbenchError):
                latex.build(p, schema.document_settings(config))
            # Restoring the old input does not revive the receipt of a failed attempt:
            # the old PDF is certified only after it is produced again.
            (p / "main.tex").write_text("changed source")
            with self.assertRaises(core.WorkbenchError):
                latex.verify(p, schema.document_settings(config))
            os.utime(p / "main.pdf")
            latex.build(p, schema.document_settings(config))
            self.assertFalse((p / ".latex-ai/artifacts/unverified/manuscript/main.pdf").exists())

    def test_effective_config_keeps_persisted_schema_and_module_defaults(self):
        persisted = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'engine': 'pdflatex', 'output_dir': '.'}}}}}
        before = json.dumps(persisted)
        effective = core.effective_config(persisted)
        self.assertEqual(effective["schema_version"], 3)
        self.assertEqual(effective, core.effective_config(effective))
        self.assertEqual(json.dumps(persisted), before)
        self.assertIn("latex.py", core.runtime_sources(effective))

    def test_bibliography_alias_selects_standalone_validation(self):
        (self.project / "refs.bib").write_text("@misc{fixture, title={Synthetic fixture}}")
        config = {'schema_version': 3, 'modules': {'bibliography': {'files': ['./refs.bib']}}}
        self.assertTrue(rt.validation_plan(self.project, config, ["refs.bib"])["bibliography"])

    def test_reference_matches_distribution(self):
        reference = boot.PACKAGE.parent
        if not (reference / boot.STATE).is_file():
            self.skipTest("standalone distribution has no installed reference")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = boot.main(["diff", str(reference)])
        self.assertEqual(result, 0, output.getvalue())  # the runtime files are this release's
        config = schema.load_config(reference)
        wanted = boot.desired_files(config, reference)
        for name in ("AGENTS.md", "CLAUDE.md", "Makefile"):  # the files the reference may add to, but must still contain
            self.assertIn(wanted[name], (reference / name).read_text(encoding="utf-8"), name)

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex"), "needs real latexmk/pdfLaTeX")
    def test_real_custom_compiler_receipt_and_incremental_build(self):
        p = self.project
        source = p / "main.tex"
        source.write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'build_command': ['latexmk', '-pdf', '-recorder', '-interaction=nonstopmode', '-halt-on-error', 'main.tex'], 'lint': {'enabled': False}, 'output_dir': '.'}}}}}
        with contextlib.redirect_stdout(io.StringIO()):
            latex.build(p, schema.document_settings(config))
            latex.build(p, schema.document_settings(config))
            latex.verify(p, schema.document_settings(config))
            source.write_text(source.read_text().replace("Fixture", "\\undefinedcommand"))
            with self.assertRaises(core.WorkbenchError):
                latex.build(p, schema.document_settings(config))
            with self.assertRaises(core.WorkbenchError):
                latex.verify(p, schema.document_settings(config))

    def test_explicit_build_inputs_are_not_hidden_by_generated_suffixes(self):
        (self.project / "main.tex").write_text("source")
        (self.project / "data.log").write_text("one")
        config = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'output_dir': '.'}}}}, 'validation': {'manuscript_inputs': ['data.log']}}
        before = latex.build_inputs(self.project, schema.document_settings(config))
        (self.project / "data.log").write_text("two")
        self.assertNotEqual(before, latex.build_inputs(self.project, schema.document_settings(config)))


class ImportLayering(unittest.TestCase):
    """Phase 2: the runtime modules sit in layers, so none needs a function-local import to dodge a cycle.

    Origin: tests/test_architecture.py.
    """

    @classmethod
    def setUpClass(cls):
        cls.package = Path(__file__).resolve().parents[1]
        cls.modules = sorted(name[:-3] for name in core.RUNTIME_FILES if name.endswith(".py"))
        cls.graph = {module: cls.imports(cls.package, module, cls.modules) for module in cls.modules}

    @staticmethod
    def imports(package, module, known):
        """The workbench modules one module imports anywhere, function-local imports included, with their lines."""
        tree = ast.parse((package / f"{module}.py").read_text(encoding="utf-8"))
        found = {}
        for node in ast.walk(tree):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
            for name in names:
                if name.split(".")[0] in known and name.split(".")[0] != module:
                    found.setdefault(name.split(".")[0], []).append(node.lineno)
        return found

    def test_every_module_imports_on_its_own(self):
        for module in self.modules:
            with self.subTest(module=module):
                done = subprocess.run([sys.executable, "-B", "-I", "-c", f"import sys; sys.path.insert(0, {str(self.package)!r}); import {module}"],
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)

    def test_the_import_graph_has_no_cycle(self):
        """Static, so a function-local import that closes a cycle counts too (`import` at module level alone never showed it)."""
        index, low, on, stack, cycles, counter = {}, {}, set(), [], [], [0]

        def visit(node):
            index[node] = low[node] = counter[0]
            counter[0] += 1
            stack.append(node)
            on.add(node)
            for other in self.graph[node]:
                if other not in index:
                    visit(other)
                    low[node] = min(low[node], low[other])
                elif other in on:
                    low[node] = min(low[node], index[other])
            if low[node] == index[node]:
                group = []
                while True:
                    member = stack.pop()
                    on.discard(member)
                    group.append(member)
                    if member == node:
                        break
                if len(group) > 1:
                    cycles.append(sorted(group))

        for module in self.modules:
            if module not in index:
                visit(module)
        edges = {m: {o: lines for o, lines in self.graph[m].items() if o in group} for group in cycles for m in group}
        self.assertEqual(cycles, [], f"import cycle among {cycles}; edges (module: imported: lines) {edges}")

    def test_function_local_imports_name_only_modules_that_not_every_project_has(self):
        """A lazy import of a module every project installs dodges nothing now that the graph has no cycle; one of
        an optional module (latex, documents, output_transaction) is how an absent module stays absent."""
        always = {name[:-3] for name in core.runtime_sources({"schema_version": 3, "modules": {}}) if name.endswith(".py")}
        offenders = []
        for module in self.modules:
            tree = ast.parse((self.package / f"{module}.py").read_text(encoding="utf-8"))
            top = {id(node) for node in tree.body}
            for node in ast.walk(tree):
                if id(node) in top or not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module] if node.level == 0 and node.module else []
                offenders += [f"{module}.py:{node.lineno} imports {name} inside a function" for name in names if name.split(".")[0] in always]
        self.assertEqual(offenders, [])

    def test_core_and_schema_sit_at_the_bottom(self):
        """core imports only processes; schema, the validated configuration and its documents, only core and the command registry,
        and those two only core."""
        self.assertLessEqual(set(self.graph["core"]), {"processes"})
        self.assertLessEqual(set(self.graph["schema"]), {"core", "commands"})
        self.assertLessEqual(set(self.graph["commands"]), {"core"})


class CommandRegistry(unittest.TestCase):
    """Origin: tests/test_commands_registry.py."""

    def test_every_action_has_exactly_one_handler_and_no_handler_is_left_over(self):
        names = [action.name for action in commands.ACTIONS]
        self.assertEqual(len(names), len(set(names)))
        defined = {name for name, value in vars(runtime).items() if name.startswith("do_") and callable(value)}
        self.assertEqual({action.handler for action in commands.ACTIONS}, defined)
        self.assertEqual(set(runtime.HANDLERS), set(names))

    def test_dispatch_is_a_lookup_not_a_chain_of_branches(self):
        source = inspect.getsource(runtime.dispatch)
        self.assertNotIn("elif", source)
        self.assertIsNone(re.search(r"args\.action\s*(==|!=|in\b|not in\b)", source))

    def test_the_argument_parser_offers_exactly_the_registered_actions(self):
        help_text = subprocess.run([sys.executable, "-B", str(PACKAGE / "runtime.py"), "--help"], capture_output=True, text=True, check=True).stdout
        choices = [set(group.split(",")) for group in re.findall(r"\{([^}]*)\}", help_text)]  # the actions are the choices that include `check`; an option may have choices of its own
        self.assertIn(set(commands.NAMES), choices)
        self.assertEqual([group for group in choices if "check" in group], [set(commands.NAMES)] * len([group for group in choices if "check" in group]))
        self.assertEqual(runtime.ACTIONS, commands.NAMES)

    def test_the_names_shown_to_readers_are_derived_not_restated(self):
        self.assertIs(guide.COMMANDS, commands.COMMANDS)
        reserved = [command.reserved for command in commands.COMMANDS if command.reserved]
        self.assertEqual(len(reserved), len(set(reserved)))
        shorts = [command.short for command in commands.COMMANDS]
        self.assertEqual(len(shorts), len(set(shorts)))

    def test_the_flags_of_an_action_agree_with_each_other(self):
        for action in commands.ACTIONS:
            with self.subTest(action=action.name):
                if action.standalone:
                    self.assertIsNone(action.module, "a standalone action reads no configuration, so it cannot require a module")
                if action.view:
                    self.assertEqual(action.module, "latex", "only a LaTeX document has a view of the configuration")
                for target in action.targets:
                    self.assertIn(target.selects, commands.RECIPE_ARGUMENTS)
                    if target.selects == "document":
                        self.assertTrue(action.document, "a recipe cannot pass DOC to an action that refuses --document")
                    if target.usage:
                        self.assertEqual(target.usage.split("=")[0], {"document": "DOC", "task": "TASK"}[target.selects])

    def test_json_output_is_native_only_where_the_commands_always_printed_their_own(self):
        self.assertEqual({action.name for action in commands.ACTIONS if action.native_json}, {"plan", "modules"})

    def test_every_installed_runtime_carries_the_registry(self):
        self.assertIn("commands.py", core.RUNTIME_FILES)
        for modules in ({}, {"latex": {"default_document": "paper", "documents": {"paper": {"root": "main.tex"}}}}, {"bibliography": {}}):
            with self.subTest(modules=sorted(modules)):
                self.assertIn("commands.py", core.runtime_sources({"schema_version": 3, "modules": modules}))


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

    def command(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-B", str(self.project / ".latex-ai/workbench.py"), *args],
                                cwd=self.project, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    PAPER = "\\documentclass{article}\n\\begin{document}\nx\n\\end{document}\n"

    def fresh_project(self):
        shutil.rmtree(self.project)
        self.project.mkdir()

    def test_one_command_table_drives_targets_actions_and_every_name_shown_to_readers(self):
        reserved = {command.reserved for command in guide.COMMANDS if command.reserved}
        self.assertEqual({command.action.split()[0] for command in guide.COMMANDS if command.action} - set(rt.ACTIONS), set())
        self.assertEqual(len(reserved), sum(1 for command in guide.COMMANDS if command.reserved))  # no reserved name twice
        # Internal targets of adapted Makefiles are the only latex-ai- names outside the table.
        internal = {"latex-ai-integrity", "latex-ai-core-check", "latex-ai-check-passed"}
        texts = {"full policy": (boot.PACKAGE / "templates/AGENTS.md").read_text(),
                 "skill": (boot.PACKAGE / "skills/latex-ai-workbench/SKILL.md").read_text()}
        texts.update({"docs/" + path.name: path.read_text() for path in sorted((boot.PACKAGE / "docs").glob("*.md"))})
        texts["README"] = (boot.PACKAGE / "README.md").read_text()
        for name, text in texts.items():
            with self.subTest(text=name):
                self.assertEqual(set(re.findall(r"\bmake (latex-ai-[a-z-]+)", text)) - reserved - internal, set())
        # The Makefile of every starting set of modules holds exactly the reserved targets they enable.
        for modules in ("", "latex"):
            with self.subTest(modules=modules):
                self.fresh_project()
                (self.project / "main.tex").write_text(self.PAPER)
                self.assertEqual(self.cli("init", "--modules", modules), 0)
                config = schema.load_config(self.project)
                targets = guide.make_targets((self.project / "Makefile").read_text())
                expected = {command.reserved for command in guide.COMMANDS if command.reserved and guide.enabled(command, config)}
                self.assertEqual({name for name in targets if name.startswith("latex-ai-")} - internal, expected)
                self.assertEqual({command.short for command in guide.COMMANDS if command.reserved and guide.enabled(command, config)} - targets, set())  # and every alias


class PinnedActions(unittest.TestCase):

    """Origin: tests/test_repairs_3_5_0.py, workbench 3.5.0."""

    def test_the_workflows_of_this_repository_are_pinned_too(self):
        folder = REPOSITORY / ".github" / "workflows"
        if not folder.is_dir():
            self.skipTest("a standalone distribution carries no workflows of its own")
        files = sorted(folder.glob("*.yml"))
        self.assertTrue(files)
        for path in files:
            with self.subTest(workflow=path.name):
                self.assertEqual(unpinned(path.read_text(encoding="utf-8")), [])

    def test_dependabot_keeps_the_pins_of_this_repository_current(self):
        path = REPOSITORY / ".github" / "dependabot.yml"
        if not path.parent.is_dir():
            self.skipTest("a standalone distribution carries no workflows of its own")
        text = path.read_text(encoding="utf-8")
        self.assertRegex(text, r"package-ecosystem: [\"']?github-actions[\"']?")
        self.assertRegex(text, r"directory: [\"']?/[\"']?")


class ReviewFixes(unittest.TestCase):
    """Origin: tests/test_review_fixes.py."""

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-review-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def test_portability_preflight_has_a_report_without_a_traceback(self):
        tools = self.project / "tools"; tools.mkdir()
        result = subprocess.run([sys.executable, str(bootstrap.PACKAGE / "tests/portability.py"),
                                 "--output-parent", str(self.project)], env={**os.environ, "PATH": str(tools)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing tools:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        report = json.loads(next(self.project.glob("latex-ai-portability-*/report.json")).read_text())
        self.assertEqual(report["status"], "blocked")
        self.assertIn("chktex", report["missing_tools"])


if __name__ == "__main__":
    unittest.main()
