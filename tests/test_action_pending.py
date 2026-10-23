"""Coordinator ownership and wire compatibility; no real device/session I/O."""
from concurrent.futures import Future
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from test_backend import Fixture, FakeRunner, backend
from test_features import ManualExecutor

PROTOCOL = importlib.util.find_spec('action_pending') is not None
BT = '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF'


class PendingWireCase(Fixture, unittest.TestCase):
    def configured(self, demo=False, settings=False):
        env = patch.dict(os.environ, XDG_STATE_HOME=str(self.root/'state'), XDG_CONFIG_HOME=str(self.root/'config'))
        env.start(); self.addCleanup(env.stop)
        live = self.make_backend(FakeRunner(available=('busctl', 'wpctl')), demo=demo)
        live.settings_only = settings
        live.feature_executor.shutdown(); live.feature_executor = ManualExecutor()
        self.addCleanup(live.charge_executor.shutdown)
        live.bluetooth = lambda: dict(available=True, enabled=True, batteries=[], devices=[dict(path=BT, connected=False)])
        return live

    def frame(self, live):
        out = io.StringIO()
        with redirect_stdout(out): backend.emit(live)
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        return json.loads(lines[0])

    def connect(self, live, serial=1):
        return live.handle(dict(action='bluetoothDevice', path=BT, connected=True, clientSerial=serial))

    def test_current_exact_duplicate_results_and_completion_keep_original_owner(self):
        live = self.configured()
        first = self.connect(live)
        owner = live.feature_jobs['bluetoothDevice']
        self.assertEqual(first, dict(ok=True, action='bluetoothDevice', message='Working…', pending=True, sequence=1))
        self.assertEqual(self.frame(live)['lastResult'], first)
        self.assertEqual(self.connect(live, 2), dict(ok=False, action='bluetoothDevice',
            message='This operation is already running', sequence=2))
        self.assertIs(live.feature_jobs['bluetoothDevice'], owner)
        self.assertEqual(live.handle(dict(action='volume', value=25, clientSerial=3)),
            dict(ok=True, action='volume', message='Volume 25%', sequence=3))
        live.feature_executor.complete()
        self.assertEqual(self.frame(live)['lastResult']['action'], 'volume')
        self.assertEqual(self.frame(live)['lastResult'], dict(ok=True, action='bluetoothDevice',
            message='Bluetooth device connected', sequence=4))
        self.assertFalse(live.feature_jobs)

    def test_current_context_demo_admission_and_direct_snapshot_facades(self):
        for demo in (False, True):
            for settings in (False, True):
                live = self.configured(demo, settings)
                result = self.connect(live)
                if settings:
                    self.assertEqual(result, dict(ok=False, action='bluetoothDevice',
                        message='This action is unavailable in the settings app', sequence=1))
                elif demo:
                    self.assertEqual(result, dict(ok=True, action='bluetoothDevice',
                        message='Demo preview: no system command executed', sequence=1))
                self.assertNotIn('actionPending', live.feature_snapshot())
                self.assertNotIn('actionPending', live.snapshot())
                if demo or settings:
                    self.assertFalse(live.feature_jobs)
                    self.assertFalse(live.runner.calls)

    @unittest.skipUnless(PROTOCOL, 'F3 wire contract not implemented on baseline')
    def test_wire_ownership_survives_duplicate_error_and_clears_after_completion(self):
        live = self.configured()
        self.assertEqual(self.frame(live)['actionPending'], dict(acknowledged=0, active=[]))
        self.connect(live)
        self.assertEqual(self.frame(live)['actionPending'], dict(acknowledged=1, active=['bluetoothDevice']))
        self.connect(live, 2)
        self.assertEqual(self.frame(live)['actionPending'], dict(acknowledged=2, active=['bluetoothDevice']))
        live.feature_executor.complete()
        self.assertEqual(self.frame(live)['actionPending'], dict(acknowledged=2, active=[]))

    @unittest.skipUnless(PROTOCOL, 'F3 wire contract not implemented on baseline')
    def test_completed_jobs_ack_first_and_ownership_is_sampled_after_each_publication(self):
        live = self.configured()
        for action, value in [('fileSearch', {}), ('wallpaperScan', {})]:
            future = Future(); future.set_result(value); live.feature_jobs[action] = future
        live.handle(dict(action='calculate', query='1+1', clientSerial=1))
        first, second, third = (self.frame(live) for _ in range(3))
        self.assertEqual([f['lastResult']['action'] for f in (first, second, third)], ['calculate', 'fileSearch', 'wallpaperScan'])
        self.assertEqual([f['actionPending']['active'] for f in (first, second, third)],
            [['fileSearch', 'wallpaperScan'], ['wallpaperScan'], []])
        self.assertEqual([f['actionPending']['acknowledged'] for f in (first, second, third)], [1, 1, 1])

    @unittest.skipUnless(PROTOCOL, 'F3 wire contract not implemented on baseline')
    def test_error_charge_owner_and_stale_capture_cleanup_use_existing_lifecycle(self):
        live = self.configured()
        self.connect(live); self.frame(live)
        live.feature_jobs['bluetoothDevice'].set_exception(backend.CommandError('Device unavailable'))
        charge = Future(); live.charge_job = charge
        state = self.frame(live)
        self.assertEqual(state['lastResult']['message'], 'Device unavailable')
        self.assertEqual(state['actionPending']['active'], ['chargeMode'])
        charge.set_result('Charge mode updated')
        state = self.frame(live)
        self.assertEqual(state['lastResult']['action'], 'chargeMode')
        self.assertEqual(state['actionPending']['active'], [])
        stale = Future(); stale.capture_token = 'old'; stale.set_result('unused')
        live.feature_jobs['captureOcr'] = stale
        self.assertEqual(self.frame(live)['actionPending']['active'], [])
        self.assertEqual(live.last_result['message'], '')

    @unittest.skipUnless(PROTOCOL, 'F3 wire contract not implemented on baseline')
    def test_file_search_replacement_keeps_new_owner_and_wifi_rejection_keeps_connect(self):
        live = self.configured(); self.preferences.values['fileSearchEnabled'] = True
        live.handle(dict(action='fileSearch', query='first', clientSerial=1)); self.frame(live)
        old = live.feature_jobs['fileSearch']; cancelled = live.file_search_cancel
        live.handle(dict(action='fileSearch', query='second', clientSerial=2))
        self.assertTrue(cancelled.is_set()); self.assertTrue(old.cancelled())
        self.assertIsNot(live.feature_jobs['fileSearch'], old)
        self.assertEqual(self.frame(live)['actionPending'], dict(acknowledged=2, active=['fileSearch']))
        live.feature_jobs['wifiConnect'] = Future()
        reply = live.handle(dict(action='wifiToggle', enabled=False, clientSerial=3))
        self.assertEqual(reply['message'], 'This operation is already running')
        self.assertEqual(self.frame(live)['actionPending']['active'], ['fileSearch', 'wifiConnect'])

    @unittest.skipUnless(PROTOCOL, 'F3 wire contract not implemented on baseline')
    def test_serial_admission_context_unknown_errors_and_demo_do_not_spawn(self):
        for demo in (False, True):
            live = self.configured(demo, settings=True)
            before = {p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
            with patch('subprocess.Popen', side_effect=AssertionError('spawn')):
                live.handle(dict(action='bluetoothDevice', clientSerial=7))
                self.assertEqual(self.frame(live)['actionPending'], dict(acknowledged=7, active=[]))
                live.handle(dict(action='unknown', clientSerial=8))
                self.assertFalse(live.last_result['ok'])
                self.assertEqual(self.frame(live)['actionPending'], dict(acknowledged=8, active=[]))
            self.assertEqual(before, {p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
            self.assertFalse(live.runner.calls)

    @unittest.skipUnless(PROTOCOL, 'F3 wire contract not implemented on baseline')
    def test_tag_boundaries_legacy_input_and_connection_reset(self):
        live = self.configured(demo=True)
        for value in (True, False, None, '1', [], {}, 0, -1, 1.0, float('nan'), float('inf'), 9007199254740992):
            with self.subTest(value=value):
                result = live.handle(dict(action='calculate', query='1+1', clientSerial=value))
                self.assertTrue(result['ok'])
                self.assertEqual(self.frame(live)['actionPending']['acknowledged'], 0)
        live.handle(dict(action='calculate', query='1+1', clientSerial=9007199254740991))
        for request in (dict(action='calculate', query='2+2'), dict(action='calculate', query='2+2', clientSerial=1)):
            live.handle(request)
            self.assertEqual(self.frame(live)['actionPending']['acknowledged'], 9007199254740991)
        self.assertEqual(self.frame(self.configured(demo=True))['actionPending'], dict(acknowledged=0, active=[]))

    @unittest.skipUnless(PROTOCOL, 'F3 wire contract not implemented on baseline')
    def test_real_pipe_batched_inputs_malformed_json_and_once_keep_legacy_results(self):
        script = Path(backend.__file__)
        env = dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'), XDG_STATE_HOME=str(self.root/'state'),
                   XDG_RUNTIME_DIR=str(self.root/'runtime'))
        lines = [json.dumps(dict(action='calculate', query='1+1', clientSerial=1)), '{broken',
                 json.dumps(dict(action='calculate', query='2+2', clientSerial=2)),
                 json.dumps(dict(action='unknown', clientSerial=3))]
        for args in (['--demo'], ['--demo', '--settings']):
            result = subprocess.run([sys.executable, str(script), *args], env=env,
                input='\n'.join(lines)+'\n', text=True, capture_output=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stderr)
            frames = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(frames), 5)
            self.assertEqual([f['actionPending']['acknowledged'] for f in frames], [0, 1, 1, 2, 3])
            self.assertEqual(frames[2]['lastResult'], dict(ok=False, action='', message='Invalid JSON input'))
            self.assertEqual(frames[3]['lastResult'], dict(ok=True, action='calculate', message='4', query='2+2', sequence=2))
            self.assertTrue(all(f['actionPending']['active']==[] for f in frames))
        once = subprocess.run([sys.executable, str(script), '--demo', '--once'], env=env,
                              text=True, capture_output=True, timeout=8)
        self.assertEqual(once.returncode, 0, once.stderr)
        self.assertEqual(json.loads(once.stdout)['actionPending'], dict(acknowledged=0, active=[]))
