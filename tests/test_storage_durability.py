"""Bounded lock waits and crash-safe directory sync for shared storage."""
import errno
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import storage
from command_runner import CommandError
from desktop_backend import Preferences


class StorageDurabilityCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_locked_wait_is_bounded_and_releases(self):
        path = self.root/'state.lock'
        with open(path, 'a', encoding='utf-8') as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            started = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, 'locked by another process'):
                with storage.locked(path): self.fail('Acquired a held lock')
            elapsed = time.monotonic() - started
            self.assertGreaterEqual(elapsed, storage.LOCK_TIMEOUT - storage.LOCK_RETRY_INTERVAL)
            self.assertLess(elapsed, storage.LOCK_TIMEOUT + 1)
        with storage.locked(path): pass

    def test_preferences_lock_timeout_is_a_command_error(self):
        preferences = Preferences(self.root/'settings.json')
        with open(preferences.path.with_suffix('.lock'), 'a', encoding='utf-8') as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            with self.assertRaisesRegex(CommandError, 'settings.json is locked by another process'):
                preferences.update({'wallpaper': ''})

    def test_directory_fsync_failure_surfaces_after_replace(self):
        path = self.root/'state.json'
        storage.write_json(path, {'old': 1})
        real, calls = os.fsync, []

        def fail_second(descriptor):
            calls.append(descriptor)
            if len(calls) == 2: raise OSError(errno.ENOSPC, 'No space left on device')
            real(descriptor)

        with patch.object(storage.os, 'fsync', fail_second):
            with self.assertRaises(OSError): storage.write_json(path, {'new': 2})
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'new': 2})

    def test_failed_replace_keeps_old_file_and_removes_temporary(self):
        path = self.root/'state.json'
        storage.write_json(path, {'old': 1})
        original = path.read_bytes()
        with patch.object(storage.os, 'replace', side_effect=OSError(errno.EIO, 'rename failed')):
            with self.assertRaises(OSError): storage.write_json(path, {'new': 2})
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual([item.name for item in self.root.iterdir()], ['state.json'])

    def test_preferences_write_fsyncs_directory(self):
        preferences = Preferences(self.root/'settings.json')
        calls = []

        def fail_directory(descriptor):
            calls.append(descriptor)
            if len(calls) == 2: raise OSError(errno.EIO, 'directory fsync failed')

        with patch('desktop_backend.os.fsync', side_effect=fail_directory):
            with self.assertRaises(OSError): preferences.update({'wallpaper': ''})
        self.assertEqual(len(calls), 2)
        self.assertIn('"wallpaper": ""', preferences.path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
