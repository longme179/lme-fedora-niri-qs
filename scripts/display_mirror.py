"""Own a wl-mirror window, without rewriting the user's niri output layout."""
# SPDX-License-Identifier: GPL-3.0-or-later
# Fullscreen recipe follows Ferdi265/wl-mirror's wl-present examples (GPL-3.0-or-later).
import subprocess
import tempfile


class DisplayMirror:
    def __init__(self, runner):
        self.runner = runner
        self.child = None
        self.log = None
        self.info = {'active': False, 'source': '', 'target': '', 'error': ''}

    def state(self, outputs=None, enabled=True):
        if self.child and self.child.poll() is not None:
            code = self.child.returncode
            if code:
                self.log.seek(0, 2)
                self.log.seek(max(0, self.log.tell() - 2000))
                self.info['error'] = 'Mirror stopped: ' + (self.log.read().strip() or str(code))
            self.child = None
            self.log.close()
            self.log = None
            self.info['active'] = False
        if self.child and not enabled:
            self.stop()
        if self.child and outputs is not None:
            names = {o['name'] for o in outputs if o.get('enabled')}
            if self.info['source'] not in names or self.info['target'] not in names:
                self.stop()
                self.info['error'] = 'A mirrored display was disconnected or disabled.'
        return {**self.info, 'available': self.runner.available('wl-mirror')}

    def start(self, source, target, outputs):
        try:
            if self.state()['active']:
                raise ValueError('Stop the current mirror before starting another.')
            if not self.runner.available('wl-mirror'):
                raise ValueError('Install wl-mirror to mirror onto a connected display.')
            names = {o['name'] for o in outputs if o.get('enabled')}
            if (not isinstance(source, str) or not isinstance(target, str) or source == target
                    or source not in names or target not in names
                    or any(name.startswith('-') or len(name) > 128 or any(ord(c) < 32 for c in name)
                           for name in (source, target))):
                raise ValueError('Choose two different, active niri displays.')
            self.log = tempfile.TemporaryFile(mode='w+', encoding='utf-8')
            try:
                self.child = subprocess.Popen(
                    [self.runner.executable('wl-mirror'), '--fullscreen-output', target,
                     '--scaling', 'fit', '--title', 'LME Display Mirror', source],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=self.log)
            except OSError:
                self.log.close()
                self.log = None
                raise
            self.info = {'active': True, 'source': source, 'target': target, 'error': ''}
            return 'Mirror started on ' + target
        except (ValueError, OSError) as exc:
            self.info['error'] = str(exc)
            raise

    def stop(self):
        if self.child:
            if self.child.poll() is None:
                self.child.terminate()
                try:
                    self.child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.child.kill()
                    self.child.wait(timeout=1)
            self.child = None
        if self.log:
            self.log.close()
            self.log = None
        self.info.update(active=False, error='')
        return 'Mirror stopped'

    def close(self):
        self.stop()
