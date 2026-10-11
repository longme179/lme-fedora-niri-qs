"""Own one swayidle child and use swaylock's ready-fd before sleeping."""
import argparse
import ctypes
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading

PR_SET_PDEATHSIG = 1

DEFAULT_IDLE_PROFILES = {
    'ac': {'display': 10, 'lock': 15, 'suspend': 0},
    'battery': {'display': 3, 'lock': 5, 'suspend': 15},
}


def validate_profiles(value):
    if not isinstance(value, dict) or set(value) != {'ac', 'battery'}: raise ValueError('Provide AC and battery idle profiles')
    for profile in value.values():
        if not isinstance(profile, dict) or set(profile) != {'display', 'lock', 'suspend'}: raise ValueError('Invalid idle profile')
        if any(type(v) is not int or not 0 <= v <= 240 for v in profile.values()): raise ValueError('Idle timeouts must be 0–240 minutes')
        if profile['lock'] and profile['suspend'] and profile['lock'] > profile['suspend']: raise ValueError('Lock must happen before automatic suspend')
    return {key: dict(profile) for key, profile in value.items()}


def idle_command(profile, lock_before_sleep, runner):
    helper = Path(__file__).resolve()
    lock = shlex.join([sys.executable, str(helper), 'lock'])
    argv = [runner.executable('swayidle'), '-w']
    if profile['lock']: argv += ['timeout', str(profile['lock']*60), lock]
    if profile['display']:
        argv += ['timeout', str(profile['display']*60), shlex.join([runner.executable('niri'), 'msg', 'action', 'power-off-monitors']),
                 'resume', shlex.join([runner.executable('niri'), 'msg', 'action', 'power-on-monitors'])]
    if profile['suspend']:
        sleep = [sys.executable, str(helper), 'sleep'] + (['--lock'] if lock_before_sleep else [])
        argv += ['timeout', str(profile['suspend']*60), shlex.join(sleep)]
    if lock_before_sleep: argv += ['before-sleep', lock]
    argv += ['after-resume', shlex.join([runner.executable('niri'), 'msg', 'action', 'power-on-monitors'])]
    return argv


class IdleControl:
    def __init__(self, runner):
        self.runner, self.child, self.log = runner, None, None
        self.signature = None
        self.error = ''
        self.paused = False

    def close(self):
        if self.child:
            if self.child.poll() is None:
                try: os.killpg(self.child.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: self.child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try: os.killpg(self.child.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    self.child.wait(timeout=2)
            self.child = None
            # Restore displays when switching profiles, disabling idle, or exiting.
            try: self.runner.run('niri', 'msg', 'action', 'power-on-monitors')
            except (RuntimeError, OSError): pass
        if self.log: self.log.close(); self.log = None

    def sync(self, preferences, ac_online):
        source = 'ac' if ac_online else 'battery'
        profile = preferences['idleProfiles'][source]
        signature = (preferences['idleEnabled'], self.paused, source, tuple(profile[k] for k in ("display", "lock", "suspend")), preferences['idleLockBeforeSleep'])
        required = ['swayidle', 'niri']
        if profile['lock'] or preferences['idleLockBeforeSleep']: required.append('swaylock')
        if profile['suspend']: required.append('systemctl')
        missing = [name for name in required if not self.runner.available(name)]
        if signature != self.signature:
            self.close(); self.signature = signature; self.error = ''
            if preferences['idleEnabled'] and not self.paused:
                if missing: self.error = 'Install ' + ', '.join(missing) + ' to enable this idle profile.'
                else:
                    try:
                        self.log = tempfile.TemporaryFile(mode='w+')
                        argv = [sys.executable, str(Path(__file__).resolve()), '--parent', str(os.getpid()), 'client', *idle_command(profile, preferences['idleLockBeforeSleep'], self.runner)]
                        self.child = subprocess.Popen(argv,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=self.log, start_new_session=True)
                    except OSError as exc: self.error = 'Could not start swayidle: ' + str(exc)
        if self.child and self.child.poll() is not None:
            self.log.seek(0); self.error = 'swayidle stopped: ' + self.log.read()[-400:].strip()
            self.close()
        if self.log:
            size = os.fstat(self.log.fileno()).st_size
            if size: self.error = os.pread(self.log.fileno(), min(size, 400), max(0, size-400)).decode(errors='replace').strip()
        return {'enabled': preferences['idleEnabled'], 'running': self.child is not None,
                'paused': self.paused, 'source': source, 'profile': profile,
                'available': not missing, 'error': self.error}


def process_birth(pid):
    try: return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError): return None


def secure_lock():
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime: raise RuntimeError('XDG_RUNTIME_DIR is required to lock the session')
    directory = Path(runtime) / 'lme-shell'
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    state = directory / 'session-lock.json'
    with open(directory / 'session-lock.guard', 'a+') as guard:
        os.chmod(guard.name, 0o600); fcntl.flock(guard, fcntl.LOCK_EX)
        try:
            saved = json.loads(state.read_text())
            if process_birth(saved['pid']) == saved['born'] and saved['born'] is not None: return
        except (OSError, ValueError, KeyError, TypeError): pass
        executable = shutil.which('swaylock')
        if not executable: raise RuntimeError('Install swaylock before enabling session locking')
        read_fd, write_fd = os.pipe()
        child = None
        try:
            with tempfile.TemporaryFile(mode='w+') as log:
                child = subprocess.Popen([executable, '--ready-fd', str(write_fd), '--color', '22212c'],
                    pass_fds=(write_fd,), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
                os.close(write_fd); write_fd = -1
                ready, _, _ = select.select([read_fd], [], [], 12)
                if not ready or not os.read(read_fd, 1) or child.poll() is not None:
                    log.seek(0); raise RuntimeError('Session lock was not confirmed: ' + log.read()[-300:].strip())
                born = process_birth(child.pid)
                if born is None: raise RuntimeError('Session lock exited before it was confirmed')
                state.write_text(json.dumps({'pid': child.pid, 'born': born})); os.chmod(state, 0o600)
                threading.Thread(target=child.wait, daemon=True).start()
        except BaseException:
            if child and child.poll() is None: child.terminate(); child.wait(timeout=3)
            raise
        finally:
            os.close(read_fd)
            if write_fd >= 0: os.close(write_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['lock', 'sleep', 'client'])
    parser.add_argument('--parent', type=int)
    parser.add_argument('--lock', action='store_true')
    args, command = parser.parse_known_args()
    if args.action != 'client' and command: parser.error('Unexpected arguments: ' + ' '.join(command))
    try:
        if args.action == 'client':
            if not args.parent or not command: raise RuntimeError('Idle client requires its parent and command')
            # Quickshell may kill the backend without cleanup; Linux then stops swayidle too.
            libc = ctypes.CDLL(None, use_errno=True)
            libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
            if libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0): raise OSError(ctypes.get_errno(), 'Cannot supervise swayidle')
            if os.getppid() != args.parent: return 0
            os.execv(command[0], command)
        if args.action == 'lock' or args.lock: secure_lock()
        if args.action == 'sleep': subprocess.run(['systemctl', 'suspend'], check=True, timeout=30)
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr); return 1

if __name__ == '__main__': raise SystemExit(main())
