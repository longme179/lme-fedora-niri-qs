"""Public infrastructure contracts, characterized before the M1 extraction."""
import errno
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import display_control
from test_backend import backend


class SharedContractsCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_json_permissions_utf8_fsync_and_atomic_replace(self):
        path = self.root/'private/state.json'
        events = []
        fsync, replace = os.fsync, os.replace
        def sync(fd):
            events.append('fsync')
            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o600)
            fsync(fd)
        def commit(source, destination):
            self.assertEqual(events, ['fsync'])
            self.assertEqual(Path(source).parent, path.parent)
            self.assertEqual(Path(destination), path)
            events.append('replace')
            replace(source, destination)
        with patch.object(os, 'fsync', sync), patch.object(os, 'replace', commit):
            display_control.write_json(path, {'text': 'Tiếng Việt', 'items': [1, False]})
        self.assertEqual(events, ['fsync', 'replace'])
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(path.read_bytes(), '{"text": "Tiếng Việt", "items": [1, false]}'.encode())
        path.chmod(0o644)
        display_control.write_json(path, {'next': True})
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_failed_writes_keep_original_and_remove_temporary_file(self):
        path = self.root/'state.json'
        display_control.write_json(path, {'old': 1})
        original = path.read_bytes()
        for stage in ('serialization', 'fsync', 'replace'):
            with self.subTest(stage=stage):
                if stage == 'serialization':
                    with self.assertRaises(ValueError): display_control.write_json(path, {'bad': float('nan')})
                else:
                    with patch.object(os, stage, side_effect=OSError(errno.ENOSPC, 'No space left on device')):
                        with self.assertRaises(OSError): display_control.write_json(path, {'new': 2})
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(list(self.root.iterdir()), [path])

    def test_json_fallback_identity_and_existing_public_aliases(self):
        path = self.root/'state.json'
        default = {'fallback': []}
        self.assertIs(display_control.read_json(path, default), default)
        for data in (b'{', b'\xff'):
            path.write_bytes(data)
            self.assertIs(display_control.read_json(path, default), default)
        path.write_text('null')
        self.assertIsNone(display_control.read_json(path, default))
        self.assertIs(backend.read_json, display_control.read_json)
        self.assertIs(backend.write_json, display_control.write_json)

    def probe_lock(self, path):
        code = '''import fcntl, sys
with open(sys.argv[1], 'a') as stream:
    try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: sys.exit(7)
'''
        return subprocess.run([sys.executable, '-c', code, str(path)], timeout=3, capture_output=True).returncode

    def test_independent_file_locks_and_release_after_exception(self):
        first, second = self.root/'locks/first.lock', self.root/'locks/second.lock'
        with self.assertRaisesRegex(RuntimeError, '^release me$'):
            with display_control.locked(first):
                self.assertEqual(stat.S_IMODE(first.parent.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o600)
                self.assertEqual(self.probe_lock(first), 7)
                self.assertEqual(self.probe_lock(second), 0)
                with display_control.locked(second):
                    self.assertEqual(self.probe_lock(first), 7)
                    self.assertEqual(self.probe_lock(second), 7)
                self.assertEqual(self.probe_lock(second), 0)
                raise RuntimeError('release me')
        self.assertEqual(self.probe_lock(first), 0)
        first.chmod(0o644)
        with display_control.locked(first): self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o600)

    def runner(self):
        runner = backend.CommandRunner()
        self.addCleanup(runner.close)
        runner.commands['nmcli'] = sys.executable
        return runner

    def test_runner_error_identity_ansi_redaction_truncation_and_stdout(self):
        runner = self.runner()
        secret = 'private-password'
        detail = '\x1b[31m failure '+secret+' '+'x'*400+'\x1b[0m\n'
        code = 'import sys; sys.stderr.write('+repr(detail)+'); sys.exit(9)'
        with self.assertRaises(backend.CommandError) as caught:
            runner.run('nmcli', '-c', code, input=secret+'\n')
        self.assertIs(type(caught.exception), backend.CommandError)
        self.assertIsInstance(caught.exception, RuntimeError)
        expected = ('failure [redacted] '+'x'*400)[:350]
        self.assertEqual(str(caught.exception), 'nmcli failed (9): '+expected)
        code = 'import sys; sys.stdout.write("  stdout only  "); sys.exit(2)'
        with self.assertRaises(backend.CommandError) as caught: runner.run('nmcli', '-c', code)
        self.assertEqual(str(caught.exception), 'nmcli failed (2): stdout only')
        self.assertEqual(runner.run('nmcli', '-c', 'print("  success  ")'), 'success')

    def test_runner_unavailable_spawn_and_oserror_messages(self):
        runner = self.runner()
        with self.assertRaises(backend.CommandError) as caught: runner.executable('unregistered-tool')
        self.assertEqual(str(caught.exception), 'Required command is unavailable: unregistered-tool')
        failure = OSError(errno.ENOENT, 'No such file or directory')
        with patch.object(subprocess, 'Popen', side_effect=failure):
            with self.assertRaises(backend.CommandError) as caught: runner.run('nmcli')
            self.assertEqual(str(caught.exception), 'Unable to run nmcli: No such file or directory')
            self.assertIs(caught.exception.__cause__, failure)
            with self.assertRaises(backend.CommandError) as caught: runner.spawn(['/missing/editor'])
            self.assertEqual(str(caught.exception), 'Unable to launch editor: No such file or directory')
            self.assertIs(caught.exception.__cause__, failure)
        self.assertFalse(runner.pending)

    def test_watchdog_module_import_and_injected_run_without_desktop_backend(self):
        # The baseline CLI imports the backend lazily; module import must remain independent.
        code = '''import importlib.abc, json, pathlib, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'desktop_backend': raise ImportError('desktop_backend deliberately unavailable')
sys.meta_path.insert(0, Block())
import display_control
item = dict(name='eDP-test', width=1920, height=1080, refresh=60003, scale=1, x=0, y=0)
original = dict(item, refresh=120002)
calls = []
path = pathlib.Path(sys.argv[1])
display_control.watch(path, dict(token='test', original=[original], layout=[item], socket='private'),
                      lambda *args: calls.append(args), duration=0)
assert 'desktop_backend' not in sys.modules
print(json.dumps(dict(calls=calls, state=display_control.read_json(path, {}))))
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.root/'watch.json')],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['state']['status'], 'reverted')
        self.assertEqual(data['state']['token'], 'test')
        self.assertEqual(data['calls'][0], ['niri', 'msg', 'output', 'eDP-test', 'mode', '1920x1080@60.003'])
        self.assertEqual(data['calls'][3], ['niri', 'msg', 'output', 'eDP-test', 'mode', '1920x1080@120.002'])
        self.assertEqual(len(data['calls']), 6)
