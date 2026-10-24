"""Characterize preview admission, rollback seams and persistence ordering."""
from contextlib import contextmanager
import copy
from concurrent.futures import Future
import importlib.util
import json
import os
import unittest
from unittest.mock import Mock, patch

from test_backend import Fixture, FakeRunner, backend
from test_upgrades import OUTPUT
from display_control import current_layout, normalized_outputs
from storage import read_json, write_json

ACTIONS = ('displayRefresh', 'displayApply', 'displayConfirm', 'displayRevert', 'platformRefresh')
OUTPUTS = normalized_outputs(OUTPUT)
LAYOUT = [dict(current_layout(OUTPUTS)[0], refresh=60000)]
STATE = dict(outputs=OUTPUTS, preview=dict(token='private', status='pending', deadline=200, layout=LAYOUT))
PLATFORM = dict(niriVersion='niri 26.04', popupBlurSupported=True)
DEMO_MESSAGE = 'Demo preview: no system command executed'
REGISTRY = importlib.util.find_spec('display_actions') is not None


class DisplayActionCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
            XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'), NIRI_SOCKET='private-display')
        env.start(); self.addCleanup(env.stop)

    def configured(self, demo=False, settings=False, tracked=True):
        runner = FakeRunner({('niri', 'msg', '--json', 'outputs'): json.dumps(OUTPUT), ('niri', '--version'): 'niri 26.04'})
        live = self.make_backend(runner=runner, demo=demo); live.settings_only = settings
        for owner in (live.charge_executor, live.feature_executor, live.weather, live.capture):
            self.addCleanup(owner.shutdown if hasattr(owner, 'shutdown') else owner.close)
        events = []
        if not tracked: return live, events
        def event(name, result):
            def call(*args):
                events.append((name, copy.deepcopy(args)))
                return copy.deepcopy(result)
            return call
        @contextmanager
        def guard():
            events.append(('enter', ()))
            try: yield
            finally: events.append(('exit', ()))
        live.battery_saver.guard = guard
        live.display_control.snapshot = event('snapshot', STATE)
        live.display_control.start = event('start', None)
        live.display_control.decide = event('decide', LAYOUT)
        live.compositor_features = event('platform', PLATFORM)
        save = live.preferences.set
        def persist(*args):
            events.append(('save', copy.deepcopy(args)))
            return save(*args)
        live.preferences.set = persist
        return live, events

    def test_shell_settings_live_demo_results_sequence_call_order_and_state(self):
        messages = ('Displays refreshed', 'Display preview requested; confirm within 20 seconds',
            'Display layout saved', 'Restoring displays', 'Compositor version checked')
        expected_calls = ([('snapshot', ())], [('enter', ()), ('start', (LAYOUT,)), ('exit', ()), ('snapshot', ())],
            [('decide', ('private', True)), ('save', ('displayLayout', LAYOUT)), ('snapshot', ())],
            [('decide', ('private', False)), ('snapshot', ())], [('platform', ())])
        for demo in (False, True):
            for settings in (False, True):
                live, events = self.configured(demo, settings)
                with patch.object(backend.time, 'time', return_value=100):
                    for sequence, (action, message, calls) in enumerate(zip(ACTIONS, messages, expected_calls), 1):
                        with self.subTest(action=action, demo=demo, settings=settings):
                            live.displays = copy.deepcopy(STATE); events.clear()
                            reply = live.handle(dict(action=action, layout=LAYOUT, token='private'))
                            self.assertEqual(reply, dict(ok=True, action=action,
                                message=DEMO_MESSAGE if demo else message, sequence=sequence))
                            self.assertEqual(events, [] if demo else calls)
                            expected = copy.deepcopy(STATE)
                            if demo and action == 'displayApply': expected['preview'].update(token='demo', deadline=120)
                            if demo and action in ('displayConfirm', 'displayRevert'):
                                expected['preview']['status'] = 'confirmed' if action == 'displayConfirm' else 'reverted'
                            self.assertEqual(live.feature_snapshot()['displays'], expected)
                            if action == 'displayConfirm': self.assertEqual(live.preferences.values['displayLayout'], LAYOUT)
                            if action == 'platformRefresh' and not demo: self.assertEqual(live.feature_snapshot()['platform'], PLATFORM)
                            self.assertFalse(live.feature_jobs)

    def journal(self, live, **changes):
        value = dict(token='private', status='pending', deadline=200, socket='private-display', layout=LAYOUT,
            original=current_layout(OUTPUTS), error='', **changes)
        write_json(live.display_control.path, value)
        return value

    def test_real_controller_confirm_revert_preserve_journal_and_private_settings(self):
        for settings in (False, True):
            for keep in (False, True):
                live, _ = self.configured(settings=settings, tracked=False)
                self.journal(live)
                action = 'displayConfirm' if keep else 'displayRevert'
                before = live.preferences.path.read_bytes() if live.preferences.path.exists() else None
                with patch.object(backend.time, 'time', return_value=100): reply = live.handle(dict(action=action, token='private'))
                self.assertEqual(reply, dict(ok=True, action=action, sequence=1,
                    message='Display layout saved' if keep else 'Restoring displays'))
                self.assertEqual(read_json(live.display_control.path, {})['status'], 'confirmed' if keep else 'reverting')
                self.assertEqual(live.display_control.path.stat().st_mode & 0o777, 0o600)
                if keep:
                    self.assertEqual(read_json(live.preferences.path, {})['displayLayout'], LAYOUT)
                    self.assertEqual(live.preferences.path.stat().st_mode & 0o777, 0o600)
                else:
                    self.assertEqual(live.preferences.path.read_bytes() if live.preferences.path.exists() else None, before)

    def test_failed_settings_save_keeps_decision_first_without_installing_a_snapshot(self):
        live, _ = self.configured(tracked=False); self.journal(live)
        before = copy.deepcopy(live.displays)
        with patch.object(backend.time, 'time', return_value=100), \
                patch.object(live.preferences, 'set', side_effect=OSError('Disk full')), \
                patch.object(live.display_control, 'snapshot') as snapshot:
            self.assertEqual(live.handle(dict(action='displayConfirm', token='private')),
                dict(ok=False, action='displayConfirm', message='Disk full', sequence=1))
            snapshot.assert_not_called()
        self.assertEqual(read_json(live.display_control.path, {})['status'], 'confirmed')
        self.assertEqual(live.displays, before)
        self.assertFalse(live.preferences.path.exists())

    def test_pending_guard_and_start_errors_preserve_admission_order_and_owners(self):
        live, events = self.configured(); owner = Future(); live.feature_jobs['batterySaver'] = owner
        self.assertEqual(live.handle(dict(action='displayApply', layout=[])),
            dict(ok=False, action='displayApply', message='Wait for Battery saver to finish', sequence=1))
        self.assertEqual(events, []); self.assertEqual(live.feature_jobs, {'batterySaver': owner})
        live.feature_jobs.clear()
        with patch.object(live.battery_saver, 'guard', side_effect=ValueError('Turn off Battery saver first')):
            self.assertEqual(live.handle(dict(action='displayApply', layout=[]))['message'], 'Turn off Battery saver first')
        self.assertEqual(events, [])
        with patch.object(live.display_control, 'start', side_effect=ValueError('invalid layout')):
            self.assertEqual(live.handle(dict(action='displayApply', layout=[])),
                dict(ok=False, action='displayApply', message='invalid layout', sequence=3))
        self.assertEqual(events, [('enter', ()), ('exit', ())])
        self.assertEqual(live.displays, dict(outputs=[], preview={}))

    def test_expired_real_decisions_never_save_or_replace_state(self):
        for token, deadline in (('wrong', 200), ('private', 100)):
            live, _ = self.configured(tracked=False)
            value = self.journal(live); value['deadline'] = deadline; write_json(live.display_control.path, value)
            for action in ('displayConfirm', 'displayRevert'):
                with patch.object(backend.time, 'time', return_value=100), patch.object(live.preferences, 'set') as save:
                    result = live.handle(dict(action=action, token=token))
                    self.assertFalse(result['ok']); self.assertEqual(result['message'], 'This display preview has expired')
                    save.assert_not_called()
                self.assertEqual(live.displays, dict(outputs=[], preview={}))

    def test_demo_seed_expiration_validation_and_permissive_confirmation_tokens(self):
        live, events = self.configured(demo=True)
        with patch.object(backend.time, 'time', return_value=100):
            self.assertTrue(live.handle(dict(action='displayRefresh'))['ok'])
            output = live.displays['outputs'][0]
            self.assertEqual(output, dict(name='eDP-1', description='Lenovo laptop display', enabled=True,
                modes=[dict(width=1920, height=1080, refresh=hz*1000, label=f'1920 × 1080 · {hz} Hz') for hz in (60,120)],
                current=dict(width=1920, height=1080, refresh=120000), scale=1, x=0, y=0, width=1920, height=1080))
            self.assertTrue(live.handle(dict(action='displayApply', layout=LAYOUT))['ok'])
            self.assertEqual(live.displays['preview'], dict(token='demo', status='pending', deadline=120, layout=LAYOUT))
        with patch.object(backend.time, 'time', return_value=120):
            live.handle(dict(action='displayRefresh')); self.assertEqual(live.displays['preview']['status'], 'reverted')
        self.assertEqual(live.handle(dict(action='displayConfirm'))['message'], 'No display preview')
        live.displays['preview']['status'] = 'pending'
        self.assertTrue(live.handle(dict(action='displayConfirm', token='ignored-in-demo'))['ok'])
        self.assertEqual(live.preferences.values['displayLayout'], LAYOUT)
        self.assertEqual(events, [])

    def test_demo_has_no_writes_or_processes_and_legacy_mirror_refresh_keeps_link(self):
        for settings in (False, True):
            live, events = self.configured(demo=True, settings=settings)
            with patch('subprocess.Popen', side_effect=AssertionError('demo spawned')), \
                    patch('io.open', side_effect=AssertionError('demo file IO')), \
                    patch('os.open', side_effect=AssertionError('demo opened fd')), \
                    patch('os.mkdir', side_effect=AssertionError('demo mkdir')):
                for action in (*ACTIONS, 'mirrorRefresh'):
                    live.displays = copy.deepcopy(STATE)
                    self.assertTrue(live.handle(dict(action=action, layout=LAYOUT, token='private'))['ok'])
            self.assertEqual([o['name'] for o in live.displays['outputs']], ['eDP-1', 'HDMI-A-1'])
            self.assertEqual(events, []); self.assertEqual(live.runner.calls, [])
            self.assertFalse(live.preferences.path.exists())

    def test_demo_rejects_bad_layouts_without_replacing_the_preview(self):
        for settings in (False, True):
            live, events = self.configured(demo=True, settings=settings)
            live.displays = copy.deepcopy(STATE)
            for sequence, (layout, message) in enumerate((([], 'Choose at least one display'),
                    ([dict(LAYOUT[0], scale=float('nan'))], 'Scale must be between 0.5 and 3'),
                    ([dict(LAYOUT[0], name='gone')], 'Display or mode is no longer available; refresh displays')), 1):
                self.assertEqual(live.handle(dict(action='displayApply', layout=layout)),
                    dict(ok=False, action='displayApply', message=message, sequence=sequence))
                self.assertEqual(live.displays, STATE)
            self.assertEqual(events, [])

    def test_unknown_prefixes_stay_legacy_and_platform_refresh_uses_current_readback(self):
        for demo in (False, True):
            for settings in (False, True):
                live, _ = self.configured(demo, settings, tracked=False)
                for action in ('displayUnknown', 'platformRefreshExtra'):
                    result = live.handle(dict(action=action))
                    self.assertEqual(result['message'], 'This action is unavailable in the settings app' if settings else 'Unknown action: '+action)
                    self.assertFalse(result['ok'])
                self.assertTrue(live.handle(dict(action='platformRefresh'))['ok'])
                if not demo: self.assertEqual(live.feature_snapshot()['platform'], PLATFORM)

    @unittest.skipUnless(REGISTRY, 'display provider absent on baseline; registry-specific N/A')
    def test_provider_registration_is_pure_and_errors_never_fall_back(self):
        from display_actions import PreviewCapabilities, PlatformCapabilities, provide, provide_platform
        capabilities = [Mock() for _ in range(9)]
        specs, project = provide(PreviewCapabilities(*capabilities))
        platform = [Mock(), Mock()]; extra, projection = provide_platform(PlatformCapabilities(*platform))
        self.assertEqual([s.name for s in (*specs, *extra)], list(ACTIONS))
        self.assertEqual(project(), {}); self.assertEqual(projection(), {})
        for operation in (*capabilities, *platform): operation.assert_not_called()
        live, _ = self.configured()
        with patch.object(live, 'perform', side_effect=AssertionError('legacy fallback')), \
                patch.object(live.display_control, 'snapshot', side_effect=ValueError('display error')):
            self.assertEqual(live.handle(dict(action='displayRefresh')),
                dict(ok=False, action='displayRefresh', message='display error', sequence=1))
        for action in ACTIONS:
            spec = live.actions.get(action)
            self.assertEqual(spec.contexts, {'shell', 'settings'}); self.assertEqual(spec.execution, 'sync')


if __name__ == '__main__': unittest.main()
