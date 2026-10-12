"""Phase 0 macOS verification: regressions against the actual older GNU Make parser."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_support import ProjectCase


OLD_MAKE = Path('/usr/bin/make')
HAS_OLD_MAKE = OLD_MAKE.is_file() and subprocess.run(
    [str(OLD_MAKE), '--version'], capture_output=True, text=True
).stdout.startswith('GNU Make 3.81')


class Repairs(ProjectCase):
    @unittest.skipUnless(HAS_OLD_MAKE, 'Actual GNU Make 3.81 required')
    def test_actual_make_3_81_keeps_adopted_project_and_read_only_goals(self):
        """3.0.2 F2: .FEATURES= on modern Make missed the unsupported private modifier."""
        (self.project / 'main.tex').write_text(
            '\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n')
        (self.project / 'Makefile').write_text('.PHONY: pdf\npdf:\n\t@echo project pdf rule\n')
        self.configure({'paper': {'root': 'main.tex', 'output_dir': '.',
                                  'lint': {'enabled': False}, 'build_command': ['make', 'pdf']}})
        # Select old Make without accidentally selecting stock macOS Python (<3.10).
        env = {**self.env, 'PATH': str(OLD_MAKE.parent) + os.pathsep + self.env.get('PATH', ''),
               'PYTHON': sys.executable}
        package = Path(__file__).resolve().parents[1]
        installed = self.run_command(sys.executable, '-B', str(package / 'latex-ai-init'),
                                     'init', '--skip-editor', str(self.project), env=env)
        self.assertIn('NOTE', installed.stdout)
        self.assertIn('GNU Make 4.3', installed.stdout)
        self.assertIn('project pdf rule', self.run_command(str(OLD_MAKE), 'pdf', env=env).stdout)
        for goal in ('help', 'status'):
            with self.subTest(goal=goal):
                self.run_command(str(OLD_MAKE), goal, env=env)
        for goal in ('latex-ai-build', 'check'):
            with self.subTest(goal=goal):
                refused = self.run_command(str(OLD_MAKE), goal, expected=2, env=env)
                self.assertIn('require GNU Make 4.3', refused.stdout + refused.stderr)
        doctor = self.run_command(str(OLD_MAKE), 'doctor', expected=2, env=env)
        self.assertIn('GNU Make 4.3+', doctor.stdout + doctor.stderr)


if __name__ == '__main__':
    unittest.main()
