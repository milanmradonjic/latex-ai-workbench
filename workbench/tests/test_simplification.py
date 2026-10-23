"""Schema-4 projects, explicit installation, and the fixed public command contract."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

from test_support import PACKAGE, ProjectCase
import commands
import core
import schema


class ExplicitProjectCase(ProjectCase):
    def config(self):
        (self.project / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n")
        config = {"schema_version": 4, "default_document": "paper",
                  "documents": {"paper": {"root": "main.tex", "lint": {"enabled": False}}}}
        self.save(config)
        return config

    def save(self, config):
        (self.project / core.CONFIG).write_text(json.dumps(config))

    def init(self, *options, expected=0):
        # Exercise the actual installer, with no fixture helper preparing settings.
        return self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), "init",
                                str(self.project), *options, expected=expected)


class ExplicitProjects(ExplicitProjectCase):
    def test_missing_configuration_does_not_discover_a_root_or_write_files(self):
        (self.project / "main.tex").write_text("\\documentclass{article}")
        before = self.snapshot()
        result = self.init(expected=2)
        self.assertIn("Installation requires an explicit .latex-ai.json", result.stderr)
        self.assertIn("examples/minimal/.latex-ai.json", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_invalid_projects_fail_before_any_installation_write(self):
        base = self.config()
        cases = [dict(base, schema_version=version) for version in (1, 2, 3)]
        cases += [dict(base, documents=value) for value in (None, {}, [], False)]
        cases += [dict(base, default_document="unknown"), dict(base, modules={}),
                  dict(base, documents={"paper": {"root": "missing.tex"}}),
                  dict(base, documents={"paper": {"root": "main.tex", "build_command": "make pdf"}}),
                  {"schema_version": 4, "bibliography": {"files": []}}]
        for config in cases:
            with self.subTest(config=config):
                self.save(config)
                before = self.snapshot()
                self.init(expected=2)
                self.assertEqual(before, self.snapshot())

    def test_shared_bibliography_cannot_silently_override_document_backend(self):
        config = self.config()
        config["bibliography"] = {"backend": "bibtex"}
        self.save(config)
        before = self.snapshot()
        result = self.init(expected=2)
        self.assertIn("backend", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_initial_choices_exist_only_in_configuration(self):
        self.config()
        for flag in ("--modules=latex", "--root=main.tex", "--no-lint", "--editor", "--skip-editor",
                     '--build-command=["make","pdf"]'):
            with self.subTest(flag=flag):
                before = self.snapshot()
                result = self.init(flag, expected=2)
                self.assertIn("unrecognized arguments", result.stderr)
                self.assertEqual(before, self.snapshot())

    def test_installer_modes_refuse_options_they_do_not_use(self):
        self.config()
        for mode, option in (("init", "--force"), ("diff", "--dry-run"), ("diff", "--json"),
                             ("diff", "--force"), ("runtime", "--diff"), ("runtime", "--json")):
            with self.subTest(mode=mode, option=option):
                before = self.snapshot()
                result = self.run_command(sys.executable, "-B", str(PACKAGE / "latex-ai-init"), mode,
                                          str(self.project), option, expected=2)
                self.assertIn("does not take", result.stdout + result.stderr)
                self.assertEqual(before, self.snapshot())

    def test_undeclared_sources_never_change_the_installation_plan(self):
        self.config()
        first = json.loads(self.init("--dry-run", "--json").stdout)
        (self.project / "another.tex").write_text("\\documentclass{book}\\usepackage{fontspec}")
        (self.project / "undeclared.bib").write_text("deliberately invalid; not a configured input")
        before = self.snapshot()
        second = json.loads(self.init("--dry-run", "--json").stdout)
        self.assertEqual(first, second)
        self.assertEqual(before, self.snapshot())
        self.assertNotIn("inventory", second)

    def test_explicit_custom_command_is_not_second_guessed_from_source(self):
        config = self.config()
        (self.project / "main.tex").write_text("% !TeX program = xelatex\n\\usepackage{fontspec}")
        config["documents"]["paper"]["build_command"] = [sys.executable, "custom.py"]
        self.save(config)
        before = (self.project / core.CONFIG).read_bytes()
        self.init()
        self.assertEqual(before, (self.project / core.CONFIG).read_bytes())
        self.assertFalse((self.project / ".vscode").exists())
        self.assertEqual(set(schema.required_tools(schema.load_config(self.project))), {"make", sys.executable})

    def test_all_document_declarations_are_validated_before_installation(self):
        config = self.config()
        config["documents"]["supplement"] = {"root": "missing.tex"}
        self.save(config)
        before = self.snapshot()
        result = self.init(expected=2)
        self.assertIn("missing.tex", result.stderr)
        self.assertEqual(before, self.snapshot())


@unittest.skipUnless(shutil.which("make"), "Make required")
class MultipleDocuments(ExplicitProjectCase):
    def setUp(self):
        ProjectCase.setUp(self)
        for stem in ("main", "supplement"):
            (self.project / (stem + ".tex")).write_text("\\documentclass{article}\n")
        (self.project / "shared.tex").write_text("Shared fixture input.\n")
        (self.project / "builder.py").write_text(
            "from pathlib import Path\nimport sys\n"
            "root = Path(sys.argv[1]); stem = root.stem\n"
            "counter = Path('count-' + stem)\n"
            "counter.write_text(str(int(counter.read_text()) + 1 if counter.exists() else 1))\n"
            "out = Path('outputs'); out.mkdir(exist_ok=True)\n"
            "(out / (stem + '.pdf')).write_bytes(b'%PDF-fixture ' + root.read_bytes() + Path('shared.tex').read_bytes())\n"
            "(out / (stem + '.log')).write_text('Clean log\\n')\n"
            "(out / (stem + '.fls')).write_text('PWD ' + str(Path.cwd()) + '\\nINPUT ' + str(root) + '\\nINPUT shared.tex\\n')\n")
        config = {"schema_version": 4, "default_document": "paper", "defaults": {"output_dir": "outputs", "lint": {"enabled": False}},
                  "documents": {name: {"root": stem + ".tex", "build_command": [sys.executable, "builder.py", stem + ".tex"]}
                                for name, stem in (("paper", "main"), ("supplement", "supplement"))}}
        self.save(config)
        self.init()

    def test_default_selected_and_all_document_builds_and_exports(self):
        self.run_command("make")
        self.assertTrue((self.project / "count-main").is_file())
        self.assertFalse((self.project / "count-supplement").exists())
        self.run_command("make", "build", "DOC=supplement")
        self.assertTrue((self.project / "count-supplement").is_file())
        self.run_command("make", "all")
        self.run_command("make", "check")
        for name in ("paper", "supplement"):
            self.run_command("make", "document-check", "DOC=" + name)
            self.run_command("make", "pdf-artifact", "DOC=" + name)
            self.assertTrue((self.project / f".latex-ai/artifacts/documents/{name}/document.pdf").is_file())
        for action in ("build", "lint", "document-check", "bib-check", "pdf-artifact"):
            result = self.run_command("make", action, "DOC=unknown", expected=2)
            self.assertIn("Unknown document", result.stderr)

    def test_help_commands_are_executable_with_one_name_each(self):
        help_text = self.run_command("make", "help").stdout
        names = re.findall(r"^  make ([a-z-]+)(?: DOC=NAME)? {2,}", help_text, re.M)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.run_command("make", "-n", name)
        makefile = (self.project / "Makefile").read_text()
        self.assertNotIn("latex-ai-", makefile)
        self.assertNotRegex(makefile, r"(?m)^(paper|supplement):")
        for removed in ("modules", "latex-ai-build", "document-lint", "supplement"):
            self.run_command("make", "-n", removed, expected=2)

    def test_custom_project_checks_are_never_bypassed(self):
        with (self.project / "Makefile").open("a") as stream:
            stream.write("\ncheck: local-check\nlocal-check:\n\t@echo checked > local-check-ran\n")
        result = self.command("validate", "--files", "main.tex")
        self.assertTrue((self.project / "local-check-ran").is_file(), result.stdout)

def tex_files(*names):
    """Whether the TeX installation has every named file: a lualatex binary alone may lack its font loader."""
    if not shutil.which("kpsewhich"):
        return False
    return all(subprocess.run(["kpsewhich", name], capture_output=True, text=True).stdout.strip() for name in names)


class AlternativeCompilers(ExplicitProjectCase):
    def compile(self, flag, source, bibliography=False):
        config = self.config()
        (self.project / "main.tex").write_text(source)
        config["documents"]["paper"].update(output_dir="build", build_command=[
            "latexmk", flag, "-recorder", "-interaction=nonstopmode", "-halt-on-error", "-outdir=build", "main.tex"])
        if bibliography:
            (self.project / "refs.bib").write_text("@misc{fixture,title={Synthetic fixture},year={2000}}\n")
            config["bibliography"] = {"files": ["refs.bib"]}
        self.save(config)
        self.init()
        self.run_command("make", "check")
        self.run_command("make", "pdf-artifact")
        self.assertTrue((self.project / ".latex-ai/artifacts/documents/paper/document.pdf").is_file())

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("lualatex") and tex_files("fontspec.sty", "luaotfload-main.lua"),
                         "latexmk and LuaLaTeX with fontspec and luaotfload required")
    def test_explicit_lualatex_command(self):
        self.compile("-lualatex", "\\documentclass{article}\n\\usepackage{fontspec}\n\\begin{document}Fixture.\\end{document}\n")

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("xelatex") and tex_files("fontspec.sty"), "latexmk and XeLaTeX with fontspec required")
    def test_explicit_xelatex_command(self):
        self.compile("-xelatex", "\\documentclass{article}\n\\usepackage{fontspec}\n\\begin{document}Fixture.\\end{document}\n")

    @unittest.skipUnless(shutil.which("latexmk") and shutil.which("pdflatex") and shutil.which("biber"), "latexmk/pdfLaTeX/biber required")
    def test_explicit_biber_command(self):
        self.compile("-pdf", "\\documentclass{article}\n\\usepackage{biblatex}\n\\addbibresource{refs.bib}\n\\begin{document}Fixture~\\cite{fixture}.\\printbibliography\\end{document}\n", bibliography=True)
