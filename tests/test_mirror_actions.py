"""Freeze main-shell ownership and Settings IPC before mirroring extraction."""
import copy
import importlib.util
import json
import os
import unittest
from unittest.mock import Mock, call, patch

from test_backend import Fixture, FakeRunner, backend
from test_mirroring import OUTPUTS

ACTIONS = ('mirrorRefresh', 'mirrorStart', 'mirrorStop')
LOCAL = dict(active=False, available=True, source='old', target='old-target', error='keep', extra=1)
REMOTE = dict(active=True, available=True, source='eDP-1', target='HDMI-A-1', error='')
REQUEST = dict(source='eDP-1', target='HDMI-A-1')
DEMO_MESSAGE = 'Demo preview: no system command executed'
REGISTRY = importlib.util.find_spec('mirror_actions') is not None


class MirrorActionCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
            XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'))
        env.start(); self.addCleanup(env.stop)

    def configured(self, demo=False, settings=False):
        live = self.make_backend(FakeRunner(available={'quickshell', 'wl-mirror'}), demo=demo)
        live.settings_only = settings
        for owner in (live.charge_executor, live.feature_executor, live.weather, live.capture, live.mirror):
            self.addCleanup(owner.shutdown if hasattr(owner, 'shutdown') else owner.close)
        live.mirror_state = copy.deepcopy(LOCAL)
        methods = Mock()
        for name, result in (('start', 'Mirror started on HDMI-A-1'), ('stop', 'Mirror stopped'), ('state', LOCAL)):
            methods.attach_mock(Mock(return_value=result), name)
            setattr(live.mirror, name, getattr(methods, name))
        methods.attach_mock(Mock(return_value=OUTPUTS), 'outputs'); live.display_control.outputs = methods.outputs
        prefix = ('quickshell', '-p', live.shell_entry, 'ipc', 'call', 'shell')
        live.runner.responses.update({prefix+('mirrorStart', 'eDP-1', 'HDMI-A-1'):'true\n',
            prefix+('mirrorStop',):'true\n', prefix+('mirrorStatus',):json.dumps(REMOTE)})
        return live, methods, prefix

    def test_all_context_demo_results_sequence_calls_state_and_privacy(self):
        for demo in (False, True):
            for settings in (False, True):
                live, methods, prefix = self.configured(demo, settings)
                for sequence, action in enumerate(ACTIONS, 1):
                    with self.subTest(action=action, demo=demo, settings=settings):
                        methods.reset_mock(); live.runner.calls.clear(); live.privacy_cache = {'old':True}
                        request = dict(action=action, **REQUEST) if action == 'mirrorStart' else dict(action=action)
                        message = DEMO_MESSAGE if demo else 'Mirror refreshed' if action == 'mirrorRefresh' else (
                            'Mirror request sent' if settings else 'Mirror started on HDMI-A-1' if action == 'mirrorStart' else 'Mirror stopped')
                        self.assertEqual(live.handle(request), dict(ok=True, action=action, message=message, sequence=sequence))
                        calls = []
                        if not demo and not settings:
                            calls = [call.state()] if action == 'mirrorRefresh' else [call.outputs(), call.start('eDP-1', 'HDMI-A-1', OUTPUTS)] if action == 'mirrorStart' else [call.stop()]
                        self.assertEqual(methods.mock_calls, calls)
                        rpc = []
                        if not demo and settings:
                            rpc = ([] if action == 'mirrorRefresh' else [prefix+(action, *REQUEST.values())] if action == 'mirrorStart' else [prefix+(action,)]) + [prefix+('mirrorStatus',)]
                        self.assertEqual(live.runner.calls, rpc)
                        expected = LOCAL if demo and action == 'mirrorRefresh' or not demo and not settings else REMOTE
                        if demo and action == 'mirrorStop': expected = dict(REMOTE, active=False)
                        self.assertEqual(live.feature_snapshot()['mirror'], expected)
                        self.assertEqual(live.privacy_cache, None if not demo and action != 'mirrorRefresh' else {'old':True})
                        self.assertFalse(live.feature_jobs); self.assertEqual(live.preferences.values['displayLayout'], [])

    def test_settings_requires_exact_true_ack_before_querying_status(self):
        for action in ('mirrorStart', 'mirrorStop'):
            for reply in ('', 'false', 'True', 'true extra', backend.CommandError('IPC failed')):
                live, methods, prefix = self.configured(settings=True)
                args = ('eDP-1','HDMI-A-1') if action == 'mirrorStart' else ()
                live.runner.responses[prefix+(action,*args)] = reply
                self.assertEqual(live.handle(dict(action=action, **REQUEST)), dict(ok=False, action=action,
                    message='IPC failed' if isinstance(reply,Exception) else 'Start LME Shell before controlling display mirroring.', sequence=1))
                self.assertEqual(live.runner.calls, [prefix+(action,*args)])
                self.assertEqual(live.mirror_state, LOCAL); self.assertFalse(methods.mock_calls)

    def test_settings_status_fallback_boolean_type_and_exact_payload(self):
        frames = ['bad json', '{}', '[]', 'null', 'true', '{"active":1}', '{"active":false,"extra":[1]}', json.dumps(REMOTE), backend.CommandError('Shell stopped')]
        for frame in frames:
            for available in (False, True):
                live, methods, prefix = self.configured(settings=True)
                live.preferences.values['shellName'] = 'Custom Shell'
                if not available: live.runner.names.discard('wl-mirror')
                live.runner.responses[prefix+('mirrorStatus',)] = frame
                self.assertEqual(live.handle(dict(action='mirrorRefresh')),
                    dict(ok=True, action='mirrorRefresh', message='Mirror refreshed', sequence=1))
                expected = dict(active=False, available=available, error='Start Custom Shell before controlling display mirroring.')
                if isinstance(frame,str):
                    try: value = json.loads(frame)
                    except ValueError: value = None
                    if isinstance(value,dict) and type(value.get('active')) is bool: expected = value
                self.assertEqual(live.feature_snapshot()['mirror'], expected)
                self.assertFalse(methods.mock_calls)
                self.assertEqual(live.runner.calls, [prefix+('mirrorStatus',)])

    def test_settings_validation_and_literal_argv_are_not_main_shell_validation(self):
        for source, target in ((None,'HDMI-A-1'), ('eDP-1',1)):
            live, methods, _ = self.configured(settings=True)
            self.assertEqual(live.handle(dict(action='mirrorStart', source=source, target=target)),
                dict(ok=False, action='mirrorStart', message='Choose source and target displays', sequence=1))
            self.assertFalse(live.runner.calls); self.assertFalse(methods.mock_calls)
        live, methods, prefix = self.configured(settings=True)
        source, target = 'source with spaces;$(literal)', ''
        live.runner.responses[prefix+('mirrorStart',source,target)] = 'true\n'
        live.runner.responses[prefix+('mirrorStatus',)] = '{"active":false,"error":"request queued"}'
        live.preferences.values['mirroringEnabled'] = False
        self.assertEqual(live.handle(dict(action='mirrorStart', source=source, target=target)),
            dict(ok=True, action='mirrorStart', message='Mirror request sent', sequence=1))
        self.assertEqual(live.runner.calls, [prefix+('mirrorStart',source,target),prefix+('mirrorStatus',)])
        self.assertEqual(live.mirror_state, dict(active=False, error='request queued')); self.assertFalse(methods.mock_calls)

    def test_main_guard_precedes_outputs_and_controller_errors_do_not_install_state(self):
        live, methods, _ = self.configured(); live.preferences.values['mirroringEnabled'] = False
        self.assertEqual(live.handle(dict(action='mirrorStart')), dict(ok=False, action='mirrorStart',
            message='Display mirroring is disabled', sequence=1))
        self.assertFalse(methods.mock_calls)
        live.preferences.values['mirroringEnabled'] = True
        with patch.object(live.mirror, 'start', side_effect=ValueError('x'*450)) as start:
            self.assertEqual(live.handle(dict(action='mirrorStart', **REQUEST)),
                dict(ok=False, action='mirrorStart', message='x'*400, sequence=2))
            start.assert_called_once_with('eDP-1','HDMI-A-1',OUTPUTS)
        self.assertEqual(live.mirror_state, LOCAL)

    def test_demo_refresh_clone_validation_order_stop_fields_and_no_io(self):
        for settings in (False, True):
            live, methods, _ = self.configured(demo=True, settings=settings)
            with patch('subprocess.Popen', side_effect=AssertionError('demo spawn')), \
                    patch('io.open', side_effect=AssertionError('demo file IO')), \
                    patch('os.open', side_effect=AssertionError('demo fd')), \
                    patch('os.mkdir', side_effect=AssertionError('demo mkdir')):
                live.preferences.values['mirroringEnabled'] = False
                self.assertEqual(live.handle(dict(action='mirrorStart', **REQUEST))['message'], 'Choose two different, active niri displays.')
                self.assertTrue(live.handle(dict(action='mirrorRefresh'))['ok'])
                before = copy.deepcopy(live.displays['outputs'])
                self.assertEqual([o['name'] for o in before], ['eDP-1','HDMI-A-1'])
                self.assertEqual(before[1], dict(before[0], name='HDMI-A-1', description='Demo projector', x=1920))
                self.assertEqual(live.handle(dict(action='mirrorStart', **REQUEST))['message'], 'Display mirroring is disabled')
                live.handle(dict(action='mirrorRefresh')); self.assertEqual(live.displays['outputs'], before)
                live.mirror_state = dict(LOCAL, active=True)
                live.handle(dict(action='mirrorStop')); self.assertEqual(live.mirror_state, dict(LOCAL, active=False))
            self.assertEqual(live.preferences.values['displayLayout'], []); self.assertFalse(live.runner.calls)
            self.assertFalse(methods.mock_calls); self.assertIsNone(live.mirror.child)

    def test_unknown_prefixes_keep_legacy_errors_and_do_not_claim_a_job(self):
        for demo in (False, True):
            for settings in (False, True):
                live, _, _ = self.configured(demo,settings)
                for sequence, action in enumerate(('mirrorUnknown','mirrorStartExtra'),1):
                    self.assertEqual(live.handle(dict(action=action)), dict(ok=False, action=action, sequence=sequence,
                        message='This action is unavailable in the settings app' if settings else 'Unknown action: '+action))
                    self.assertFalse(live.feature_jobs)

    @unittest.skipUnless(REGISTRY, 'mirror provider absent on baseline; registry-specific N/A')
    def test_registration_is_pure_contexts_and_no_fallback_after_error(self):
        from mirror_actions import MirrorCapabilities, provide
        operations = [Mock() for _ in range(14)]
        specs, project = provide(MirrorCapabilities(*operations))
        self.assertEqual([s.name for s in specs], list(ACTIONS)); self.assertEqual(project(), {})
        for operation in operations: operation.assert_not_called()
        live, _, _ = self.configured()
        with patch.object(live, 'perform', side_effect=AssertionError('legacy fallback')), \
                patch.object(live.mirror, 'state', side_effect=ValueError('mirror failure')):
            self.assertEqual(live.handle(dict(action='mirrorRefresh')),
                dict(ok=False, action='mirrorRefresh', message='mirror failure', sequence=1))
        for action in ACTIONS:
            spec = live.actions.get(action)
            self.assertEqual(spec.contexts, {'shell','settings'}); self.assertEqual(spec.execution,'sync')


if __name__ == '__main__': unittest.main()
