"""Cross-component contracts: identities, evidence, execution and recovery."""
import ast
import contextlib
import io
import json
import os
import re
import shlex
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_support import isolate_environment
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap as boot
import core
import schema
import latex
import runtime as rt


class ArchitectureTests(unittest.TestCase):
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
    """Phase 2: the runtime modules sit in layers, so none needs a function-local import to dodge a cycle."""

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


if __name__ == "__main__":
    unittest.main()
