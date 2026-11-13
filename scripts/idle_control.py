"""Own one swayidle child; the native lock owns locking, swaylock is the fallback.
Callers/callees: see config/architecture.json and docs/WORKSPACE_MAP.md (owner: idle; Phase 3 graph).
Q4 split: IdleControl (the swayidle ownership/sync) is DEPRECATED(Q4->Q6) — the native
IdleState.qml serves it — but this file STAYS as the session-infrastructure helper:
the lock/prepare-sleep/resume subcommands (swayidle invokes them; flock + ready-fd +
/proc birth checks + the IPC status polling are outside quickshell 0.3.2's API surface,
the same infra-helper pattern as the pkexec charge helper), the PDEATHSIG client
wrapper for both swayidle and wlsunset, and the probe subcommand the native services
use for availability discovery.

Phase 2 (idle rewiring, iNiR Idle.qml v3.1.0 semantics): the shell's native lock
(LockState.qml, the `lock` IPC target) is the primary locker; secure_lock()'s swaylock
stays as the fail-closed fallback for demo sessions, boot windows and a stuck shell.
`prepare-sleep` is the before-sleep handshake — swayidle holds logind's delay
inhibitor while it runs, but a delay inhibitor can only delay the sleep: logind
ignores it after InhibitDelayMaxSec (default 5s) and the command continues after
resume, so the handshake is deadline-budgeted to finish the secure-or-fallback
decision inside that window.
`resume` is the after-resume hook: power the displays back on and refocus the lock
input (niri drops lock-surface focus after resume).
"""
import argparse
import ctypes
import fcntl
import json
import os
from pathlib import Path
import select
import shutil
import signal
import shlex
import subprocess
import sys
import tempfile
import threading
import time

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


def effective_lock_seconds(profile, lock_before_sleep):
    """The idle lock timer (iNiR Idle.qml): with suspend and lock-before-sleep on, the
    lock must engage before the suspend timer fires — pull it 5 seconds earlier when
    the raw lock timeout is disabled or would fire later than the suspend timeout."""
    if not profile['lock'] and not lock_before_sleep: return 0
    if not profile['suspend'] or not lock_before_sleep: return profile['lock']*60
    floor = max(1, profile['suspend']*60 - 5)
    return floor if (not profile['lock'] or profile['lock']*60 > floor) else profile['lock']*60


def idle_command(profile, lock_before_sleep, runner):
    helper = Path(__file__).resolve()
    argv = [runner.executable('swayidle'), '-w']
    lock_seconds = effective_lock_seconds(profile, lock_before_sleep)
    if lock_seconds: argv += ['timeout', str(lock_seconds), shlex.join([sys.executable, str(helper), 'lock'])]
    if profile['display']:
        argv += ['timeout', str(profile['display']*60), shlex.join([runner.executable('niri'), 'msg', 'action', 'power-off-monitors']),
                 'resume', shlex.join([runner.executable('niri'), 'msg', 'action', 'power-on-monitors'])]
    if profile['suspend']:
        argv += ['timeout', str(profile['suspend']*60), shlex.join([sys.executable, str(helper), 'sleep'])]
    if lock_before_sleep: argv += ['before-sleep', shlex.join([sys.executable, str(helper), 'prepare-sleep'])]
    argv += ['after-resume', shlex.join([sys.executable, str(helper), 'resume'])]
    return argv


class IdleControl:
    """DEPRECATED(Q4->Q6): native IdleState.qml owns the swayidle child; A/B window."""

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
        required = ['swayidle', 'niri']  # the native lock is the primary locker; swaylock is only its fallback
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


def swaylock_engaged():
    """Read-only variant of secure_lock's single-instance guard: is a confirmed
    swaylock still alive? (The native lock is not tracked here — engaging it over a
    live swaylock would stack two session-lock clients.)"""
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime: return False
    try:
        saved = json.loads((Path(runtime)/'lme-shell/session-lock.json').read_text())
        return process_birth(saved['pid']) == saved['born'] and saved['born'] is not None
    except (OSError, ValueError, KeyError, TypeError): return False


def quickshell_binary():
    # The deploy wrapper exports the deployment's private binary; PATH covers the rest.
    binary = os.environ.get('LME_QS_BINARY')
    if binary and Path(binary).exists(): return binary
    return shutil.which('quickshell')


# logind ignores a delay inhibitor after InhibitDelayMaxSec (default 5s) and sleeps
# anyway — the handshake must decide secure-or-fallback inside that window, leaving
# roughly a second for the swaylock fallback to engage.
HANDSHAKE_BUDGET = 4.0


def lock_ipc(function, *args, timeout=3.0):
    """Call the shell's lock IPC; None when the shell (or its lock target) is unreachable."""
    binary = quickshell_binary()
    if not binary: return None
    try:
        result = subprocess.run([binary, '-c', 'lme-shell', 'ipc', 'call', 'lock', function, *args],
                                capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError): return None
    return result.stdout.strip() if result.returncode == 0 else None


def wait_lock_status(states, attempts, delay=0.05, timeout=1.0, deadline=None):
    for _ in range(attempts):
        if lock_ipc('status', timeout=timeout) in states: return True
        if deadline is not None and time.monotonic() >= deadline: return False
        time.sleep(delay)
    return False


def native_lock():
    """The idle-timeout lock: engage the shell's native lock, fall back to swaylock.
    Mirrors Super+L — no secure handshake needed, nothing downstream waits on it."""
    if swaylock_engaged(): return
    response = lock_ipc('activate')
    if response is not None and wait_lock_status(('locked', 'secure'), 20): return
    lock_ipc('deactivate')  # do not stack swaylock over a half-engaged native lock
    wait_lock_status(('unlocked',), 10)
    secure_lock()  # fail closed: raises when neither locker can take the session


def prepare_sleep():
    """The before-sleep handshake (iNiR inir `lock prepareSleep`): swayidle holds
    logind's delay inhibitor while this runs, but a delay inhibitor cannot cancel the
    sleep — logind ignores it after InhibitDelayMaxSec (default 5s) and the command
    keeps running after resume (man swayidle). The shared budget below keeps the
    secure-or-swaylock decision inside that window; the exit code only reports
    whether the session got protected — swayidle releases the inhibitor either way."""
    deadline = time.monotonic() + HANDSHAKE_BUDGET
    if swaylock_engaged(): return
    have_swaylock = shutil.which('swaylock') is not None
    # Boot window: the lock IPC registers after the first shell frame — a fast-failing
    # call retries for the whole budget (a lid close during boot still fails closed
    # below); a hung call burns its timeout against the same budget and falls back.
    response = lock_ipc('prepareSleep', timeout=1.0)
    while response is None and time.monotonic() < deadline:
        time.sleep(0.1)
        response = lock_ipc('prepareSleep', timeout=1.0)
    if response is None:
        if have_swaylock: secure_lock(); return
        raise RuntimeError('Lock IPC was unavailable before sleep and no fallback could secure the session')
    if response == 'secure': return
    # 'unlocked' = the demo/env gates keep the native lock inert → the swaylock path.
    if response != 'unlocked' and wait_lock_status(('secure',), 20, deadline=deadline): return
    if have_swaylock:
        lock_ipc('deactivate', timeout=1.0)  # do not race a second ext-session-lock client against QS
        wait_lock_status(('unlocked',), 10, deadline=deadline)
        try:
            secure_lock(); return
        except (OSError, RuntimeError):
            lock_ipc('prepareSleep', timeout=1.0)  # restore the QS lock request, keep waiting
    else:
        # Not inert, not secure, no fallback: raise swaylock's own guidance if absent.
        secure_lock(); return
    # Past the budget this may already be running post-resume — confirming the
    # restored request (or failing loud) still beats returning silently.
    if wait_lock_status(('secure',), 40, deadline=deadline + 2.0): return
    raise RuntimeError('Lock did not become secure before sleep')


def resume():
    """The after-resume hook: power the displays back on and refocus the lock input
    (niri drops lock-surface focus after resume). Both steps are best-effort — the
    2s focus heartbeat inside the shell is the safety net."""
    try:
        subprocess.run(['niri', 'msg', 'action', 'power-on-monitors'], timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError): pass
    lock_ipc('focus')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['lock', 'sleep', 'prepare-sleep', 'resume', 'client', 'probe'])
    parser.add_argument('--parent', type=int)
    args, command = parser.parse_known_args()
    if args.action not in ('client', 'probe') and command: parser.error('Unexpected arguments: ' + ' '.join(command))
    try:
        if args.action == 'probe':
            # Availability discovery for the native services: print the missing names.
            print(' '.join(name for name in command if not shutil.which(name)))
            return 0
        if args.action == 'client':
            if not args.parent or not command: raise RuntimeError('Idle client requires its parent and command')
            # Quickshell may kill the backend without cleanup; Linux stops its owned client too.
            libc = ctypes.CDLL(None, use_errno=True)
            libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
            if libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0): raise OSError(ctypes.get_errno(), 'Cannot supervise session client')
            if os.getppid() != args.parent: return 0
            # execvp (PATH-resolved): the native services pass plain command names where the
            # backend passed which()-resolved absolute paths — both resolve to the same binary.
            os.execvp(command[0], command)
        if args.action == 'lock': native_lock()
        if args.action == 'prepare-sleep': prepare_sleep()
        if args.action == 'resume': resume()
        if args.action == 'sleep': subprocess.run(['systemctl', 'suspend'], check=True, timeout=30)
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr); return 1

if __name__ == '__main__': raise SystemExit(main())
