#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""User-triggered Git updates, detached from Quickshell's hot-reload lifetime."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


BUSY = {'checking', 'updating'}


class ShellUpdate:
    def __init__(self, repo, state_dir=None):
        self.repo = Path(repo).resolve()
        folder = Path(state_dir or Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local/state')/'lme-shell')
        key = hashlib.sha256(os.fsencode(self.repo)).hexdigest()[:16]
        self.path = folder / f'update-{key}.json'
        self.lock_path = self.path.with_suffix('.lock')
        self.worker = None

    def git(self, *args, timeout=15):
        env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='/bin/false', SSH_ASKPASS='/bin/false')
        env.setdefault('GIT_SSH_COMMAND', 'ssh -o BatchMode=yes -o ConnectTimeout=15')
        try:
            result = subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True,
                                    text=True, timeout=timeout, env=env)
        except FileNotFoundError:
            raise ValueError('Git is unavailable. Install git to enable shell updates.') from None
        if result.returncode:
            message = re.sub(r'(https?://)[^\s/@]+@', r'\1', result.stderr.strip())
            raise ValueError(message[-1200:] or 'Git command failed')
        return result.stdout.strip()

    def local(self):
        if not (self.repo/'.git').exists():
            raise ValueError('This is a ZIP/source installation. Use a Git checkout to enable updates.')
        if Path(self.git('rev-parse', '--show-toplevel')).resolve() != self.repo:
            raise ValueError('The shell must be at the root of its own Git checkout.')
        current = self.git('rev-parse', 'HEAD')
        if self.git('branch', '--show-current') != 'main':
            raise ValueError('Switch this checkout to main before updating. No branch was changed.')
        if self.git('status', '--porcelain=v1', '--untracked-files=normal'):
            raise ValueError('Local changes found. Commit or stash them before updating; nothing was overwritten.')
        self.git('remote', 'get-url', 'origin')
        return current

    def read(self):
        try:
            value = json.loads(self.path.read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError): return {}

    def state(self, stage, message, **values):
        return dict(stage=stage, message=message, statePath=str(self.path), canUpdate=False, **values)

    def write(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='.update-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(value, stream)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
        return value

    def lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception:
            os.close(fd)
            raise
        return fd

    def inspect(self):
        value = self.read()
        if value.get('stage') in BUSY:
            try: fd = self.lock()
            except BlockingIOError: return value
            os.close(fd)
            return self.write(self.state('error', 'The previous update was interrupted. Check again to retry.'))
        try: current = self.local()
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            return self.state('blocked', str(error))
        if value.get('current') == current: return value
        return self.state('idle', 'Check origin/main for updates.', current=current)

    def launch(self, action):
        try: fd = self.lock()
        except BlockingIOError: return self.read() or self.state('checking', 'Another update is running.')
        try:
            current = self.local()
            value = self.write(self.state('checking' if action == 'check' else 'updating',
                                         'Checking origin/main…' if action == 'check' else 'Updating from origin/main…', current=current))
            # The inherited flock and detached worker survive QML reloads during checkout.
            self.worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), action, '--worker',
                              '--repo', str(self.repo), '--state-dir', str(self.path.parent), '--lock-fd', str(fd)],
                             pass_fds=(fd,), start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return value
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            return self.write(self.state('blocked', str(error)))
        finally: os.close(fd)

    def perform(self, action):
        current = self.local()
        self.git('fetch', '--no-tags', 'origin', 'refs/heads/main:refs/remotes/origin/main', timeout=90)
        latest = self.git('rev-parse', 'refs/remotes/origin/main')
        ahead, behind = map(int, self.git('rev-list', '--left-right', '--count', 'HEAD...'+latest).split())
        if ahead:
            raise ValueError('Local main has commits outside origin/main. Resolve them manually; no reset or rebase was attempted.')
        if not behind: return self.state('current', 'Already up to date.', current=current, latest=latest)
        if action == 'check':
            value = self.state('available', f"{behind} new commit{'s' if behind != 1 else ''} on origin/main.", current=current, latest=latest)
            value['canUpdate'] = True
            return value
        # Recheck after the network request; edits made while fetching must be retained.
        if self.local() != current: raise ValueError('The checkout changed while fetching. Check again before updating.')
        self.git('-c', 'merge.autoStash=false', '-c', 'core.hooksPath=/dev/null',
                 'merge', '--ff-only', '--no-edit', latest, timeout=45)
        return self.state('updated', 'Source updated. Restart the shell and Settings to load all changes.',
                          current=self.git('rev-parse', 'HEAD'), latest=latest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'check', 'update'))
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--state-dir', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--lock-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    updater = ShellUpdate(args.repo, args.state_dir)
    if args.worker:
        try:
            if args.lock_fd is None: raise ValueError('Missing updater lock')
            os.fstat(args.lock_fd)
            try: value = updater.perform(args.action)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                value = updater.state('error', str(error), current=updater.read().get('current', ''))
            updater.write(value)
        finally:
            if args.lock_fd is not None: os.close(args.lock_fd)
    else:
        value = updater.inspect() if args.action == 'inspect' else updater.launch(args.action)
        print(json.dumps(value))


if __name__ == '__main__': main()
