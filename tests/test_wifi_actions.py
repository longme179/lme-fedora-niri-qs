"""Wi-Fi dispatch characterization; no real NetworkManager or network mutations."""
import copy
import importlib.util
import json
import os
from threading import Event
import unittest
from unittest.mock import Mock, patch

from test_backend import Fixture, FakeRunner, backend
from test_features import ManualExecutor

ACTIONS = ('wifiScan', 'wifiConnect', 'wifiSaved', 'wifiDisconnect', 'wifiForget')
DEMO = 'Demo preview: no system command executed'
CONTEXT = 'This action is unavailable in the settings app'
STATE = dict(available=True, enabled=True, connected=False, wifiConnected=False, ssid='', strength=None,
             device='wlp1s0', networks=[dict(ssid='Home:5G', bssid='AA:BB', enterprise=False),
                                      dict(ssid='Enterprise', bssid='CC:DD', enterprise=True)],
             saved=[dict(uuid='safe-uuid', name='Home')])
REQUEST = dict(device='wlp1s0', bssid='AA:BB', uuid='safe-uuid', password='literal ; $secret')
MESSAGES = ('Wi-Fi scan completed', 'Wi-Fi connected', 'Wi-Fi connected', 'Wi-Fi disconnected', 'Saved network removed')


class WifiDispatchCase(Fixture, unittest.TestCase):
    def configured(self, demo=False, settings=False, manual=True):
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
                         XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'))
        env.start(); self.addCleanup(env.stop)
        live = self.make_backend(FakeRunner(available=('nmcli',)), demo=demo); live.settings_only = settings
        live.network = Mock(return_value=copy.deepcopy(STATE))
        self.addCleanup(live.charge_executor.shutdown); self.addCleanup(live.feature_executor.shutdown)
        if manual:
            live.feature_executor.shutdown(wait=True); live.feature_executor = ManualExecutor()
        return live

    @staticmethod
    def result(action, message='Working…', sequence=1, ok=True, pending=False):
        value = dict(action=action, ok=ok, message=message, sequence=sequence)
        if pending: value['pending'] = True
        return value

    def test_live_commands_stdin_timeouts_ack_and_snapshot_shape(self):
        commands = (
            (('nmcli', '--wait', '15', 'device', 'wifi', 'rescan', 'ifname', 'wlp1s0'), dict(timeout=18)),
            (('nmcli', '--wait', '45', '--ask', 'device', 'wifi', 'connect', 'AA:BB', 'ifname', 'wlp1s0'), dict(input=REQUEST['password']+'\n', timeout=50)),
            (('nmcli', '--wait', '45', '--ask', 'connection', 'up', 'uuid', 'safe-uuid', 'ifname', 'wlp1s0'), dict(input=REQUEST['password']+'\n', timeout=50)),
            (('nmcli', '--wait', '15', 'device', 'disconnect', 'wlp1s0'), dict(timeout=18)),
            (('nmcli', 'connection', 'delete', 'uuid', 'safe-uuid'), {}))
        for action, message, (args, kwargs) in zip(ACTIONS, MESSAGES, commands):
            with self.subTest(action=action):
                live = self.configured(); before = copy.deepcopy(live.snapshot()); live.network.reset_mock()
                with patch.object(live.runner, 'run', return_value='') as run:
                    ack = self.result(action, pending=True)
                    self.assertEqual(live.handle(dict(action=action, **REQUEST)), ack)
                    live.network.assert_not_called(); run.assert_not_called()
                    live.feature_executor.complete()
                    live.network.assert_called_once_with(details=True); run.assert_called_once_with(*args, **kwargs)
                    self.assertEqual(live.snapshot()['lastResult'], ack)
                    done = live.snapshot()
                self.assertEqual(done['lastResult'], self.result(action, message, 2))
                self.assertEqual(done['system']['network'], STATE); self.assertEqual(set(done), set(before))
                self.assertEqual(done['preferences'], before['preferences']); self.assertFalse(live.feature_jobs)
                self.assertNotIn(REQUEST['password'], json.dumps(done)); self.assertFalse(self.preferences.path.exists())

    def test_settings_rejects_before_live_demo_selection_or_any_work(self):
        for preview in (False, True):
            live = self.configured(demo=preview, settings=True)
            with patch.object(live, 'demo_snapshot', side_effect=AssertionError('premature demo')), \
                 patch.object(live.runner, 'run', side_effect=AssertionError('Settings command')):
                for sequence, action in enumerate(ACTIONS, 1):
                    self.assertEqual(live.handle(dict(action=action, context='shell', demo=False, **REQUEST)),
                                     self.result(action, CONTEXT, sequence, ok=False))
            live.network.assert_not_called(); self.assertFalse(live.feature_jobs)
            self.assertFalse(live.feature_executor.jobs); self.assertFalse(hasattr(live, '_demo_state'))

    def test_deferred_validation_keeps_exact_errors_and_clears_pending(self):
        cases = [(action, {'device': 'stale'}, STATE, 'No Wi-Fi adapter is available') for action in ACTIONS]
        cases += [('wifiScan', {}, {**STATE, 'available': False}, 'NetworkManager is unavailable'),
                  ('wifiScan', {}, {**STATE, 'device': ''}, 'No Wi-Fi adapter is available'),
                  ('wifiConnect', {'bssid': 'missing'}, STATE, 'Network is no longer visible; scan again'),
                  ('wifiConnect', {'bssid': 'CC:DD'}, STATE, 'Enterprise Wi-Fi needs a certificate or account. Use Advanced network settings.')]
        cases += [(action, {'uuid': value}, STATE, 'Saved network is no longer available')
                  for action in ('wifiSaved', 'wifiForget') for value in (None, [], 'missing')]
        cases += [(action, {'password': value}, STATE, 'Invalid Wi-Fi password')
                  for action in ('wifiConnect', 'wifiSaved') for value in (None, True, [], 'x'*129, 'a\nb', 'a\rb', 'a\x00b')]
        for action, changes, state, message in cases:
            with self.subTest(action=action, changes=changes):
                live = self.configured(); live.network.return_value = copy.deepcopy(state)
                with patch.object(live.runner, 'run') as run:
                    self.assertEqual(live.handle(dict(action=action, **{**REQUEST, **changes})), self.result(action, pending=True))
                    live.network.assert_not_called(); live.feature_executor.complete(); live.finish_features()
                    run.assert_not_called()
                self.assertEqual(live.last_result, self.result(action, message, 2, ok=False))
                self.assertFalse(live.feature_jobs); self.assertIsNone(live.system_cache)

    def test_password_boundaries_and_worker_time_adapter_read_are_preserved(self):
        for action in ('wifiConnect', 'wifiSaved'):
            for password in ('', 'x'*128):
                live = self.configured()
                with patch.object(live.runner, 'run') as run:
                    live.handle(dict(action=action, **{**REQUEST, 'device': '', 'password': password}))
                    live.network.return_value['device'] = 'wlan1'
                    live.feature_executor.complete(); live.finish_features()
                    self.assertTrue(live.last_result['ok'])
                    self.assertEqual(run.call_args.args[-2:], ('ifname', 'wlan1'))
                    self.assertEqual(run.call_args.kwargs, dict(input=password+'\n', timeout=50))
        live = self.configured(); live.handle(dict(action='wifiScan', **REQUEST))
        live.network.return_value['device'] = 'wlan1'
        live.feature_executor.complete(); live.finish_features()
        self.assertEqual(live.last_result, self.result('wifiScan', 'No Wi-Fi adapter is available', 2, ok=False))

    def test_job_errors_duplicate_owners_and_one_completion_per_snapshot(self):
        live = self.configured()
        for sequence, action in enumerate(ACTIONS, 1):
            self.assertEqual(live.handle(dict(action=action, **REQUEST)), self.result(action, sequence=sequence, pending=True))
        owners = dict(live.feature_jobs)
        self.assertEqual(live.handle(dict(action='wifiScan')), self.result('wifiScan', 'This operation is already running', 6, ok=False))
        self.assertEqual(live.feature_jobs, owners); self.assertEqual(len(live.feature_executor.jobs), 5)
        with patch.object(live.runner, 'run', side_effect=backend.CommandError('x'*450)):
            for action in ACTIONS: live.feature_executor.complete()
        self.assertEqual(live.snapshot()['lastResult']['sequence'], 6)
        for sequence, action in enumerate(ACTIONS, 7):
            self.assertEqual(live.snapshot()['lastResult'], self.result(action, 'x'*400, sequence, ok=False))
            self.assertNotIn(action, live.feature_jobs)
        self.assertFalse(live.feature_jobs)

    def test_demo_state_and_invalid_payloads_have_no_io_or_jobs(self):
        live = self.configured(demo=True); network = live.demo_snapshot()['system']['network']
        files = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch.object(live.runner, 'run', side_effect=AssertionError('demo command')), \
             patch('subprocess.Popen', side_effect=AssertionError('demo spawn')), \
             patch('os.open', side_effect=AssertionError('demo file open')), patch('os.replace', side_effect=AssertionError('demo write')):
            for sequence, action in enumerate(ACTIONS, 1):
                expected = copy.deepcopy(network)
                if action in ('wifiConnect', 'wifiSaved'): expected.update(connected=True, ssid='Home Wi-Fi')
                elif action == 'wifiDisconnect': expected.update(connected=False, ssid='')
                self.assertEqual(live.handle(dict(action=action, device=[], bssid={}, uuid=None, password=[])),
                                 self.result(action, DEMO, sequence))
                self.assertEqual(live.snapshot()['system']['network'], expected)
                self.assertIs(network, live.demo_snapshot()['system']['network'])
        live.network.assert_not_called(); self.assertFalse(live.feature_jobs); self.assertFalse(live.feature_executor.jobs)
        self.assertEqual(files, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_direct_facades_keep_sync_helper_worker_start_and_demo_none(self):
        live = self.configured(); demo = self.configured(demo=True)
        for action, message in zip(ACTIONS, MESSAGES):
            self.assertEqual(live.wifi_action(action, REQUEST), message); self.assertFalse(live.feature_jobs)
            self.assertEqual(live.perform(action, REQUEST), 'Working…')
            live.feature_executor.complete(); live.finish_features()
            self.assertEqual(live.last_result['message'], message)
            self.assertIsNone(demo.perform_demo(action, REQUEST))
        self.assertFalse(demo.feature_jobs)

    def test_unknown_ids_keep_original_live_demo_and_context_errors(self):
        for preview in (False, True):
            for settings in (False, True):
                live = self.configured(demo=preview, settings=settings)
                for sequence, action in enumerate(('wifiUnknown', 'wifiConnectExtra'), 1):
                    message = CONTEXT if settings else 'Unknown action: '+action
                    self.assertEqual(live.handle(dict(action=action)), self.result(action, message, sequence, ok=False))
                self.assertFalse(live.feature_jobs)

    def test_shutdown_cancels_all_queued_wifi_jobs_without_network_mutation(self):
        live = self.configured(settings=False, manual=False); live.runner.close = Mock()
        gate = Event(); started = [Event(), Event()]; self.addCleanup(gate.set)
        def occupy(ready): ready.set(); gate.wait(5)
        for ready in started: live.feature_executor.submit(occupy, ready)
        for ready in started: self.assertTrue(ready.wait(2))
        read_fd, write_fd = os.pipe()
        with os.fdopen(read_fd, 'r') as source:
            os.write(write_fd, ''.join(json.dumps(dict(action=action, **REQUEST))+'\n' for action in ACTIONS).encode())
            os.close(write_fd); frames = []
            with patch.object(backend, 'DesktopBackend', return_value=live), \
                 patch.object(backend.sys, 'stdin', source), patch.object(backend.signal, 'signal'), \
                 patch.object(backend, 'emit', side_effect=lambda b: frames.append(copy.deepcopy(b.snapshot()))):
                self.assertEqual(backend.main([]), 0)
            self.assertEqual([frame['lastResult']['action'] for frame in frames], ['ready', *ACTIONS])
            for sequence, (action, frame) in enumerate(zip(ACTIONS, frames[1:]), 1):
                self.assertEqual(frame['lastResult'], self.result(action, sequence=sequence, pending=True))
                self.assertTrue(live.feature_jobs[action].cancelled())
            self.assertFalse(any(call[0] == 'nmcli' for call in live.runner.calls))
            self.assertFalse(any(call.kwargs.get('details') for call in live.network.call_args_list))
        gate.set()

    def test_provider_is_inert_and_registered_errors_never_fall_back(self):
        if importlib.util.find_spec('wifi_actions') is None:
            self.skipTest('M7d Wi-Fi provider absent on baseline; registry ownership N/A')
        from wifi_actions import WifiCapabilities, provide
        network = Mock(); run = Mock(); demo_network = Mock()
        specs, project = provide(WifiCapabilities(network, run, demo_network))
        self.assertEqual({spec.name for spec in specs}, set(ACTIONS)); self.assertEqual(project(), {})
        for spec in specs:
            self.assertEqual(spec.contexts, frozenset({'shell'})); self.assertEqual(spec.execution, 'worker')
            self.assertIsNone(spec.complete(ValueError('failed')))
        network.assert_not_called(); run.assert_not_called(); demo_network.assert_not_called()
        for preview in (False, True):
            live = self.configured(demo=preview)
            target = 'perform_demo' if preview else 'perform'
            with patch.object(live, target, side_effect=AssertionError('legacy fallback')), \
                 patch.object(live, 'start_feature', side_effect=ValueError('submission failed')) as start:
                for sequence, action in enumerate(ACTIONS, 1):
                    self.assertEqual(live.handle(dict(action=action)),
                                     self.result(action, DEMO if preview else 'submission failed', sequence, ok=preview))
            if preview: start.assert_not_called()
            else: self.assertEqual(start.call_count, 5)
