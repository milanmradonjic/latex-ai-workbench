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
    def test_actual_make_3_81_runs_the_generated_makefile(self):
        """3.0.2 F2, now simpler: the Makefile init writes asks nothing of the Make version, so the one macOS ships runs it."""
        (self.project / 'main.tex').write_text('\\documentclass{article}\n\\begin{document}Fixture.\\end{document}\n')
        self.builder()
        self.configure()
        # Select old Make without accidentally selecting stock macOS Python (<3.10).
        env = {**self.env, 'PATH': str(OLD_MAKE.parent) + os.pathsep + self.env.get('PATH', ''), 'PYTHON': sys.executable}
        package = Path(__file__).resolve().parents[1]
        self.run_command(sys.executable, '-B', str(package / 'latex-ai-init'), 'init', '--skip-editor', str(self.project), env=env)
        for goal in ('help', 'status', 'doctor', 'check'):
            with self.subTest(goal=goal):
                self.run_command(str(OLD_MAKE), goal, env=env)
        self.assertEqual(self.state(), 'current')


if __name__ == '__main__':
    unittest.main()
