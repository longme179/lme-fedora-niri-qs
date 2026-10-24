"""Baseline contracts for capture start/close/language admission and lifecycle."""
import copy
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, call, patch

import capture_actions
from test_backend import Fixture, FakeRunner, backend
from test_clipboard import PNG

ACTIONS = ('screenshot', 'screenshotArea', 'screenshotWindow', 'captureClose', 'captureLanguages')
MODES = dict(zip(ACTIONS, ('screen', 'area', 'window')))
CONTEXT_ERROR = 'This action is unavailable in the settings app'
DEMO_MESSAGE = 'Demo preview: no system command executed'


class CaptureEntryCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
            XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'))
        env.start(); self.addCleanup(env.stop)

    def configured(self, demo=False, settings=False, runner=None):
        live = self.make_backend(runner=runner, demo=demo)
        live.settings_only = settings
        self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.feature_executor.shutdown)
        self.addCleanup(live.weather.close)
        self.addCleanup(live.capture.close)
        return live

    def test_five_entries_shell_settings_live_demo_exact_results_and_call_order(self):
        for demo in (False, True):
            for settings in (False, True):
                live = self.configured(demo, settings)
                methods = Mock()
                for name, result in (('start', 'Capture started'), ('close', None), ('languages', ['vie'])):
                    methods.attach_mock(Mock(return_value=result), name)
                    setattr(live.capture, name, getattr(methods, name))
                live.capture.state['languages'] = ['old']
                with patch.object(backend.time, 'sleep', methods.delay):
                    for sequence, action in enumerate(ACTIONS, 1):
                        with self.subTest(action=action, demo=demo, settings=settings):
                            methods.reset_mock()
                            message = (CONTEXT_ERROR if settings else DEMO_MESSAGE if demo else
                                'Capture started' if action in MODES else 'Screenshot closed' if action == 'captureClose'
                                else 'OCR languages refreshed')
                            self.assertEqual(live.handle(dict(action=action)),
                                dict(ok=not settings, action=action, message=message, sequence=sequence))
                            expected = []
                            if not settings:
                                if action in MODES and not demo: expected = [call.delay(.2), call.start(MODES[action])]
                                elif action == 'captureClose': expected = [call.close()]
                                elif action == 'captureLanguages' and not demo: expected = [call.languages()]
                            self.assertEqual(methods.mock_calls, expected)
                            self.assertFalse(live.feature_jobs)
                    self.assertEqual(live.capture.state['languages'], ['eng', 'vie'] if demo and not settings else ['old'])
                    self.assertEqual(live.runner.calls, [])
                    self.assertEqual(live.runner.spawns, [])

    def test_controller_failures_keep_exact_messages_sequence_and_delay(self):
        for action in ACTIONS:
            live = self.configured()
            method = 'start' if action in MODES else 'close' if action == 'captureClose' else 'languages'
            with patch.object(live.capture, method, side_effect=backend.CommandError('x'*450)) as operation, \
                    patch.object(backend.time, 'sleep') as delay:
                self.assertEqual(live.handle(dict(action=action)),
                    dict(ok=False, action=action, message='x'*400, sequence=1))
                self.assertEqual(operation.call_count, 1)
                self.assertEqual(delay.call_args_list, [call(.2)] if action in MODES else [])
                self.assertFalse(live.feature_jobs)

    def test_real_controller_session_ready_duplicate_close_and_reopen(self):
        live = self.configured(runner=FakeRunner(available={'niri'}))
        with patch.object(backend.time, 'sleep'):
            for action, mode in MODES.items():
                reply = live.handle(dict(action=action))
                self.assertEqual(reply['message'], 'Choose an area in niri' if mode == 'area' else 'Capturing screenshot…')
                self.assertTrue(reply['ok']); self.assertNotIn('pending', reply)
                folder = live.capture.directory.name
                source = Path(live.capture.state['path']); source.write_bytes(PNG)
                live.capture.refresh(); live.capture.refresh()
                state = copy.deepcopy(live.capture.state)
                self.assertEqual(state['status'], 'ready'); self.assertEqual(state['mode'], mode)
                self.assertEqual(source.stat().st_mode & 0o777, 0o600)
                self.assertEqual(live.feature_snapshot()['capture'], state)
                result = live.handle(dict(action=action))
                self.assertEqual(result['message'], 'Finish or close the current screenshot first')
                self.assertFalse(result['ok']); self.assertEqual(live.capture.state, state)
                self.assertEqual(live.handle(dict(action='captureClose'))['message'], 'Screenshot closed')
                self.assertFalse(Path(folder).exists())
                self.assertEqual(live.feature_snapshot()['capture'], dict(status='idle', error='', ocrText='', languages=[]))

    def test_language_detection_filters_output_and_close_retains_languages(self):
        runner = FakeRunner({('tesseract', '--list-langs'): 'List of languages:\neng\nvie\nosd\n../bad\n'})
        live = self.configured(runner=runner)
        self.assertEqual(live.handle(dict(action='captureLanguages')),
            dict(ok=True, action='captureLanguages', message='OCR languages refreshed', sequence=1))
        self.assertEqual(runner.calls, [('tesseract', '--list-langs')])
        self.assertEqual(live.feature_snapshot()['capture']['languages'], ['eng', 'vie'])
        live.handle(dict(action='captureClose'))
        self.assertEqual(live.capture.state, dict(status='idle', error='', ocrText='', languages=['eng', 'vie']))

    def test_demo_start_and_languages_do_not_spawn_or_write(self):
        for settings in (False, True):
            live = self.configured(demo=True, settings=settings)
            before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
            with patch('subprocess.Popen', side_effect=AssertionError('demo spawn')), \
                    patch('os.open', side_effect=AssertionError('demo open')), \
                    patch('os.mkdir', side_effect=AssertionError('demo mkdir')), \
                    patch('io.open', side_effect=AssertionError('demo file IO')):
                for action in (*MODES, 'captureLanguages'):
                    self.assertEqual(live.handle(dict(action=action))['ok'], not settings)
            self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
            self.assertIsNone(live.capture.directory)

    def test_unknown_prefixes_keep_legacy_errors_and_unrelated_owners(self):
        from concurrent.futures import Future
        for demo in (False, True):
            for settings in (False, True):
                live = self.configured(demo, settings)
                owner = Future(); live.feature_jobs['captureOcr'] = owner
                for sequence, action in enumerate(('captureUnknown', 'screenshotUnknown'), 1):
                    self.assertEqual(live.handle(dict(action=action)), dict(ok=False, action=action,
                        message=CONTEXT_ERROR if settings else 'Unknown action: '+action, sequence=sequence))
                    self.assertEqual(live.feature_jobs, {'captureOcr': owner})
                live.handle(dict(action='captureClose'))
                self.assertEqual(live.feature_jobs, {'captureOcr': owner})

    @unittest.skipUnless(hasattr(capture_actions, 'provide_controls'), 'capture entry provider absent on baseline; registry-specific N/A')
    def test_registration_is_pure_and_registered_errors_never_fall_back(self):
        cap = capture_actions.ControlCapabilities(Mock(), Mock(), Mock(), Mock())
        specs, project = capture_actions.provide_controls(cap)
        self.assertEqual([spec.name for spec in specs], list(ACTIONS))
        self.assertEqual(project(), {})
        for operation in (cap.start, cap.close, cap.languages, cap.current): operation.assert_not_called()
        live = self.configured()
        with patch.object(live, 'perform', side_effect=AssertionError('legacy fallback')), \
                patch.object(live.capture, 'close', side_effect=ValueError('capture failure')):
            self.assertEqual(live.handle(dict(action='captureClose')),
                dict(ok=False, action='captureClose', message='capture failure', sequence=1))
        for action in ACTIONS:
            spec = live.actions.get(action)
            self.assertEqual(spec.execution, 'sync'); self.assertEqual(spec.contexts, {'shell'})


if __name__ == '__main__': unittest.main()
