"""Independent audit 3 failures, exercised through installed workflows.

Compiler fixtures disable lint explicitly. Process/move tests isolate infrastructure;
the source-content and stdin tests use genuine TeX tools.
"""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap
import core
import schema
import documents
import guide
import latex
import runtime
import output_transaction
from test_support import fixture_env, isolate_environment

SOURCE = "\\documentclass{article}\n\\begin{document}Audit fixture.\\end{document}\n"
TEX = bool(shutil.which('latexmk') and shutil.which('pdflatex'))


class Audit3Repairs(unittest.TestCase):
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

    def named(self, makefile=None):
        for name in ('main.tex', 'note.tex'):
            (self.project / name).write_text(SOURCE)
        config = {'schema_version': 3, 'modules': {'latex': {
            'default_document': 'paper', 'defaults': {'lint': {'enabled': False}},
            'documents': {'paper': {'root': 'main.tex'}, 'note': {'root': 'note.tex'}}}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        if makefile is not None:
            (self.project / 'Makefile').write_text(makefile)
        self.install('init', '--skip-editor')
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
        config = {'schema_version': 3, 'modules': {'latex': {
            'default_document': 'paper', 'defaults': {'lint': {'enabled': False}},
            'documents': {name: {'root': root, 'build_command': [sys.executable, 'compile.py', root,
                f'.latex-ai/artifacts/documents/{name}/build']} for name, root in [('paper','main.tex'),('note','note.tex')]}}}}
        (self.project / core.CONFIG).write_text(json.dumps(config))
        if makefile is not None:
            (self.project / 'Makefile').write_text(makefile)
        self.install('init', '--skip-editor')
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

    @unittest.skipUnless(TEX, 'real latexmk/pdflatex required')
    def test_a1_declared_makefile_source_hashes_managed_text(self):
        config = self.named('# Displayed Makefile\n')
        config['modules']['latex']['documents']['paper']['inputs'] = ['Makefile']
        (self.project / core.CONFIG).write_text(json.dumps(config))
        (self.project / 'main.tex').write_text(
            '\\documentclass{article}\n\\usepackage{verbatim}\n\\begin{document}\\verbatiminput{Makefile}\\end{document}\n')
        self.command('document-check', '--document', 'paper')
        makefile = self.project / 'Makefile'
        makefile.write_text(makefile.read_text().replace('# END LATEX AI WORKBENCH', '# a change inside the managed block\n# END LATEX AI WORKBENCH'))
        self.command('verify', '--document', 'paper', expected=1)
        self.command('artifact', '--document', 'paper', expected=1)

    @unittest.skipUnless(TEX,'real compiler required')
    def test_review_included_make_policy_changes_invalidate_pdf(self):
        (self.project/'main.tex').write_text(SOURCE.replace('Audit fixture.','\\fixturetext'))
        (self.project/'compile.mk').write_text('TEX_TEXT := First\n')
        (self.project/'Makefile').write_text('include compile.mk\n.PHONY: build\nbuild: main.pdf\n'
            "main.pdf: main.tex\n\tpdflatex -recorder -interaction=nonstopmode -halt-on-error '\\def\\fixturetext{$(TEX_TEXT)}\\input{main.tex}'\n")
        self.install('init','--no-lint','--skip-editor','--engine','pdflatex')
        self.run_command('make','check')
        receipt=json.loads((self.project/'.latex-ai/artifacts/documents/manuscript/build-receipt.json').read_text())
        self.assertEqual(receipt['input_roles']['compile.mk'],'make-policy')
        before=(self.project/'main.pdf').read_bytes()
        with (self.project/'compile.mk').open('a') as stream:
            stream.write('# BEGIN LATEX AI WORKBENCH\n# Managed policy comment\n# END LATEX AI WORKBENCH\n')
        self.command('verify')
        self.command('artifact')
        (self.project/'compile.mk').write_text('TEX_TEXT := Second\n')
        self.command('verify',expected=1)
        self.command('artifact',expected=1)
        self.run_command('make','check')
        self.command('verify')
        self.command('artifact')
        self.assertNotEqual(before,(self.project/'main.pdf').read_bytes())

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

    def wait_file(self, name):
        deadline = time.monotonic() + 8
        path = self.project / name
        while time.monotonic() < deadline:
            if path.is_file() and path.read_text().strip():
                return path.read_text().strip()
            time.sleep(.03)
        self.fail(f'{name} was not written')

    @unittest.skipUnless(os.name == 'posix' and TEX, 'POSIX and real compiler required')
    def test_a3_phased_make_compiler_keeps_ownership_after_owner_dies(self):
        (self.project / 'main.tex').write_text(SOURCE)
        (self.project / 'slow.py').write_text(
            "import os,time,subprocess\nfrom pathlib import Path\n"
            "if not Path('compiler.pid').exists():\n"
            " Path('compiler.pid').write_text(str(os.getpid()))\n"
            " while not Path('release').exists(): time.sleep(.05)\n"
            "subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],check=True)\n")
        (self.project / 'Makefile').write_text('.PHONY: build check\nbuild: main.pdf\nmain.pdf: main.tex\n\t'+sys.executable+' slow.py\ncheck: build\n')
        self.install('init', '--no-lint', '--skip-editor', '--engine', 'pdflatex')
        owner = subprocess.Popen(['make','-j4','check'], cwd=self.project, env=self.env,
                                 start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: owner.poll() is None and owner.kill())
        pid = int(self.wait_file('compiler.pid'))
        self.children.append(pid)
        owner.kill()
        owner.wait(timeout=5)
        result = self.command('build', expected=1)
        self.assertIn('Another build is active', result.stderr)
        (self.project / 'release').write_text('continue')

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

    @unittest.skipUnless(TEX, 'real latexmk/pdflatex required')
    def test_a5_custom_compiler_receives_supplied_stdin(self):
        (self.project / 'main.tex').write_text(SOURCE)
        (self.project / 'compile.py').write_text(
            "import subprocess,sys\n"
            "if sys.stdin.readline().strip()!='approve': raise SystemExit(3)\n"
            "subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],check=True)\n")
        self.install('init','--no-lint','--skip-editor','--engine','pdflatex',
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
        self.install('init','--no-lint','--skip-editor','--engine','pdflatex')
        first = self.command('build',expected=1)
        self.assertIn('Undefined control sequence',first.stderr)
        (self.project / 'main.tex').write_text(SOURCE)
        (self.project / '.latexmkrc').write_text('die "CURRENT_RC_FAILURE before TeX starts\\n";\n')
        # Ensure the old log falls inside the previous implementation's one-second allowance.
        os.utime(Path(str(latex.output_paths(self.project, schema.document_settings(schema.load_config(self.project)))[2]) + '.log'), None)
        second = self.command('build',expected=1)
        self.assertIn('CURRENT_RC_FAILURE',second.stderr)
        self.assertNotIn('ERROR: main.tex:',second.stderr)

    @unittest.skipUnless(os.name=='posix','POSIX signals required')
    def test_a9_interruptions_emit_one_structured_result(self):
        self.synthetic()
        compiler = self.project/'compile.py'
        compiler.write_text("import os,time\nfrom pathlib import Path\nPath('compiler.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n")
        for number in (signal.SIGTERM,signal.SIGINT):
            with self.subTest(signal=number):
                (self.project/'compiler.pid').unlink(missing_ok=True)
                owner = subprocess.Popen([sys.executable,'-B','.latex-ai/workbench.py','build','--json'],
                    cwd=self.project,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                pid = int(self.wait_file('compiler.pid'))
                self.children.append(pid)
                owner.send_signal(number)
                stdout,stderr = owner.communicate(timeout=10)
                self.assertEqual(owner.returncode,128+number,stderr)
                result = json.loads(stdout)
                self.assertEqual(result['status'],'interrupted')
                self.assertEqual(result['exit_status'],128+number)
                self.assertNotIn('Traceback',stderr)
                self.assertEqual(latex.read_receipt(self.project,schema.resolve(schema.load_config(self.project)).view)['status'],'failed')

    @unittest.skipUnless(Path('/proc').is_dir(),'Linux process state required')
    def test_a10_zombie_owner_is_not_running(self):
        child = subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        try:
            token = latex.process_token(child.pid)
            child.kill()
            deadline = time.monotonic()+5
            while time.monotonic()<deadline:
                fields = Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split()
                if fields[0]=='Z': break
                time.sleep(.01)
            self.assertEqual(fields[0],'Z')
            self.assertFalse(latex.owner_alive({'owner_pid':child.pid,'owner_token':token}))
        finally:
            child.wait(timeout=5)

    def test_a11_double_colon_installation_never_produces_invalid_make(self):
        makefile='check:: local-test\nlocal-test:\n\ttouch project-check-ran\n'
        (self.project/'Makefile').write_text(makefile)
        (self.project/'main.tex').write_text(SOURCE)
        result=self.install('init','--no-lint','--skip-editor','--engine','pdflatex',
                            '--build-command',json.dumps([sys.executable,'-c','pass']),expected=None)
        if result.returncode==0:
            parsed=self.run_command('make','-n','check')
            self.assertIn('local-test',(self.project/'Makefile').read_text())
        else:
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertEqual((self.project/'Makefile').read_text(),makefile)
            self.assertFalse((self.project/'.latex-ai/installation.json').exists())

    def adopted(self, header=''):
        (self.project/'main.tex').write_text(SOURCE)
        (self.project/'compile.py').write_text(
            "from pathlib import Path\nPath('main.pdf').write_bytes(b'%PDF-1.4 fixture')\n"
            "Path('main.log').write_text('Clean fixture log')\n")
        (self.project/'Makefile').write_text(header+'.PHONY: build check\nbuild: main.pdf\n'
            'main.pdf: main.tex\n\t@'+sys.executable+' compile.py\n\t@touch recipe-completed\ncheck: build\n')
        self.install('init','--no-lint','--skip-editor','--engine','pdflatex')

    def test_review_raw_adopted_goal_still_builds_without_receipt(self):
        self.adopted()
        self.run_command('make','build')
        self.assertTrue((self.project/'main.pdf').is_file())
        self.assertFalse((self.project/'.latex-ai/artifacts/active-build.json').exists())
        self.command('verify',expected=1)

    def test_review_oneshell_and_chosen_shell_keep_receipt_ownership(self):
        original = self.project
        for oneshell in (False, True):
            for shell in ('/bin/sh', '/bin/bash'):
                for flags in ('-c', '-ec'):
                    with self.subTest(oneshell=oneshell, shell=shell, flags=flags):
                        self.project = original / f'{oneshell} {Path(shell).name} {flags}'
                        self.project.mkdir()
                        self.adopted('.ONESHELL:\n' if oneshell else '')
                        self.run_command('make','-j4',f'SHELL={shell}',f'.SHELLFLAGS={flags}','check')
                        self.assertTrue((self.project/'recipe-completed').exists())
                        self.command('verify')
        self.project = original

    def test_review_command_line_shell_cannot_bypass_owner(self):
        self.adopted()
        (self.project/'compile.py').write_text("import os,time\nfrom pathlib import Path\n"
            "Path('compiler.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n")
        owner=subprocess.Popen(['make','-j4','SHELL=/bin/sh','check'],cwd=self.project,env=self.env,
            start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: owner.poll() is None and owner.kill())
        pid=int(self.wait_file('compiler.pid'))
        self.children.append(pid)
        state=json.loads((self.project/'.latex-ai/artifacts/documents/manuscript/build-receipt.json').read_text())
        self.assertTrue(state.get('compiler_groups'),state)
        owner.kill()
        owner.wait(timeout=5)
        result=self.command('build',expected=1)
        self.assertIn('Another build is active',result.stderr)

    def test_review_make_nonbuilding_modes_do_not_write_receipts(self):
        self.adopted()
        for mode in ('-n','-q','-t'):
            with self.subTest(mode=mode):
                self.run_command('make',mode,'check',expected=None)
                self.assertFalse((self.project/'.latex-ai/artifacts/active-build.json').exists())
                self.assertFalse((self.project/'.latex-ai/artifacts/documents/manuscript/build-receipt.json').exists())

    def test_review_conditional_rule_styles_refuse_before_installing(self):
        makefile='ifeq (0,1)\ncheck::\nelse\ncheck:\nendif\n'
        (self.project/'Makefile').write_text(makefile)
        (self.project/'main.tex').write_text(SOURCE)
        result=self.install('init','--no-lint','--skip-editor',
            '--engine','pdflatex','--build-command',json.dumps([sys.executable,'-c','pass']),expected=2)
        self.assertIn('colon',result.stdout+result.stderr)
        self.assertEqual((self.project/'Makefile').read_text(),makefile)
        self.assertFalse((self.project/'.latex-ai/installation.json').exists())

    def test_review_custom_recipe_prefix_refuses_before_installing(self):
        makefile='.RECIPEPREFIX := >\ncheck:\n>touch project-check-ran\n'
        (self.project/'Makefile').write_text(makefile)
        (self.project/'main.tex').write_text(SOURCE)
        result=self.install('init','--no-lint','--skip-editor','--engine','pdflatex',
            '--build-command',json.dumps([sys.executable,'-c','pass']),expected=2)
        self.assertIn('recipe prefix',result.stdout+result.stderr)
        self.assertEqual((self.project/'Makefile').read_text(),makefile)
        self.assertFalse((self.project/'.latex-ai/installation.json').exists())

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

    def test_review_missing_optional_make_include_selects_project_check(self):
        self.synthetic('-include generated.mk\ngenerated.mk:\n'
            '\t@echo "check: generated-check" > $@\n'
            '\t@echo "generated-check: ; touch generated-check-ran" >> $@\n')
        plan=json.loads(self.command('plan','--files','note.tex','--json').stdout)
        self.assertTrue(plan['project_check'],plan)
        self.command('validate','--files','note.tex')
        self.assertTrue((self.project/'generated-check-ran').is_file())

    @unittest.skipUnless(os.name=='posix','POSIX signals required')
    def test_review_repeated_interrupt_waits_for_stubborn_compiler_cleanup(self):
        self.synthetic()
        (self.project/'compile.py').write_text('import os,time,signal\nfrom pathlib import Path\n'
            'signal.signal(signal.SIGTERM,signal.SIG_IGN)\nsignal.signal(signal.SIGINT,signal.SIG_IGN)\n'
            "Path('compiler.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n")
        owner=subprocess.Popen([sys.executable,'-B','.latex-ai/workbench.py','build','--json'],
            cwd=self.project,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        pid=int(self.wait_file('compiler.pid'))
        self.children.append(pid)
        owner.send_signal(signal.SIGINT)
        time.sleep(.15)
        owner.send_signal(signal.SIGINT)
        stdout,stderr=owner.communicate(timeout=12)
        self.assertEqual(owner.returncode,130,stderr)
        self.assertEqual(json.loads(stdout)['status'],'interrupted')
        self.assertFalse(latex.group_alive(pid))

    @unittest.skipUnless(os.name=='posix' and TEX,'POSIX and real compiler required')
    def test_review_owner_death_before_publication_never_executes_compiler(self):
        (self.project/'main.tex').write_text(SOURCE)
        launcher=self.project/'owner.py'
        launcher.write_text('import sys,os\nfrom pathlib import Path\n'
            'sys.path.insert(0,'+repr(str(bootstrap.PACKAGE))+')\nimport core\n'
            "def started(pid):\n Path('compiler.pid').write_text(str(pid))\n os._exit(97)\n"
            "core.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],Path.cwd(),started=started)\n")
        self.run_command(sys.executable,'-B',str(launcher),expected=97)
        pid=int(self.wait_file('compiler.pid'))
        self.children.append(pid)
        deadline=time.monotonic()+3
        while latex.group_alive(pid) and time.monotonic()<deadline:
            time.sleep(.03)
        self.assertFalse(latex.group_alive(pid))
        self.assertFalse((self.project/'main.pdf').exists())

    def test_a12_lifecycle_fixture_ignores_callers_doc_and_makeflags(self):
        result=subprocess.run([sys.executable,'-B','-m','unittest',
            'test_document_lifecycle.DocumentLifecycleTests.test_failed_named_build_regenerates_instead_of_reviving_a_receipt'],
            cwd=bootstrap.PACKAGE/'tests',env={**self.env,'DOC':'external','MAKEFLAGS':'n'},
            capture_output=True,text=True,timeout=25)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_git_initialization_and_cloning_have_matching_approval_rules(self):
        templates=bootstrap.PACKAGE/'templates'
        rules=set()
        for node in ast.walk(ast.parse((templates/'.codex/rules/git-safety.rules').read_text())):
            if isinstance(node,ast.Call) and getattr(node.func,'id','')=='prefix_rule':
                values={k.arg:ast.literal_eval(k.value) for k in node.keywords}
                if len(values['pattern'])==2:rules.add(tuple(values['pattern']))
        claude=json.loads((templates/'.claude/settings.json').read_text())['permissions']['ask']
        for action in ('init','clone'):
            self.assertIn(('git',action),rules)
            self.assertIn('Bash(git '+action+')',claude)
            self.assertIn('Bash(git '+action+':*)',claude)


if __name__=='__main__':
    unittest.main()
