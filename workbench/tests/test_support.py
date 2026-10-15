"""Fixture environments do not inherit another project's selectors or Git state, and the shared project fixture."""
import json
import re
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import core
import schema
import documents

OPERATIONAL = {'DOC', 'TASK', 'TOPIC', 'PYTHON', 'MAKEFLAGS', 'MFLAGS', 'GNUMAKEFLAGS', 'MAKELEVEL', 'MAKEOVERRIDES',
               'TEXINPUTS', 'BIBINPUTS', 'BSTINPUTS', 'TEXMFOUTPUT',
               'GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY',
               'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT'}


def fixture_env(**overrides):
    result = {key: value for key, value in os.environ.items() if key not in OPERATIONAL
              and not key.startswith('LATEX_AI_') and not key.startswith(('GIT_CONFIG_KEY_', 'GIT_CONFIG_VALUE_'))}
    result.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
    result.update(overrides)
    return result


def isolate_environment(test):
    context = patch.dict(os.environ, fixture_env(), clear=True)
    context.start()
    test.addCleanup(context.stop)


def prepare_config(project, root="main.tex", lint=True, editor=False, build_command=None, output_dir=None):
    """Declare a synthetic project's settings explicitly; never infer configuration from its sources."""
    path = project / core.CONFIG
    if not path.exists():
        if root == "main.tex" and not (project / root).exists():
            (project / root).write_text("\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n")
        path.write_text(json.dumps({"schema_version": 4, "default_document": "manuscript",
                                   "documents": {"manuscript": {"root": root, "lint": {"enabled": lint},
                                                                 "build_command": build_command, "output_dir": output_dir if output_dir is not None else ("." if build_command else None)}},
                                   "integrations": {"editor": editor}}))


def own_targets(project, *names, recipe="@echo mine"):
    """The project takes over these short Make names: each alias line init wrote becomes the project's own recipe."""
    makefile = project / "Makefile"
    text = makefile.read_text(encoding="utf-8")
    for name in names:
        alias = re.search(rf"^{re.escape(name)}: (latex-ai-[\w-]+)$", text, re.M)
        assert alias, f"no alias line for {name} in the Makefile init wrote"
        text = text.replace(alias[0], f"{name}:\n\t{recipe}")
    makefile.write_text(text, encoding="utf-8")


class ProjectCase(unittest.TestCase):
    """A throwaway project with the installer and installed runtime run as subprocesses.

    Compiler-independent fixtures use a small deterministic build command (``builder``) and disable lint
    explicitly, so only the scenarios that name real TeX tools need them.
    """

    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="workbench-project-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        self.env = fixture_env()
        # Commands that snapshot or populate TeX caches must never write into the real home.
        home = self.root / "fixture-home"
        home.mkdir()
        cache = home / "texmf-var"
        cache.mkdir()
        self.env.update(HOME=str(home), TEXMFVAR=str(cache), TEXMFCACHE=str(cache))

    def run_command(self, *args, expected=0, env=None, cwd=None):
        result = subprocess.run(args, cwd=cwd or self.project, env=env or self.env, capture_output=True, text=True, timeout=60)
        if expected is not None:
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def install(self, *args, expected=0, **choices):
        prepare_config(self.project, **choices)
        return self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), *args, str(self.project), expected=expected)

    def own_targets(self, *names):
        own_targets(self.project, *names)

    def edit_config(self, change):
        """Change .latex-ai.json directly: since 4.3 the configuration is edited by hand (or by an agent), not by a command."""
        path = self.project / core.CONFIG
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def add_document(self, name, root, **fields):
        self.edit_config(lambda data: data["documents"].setdefault(name, {}).update(root=root, **fields))

    def command(self, *args, **kwargs):
        return self.run_command(sys.executable, "-B", ".latex-ai/workbench.py", *args, **kwargs)

    def configure(self, documents_=None, **extra):
        settings = {"root": "main.tex", "lint": {"enabled": False}, "output_dir": "outputs",
                    "build_command": [sys.executable, "builder.py"]}
        config = {"schema_version": 4, "default_document": "paper", "documents": documents_ or {"paper": settings},
                  **extra}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        return config

    def builder(self, generate="", inputs=("main.tex",)):
        """A deterministic stand-in compiler: it writes outputs and the recorder a TeX run would."""
        (self.project / "builder.py").write_text(
            "from pathlib import Path\n"
            "count = Path('count')\n"
            "count.write_text(str(int(count.read_text()) + 1 if count.exists() else 1))\n"
            + generate +
            "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
            "(out / 'main.pdf').write_bytes(b'%PDF-fixture ' + count.read_bytes())\n"
            "(out / 'main.log').write_text('Clean log\\n')\n"
            "(out / 'main.fls').write_text('PWD ' + str(Path.cwd()) + '\\n' + ''.join('INPUT ' + name + '\\n' for name in " + repr(list(inputs)) + "))\n")

    def state(self):
        return documents.report(self.project, schema.load_config(self.project))[0]["state"]

    def receipt(self):
        return json.loads((self.project / ".latex-ai/artifacts/documents/paper/build-receipt.json").read_text())

    def snapshot(self):
        """Every file of the project with its bytes: what a read-only command must leave as it was."""
        return {path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in sorted(self.project.rglob("*")) if path.is_file() and ".git/" not in path.as_posix()}
