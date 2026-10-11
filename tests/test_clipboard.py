"""Local history contracts and optional native private-Wayland capture checks."""
import base64
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from test_backend import backend
from clipboard import History, MAX_TEXT, MAX_IMAGE, MAX_PINS, capture

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGOY2vD/PwAG1gMUVF+n7wAAAABJRU5ErkJggg==')


class HistoryCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.history = History(self.root / 'history', limit=20)
        self.addCleanup(self.history.db.close)

    def test_unicode_multiline_roundtrip_and_deduplication(self):
        data = 'Xin chào\nA second line\n'.encode()
        ident = self.history.store('text', data)
        self.assertEqual(self.history.store('text', data), ident)
        self.assertEqual(len(self.history.entries()), 1)
        self.assertEqual(self.history.item(ident)['data'], data)
        self.assertEqual(self.history.entries('CHÀO')[0]['id'], ident)

    def test_search_finds_text_beyond_visible_preview_and_filters_images(self):
        self.history.store('text', ('a' * 500 + 'find-me').encode())
        image = self.history.store('image', PNG)
        self.assertEqual(len(self.history.entries('find-me')), 1)
        self.assertEqual([i['id'] for i in self.history.entries(kind='image')], [image])
        self.assertEqual(len(self.history.entries(kind='text')), 1)
        with self.assertRaises(ValueError): self.history.entries(kind='unknown')

    def test_images_export_preview_and_are_deleted_with_their_content(self):
        ident = self.history.store('image', PNG)
        path = self.history.images / (ident + '.png')
        self.assertEqual(path.read_bytes(), PNG)
        self.assertEqual(self.history.entries()[0]['mime'], 'image/png')
        self.history.delete(ident)
        self.assertFalse(path.exists())
        self.assertEqual(self.history.entries(), [])

    def test_automatic_cleanup_preserves_pins_and_newest_items(self):
        first = self.history.store('text', b'keep pinned')
        self.history.pin(first)
        for index in range(30): self.history.store('text', f'item-{index}'.encode())
        items = self.history.entries()
        self.assertEqual(len(items), 20)
        self.assertEqual(items[0]['id'], first)
        self.assertIn('item-29', [i['preview'] for i in items])
        self.assertNotIn('item-0', [i['preview'] for i in items])

    def test_content_budget_evicts_oldest_unpinned_items(self):
        self.history.max_total = 15
        first = self.history.store('text', b'1234567890')
        second = self.history.store('text', b'abcdefghij')
        self.assertEqual([item['id'] for item in self.history.entries()], [second])
        with self.assertRaises(ValueError): self.history.item(first)

    def test_pause_persists_and_new_selections_are_ignored(self):
        self.history.pause(True)
        other = History(self.history.directory)
        try:
            self.assertTrue(other.paused)
            self.assertIsNone(other.store('text', b'ignored'))
            other.pause(False)
            self.assertIsNotNone(self.history.store('text', b'captured'))
        finally: other.db.close()

    def test_clear_can_preserve_or_remove_pins_and_image_files(self):
        image = self.history.store('image', PNG)
        self.history.pin(image)
        self.history.store('text', b'remove')
        self.history.clear(False)
        self.assertEqual([i['id'] for i in self.history.entries()], [image])
        self.history.clear(True)
        self.assertEqual(self.history.entries(), [])
        self.assertEqual(list(self.history.images.iterdir()), [])

    def test_history_survives_restart_and_uses_private_permissions(self):
        ident = self.history.store('text', b'persist')
        other = History(self.history.directory)
        try: self.assertEqual(other.item(ident)['data'], b'persist')
        finally: other.db.close()
        self.assertEqual(self.history.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.history.directory / 'history.sqlite3').stat().st_mode & 0o777, 0o600)

    def test_size_type_and_stale_id_rejections_leave_history_intact(self):
        self.history.store('text', b'keep')
        for kind, data in [('text', b'x' * (MAX_TEXT + 1)), ('image', b'x' * (MAX_IMAGE + 1)), ('image', b'not an image'), ('file', b'x')]:
            with self.assertRaises(ValueError): self.history.store(kind, data)
        with self.assertRaises(ValueError): self.history.delete('../../invalid')
        with self.assertRaises(ValueError): self.history.clear('yes')
        self.assertEqual(len(self.history.entries()), 1)

    def test_pin_limit_is_enforced_and_unpin_frees_a_slot(self):
        self.history.configure(100)
        ids = [self.history.store('text', str(i).encode()) for i in range(MAX_PINS + 1)]
        for ident in ids[:-1]: self.history.pin(ident)
        with self.assertRaises(ValueError): self.history.pin(ids[-1])
        self.history.pin(ids[0]); self.history.pin(ids[-1])
        self.assertEqual(sum(i['pinned'] for i in self.history.entries()), MAX_PINS)

    def test_preference_validation_and_sensitive_selection_hint(self):
        for key in ['clipboardEnabled', 'clipboardImages']:
            self.assertFalse(backend.validate_preference(key, False))
            with self.assertRaises(ValueError): backend.validate_preference(key, 'yes')
        for value in [True, 19, 501, 100.0]:
            with self.assertRaises(ValueError): backend.validate_preference('clipboardLimit', value)
        with patch.dict(os.environ, {'CLIPBOARD_STATE': 'sensitive'}): capture('text', self.root / 'unused')
        self.assertFalse((self.root / 'unused').exists())


@unittest.skipUnless(os.environ.get('LME_TEST_CLIPBOARD_NATIVE') == '1', 'Enable only in a private Wayland session')
class NativeClipboardCase(unittest.TestCase):
    def setUp(self):
        if not shutil.which('wl-copy') or not shutil.which('wl-paste'): raise unittest.SkipTest('wl-clipboard is required')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'history'
        self.config = Path(self.temp.name) / 'config/lme-shell/settings.json'
        script = Path(__file__).resolve().parents[1] / 'scripts/clipboard.py'
        self.log = tempfile.TemporaryFile(mode='w+')
        self.process = subprocess.Popen(['python3', str(script), '--directory', str(self.directory)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                                         env=dict(os.environ, XDG_CONFIG_HOME=str(self.config.parent.parent)))
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer, self.state = b'', None
        self.wait_for(lambda state: state['capturing'])

    def tearDown(self):
        self.process.terminate(); self.process.wait(timeout=6)
        self.process.stdin.close(); self.process.stdout.close(); self.selector.close()
        self.log.seek(0)
        output = self.log.read(); self.log.close()
        self.assertNotIn('native clipboard test', output)

    def wait_for(self, predicate):
        end = time.monotonic() + 8
        while time.monotonic() < end:
            if self.state and predicate(self.state): return self.state
            if not self.selector.select(.1): continue
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk: raise AssertionError('Clipboard service stopped')
            self.buffer += chunk
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                self.state = json.loads(line)
        raise AssertionError('Clipboard service did not reach expected state')

    def action(self, action, **payload):
        previous = (self.state.get('lastResult') or {}).get('sequence', 0)
        self.process.stdin.write(json.dumps(dict(action=action, **payload)).encode() + b'\n'); self.process.stdin.flush()
        return self.wait_for(lambda state: (state.get('lastResult') or {}).get('sequence', 0) > previous)

    def test_real_text_and_image_capture_copy_pause_and_clear(self):
        text = 'native clipboard test\nXin chào\n'.encode()
        subprocess.run(['wl-copy', '--type', 'text/plain;charset=utf-8'], input=text, check=True)
        state = self.wait_for(lambda s: any(item['preview'].startswith('native clipboard test') for item in s['entries']))
        ident = next(i['id'] for i in state['entries'] if i['preview'].startswith('native clipboard test'))
        self.assertTrue(self.action('pin', id=ident)['lastResult']['ok'])
        self.action('copy', id=ident)
        self.assertEqual(subprocess.check_output(['wl-paste', '--no-newline']), text)
        subprocess.run(['wl-copy', '--type', 'image/png'], input=PNG, check=True)
        state = self.wait_for(lambda s: any(i['kind'] == 'image' for i in s['entries']))
        image = next(i for i in state['entries'] if i['kind'] == 'image')
        self.action('copy', id=image['id'])
        self.assertEqual(subprocess.check_output(['wl-paste', '--type', 'image/png']), PNG)
        self.action('pause', value=True)
        self.wait_for(lambda s: not s['capturing'])
        count = self.state['total']
        subprocess.run(['wl-copy', '--type', 'text/plain'], input=b'paused item', check=True)
        time.sleep(.3)
        self.action('search', query='', kind='all')
        self.assertEqual(self.state['total'], count)
        self.action('clear', includePinned=False)
        self.assertEqual([i['id'] for i in self.state['entries']], [ident])
        self.action('clear', includePinned=True)
        self.assertEqual(self.state['total'], 0)
        self.action('pause', value=False)
        self.wait_for(lambda s: s['capturing'])
        subprocess.run(['wl-copy', '--type', 'text/plain'], input=b'capture resumed', check=True)
        self.wait_for(lambda s: any(i['preview'] == 'capture resumed' for i in s['entries']))
        prefs = backend.Preferences(self.config)
        prefs.set('clipboardEnabled', False)
        self.wait_for(lambda s: not s['capturing'])
        count = self.state['total']
        subprocess.run(['wl-copy', '--type', 'text/plain'], input=b'disabled through settings', check=True)
        time.sleep(.3)
        self.action('search', query='', kind='all')
        self.assertEqual(self.state['total'], count)
        prefs.set('clipboardEnabled', True)
        self.wait_for(lambda s: s['capturing'])
        subprocess.run(['wl-copy', '--type', 'text/plain'], input=b'settings capture resumed', check=True)
        self.wait_for(lambda s: any(i['preview'] == 'settings capture resumed' for i in s['entries']))


@unittest.skipUnless(os.environ.get('LME_TEST_CLIPBOARD_UI') == '1', 'Enable only in a private Wayland session')
class ClipboardInterfaceCase(unittest.TestCase):
    def test_search_and_keyboard_copy_use_real_clipboard(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            fixture = Path(__file__).resolve().parents[1] / 'native-features-demo.qml'
            env = dict(os.environ, LME_SHELL_DEMO='0', LME_SHELL_BACKEND_DEMO='1', LME_TEST_FEATURES='1', XDG_STATE_HOME=directory)
            process = subprocess.Popen(['quickshell', '-p', str(fixture)], env=env, stdout=log, stderr=log)
            def status():
                reply = subprocess.run(['quickshell', '-p', str(fixture), 'ipc', 'call', 'featuresFixture', 'clipboardStatus'], env=env, capture_output=True, text=True, timeout=4)
                try: return json.loads(reply.stdout)
                except ValueError: return {}
            def wait(predicate):
                end = time.monotonic() + 10
                while time.monotonic() < end:
                    state = status()
                    if predicate(state): return state
                    time.sleep(.1)
                log.seek(0)
                raise AssertionError('Clipboard UI did not reach expected state: ' + log.read())
            try:
                wait(lambda s: s.get('capturing'))
                text = b'UI clipboard target\nsecond line\n'
                subprocess.run(['wl-copy', '--type', 'text/plain'], input=text, check=True)
                wait(lambda s: s.get('count', 0) > 0)
                subprocess.run(['wl-copy', '--type', 'text/plain'], input=b'another entry', check=True)
                wait(lambda s: s.get('count', 0) >= 2)
                subprocess.run(['wtype', '-s', '200', '-d', '30', 'UI clipboard target'], check=True)
                wait(lambda s: s.get('query') == 'UI clipboard target' and s.get('count') == 1)
                subprocess.run(['wtype', '-s', '200', '-k', 'Return'], check=True)
                wait(lambda s: s.get('visible') is False)
                self.assertEqual(subprocess.check_output(['wl-paste', '--no-newline']), text)
                subprocess.run(['quickshell', '-p', str(fixture), 'ipc', 'call', 'featuresFixture', 'openClipboard'], env=env, check=True, capture_output=True)
                wait(lambda s: s.get('visible') and s.get('focused') and s.get('query') == '')
                # Enter before the debounce expires must copy the matching item.
                subprocess.run(['wtype', '-s', '200', '-d', '5', 'UI clipboard target', '-k', 'Return'], check=True)
                wait(lambda s: s.get('visible') is False)
                self.assertEqual(subprocess.check_output(['wl-paste', '--no-newline']), text)
                pointer = os.environ.get('LME_TEST_POINTER')
                if pointer:
                    subprocess.run(['quickshell', '-p', str(fixture), 'ipc', 'call', 'featuresFixture', 'openClipboard'], env=env, check=True, capture_output=True)
                    wait(lambda s: s.get('visible') and s.get('focused') and s.get('query') == '')
                    subprocess.run(['wl-copy', '--type', 'image/png'], input=PNG, check=True)
                    wait(lambda s: s.get('images') == 1)
                    def click(name):
                        reply = subprocess.check_output(['quickshell', '-p', str(fixture), 'ipc', 'call', 'featuresFixture', 'buttonPosition', name], env=env, text=True)
                        point = json.loads(reply)
                        subprocess.run([pointer, str(point['x']), str(point['y'])], check=True, timeout=4)
                    click('clipboardImage0'); wait(lambda s: s.get('preview'))
                    click('clipboardPreviewBack'); wait(lambda s: not s.get('preview'))
                    click('clipboardPin0'); wait(lambda s: s.get('pinned') == 1)
                    click('clipboardClear'); click('clipboardKeepPins')
                    wait(lambda s: s.get('count') == 1 and s.get('pinned') == 1)
                    click('clipboardDelete0'); wait(lambda s: s.get('count') == 0)
            finally:
                process.terminate(); process.wait(timeout=6)
            log.seek(0)
            output = log.read()
            for error in ['ReferenceError', 'TypeError', 'QML error', 'Failed to load configuration', 'Error decoding', 'Unable to assign']:
                self.assertNotIn(error, output)
