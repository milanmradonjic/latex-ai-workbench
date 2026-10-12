"""Process identity, liveness and cooperative interruption for owned commands."""
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import sys


class Interrupted(BaseException):
    def __init__(self, number):
        self.number = number
        self.exit_status = 128 + number


def launch(descriptor, command):
    """Execute only after the parent publishes ownership; EOF means it died."""
    try:
        released = os.read(descriptor, 1) == b'1'
    finally:
        os.close(descriptor)
    if not released:
        return 125
    try:
        os.execvpe(command[0], command, os.environ)
    except OSError as error:
        print(f'Cannot execute {command[0]}: {error}', file=sys.stderr)
        return 127


def state(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return {'state': fields[0], 'group': int(fields[2]), 'session': int(fields[3]), 'token': fields[19]}
    except (OSError, IndexError, ValueError):
        return None


def token(pid):
    """A birth token that changes when the PID is reused: the start time in clock ticks from /proc, or,
    where there is no /proc (macOS, the BSDs), the start time POSIX ps reports."""
    value = state(pid)
    if value:
        return value['token']
    if type(pid) is not int or pid <= 0 or os.name != 'posix':
        return None
    try:
        done = subprocess.run(['ps', '-o', 'lstart=', '-p', str(pid)], capture_output=True, text=True, timeout=5,
                              env={**os.environ, 'LC_ALL': 'C'})
    except (OSError, subprocess.SubprocessError):
        return None
    started = ' '.join(done.stdout.split())
    return f'ps:{started}' if done.returncode == 0 and started else None


def alive(pid, birth=None):
    if type(pid) is not int or pid <= 0:
        return False
    value = state(pid)
    if value:
        return value['state'] not in {'Z', 'X'} and (birth is None or birth == value['token'])
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return birth is None or token(pid) == birth


def group_alive(group, birth=None):
    if type(group) is not int or group <= 0 or os.name != 'posix':
        return False
    leader = state(group)
    if birth is not None and leader and leader['token'] != birth:
        return False  # the group number now belongs to a different session leader
    proc = Path('/proc')
    if leader is None and birth is not None and not proc.is_dir():
        current = token(group)
        if current is not None and current != birth:
            return False  # without /proc the leader's start time tells a reused group number apart
    if proc.is_dir():
        for entry in proc.iterdir():
            if entry.name.isdigit():
                value = state(int(entry.name))
                if value and value['group'] == group and value['state'] not in {'Z', 'X'}:
                    if birth is None or value['session'] == group:
                        return True
        return False
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def jobserver_fds(env):
    """Preserve only open pipe jobserver descriptors already delegated by Make."""
    if os.name != 'posix':
        return ()
    value = (env or os.environ).get('MAKEFLAGS', '')
    match = re.search(r'--jobserver-(?:auth|fds)=(\d+),(\d+)(?:\s|$)', value)
    if not match:
        return ()  # FIFO jobservers do not need inherited descriptors.
    result = []
    for number in match.groups():
        descriptor = int(number)
        if descriptor <= 2:
            continue
        try:
            os.fstat(descriptor)
        except OSError:
            return ()
        result.append(descriptor)
    return tuple(result)


def make_dry_run(env=None):
    flags = (env or os.environ).get('MAKEFLAGS', '').split()
    return bool(flags and '=' not in flags[0] and not flags[0].startswith('--') and set('nqt') & set(flags[0])) or any(
        flag in {'--just-print', '--dry-run', '--recon', '--question', '--touch', '-n', '-q', '-t'} for flag in flags)


def stop(process, grouped, grace=5):
    def signal_all(number):
        try:
            os.killpg(process.pid, number) if grouped else process.send_signal(number)
        except OSError:
            pass
    handlers = {}
    if threading.current_thread() is threading.main_thread():
        for number in (signal.SIGINT, signal.SIGTERM):
            handlers[number] = signal.signal(number, signal.SIG_IGN)
    try:
        signal_all(signal.SIGTERM)
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
        signal_all(getattr(signal, 'SIGKILL', signal.SIGTERM))
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
    finally:
        for number, handler in handlers.items():
            signal.signal(number, handler)


if __name__ == '__main__':
    if len(sys.argv) < 4 or sys.argv[1] != '--launch':
        raise SystemExit('process launch requires a private gate and command')
    raise SystemExit(launch(int(sys.argv[2]), sys.argv[3:]))
