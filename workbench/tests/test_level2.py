"""The Level 2 contract: file checks or one complete project check."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import core
import latex
import runtime
import schema
from test_support import ProjectCase


class Level2Routing(ProjectCase):
    def setUp(self):
        super().setUp()
        for name in ('main.tex', 'supplement.tex'):
            (self.project / name).write_text('\\documentclass{article}\\begin{document}x\\end{document}\n')
        self.config = self.configure(documents_={
            'paper': {'root': 'main.tex'}, 'supplement': {'root': 'supplement.tex'}})

    def plan(self, *paths):
        return runtime.validation_plan(self.project, self.config, list(paths))

    def test_files_or_full_with_all_documents(self):
        files = ('README.md', 'analysis/results.json', 'analysis/calculate.py',
                 'notes/session.txt', 'notes/config.yaml', 'change.diff', 'change.patch',
                 'archive/main.tex', 'archive/references.bib', 'archive/Makefile',
                 'archive/old.pdf', 'revision/baseline/old.tex', 'archive/.latex-ai/core.py')
        full = ('main.tex', 'references.bib', 'figures/plot.pdf', 'data/table.csv',
                'style.cls', 'unknown.bin', 'Makefile', core.CONFIG, '.vscode/tasks.json',
                '.latex-ai/latex.py', '.chktex-baseline.json', 'archive-old/main.tex',
                'baseline-results/plot.pdf', 'Archive/old.tex')
        for level, paths in (('files', files), ('full', full)):
            for name in paths:
                with self.subTest(path=name):
                    plan = self.plan(name)
                    self.assertEqual(plan['level'], level)
                    self.assertEqual(plan['actions'], ['full'] if level == 'full' else [])
                    self.assertEqual(plan['documents'], ['paper', 'supplement'] if level == 'full' else [])
                    for obsolete in ('document_reasons', 'project_check', 'unit', 'portability', 'bibliography', 'package', 'manuscript', 'files'):
                        self.assertNotIn(obsolete, plan)
        self.assertEqual(self.plan('README.md', 'figures/plot.pdf')['level'], 'full')

    def test_routing_does_not_inspect_source_recorder_or_dependency_identities(self):
        (self.project / 'main.tex').write_text('\\input{notes.md}\\lstinputlisting{helper.py}')
        with patch.object(latex, 'manuscript_dependencies', side_effect=AssertionError('dependency scan')):
            self.assertEqual(self.plan('notes.md', 'helper.py')['level'], 'files')

    def test_configured_builder_and_lint_baseline_are_controls_even_when_deleted(self):
        self.config['documents']['paper']['build_command'] = ['python3', '-B', 'scripts/build.py']
        self.config['documents']['paper']['lint'] = {'enabled': True, 'baseline': 'accepted.json'}
        for name in ('scripts/build.py', 'accepted.json'):
            with self.subTest(path=name):
                self.assertFalse((self.project / name).exists())
                self.assertEqual(self.plan(name)['level'], 'full')
        self.assertEqual(self.plan('analysis/calculate.py')['level'], 'files')

    def test_archived_policy_does_not_check_active_policy(self):
        plan = self.plan('archive/CLAUDE.md', 'revision/baseline/.claude/settings.json')
        self.assertFalse(plan['policy'])
        self.assertEqual(plan['level'], 'files')
        self.assertTrue(self.plan('CLAUDE.md', '.codex/rules/git-safety.rules')['policy'])

    def test_full_invokes_canonical_check_once_and_files_only_invokes_nothing(self):
        plan = self.plan('main.tex', 'supplement.tex')
        with patch.object(runtime, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            runtime.validate_changes(self.project, plan)
        self.assertEqual([call.args[0] for call in run.call_args_list], [['make', 'check']])
        for selected, override in ((self.plan('README.md'), False), (plan, True)):
            with patch.object(runtime, 'run', side_effect=AssertionError('build invoked')), contextlib.redirect_stdout(io.StringIO()):
                runtime.validate_changes(self.project, selected, files_only=override)

    def test_failed_build_promotes_a_clean_comparison_to_full(self):
        with patch('documents.failed', return_value=['supplement']):
            plan = self.plan()
        self.assertEqual(plan['level'], 'full')
        self.assertEqual(plan['documents'], ['paper', 'supplement'])
        self.assertEqual(plan['failed_documents'], ['supplement'])
        self.assertEqual(self.plan()['level'], 'files')

    def test_patches_get_integrity_checks_without_parsing_embedded_code(self):
        path = self.project / 'revision.patch'
        path.write_text('--- before.py\n+++ after.py\n@@ -1 +1 @@\n-def valid(): pass\n+def broken(\n')
        with contextlib.redirect_stdout(io.StringIO()):
            runtime.file_checks(self.project, self.plan(path.name))
        path.write_text('<<<<<<< HEAD\nunresolved\n>>>>>>> branch\n')
        with self.assertRaisesRegex(core.WorkbenchError, 'conflict marker'):
            runtime.file_checks(self.project, self.plan(path.name))

    def test_removed_routing_configuration_is_rejected(self):
        for key, value in (('ignore', ['docs/**']), ('manuscript_inputs', ['data/*.json']), ('package', None)):
            config = {**self.config, 'validation': {key: value}}
            with self.subTest(key=key), self.assertRaisesRegex(core.WorkbenchError, 'validation'):
                schema.validate_config(self.project, config)


if __name__ == '__main__':
    unittest.main()
