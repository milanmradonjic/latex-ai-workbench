import argparse
import ast
import contextlib
import io
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_support import isolate_environment
import shutil
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap as boot
import core
import schema
import runtime as rt
import latex

TEX = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        isolate_environment(self)
        self.temp = tempfile.TemporaryDirectory(prefix="latex-ai-unit-")
        self.project = Path(self.temp.name).resolve()
        (self.project / "paper.tex").write_text(TEX)

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
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

    def test_ambiguous_root_refuses_all_writes(self):
        (self.project / "thesis.tex").write_text(TEX)
        before = self.snapshot()
        self.assertEqual(self.cli("init"), 2)
        self.assertEqual(before, self.snapshot())

    def test_commented_documentclass_is_not_a_root(self):
        (self.project / "chapter.tex").write_text("% \\documentclass{article}\nA chapter.\n")
        self.init()
        self.assertEqual(rt.document_settings(rt.load_config(self.project))["root"], "paper.tex")

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
        self.assertEqual(self.cli("init", "--skip-editor"), 0)

    def test_jsonc_preserved(self):
        path = self.project / ".vscode/settings.json"
        path.parent.mkdir()
        content = '{\n// Local comment\n"editor.tabSize": 4,\n}\n'
        path.write_text(content)
        self.assertEqual(self.cli("init"), 2)
        self.assertEqual(self.cli("init", "--skip-editor"), 0)
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

    def test_agent_guardrails_agree_and_cover_every_git_operation_the_policy_names(self):
        templates = boot.PACKAGE / "templates"
        codex, refused = set(), set()  # prompts, and pushes to the default branch that are refused (3.0.4)
        for call in ast.walk(ast.parse((templates / ".codex/rules/git-safety.rules").read_text())):
            if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "prefix_rule":
                rule = {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords}
                self.assertIn(rule["decision"], {"prompt", "forbidden"})
                self.assertTrue(rule["justification"])
                alternatives = [token if isinstance(token, list) else [token] for token in rule["pattern"]]
                (codex if rule["decision"] == "prompt" else refused).update(itertools.product(*alternatives))
        settings = json.loads((templates / ".claude/settings.json").read_text())["permissions"]
        def commands(entries):  # shell rules; Claude's GitHub-tool rules (mcp__...) have no Codex counterpart
            return {tuple(entry[len("Bash("):-1].removesuffix(":*").split()) for entry in entries if entry.startswith("Bash(")}
        claude = commands(settings["ask"])
        self.assertEqual(claude, codex)  # the two agents must not drift apart
        # Claude's wildcard denies (4.10.0: `git push *:main` and the like) have no Codex counterpart, which matches whole words only; the others agree.
        self.assertEqual(commands(entry for entry in settings.get("deny", []) if "*" not in entry[len("Bash("):-1].removesuffix(":*")), refused)
        # Refused outright: pushes to the default branch and merging pull requests (3.0.4); everything else prompts.
        self.assertTrue(all(command[:2] == ("git", "push") or command == ("gh", "pr", "merge") for command in refused))
        self.assertTrue(all(entry.startswith(("Bash(", "mcp__github__")) for entry in settings.get("deny", [])))
        # AGENTS.md (4.10.0, gate G1): what writes history, branches or the working tree: committing, pushing, pulling, merging, rebasing, resetting,
        # restoring, cleaning, stashing, branch changes/deletion, worktree creation/removal and history rewriting. Staging and fetch prompt no more.
        named = {("git", name) for name in ("commit", "push", "pull", "merge", "rebase", "reset", "restore", "clean", "stash", "checkout", "switch",
                                            "cherry-pick", "revert", "am", "rm", "mv", "tag", "update-ref", "filter-branch", "commit-tree")}
        named |= {("git", "branch", flag) for flag in ("-d", "-D", "--delete", "-m", "-f")}
        named |= {("git", "worktree", action) for action in ("add", "remove")}
        named |= {("git", "remote", "set-url"), ("git", "remote", "update"), ("git", "reflog", "expire")}
        self.assertFalse(named - codex, f"policy-named operations without a guardrail: {sorted(named - codex)}")
        for read_only in ("status", "diff", "log", "show", "ls-files", "rev-parse"):
            self.assertNotIn(("git", read_only), codex)  # inspection must stay prompt-free
        self.assertFalse({tuple(entry[len("Bash("):-1].removesuffix(":*").split()) for entry in settings["allow"]} & codex)
        # Claude Code already runs read-only forms of git unasked; an explicit allow would also cover `git diff --output=PATH`.
        self.assertEqual([entry for entry in settings["allow"] if "git" in entry], [])

    def test_malformed_document_configuration_is_reported_never_crashes(self):
        self.init()
        base = rt.load_config(self.project)
        base["modules"]["bibliography"] = {"files": [], "export": {"path": "zotero.bib", "required": False, "format": "bibtex"}}
        gone = object()
        tex = ("modules", "latex", "documents", "manuscript")
        bib = ("modules", "bibliography")
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

    def test_installer_separates_internal_defects_from_ordinary_errors(self):
        errors = io.StringIO()
        with patch.object(boot, "detect_config", side_effect=KeyError("missing")), contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            status = boot.main(["init", str(self.project)])
        self.assertEqual(status, 70)
        self.assertIn("INTERNAL ERROR: KeyError", errors.getvalue())
        for ordinary in (rt.WorkbenchError("conflict"), OSError("disk"), ValueError("json")):
            with self.subTest(ordinary=type(ordinary).__name__), patch.object(boot, "detect_config", side_effect=ordinary), \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(boot.main(["init", str(self.project)]), 2)

    def test_policy_tells_agents_how_to_treat_a_suspected_workbench_defect(self):
        template = (boot.PACKAGE / "templates/AGENTS.md").read_text()
        section = template[template.index("# Suspected workbench defects"):template.index("# Writer/reviewer workflow")]
        for phrase in ("INTERNAL ERROR", "Error 70", "Do not edit `.latex-ai/`", "make latex-ai-issue", "nothing is sent anywhere", "need the user's approval"):
            self.assertIn(phrase, section)

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
        config["modules"].setdefault("bibliography", {"files": [], "export": None})["files"] = ["one.bib", "two.bib"]
        for name in config["modules"].setdefault("bibliography", {"files": [], "export": None})["files"]:
            (self.project / name).write_text('@book{same, title={T}}')
        with self.assertRaisesRegex(rt.WorkbenchError, "Duplicate"):
            rt.bibliography_check(self.project, schema.document_settings(config))

    def test_case_variant_duplicate_keys_follow_the_backend(self):
        self.init()
        config = rt.load_config(self.project)
        config["modules"].setdefault("bibliography", {"files": [], "export": None})["files"] = ["one.bib", "two.bib"]
        (self.project / "one.bib").write_text('@book{Smith2020, title={T}}')
        (self.project / "two.bib").write_text('@book{smith2020, title={U}}')
        config["modules"]["latex"]["documents"]["manuscript"]["backend"] = "bibtex"
        with self.assertRaisesRegex(rt.WorkbenchError, r"Duplicate bibliography key 'smith2020' \(same key as 'Smith2020'; BibTeX ignores case\)"):
            rt.bibliography_check(self.project, schema.document_settings(config))
        config["modules"]["latex"]["documents"]["manuscript"]["backend"] = "none"  # unprocessed exports keep case-variant keys distinct
        self.assertEqual(len(rt.bibliography_check(self.project, schema.document_settings(config))), 2)
        (self.project / "two.bib").write_text('@book{Smith2020, title={U}}')  # exact duplicates stay errors everywhere
        for backend in ("bibtex", "none"):
            config["modules"]["latex"]["documents"]["manuscript"]["backend"] = backend
            with self.subTest(backend=backend, exact=True), self.assertRaisesRegex(rt.WorkbenchError, "Duplicate bibliography key 'Smith2020': "):
                rt.bibliography_check(self.project, schema.document_settings(config))

    def test_optional_then_required_export(self):
        self.init()
        config = rt.load_config(self.project)
        config["modules"].setdefault("bibliography", {"files": [], "export": None})["export"] = {"path": "zotero.bib", "required": False, "format": "bibtex"}
        self.assertEqual(rt.bibliography_check(self.project, schema.document_settings(config)), {})
        config["modules"].setdefault("bibliography", {"files": [], "export": None})["export"]["required"] = True
        with self.assertRaisesRegex(rt.WorkbenchError, "Missing"):
            rt.bibliography_check(self.project, schema.document_settings(config))
        (self.project / "zotero.bib").write_text("% Empty export\n")
        with self.assertRaisesRegex(rt.WorkbenchError, "no entries"):
            rt.bibliography_check(self.project, schema.document_settings(config))

    def test_log_failures_and_advisory_warnings(self):
        self.init()
        config = rt.load_config(self.project)
        config["modules"]["latex"]["documents"]["manuscript"]["output_dir"] = "."
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
        config["modules"]["latex"]["documents"]["manuscript"]["output_dir"] = "."
        (self.project / "paper.pdf").write_bytes(b"%PDF-1.5\n")
        (self.project / "paper.log").write_text("Output written on paper.pdf.\n")
        (self.project / "paper.blg").write_text("I couldn't open database file obsolete.bib\n")
        with contextlib.redirect_stdout(io.StringIO()):
            rt.verify(self.project, schema.document_settings(config), check_receipt=False)
        config["modules"]["latex"]["documents"]["manuscript"]["backend"] = "bibtex"
        with self.assertRaisesRegex(rt.WorkbenchError, "integrity"):
            rt.verify(self.project, schema.document_settings(config), check_receipt=False)

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
        (self.project / "paper.tex").write_text(TEX.replace("Hello.", "\\input{notes.md}\n\\lstinputlisting{helper.py}"))
        for name in ("notes.md", "helper.py"):
            with self.subTest(name=name):
                self.assertTrue(self.selection(name)["manuscript"])

    def test_files_named_in_braces_are_inputs_without_a_recorder_file(self):
        self.init()
        body = ("\\verbatiminput{data/results.txt}\n\\pgfplotstableread[col sep=comma]{data/table.json}\\loadedtable\n\\directlua{dofile(\"x.lua\")}\n"
                "\\verbatiminput{data/result file.txt}\n\\input{\"data/quoted name.txt\"}")
        (self.project / "paper.tex").write_text(TEX.replace("Hello.", body))
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
        config["modules"]["latex"]["documents"]["manuscript"]["build_command"] = ["python3", "helper.py"]
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
        git("add", "paper.tex")
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
        self.throwaway_git("add", "paper.tex")
        self.throwaway_git("commit", "-q", "-m", "one")
        self.throwaway_git("update-index", "--split-index")
        paper = self.project / "paper.tex"
        paper.write_text(paper.read_text() + "% second revision\n")
        self.throwaway_git("add", "paper.tex")
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
        self.assertEqual([item.args[0] for item in run.call_args_list], [["make", "-C", "workbench", "test"], ["make", "-C", "workbench", "portability"], ["make", "latex-ai-document-check", "DOC=manuscript"]])
        with patch.object(rt, "run", side_effect=AssertionError("Build tool invoked")), contextlib.redirect_stdout(io.StringIO()):
            rt.validate_changes(self.project, plan, files_only=True)

    def test_recursion_guard_blocks_same_project_but_allows_synthetic_children(self):
        self.init()
        plan = self.selection("paper.tex")
        with patch.dict(rt.os.environ, {"LATEX_AI_VALIDATE_ACTIVE": str(self.project)}), self.assertRaisesRegex(rt.WorkbenchError, "Recursive"), contextlib.redirect_stdout(io.StringIO()):
            rt.validate_changes(self.project, plan)
        with patch.dict(rt.os.environ, {"LATEX_AI_VALIDATE_ACTIVE": str(self.project.parent / "different-project")}), patch.object(rt, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            rt.validate_changes(self.project, plan)
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
