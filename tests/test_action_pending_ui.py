"""Ownership through real QML, backend and pending-driven controls in a copy."""
import json
import importlib.util
import os
import tempfile
import unittest

from action_pending_fixture import BT, world


@unittest.skipUnless(os.environ.get('LME_TEST_ACTION_PENDING') == '1', 'private Wayland action pending ownership')
class NativePendingCase(unittest.TestCase):
    def state(self, probe):
        return json.loads(probe.call('state', target='actionPending'))

    def wait(self, probe, predicate):
        probe.wait(lambda _:predicate(self.state(probe)))
        return self.state(probe)

    def connect(self, probe):
        probe.call('run', 'bluetoothDevice', json.dumps(dict(path=BT, connected=True)), target='actionPending')

    def devices(self, probe):
        probe.call('toggle', 'control', target='shell')
        probe.call('devices', target='actionPending')
        self.wait(probe, lambda s:s['button'] is not None)

    def test_duplicate_failure_retry_and_close_reopen_keep_actual_control_busy(self):
        with tempfile.TemporaryDirectory(prefix='pending-ui-') as directory:
            fixture = world(directory); fixture.hold.touch()
            with fixture.launch() as probe:
                try:
                    self.devices(probe)
                    self.wait(probe, lambda s:s['button'] is True)
                    probe.click('bluetoothDevice-'+BT)
                    self.wait(probe, lambda s:fixture.started.exists() and s['pending'].get('bluetoothDevice'))
                    self.connect(probe)
                    rejected = self.wait(probe, lambda s:s['result']['action']=='bluetoothDevice' and not s['result']['ok'])
                    self.assertEqual(rejected['result']['message'], 'This operation is already running')
                    self.assertTrue(rejected['pending'].get('bluetoothDevice'))
                    self.assertFalse(rejected['button']); self.assertTrue(fixture.hold.exists())
                    probe.call('close', target='shell'); self.devices(probe)
                    self.assertFalse(self.state(probe)['button'])
                    fixture.fail.touch(); fixture.hold.unlink()
                    failed = self.wait(probe, lambda s:s['result']['action']=='bluetoothDevice'
                        and s['result']['sequence']>rejected['result']['sequence'] and not s['pending'].get('bluetoothDevice'))
                    self.assertFalse(failed['result']['ok']); self.assertIn('Device unavailable', failed['result']['message'])
                    self.assertTrue(failed['button']); fixture.fail.unlink()
                    probe.click('bluetoothDevice-'+BT)
                    final = self.wait(probe, lambda s:s['result']['action']=='bluetoothDevice'
                        and s['result']['sequence']>failed['result']['sequence'] and not s['pending'].get('bluetoothDevice'))
                    self.assertTrue(final['result']['ok']); self.assertTrue(final['button'])
                finally: fixture.hold.unlink(missing_ok=True)

    def test_old_snapshot_and_reentrant_result_cannot_erase_new_send(self):
        with tempfile.TemporaryDirectory(prefix='pending-reentrant-') as directory:
            fixture = world(directory)
            with fixture.launch() as probe:
                for method in ('delayed', 'reenter'):
                    with self.subTest(method=method):
                        result = json.loads(probe.call(method, target='actionPending'))
                        self.assertTrue(result['pending'], method)
                        self.wait(probe, lambda s:s['result']['action']=='calculate' and not s['pending'].get('calculate'))

    @unittest.skipUnless(importlib.util.find_spec('action_pending'), 'F3 wire contract not implemented on baseline')
    def test_restart_clears_ownership_without_replaying_mutation(self):
        with tempfile.TemporaryDirectory(prefix='pending-restart-') as directory:
            fixture = world(directory); fixture.hold.touch()
            with fixture.launch() as probe:
                try:
                    self.connect(probe)
                    self.wait(probe, lambda s:fixture.started.exists() and s['pending'].get('bluetoothDevice'))
                    probe.call('restart', target='actionPending')
                    stopped = self.wait(probe, lambda s:not s['ready'])
                    self.assertFalse(stopped['pending'])
                finally: fixture.hold.unlink(missing_ok=True)
                restored = self.wait(probe, lambda s:s['ready'])
                self.assertFalse(restored['pending'].get('bluetoothDevice'))
                self.assertEqual(restored['wire']['active'], [])
                self.connect(probe)
                self.wait(probe, lambda s:s['result']['action']=='bluetoothDevice' and not s['pending'].get('bluetoothDevice'))
                self.assertTrue(self.state(probe)['result']['ok'])

    def test_legacy_backend_shell_and_standalone_settings_remain_usable(self):
        for mode in ('shell', 'settings'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='pending-legacy-') as directory:
                fixture = world(directory, legacy=True)
                with fixture.launch(mode, page='appearance') as probe:
                    probe.call('run', 'setting', json.dumps(dict(key='opacity', value=.8)), target='actionPending')
                    state = self.wait(probe, lambda s:s['result']['action']=='setting' and not s['pending'].get('setting'))
                    self.assertTrue(state['result']['ok']); self.assertNotIn('wire', state)
                    self.assertEqual(json.loads(fixture.settings.read_text())['opacity'], .8)
