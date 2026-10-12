"""Journal displaced compiler outputs until their replacement has been verified.

Recovery restores missing originals only. It never overwrites a replacement or
silently reuses another attempt's backup, including after abrupt process death.
"""
import json
import shutil
import uuid

from core import WorkbenchError, atomic_write, local_path, path_name

UNVERIFIED = '.latex-ai/artifacts/unverified'


class OutputTransaction:
    def __init__(self, project, document, paths):
        self.project = project
        self.directory = local_path(project, f'{UNVERIFIED}/{document}/{uuid.uuid4().hex}')
        self.directory.mkdir(parents=True)
        self.journal = self.directory / 'journal.json'
        self.entries = [{'original': path_name(project, path.relative_to(project).as_posix()),
                         'backup': (self.directory / path.name).relative_to(project).as_posix()}
                        for path in paths if path.is_file()]
        self.write('prepared')  # record intent before the first move

    def write(self, status):
        atomic_write(self.journal, json.dumps({'schema_version': 1, 'status': status, 'entries': self.entries}, indent=2)+'\n')

    def displace(self):
        for entry in self.entries:
            shutil.move(str(local_path(self.project, entry['original'])),
                        str(local_path(self.project, entry['backup'])))
        self.write('displaced')

    def restore_missing(self):
        missing = []
        for entry in self.entries:
            original = local_path(self.project, entry['original'])
            backup = local_path(self.project, entry['backup'])
            if not original.exists():
                missing.append(original)
                if not backup.is_file():
                    raise WorkbenchError(f'Cannot recover {entry["original"]}; inspect {self.journal.relative_to(self.project)}')
                shutil.move(str(backup), str(original))
        return missing

    def rollback(self):
        self.restore_missing()
        settle(self.project, self.journal, self.entries)

    def commit(self):
        self.write('verified')
        for entry in self.entries:
            local_path(self.project, entry['backup']).unlink(missing_ok=True)
        self.journal.unlink()
        self.directory.rmdir()


def settle(project, journal, entries):
    """Retire restored/unmoved intent; archive only original bytes still displaced."""
    remaining = [entry for entry in entries if local_path(project, entry['backup']).is_file()]
    if remaining:
        atomic_write(journal, json.dumps({'schema_version': 1, 'status': 'failed', 'entries': remaining}, indent=2)+'\n')
    else:
        journal.unlink()
        journal.parent.rmdir()


def recover(project, document):
    root = local_path(project, f'{UNVERIFIED}/{document}')
    if not root.is_dir():
        return
    for journal in sorted(root.glob('*/journal.json')):
        try:
            value = json.loads(journal.read_text())
            entries = value['entries']
            if value.get('schema_version') != 1 or not isinstance(entries, list):
                raise ValueError('unsupported journal')
            status = value.get('status')
            if status not in {'prepared', 'displaced', 'failed', 'verified'}:
                raise ValueError('invalid journal status')
            for entry in entries:
                if not isinstance(entry, dict) or set(entry) != {'original','backup'}:
                    raise ValueError('invalid output entry')
                original = local_path(project, entry['original'])
                backup = local_path(project, entry['backup'])
                if backup.parent != journal.parent.resolve():
                    raise ValueError('backup outside its attempt')
                if status == 'verified':
                    backup.unlink(missing_ok=True)
                elif status != 'failed' and not original.exists():
                    if not backup.is_file():
                        raise ValueError(f'missing original and backup: {entry["original"]}')
                    shutil.move(str(backup), str(original))
                    print(f'Restored interrupted build output: {entry["original"]}')
            settle(project, journal, entries)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise WorkbenchError(f'Cannot recover interrupted outputs from {journal.relative_to(project)}: {error}',
                                 hint='preserve the journal and backups; inspect them before rebuilding') from error
