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
import adapters
import bootstrap as boot
import installation
import core
import schema
import latex
import research
import runtime as rt


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-contract-")
        self.project = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def test_path_aliases_propagate_staleness_and_select_checks(self):
        p = self.project
        (p / "params").write_text("one")
        (p / "producer.py").write_text("from pathlib import Path\nPath('result').write_text(Path('params').read_text())\n")
        (p / "consumer.py").write_text("from pathlib import Path\nPath('figure').write_text(Path('result').read_text())\n")
        config = {'schema_version': 3, 'modules': {'numerics': {}, 'provenance': {}, 'freshness': {}}}
        tasks = {"producer": {"command": [sys.executable, "producer.py"], "inputs": ["./params"], "outputs": ["result"]},
                 "consumer": {"command": [sys.executable, "consumer.py"], "inputs": ["./result"], "outputs": ["figure"]}}
        (p / "experiments.json").write_text(json.dumps({"schema_version": 1, "tasks": tasks}))
        with contextlib.redirect_stdout(io.StringIO()):
            for name in tasks:
                research.execute(p, config, "numerics", name)
        (p / "params").write_text("two")
        report = research.freshness(p, config)
        self.assertEqual([r["status"] for r in report], ["stale", "stale"])
        self.assertEqual(research.affected(p, config, ["params"]), ["freshness", "numerics"])

    def test_input_output_aliases_and_duplicate_producers_are_rejected(self):
        p = self.project
        (p / "result").write_text("original")
        (p / "alias").symlink_to("result")
        os.link(p / "result", p / "hardlink")
        for name in ("./result", "alias", "hardlink"):
            with self.subTest(name=name), self.assertRaises(core.WorkbenchError):
                research.checked_tasks(p, {}, {"schema_version": 1, "tasks": {
                    "bad": {"command": ["true"], "inputs": [name], "outputs": ["result"]}}})
        config = {'schema_version': 3, 'modules': {'numerics': {}, 'provenance': {}, 'freshness': {}}}
        (p / "input").write_text("input")
        task = {"command": ["true"], "inputs": ["input"], "outputs": ["result"]}
        (p / "experiments.json").write_text(json.dumps({"schema_version": 1, "tasks": {
            "a": task, "b": {**task, "outputs": ["./result"]}}}))
        with self.assertRaisesRegex(core.WorkbenchError, "Multiple producers"):
            research.freshness(p, config)

    def test_root_aliases_are_configuration_errors(self):
        for module, values in (("notes", {"path": "./"}), ("markdown", {"files": ["."]})):
            with self.subTest(module=module), self.assertRaises(core.WorkbenchError):
                schema.validate_config(self.project, {'schema_version': 3, 'modules': {module: values}})

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

    def test_installation_recovers_after_process_death(self):
        p = self.project
        (p / "existing").write_text("before")
        updates = [{"path": "existing", "before": "before", "after": "after"},
                   {"path": "new", "before": None, "after": "new contents"}]
        code = """import sys, json, os
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import bootstrap as boot
import installation
real = installation.atomic_write
def crash(path, text):
    real(path, text)
    if path == Path(sys.argv[2]) / 'existing': os._exit(91)
installation.atomic_write = crash
boot.apply(Path(sys.argv[2]), json.loads(sys.argv[3]))
"""
        result = subprocess.run([sys.executable, "-B", "-c", code, str(boot.PACKAGE), str(p), json.dumps(updates)])
        self.assertEqual(result.returncode, 91)
        self.assertEqual((p / "existing").read_text(), "after")
        self.assertTrue((p / ".latex-ai/transaction.json").exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(boot.main(["recover", str(p)]), 0)
        self.assertEqual((p / "existing").read_text(), "before")
        self.assertFalse((p / "new").exists())
        self.assertFalse((p / ".latex-ai/transaction.json").exists())

    def test_recovery_preserves_edits_made_after_interruption(self):
        p = self.project
        (p / "existing").write_text("before")
        real = installation.atomic_write
        def crash(path, text):
            real(path, text)
            if path == p / "existing":
                raise SystemExit(91)
        # Simulate failure of both application and rollback, retaining the journal.
        with patch.object(installation, "atomic_write", side_effect=crash):
            with self.assertRaises(BaseException):
                boot.apply(p, [{"path": "existing", "before": "before", "after": "after"}])
        (p / "existing").write_text("user edit")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertNotEqual(boot.main(["recover", str(p)]), 0)
        self.assertEqual((p / "existing").read_text(), "user edit")


    def test_profiles_share_local_and_ci_validation_actions(self):
        p = self.project
        (p / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Fixture\\end{document}\n")
        (p / "AGENTS.md").write_text("Policy")
        (p / "CLAUDE.md").write_text("See AGENTS.md")
        (p / "README.md").write_text("Notes")
        for profile, modules in core.PROFILES.items():
            with self.subTest(profile=profile):
                config = {'schema_version': 3, 'modules': {name: {} for name in modules}, 'integrations': {'ci': {'enabled': True}}}
                if "latex" in modules:
                    config["modules"]["latex"] = {"default_document": "manuscript", "documents": {"manuscript": {"root": "main.tex"}}}
                for name in ("numerics", "figures"):
                    if name in modules:
                        manifest = p / core.module_config(config, name)["manifest"]
                        manifest.parent.mkdir(parents=True, exist_ok=True)
                        manifest.write_text(json.dumps({"schema_version": 1, "tasks": {}}))
                (p / core.CONFIG).write_text(json.dumps(config))
                workflow = boot.workflow(config)
                supported = set(re.findall(r"outputs.check_([a-z]+)", workflow))
                for paths in (["README.md"], ["Makefile"]):
                    plan = rt.validation_plan(p, config, paths)
                    self.assertLessEqual(set(plan["actions"]), supported)
                    order = list(dict.fromkeys(re.findall(r"outputs.check_([a-z]+)", workflow)))
                    # Container's outer gate mentions both flags before its actual commands.
                    if "portability" in order and "full" in order and "latex" in modules:
                        order = [name for name in order if name not in {"portability", "full"}] + ["portability", "full"]
                    self.assertEqual([name for name in order if name in plan["actions"]], plan["actions"])
                    for name in plan["actions"]:
                        self.assertIn(adapters.ci_command(name, config), workflow)
                    output = p / "github-output"
                    output.write_text("")
                    with patch.object(sys, "argv", ["runtime", "plan", "--project", str(p), "--files", *paths,
                                                    "--github-output", str(output)]), contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(rt.main(), 0)
                    enabled = {line.split("=", 1)[0].removeprefix("check_") for line in output.read_text().splitlines()
                               if line.startswith("check_") and line.endswith("=true")}
                    self.assertEqual(enabled, set(plan["actions"]))

    def test_effective_config_keeps_persisted_schema_and_module_defaults(self):
        persisted = {'schema_version': 3, 'modules': {'latex': {'default_document': 'manuscript', 'documents': {'manuscript': {'root': 'main.tex', 'engine': 'pdflatex', 'output_dir': '.'}}}}}
        before = json.dumps(persisted)
        effective = core.effective_config(persisted)
        self.assertEqual(effective["schema_version"], 3)
        self.assertEqual(effective, core.effective_config(effective))
        self.assertEqual(json.dumps(persisted), before)
        self.assertIn("latex.py", core.runtime_sources(effective))
        self.assertNotIn("research.py", core.runtime_sources(effective))


    def test_bibliography_alias_selects_standalone_validation(self):
        (self.project / "refs.bib").write_text("@misc{fixture, title={Synthetic fixture}}")
        config = {'schema_version': 3, 'modules': {'bibliography': {'files': ['./refs.bib']}}}
        self.assertTrue(rt.validation_plan(self.project, config, ["refs.bib"])["bibliography"])

    def test_installer_lock_refuses_a_second_process(self):
        code = """import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import bootstrap
try:
    bootstrap.apply(Path(sys.argv[2]), [])
except bootstrap.WorkbenchError as error:
    print(error)
    sys.exit(23)
"""
        with boot.installation_lock(self.project):
            result = subprocess.run([sys.executable, "-B", "-c", code, str(boot.PACKAGE), str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
        self.assertIn("lock installation", result.stdout)
        # Nothing but the lock file that the holder itself created.
        self.assertEqual([path.relative_to(self.project).as_posix() for path in self.project.rglob("*") if path.is_file()],
                         [".latex-ai/artifacts/locks/installation.lock"])

    def test_installation_manifest_is_written_last(self):
        updates = [{"path": boot.STATE, "before": None, "after": "{}"},
                   {"path": "runtime", "before": None, "after": "new runtime"}]
        writes = []
        real = installation.atomic_write
        def record(path, text):
            writes.append(path.relative_to(self.project).as_posix())
            return real(path, text)
        with patch.object(installation, "atomic_write", side_effect=record):
            boot.apply(self.project, updates)
        self.assertEqual(writes[-1], boot.STATE)

    def test_reference_matches_distribution(self):
        reference = boot.PACKAGE.parent
        if not (reference / boot.STATE).is_file():
            self.skipTest("standalone distribution has no installed reference")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = boot.main(["audit", str(reference), "--json"])
        report = json.loads(output.getvalue())
        self.assertEqual(result, 0, report)
        self.assertEqual(report["changes"], [])
        self.assertEqual(report["conflicts"], [])


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
        an optional module (latex, research, markdown, documents, output_transaction) is how an absent module stays absent."""
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
        """core imports only processes; schema, the validated configuration and its documents, only core, the command registry and
        the Makefile reader, and those two only core."""
        self.assertLessEqual(set(self.graph["core"]), {"processes"})
        self.assertLessEqual(set(self.graph["schema"]), {"core", "commands", "make_graph"})
        self.assertLessEqual(set(self.graph["commands"]), {"core"})
        self.assertLessEqual(set(self.graph["make_graph"]), {"core"})


if __name__ == "__main__":
    unittest.main()
