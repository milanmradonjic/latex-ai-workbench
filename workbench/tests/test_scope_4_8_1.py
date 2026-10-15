"""4.8.1: independent-audit regressions, output safety, source integrity and bounded scans.

Every project is disposable; overwrite probes use only synthetic sentinel files.
"""
import contextlib
import argparse
import io
import json
import os
import shutil
import struct
import sys
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from test_support import ProjectCase

import bootstrap
import core
import guide
import latex
import runtime
import schema
import snapshot

TEX = bool(shutil.which('latexmk') and shutil.which('pdflatex'))
SOURCE = '\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n'


def red_png():
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00')) + chunk(b'IEND', b''))


class AuditRepairs(ProjectCase):
    def setUp(self):
        super().setUp()
        (self.project / 'main.tex').write_text(SOURCE)

    def native(self, source=SOURCE):
        (self.project / 'main.tex').write_text(source)
        self.install('init', '--no-lint', '--skip-editor')
        return schema.document_settings(schema.load_config(self.project))

    def test_f1_standard_auxiliary_output_links_cannot_escape(self):
        outside = self.root / 'outside.txt'
        outside.write_text('keep')
        for suffix in ('.lof', '.lot', '.lol', '.loe', '.idx', '.ind', '.ilg', '.glo', '.gls', '.glg', '.acn', '.acr', '.alg', '.nav', '.snm', '.vrb'):
            with self.subTest(suffix=suffix):
                child = self.project / ('main' + suffix)
                child.symlink_to(outside)
                try:
                    with self.assertRaises(core.WorkbenchError):
                        core.document_paths(self.project, 'main.tex', '.')
                    self.assertEqual(outside.read_text(), 'keep')
                finally:
                    child.unlink()

    def test_f2_outputs_cannot_alias_any_declared_root_in_either_order(self):
        (self.project / 'notes.tex').write_text(SOURCE + '% notes\n')
        for kind in ('hard', 'symbolic'):
            for default in ('paper', 'notes'):
                with self.subTest(kind=kind, default=default):
                    alias = self.project / 'main.log'
                    alias.hardlink_to(self.project / 'notes.tex') if kind == 'hard' else alias.symlink_to('notes.tex')
                    config = self.configure(documents_={
                        'paper': {'root': 'main.tex', 'output_dir': '.'},
                        'notes': {'root': 'notes.tex', 'output_dir': '.'}})
                    config['modules']['latex']['default_document'] = default
                    try:
                        with self.assertRaisesRegex(core.WorkbenchError, 'collision|overlap|aliases'):
                            schema.validate_config(self.project, config)
                        self.assertEqual((self.project / 'notes.tex').read_text(), SOURCE + '% notes\n')
                    finally:
                        alias.unlink()

    def test_f2_output_cannot_alias_its_own_root(self):
        (self.project / 'main.aux').hardlink_to(self.project / 'main.tex')
        config = self.configure(documents_={'paper': {'root': 'main.tex', 'output_dir': '.'}})
        with self.assertRaises(core.WorkbenchError):
            schema.validate_config(self.project, config)

    def test_f2_build_protects_known_nonroot_source_from_output_alias(self):
        (self.project / 'fragment.tex').write_text('Valuable fragment.\n')
        (self.project / 'main.tex').write_text(SOURCE.replace('Fixture.', '\\input{fragment}'))
        (self.project / 'main.log').hardlink_to(self.project / 'fragment.tex')
        self.configure(documents_={'paper': {'root': 'main.tex', 'output_dir': '.',
            'lint': {'enabled': False}, 'build_command': [sys.executable, '-c', 'raise SystemExit(99)']}})
        self.install('init', '--skip-editor')
        result = self.command('build', expected=1)
        self.assertRegex(result.stderr, 'aliases|overlap|collision')
        self.assertEqual((self.project / 'fragment.tex').read_text(), 'Valuable fragment.\n')

    def test_f2_generated_suffix_does_not_hide_an_authored_listing(self):
        (self.project / 'example.idx').write_text('Keep the authored listing.\n')
        (self.project / 'main.tex').write_text(SOURCE.replace('Fixture.', '\\lstinputlisting{example.idx}'))
        self.builder(inputs=('main.tex', 'example.idx'))
        with (self.project / 'builder.py').open('a') as stream:
            stream.write("(out / 'main.idx').write_text('would overwrite the source')\n")
        self.configure()
        (self.project / 'outputs').mkdir()
        (self.project / 'outputs/main.idx').hardlink_to(self.project / 'example.idx')
        self.install('init', '--skip-editor')
        result = self.command('build', expected=1)
        self.assertIn('aliases a source input', result.stderr)
        self.assertEqual((self.project / 'example.idx').read_text(), 'Keep the authored listing.\n')

    def test_f2_recorder_only_same_suffix_data_still_invalidates_receipts(self):
        (self.project / 'train.log').write_text('first')
        self.builder(inputs=('main.tex', 'train.log'))
        self.configure()
        self.install('init', '--skip-editor')
        self.command('build')
        self.assertIn('train.log', self.receipt()['inputs'])
        (self.project / 'train.log').write_text('changed')
        self.assertEqual(self.state(), 'stale')

    def test_f2_explicit_listing_at_an_output_path_is_protected(self):
        (self.project / 'main.tex').write_text(SOURCE.replace('Fixture.', '\\lstinputlisting{outputs/main.idx}'))
        self.builder(inputs=('main.tex', 'outputs/main.idx'))
        with (self.project / 'builder.py').open('a') as stream:
            stream.write("(out / 'main.idx').write_text('would overwrite the source')\n")
        self.configure()
        (self.project / 'outputs').mkdir()
        (self.project / 'outputs/main.idx').write_text('Keep the authored listing.\n')
        self.install('init', '--skip-editor')
        result = self.command('build', expected=1)
        self.assertIn('aliases a source input', result.stderr)
        self.assertEqual((self.project / 'outputs/main.idx').read_text(), 'Keep the authored listing.\n')

    def test_f2_a_build_script_at_an_output_path_is_protected(self):
        self.builder()
        self.configure()
        (self.project / 'outputs').mkdir()
        script = self.project / 'outputs/main.log'
        original = (self.project / 'builder.py').read_text()
        script.write_text(original)
        self.edit_config(lambda data: data['modules']['latex']['documents']['paper'].update(
            build_command=[sys.executable, 'outputs/main.log']))
        self.install('init', '--skip-editor')
        self.assertIn('aliases a source input', self.command('build', expected=1).stderr)
        self.assertEqual(script.read_text(), original)

    def test_f2_mentioning_an_output_filename_is_not_reading_it(self):
        (self.project / 'main.tex').write_text(SOURCE.replace('Fixture.', '\\texttt{outputs/main.log}'))
        self.builder()
        self.configure()
        self.install('init', '--skip-editor')
        self.command('build')
        self.command('build')
        self.assertEqual(self.state(), 'current')

    def test_f2_output_command_arguments_are_not_treated_as_source_scripts(self):
        self.builder()
        config = self.configure()
        config['modules']['latex']['documents']['paper']['build_command'] += ['--output', 'outputs/main.pdf']
        (self.project / core.CONFIG).write_text(json.dumps(config))
        self.install('init', '--skip-editor')
        self.command('build')
        self.command('build')
        self.assertNotIn('outputs/main.pdf', self.receipt()['inputs'])
        self.assertEqual(self.state(), 'current')

    def test_f2_makefiles_at_an_output_path_are_protected(self):
        self.builder()
        self.configure()
        self.install('init', '--skip-editor')
        original = 'raw:\n\t' + sys.executable + ' builder.py\n'
        for stem, directory in (('main', 'outputs'), ('-paper', '.'), ('-file', '.')):
            (self.project / (stem + '.tex')).write_text(SOURCE)
            name = (Path(directory) / (stem + '.log')).as_posix()
            script = self.project / name
            script.parent.mkdir(exist_ok=True)
            (self.project / 'builder.py').write_text('from pathlib import Path\n'
                + 'Path(' + repr(str(Path(directory) / (stem + '.pdf'))) + ").write_bytes(b'%PDF-fixture')\n"
                + 'Path(' + repr(name) + ").write_text('would overwrite the makefile')\n")
            for arguments in (['-f', name], ['--file', name], ['--makefile', name],
                              ['-f' + name], ['--file=' + name], ['--makefile=' + name]):
                with self.subTest(arguments=arguments):
                    script.write_text(original)
                    (self.project / '.latex-ai/artifacts/documents/paper/build-receipt.json').unlink(missing_ok=True)
                    self.edit_config(lambda data: data['modules']['latex']['documents']['paper'].update(
                        root=stem + '.tex', output_dir=directory, build_command=['make', *arguments, 'raw']))
                    self.assertIn('aliases a source input', self.command('build', expected=1).stderr)
                    self.assertEqual(script.read_text(), original)

    def test_f2_actual_generated_auxiliary_is_not_treated_as_authored(self):
        self.builder("Path('outputs').mkdir(exist_ok=True)\nPath('outputs/main.aux').write_text('generated')\n",
                     inputs=('main.tex', 'outputs/main.aux'))
        self.configure()
        self.install('init', '--skip-editor')
        self.command('build')
        self.assertNotIn('outputs/main.aux', self.receipt()['inputs'])
        self.assertEqual(self.state(), 'current')

    def test_f2_dash_named_makefile_does_not_turn_an_output_goal_into_source(self):
        self.builder()
        self.configure()
        self.install('init', '--skip-editor')
        (self.project / '-f').write_text('outputs/main.pdf: main.tex builder.py\n\t' + sys.executable + ' builder.py\n')
        for arguments in (['-f', '-f'], ['--file', '-f'], ['--makefile', '-f'],
                          ['-f-f'], ['--file=-f'], ['--makefile=-f']):
            with self.subTest(arguments=arguments):
                (self.project / '.latex-ai/artifacts/documents/paper/build-receipt.json').unlink(missing_ok=True)
                self.edit_config(lambda data: data['modules']['latex']['documents']['paper'].update(
                    build_command=['make', *arguments, 'outputs/main.pdf']))
                self.command('build')
                self.command('build')
                self.assertIn('-f', self.receipt()['inputs'])
                self.assertNotIn('outputs/main.pdf', self.receipt()['inputs'])
                self.assertEqual(self.state(), 'current')

    def test_f2_known_script_roles_preserve_dash_named_source_scripts(self):
        self.builder()
        self.configure()
        self.install('init', '--skip-editor')
        (self.project / '-paper.tex').write_text(SOURCE)
        builder = "from pathlib import Path\nPath('-paper.pdf').write_bytes(b'%PDF-fixture')\nPath('-paper.log').write_text('would overwrite the script')\n"
        (self.project / 'builder.py').write_text(builder)
        self.env['PATH'] = str(self.project) + os.pathsep + self.env['PATH']
        for executable, options, original in (
                (sys.executable, ['--'], builder), (sys.executable, ['-u', '--'], builder),
                ('bash', ['--'], sys.executable + ' builder.py\n'),
                ('bash', ['-eu', '--'], sys.executable + ' builder.py\n'),
                ('-paper.log', [], '#!' + sys.executable + '\n' + builder)):
            with self.subTest(executable=executable, options=options):
                script = self.project / '-paper.log'
                script.write_text(original)
                script.chmod(0o700)
                if not shutil.which(executable, path=self.env['PATH']):
                    self.skipTest(executable + ' required')
                (self.project / '.latex-ai/artifacts/documents/paper/build-receipt.json').unlink(missing_ok=True)
                self.edit_config(lambda data: data['modules']['latex']['documents']['paper'].update(
                    root='-paper.tex', output_dir='.', build_command=[executable, *options, '-paper.log']))
                self.assertIn('aliases a source input', self.command('build', expected=1).stderr)
                self.assertEqual(script.read_text(), original)

    @unittest.skipUnless(TEX, 'real latexmk and pdflatex required')
    def test_f1_listings_auxiliary_cannot_overwrite_an_external_file(self):
        view = self.native('\\documentclass{article}\n\\usepackage{listings}\n\\begin{document}\n\\lstlistoflistings\n'
                           '\\begin{lstlisting}[caption=Demo]\nexample\n\\end{lstlisting}\n\\end{document}\n')
        stem = latex.output_paths(self.project, view)[2]
        stem.parent.mkdir(parents=True, exist_ok=True)
        outside = self.root / 'outside.txt'
        outside.write_text('keep')
        Path(str(stem) + '.lol').symlink_to(outside)
        self.command('build', expected=1)
        self.assertEqual(outside.read_text(), 'keep')

    def test_f3_graphics_search_paths_in_fragments_add_all_candidates(self):
        (self.project / 'figures').mkdir()
        (self.project / 'other').mkdir()
        (self.project / 'paths.tex').write_text('\\graphicspath{\n {figures/} {other/}\n}\n')
        (self.project / 'main.tex').write_text(SOURCE.replace('Fixture.', '\\input{paths}\\includegraphics*{plot}\\includegraphics{fixed.png}'))
        for name in ('figures/plot.png', 'other/plot.pdf', 'figures/fixed.png', 'other/fixed.png'):
            (self.project / name).write_bytes(b'fixture')
        view = schema.document_settings(self.configure())
        dependencies = latex.manuscript_dependencies(self.project, view)
        for name in ('figures/plot.png', 'other/plot.pdf', 'figures/fixed.png', 'other/fixed.png'):
            self.assertIn(name, dependencies)

    @unittest.skipUnless(TEX, 'real latexmk and pdflatex required')
    def test_f3_preferred_graphic_invalidates_and_rebuilds_the_pdf(self):
        (self.project / 'figures').mkdir()
        (self.project / 'figures/plot.png').write_bytes(red_png())
        view = self.native('\\documentclass{article}\n\\usepackage{graphicx}\n\\graphicspath{{figures/}}\n'
                           '\\begin{document}\\includegraphics[width=1cm]{plot}\\end{document}\n')
        self.command('build')
        stem = latex.output_paths(self.project, view)[2]
        before = Path(str(stem) + '.pdf').read_bytes()
        self.run_command('pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-jobname=plot',
                         '-output-directory=figures', SOURCE.replace('Fixture.', 'New preferred figure.').replace('\n', ' '))
        self.assertEqual(latex.receipt_state(self.project, view), 'stale')
        self.command('build')
        self.assertEqual(latex.receipt_state(self.project, view), 'current')
        self.assertIn('figures/plot.pdf', Path(str(stem) + '.fls').read_text())
        self.assertNotEqual(before, Path(str(stem) + '.pdf').read_bytes())

    def test_f4_recipeprefix_selects_the_projects_own_check(self):
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
        (self.project / 'main.tex').write_text(SOURCE.replace('Fixture.', '<<<<<<< HEAD\nOld\n=======\nNew\n>>>>>>> topic\n'))
        self.builder()
        self.configure()
        self.install('init', '--skip-editor')
        result = self.command('check', expected=1)
        self.assertIn('conflict marker', result.stderr)

    def test_f5_full_check_covers_inputs_first_discovered_by_the_compiler(self):
        (self.project / 'hidden.txt').write_text('<<<<<<< HEAD\nOld\n>>>>>>> topic\n')
        self.builder(inputs=('main.tex', 'hidden.txt'))
        self.configure()
        self.install('init', '--skip-editor')
        result = self.command('document-check', expected=1)
        self.assertIn('hidden.txt', result.stderr)

    def test_f6_comment_stripping_counts_backslash_parity(self):
        for count in range(6):
            source = 'prefix ' + '\\' * count + '% comment'
            expected = source if count % 2 else source[:source.index('%')]
            with self.subTest(backslashes=count):
                self.assertEqual(latex.tex_without_comments(source), expected)

    def test_f6_commented_bibliography_after_linebreak_does_not_block_init(self):
        (self.project / 'main.tex').write_text(SOURCE.replace('Fixture.', 'Text.\\\\% \\bibliography{missing}\nMore.'))
        self.install('init', '--no-lint', '--skip-editor')
        self.assertEqual(schema.document_settings(schema.load_config(self.project)).bibliography['backend'], 'none')

    def test_f7_bibliography_backend_and_discovery_accept_the_same_whitespace(self):
        (self.project / 'refs.bib').write_text('@misc{fixture,title={Synthetic fixture}}\n')
        for whitespace in (' ', '\n', '\t'):
            with self.subTest(whitespace=repr(whitespace)):
                (self.project / 'main.tex').write_text(SOURCE.replace('Fixture.', '\\bibliography' + whitespace + '{refs}'))
                args = argparse.Namespace(modules=None, root=None, build_command=None,
                    no_lint=True, skip_editor=True, editor=False)
                config = bootstrap.detect_config(self.project, bootstrap.discover(self.project), args)
                view = schema.document_settings(config)
                self.assertEqual(view.bibliography['backend'], 'bibtex')
                self.assertEqual(view.bibliography['files'], ['refs.bib'])

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
        (self.project / 'notes.tex').write_text(SOURCE)
        config = self.configure(documents_={'paper': {'root': 'main.tex'}, 'notes': {'root': 'notes.tex'}})
        with patch.object(latex, 'manuscript_dependencies', wraps=latex.manuscript_dependencies) as scan:
            runtime.validation_plan(self.project, config, ['main.tex'])
        self.assertEqual(scan.call_count, 2)

    def test_o3_snapshot_inventories_files_only_after_taking_its_lock(self):
        @contextlib.contextmanager
        def waited_lock(*args, **kwargs):
            (self.project / 'new.txt').write_text('Created while this run waited')
            yield
        with patch.object(snapshot, 'operation_lock', waited_lock), contextlib.redirect_stdout(io.StringIO()):
            result = snapshot.take(self.project, base=self.root / 'snapshots')
        repository = Path(result['store']) / 'manual'
        self.assertIn('new.txt', snapshot.git(repository, None, 'ls-tree', '-r', '--name-only', result['commit']).splitlines())


if __name__ == '__main__':
    unittest.main()
