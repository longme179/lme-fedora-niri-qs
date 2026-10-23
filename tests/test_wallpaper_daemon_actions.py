"""Freeze daemon action boundaries before moving their live/demo handlers."""
import copy
import json
import os
from threading import Event
import unittest
from unittest.mock import Mock, patch

from test_backend import Fixture, FakeRunner, backend
from test_features import ManualExecutor

ACTIONS = ('wallpaperStatus', 'wallpaperEnsure')
QUERY = 'eDP-1: 1920x1080 · wallpaper.png'
DEMO = 'Demo preview: no system command executed'


class WallpaperDaemonDispatchCase(Fixture, unittest.TestCase):
    def configured(self, demo=False, settings=False, manual=True):
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
                         XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'))
        env.start(); self.addCleanup(env.stop)
        runner = FakeRunner({('awww', 'query'): QUERY})
        live = self.make_backend(runner, demo=demo); live.settings_only = settings
        self.addCleanup(live.charge_executor.shutdown); self.addCleanup(live.feature_executor.shutdown)
        if manual:
            live.feature_executor.shutdown(wait=True)
            live.feature_executor = ManualExecutor()
        return live

    @staticmethod
    def result(action, message='Working…', sequence=1, ok=True, pending=False):
        value = dict(action=action, ok=ok, message=message, sequence=sequence)
        if pending: value['pending'] = True
        return value

    def test_live_contexts_ack_before_completion_and_exact_snapshot_projection(self):
        for settings in (False, True):
            for action in ACTIONS:
                with self.subTest(settings=settings, action=action):
                    live = self.configured(settings=settings)
                    original = {'sentinel': 'old daemon state'}; live.wallpaper_daemon = original
                    before = copy.deepcopy(live.snapshot())
                    with patch.object(live.runner, 'run', wraps=live.runner.run) as run, \
                         patch.object(live.wallpapers, 'ready', return_value=QUERY) as ready:
                        ack = self.result(action, pending=True)
                        self.assertEqual(live.handle(dict(action=action)), ack)
                        ready.assert_not_called()
                        self.assertFalse(any(call.args[0] == 'awww' for call in run.call_args_list))
                        live.feature_executor.complete()
                        self.assertEqual(live.snapshot()['lastResult'], ack)
                        self.assertIs(live.wallpaper_daemon, original)
                        done = live.snapshot()
                        if action == 'wallpaperStatus':
                            run.assert_any_call('awww', 'query', timeout=2); ready.assert_not_called()
                            expected = dict(available=True, running=True, query=QUERY, error='')
                            message = 'Wallpaper daemon checked'
                        else:
                            ready.assert_called_once_with(); expected = original; message = 'Wallpaper daemon ready'
                        self.assertEqual(done['lastResult'], self.result(action, message, 2))
                        self.assertEqual(done['wallpaperDaemon'], expected)
                        self.assertEqual(live.feature_snapshot()['wallpaperDaemon'], expected)
                        self.assertEqual(set(done), set(before)); self.assertEqual(done['preferences'], before['preferences'])
                    self.assertFalse(live.feature_jobs); self.assertFalse(self.preferences.path.exists())

    def test_status_runtime_errors_are_successful_state_reports_not_failed_results(self):
        for error, available in ((backend.CommandError('Required command is unavailable: awww'), False),
                                 (RuntimeError('x'*450), True)):
            live = self.configured(settings=True)
            with patch.object(live.runner, 'available', return_value=available), \
                 patch.object(live.runner, 'run', side_effect=error):
                self.assertEqual(live.handle(dict(action='wallpaperStatus')), self.result('wallpaperStatus', pending=True))
                live.feature_executor.complete(); live.finish_features()
            self.assertEqual(live.last_result, self.result('wallpaperStatus', 'Wallpaper daemon checked', 2))
            self.assertEqual(live.wallpaper_daemon, dict(available=available, running=False, query='', error=str(error)))
            self.assertFalse(live.feature_jobs)

    def test_deferred_errors_preserve_state_truncate_results_and_clear_pending(self):
        for action in ACTIONS:
            for error in (ValueError('cancelled'), OSError('x'*450), backend.CommandError('daemon unavailable')):
                if action == 'wallpaperStatus' and isinstance(error, RuntimeError): continue
                live = self.configured(); original = {'old': True}; live.wallpaper_daemon = original
                owner, method = (live.runner, 'run') if action == 'wallpaperStatus' else (live.wallpapers, 'ready')
                with patch.object(owner, method, side_effect=error) as operation:
                    self.assertEqual(live.handle(dict(action=action)), self.result(action, pending=True))
                    operation.assert_not_called(); live.feature_executor.complete(); live.finish_features()
                self.assertEqual(live.last_result, self.result(action, str(error)[:400], 2, ok=False))
                self.assertIs(live.wallpaper_daemon, original); self.assertFalse(live.feature_jobs)
                self.assertIsNone(live.system_cache)

    def test_duplicate_ownership_and_parallel_completion_keep_sequence_and_order(self):
        live = self.configured()
        with patch.object(live.wallpapers, 'ready', return_value=QUERY):
            for sequence, action in enumerate(ACTIONS, 1):
                self.assertEqual(live.handle(dict(action=action)), self.result(action, sequence=sequence, pending=True))
            owners = dict(live.feature_jobs)
            self.assertEqual(live.handle(dict(action=ACTIONS[0])),
                             self.result(ACTIONS[0], 'This operation is already running', 3, ok=False))
            self.assertEqual(live.feature_jobs, owners); self.assertEqual(len(live.feature_executor.jobs), 2)
            live.feature_executor.complete(); live.feature_executor.complete()
            self.assertEqual(live.snapshot()['lastResult']['sequence'], 3)
            self.assertEqual(live.snapshot()['lastResult'], self.result(ACTIONS[0], 'Wallpaper daemon checked', 4))
            self.assertEqual(set(live.feature_jobs), {ACTIONS[1]})
            self.assertEqual(live.snapshot()['lastResult'], self.result(ACTIONS[1], 'Wallpaper daemon ready', 5))
            self.assertFalse(live.feature_jobs)
            self.assertEqual(live.handle(dict(action=ACTIONS[1])), self.result(ACTIONS[1], sequence=6, pending=True))

    def test_demo_contexts_no_io_no_jobs_status_state_and_ensure_no_op(self):
        for settings in (False, True):
            live = self.configured(demo=True, settings=settings)
            original = {'keep': True}; live.wallpaper_daemon = original
            files = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
            with patch.object(live.wallpapers, 'ready', side_effect=AssertionError('demo daemon')), \
                 patch.object(live.runner, 'run', side_effect=AssertionError('demo command')), \
                 patch('subprocess.Popen', side_effect=AssertionError('demo spawn')), \
                 patch('os.open', side_effect=AssertionError('demo file open')), \
                 patch('os.replace', side_effect=AssertionError('demo write')):
                self.assertEqual(live.handle(dict(action='wallpaperEnsure')), self.result('wallpaperEnsure', DEMO))
                self.assertIs(live.wallpaper_daemon, original)
                self.assertEqual(live.handle(dict(action='wallpaperStatus')), self.result('wallpaperStatus', DEMO, 2))
                self.assertEqual(live.snapshot()['wallpaperDaemon'], dict(available=True, running=True,
                    query='eDP-1: 1920x1080 · demo wallpaper', error=''))
            self.assertFalse(live.feature_jobs); self.assertFalse(live.feature_executor.jobs)
            self.assertEqual(files, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_direct_facades_and_unknown_prefixes_keep_original_contracts(self):
        live = self.configured(); demo = self.configured(demo=True)
        for action in ACTIONS:
            with patch.object(live.wallpapers, 'ready', return_value=QUERY):
                self.assertEqual(live.perform(action, {}), 'Working…')
                live.feature_executor.complete(); live.finish_features()
            self.assertIsNone(demo.perform_demo(action, {}))
        for preview in (False, True):
            for settings in (False, True):
                other = self.configured(demo=preview, settings=settings)
                for sequence, action in enumerate(('wallpaperUnknown', 'wallpaperStatusExtra'), 1):
                    message = 'This action is unavailable in the settings app' if settings else 'Unknown action: '+action
                    self.assertEqual(other.handle(dict(action=action)), self.result(action, message, sequence, ok=False))

    def test_shutdown_cancels_queued_work_without_daemon_calls_or_final_completion(self):
        for action in ACTIONS:
            live = self.configured(settings=True, manual=False); live.runner.close = Mock()
            gate = Event(); started = [Event(), Event()]; self.addCleanup(gate.set)
            def occupy(ready): ready.set(); gate.wait(5)
            for ready in started: live.feature_executor.submit(occupy, ready)
            for ready in started: self.assertTrue(ready.wait(2))
            read_fd, write_fd = os.pipe()
            with os.fdopen(read_fd, 'r') as source:
                os.write(write_fd, (json.dumps(dict(action=action))+'\n').encode()); os.close(write_fd)
                frames = []
                with patch.object(backend, 'DesktopBackend', return_value=live), \
                     patch.object(backend.sys, 'stdin', source), patch.object(backend.signal, 'signal'), \
                     patch.object(backend, 'emit', side_effect=lambda b: frames.append(copy.deepcopy(b.snapshot()))), \
                     patch.object(live.wallpapers, 'ready', side_effect=AssertionError('cancelled daemon call')):
                    self.assertEqual(backend.main(['--settings']), 0)
                self.assertEqual([frame['lastResult']['action'] for frame in frames], ['ready', action])
                self.assertEqual(frames[-1]['lastResult'], self.result(action, pending=True))
                self.assertTrue(live.feature_jobs[action].cancelled())
                self.assertFalse(any(call[0] == 'awww' for call in live.runner.calls))
            gate.set()

    def test_registered_ownership_is_inert_and_start_errors_never_fall_back(self):
        import wallpaper_actions as provider
        if not hasattr(provider, 'provide_daemon'):
            self.skipTest('M7c daemon provider absent on baseline; registry ownership N/A')
        available = Mock(); run = Mock(); ready = Mock(); install = Mock()
        specs, project = provider.provide_daemon(provider.WallpaperDaemonCapabilities(available, run, ready, install))
        self.assertEqual({spec.name for spec in specs}, set(ACTIONS)); self.assertEqual(project(), {})
        available.assert_not_called(); run.assert_not_called(); ready.assert_not_called(); install.assert_not_called()
        for spec in specs:
            self.assertEqual(spec.contexts, frozenset({'shell', 'settings'}))
            self.assertEqual(spec.execution, 'worker'); spec.complete(ValueError('failed'))
        install.assert_not_called()
        for preview in (False, True):
            for settings in (False, True):
                live = self.configured(demo=preview, settings=settings)
                target = 'perform_demo' if preview else 'perform'
                with patch.object(live, target, side_effect=AssertionError('legacy fallback')), \
                     patch.object(live, 'start_feature', side_effect=ValueError('submission failed')) as start:
                    for sequence, action in enumerate(ACTIONS, 1):
                        expected = self.result(action, DEMO if preview else 'submission failed', sequence, ok=preview)
                        self.assertEqual(live.handle(dict(action=action)), expected)
                if preview: start.assert_not_called()
                else: self.assertEqual(start.call_count, 2)
