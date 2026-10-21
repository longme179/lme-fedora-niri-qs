"""Clipboard integration executes the real hosts and worker on private Wayland."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import subprocess

from clipboard_slice_fixture import World
from test_clipboard import PNG


@unittest.skipUnless(os.environ.get('LME_TEST_CLIPBOARD_UI') == '1', 'private Wayland Clipboard slice')
class NativeEntryCase(unittest.TestCase):
    def setUp(self):
        if not os.environ.get('LME_TEST_POINTER'): self.skipTest('Set private virtual-pointer helper')
        self.temp = tempfile.TemporaryDirectory(prefix='clip-slice-')
        self.addCleanup(self.temp.cleanup)
        self.world = World(Path(self.temp.name))

    def test_bar_ipc_gesture_close_reopen_and_capture_switch_keep_history(self):
        with self.world.launch() as probe:
            probe.wait(lambda state: state['workerReady'] and state['count'] == 2)
            self.assertEqual(len(self.world.workers()), 1)
            probe.click('barAction-clipboard')
            state = probe.wait(lambda state: state['open'] and state['history'])
            self.assertFalse(state['capturing'])
            probe.call('toggle', 'clipboard', target='shell'); probe.wait(lambda state: not state['open'])
            probe.call('toggle', 'clipboard', target='shell'); probe.wait(lambda state: state['open'] and state['history'])
            probe.call('close', target='shell'); probe.wait(lambda state: not state['open'])
            probe.call('gesture'); probe.wait(lambda state: state['open'] and state['history'])
            probe.call('capture', 'true'); probe.wait(lambda state: state['capturing'])
            probe.call('capture', 'false')
            probe.wait(lambda state: not state['capturing'] and state['open'] and state['history'])
            self.assertEqual(len(self.world.workers()), 1)

    def test_settings_cli_search_reuse_and_first_page_ready_without_worker(self):
        with self.world.launch('settings') as probe:
            self.assertEqual(probe.call('openPage', 'clipboard', target='settings'), 'true')
            self.assertEqual(probe.call('startupPending', target='settings'), 'false')
            self.assertEqual(probe.call('page'), 'clipboard')
            self.assertEqual(probe.wait(lambda state: state['firstVisible'])['firstVisible'],
                dict(catalog=True, theme=True, backend=True))
            self.assertFalse(probe.wait(lambda state: state['ready'])['started'])
            self.assertEqual(self.world.workers(), [])
            probe.call('openPage', 'appearance', target='settings')
            self.assertEqual(probe.call('search', 'clipboard'), 'true')
            end = time.monotonic()+5
            while probe.call('page') != 'clipboard' and time.monotonic()<end: time.sleep(.05)
            self.assertEqual(probe.call('page'), 'clipboard')
            reply = subprocess.run([str(self.world.root/'scripts/settings.sh'), '--page', 'appearance', '--daemonize'],
                env=probe.env, capture_output=True, text=True, timeout=8)
            self.assertEqual(reply.returncode, 0, reply.stderr)
            self.assertIsNone(probe.process.poll())
            self.assertEqual(self.world.workers(), [])

    def test_image_click_routes_through_capture_service(self):
        with self.world.launch() as probe:
            probe.wait(lambda state: state['workerReady'] and state['count'] == 2)
            probe.call('toggle', 'clipboard', target='shell')
            probe.wait(lambda state: state['open'] and state['history'])
            probe.click('clipboardImage0')
            probe.wait(lambda state: not state['open'] and self.world.editor.exists())
            argv = json.loads(self.world.editor.read_text())
            self.assertEqual(argv[0], '-f')
            image = Path(argv[1]); self.assertTrue(image.is_relative_to(self.world.home/'Pictures'))
            self.assertEqual(image.read_bytes(), PNG)

    def test_demo_preview_never_start_worker(self):
        for mode in ('demo', 'preview'):
            with self.subTest(mode=mode), self.world.launch(mode) as probe:
                self.assertFalse(probe.wait(lambda state: state['demo'])['started'])
                self.assertEqual(self.world.workers(), [])

    def test_demo_preview_clipboard_dispatch_keeps_history_without_worker(self):
        for mode in ('demo', 'preview'):
            with self.subTest(mode=mode), self.world.launch(mode) as probe:
                probe.call('close', target='shell'); probe.wait(lambda state: not state['panelOpen'])
                probe.call('toggle', 'clipboard', target='shell')
                state = probe.wait(lambda state: state['open'] and state['history'])
                self.assertFalse(state['started']); self.assertEqual(self.world.workers(), [])

    def test_preview_initial_clipboard_env_opens_history_without_worker(self):
        self.world.env['LME_SHELL_PREVIEW_PANEL'] = 'clipboard'
        with self.world.launch('preview') as probe:
            state = probe.wait(lambda state: state['open'] and state['history'])
            self.assertFalse(state['started']); self.assertEqual(self.world.workers(), [])
