"""Wallpaper scan characterization, also run through test_action_registry."""
from concurrent.futures import CancelledError, Future
import copy
import io
import json
import os
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import Mock, patch

from test_backend import Fixture, backend
from test_features import ManualExecutor


class WallpaperScanDispatchCase(Fixture, unittest.TestCase):
    def configured(self, demo=False, settings=False, manual=True):
        env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root/'config'),
                         XDG_STATE_HOME=str(self.root/'state'), XDG_RUNTIME_DIR=str(self.root/'runtime'))
        env.start(); self.addCleanup(env.stop)
        live = self.make_backend(demo=demo); live.settings_only = settings
        self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.feature_executor.shutdown)
        if manual:
            live.feature_executor.shutdown(wait=True)
            live.feature_executor = ManualExecutor()
        return live

    @staticmethod
    def result(ok=True, message='Working…', sequence=1, pending=False):
        value = dict(ok=ok, action='wallpaperScan', message=message, sequence=sequence)
        if pending: value['pending'] = True
        return value

    def test_shell_settings_ack_precedes_fast_completion_and_snapshot_shape_is_identical(self):
        image = self.put('images/a.png', 'image')
        expected = dict(entries=[dict(path=str(image), name='a.png', url=image.as_uri())],
                        folder=str(image.parent), truncated=False, error='')
        for settings in (False, True):
            live = self.configured(settings=settings)
            before = copy.deepcopy(live.snapshot()); original = copy.deepcopy(live.wallpaper_library)
            self.assertEqual(live.handle(dict(action='wallpaperScan', folder=str(image.parent))), self.result(pending=True))
            self.assertEqual(set(live.feature_jobs), {'wallpaperScan'})
            live.feature_executor.complete()
            ack = live.snapshot()
            self.assertEqual(ack['lastResult'], self.result(pending=True))
            self.assertEqual(ack['wallpaperLibrary'], original)
            done = live.snapshot()
            self.assertEqual(done['lastResult'], self.result(message='Wallpaper library refreshed', sequence=2))
            self.assertEqual(done['wallpaperLibrary'], expected)
            self.assertEqual(set(done), set(before)); self.assertEqual(done['preferences'], before['preferences'])
            self.assertFalse(live.feature_jobs); self.assertEqual(live.runner.calls, [])
            self.assertFalse(self.preferences.path.exists())

    def test_duplicate_owner_rejects_without_replacing_job_or_repeating_scan(self):
        live = self.configured(); request = dict(action='wallpaperScan', folder=str(self.root))
        self.assertEqual(live.handle(request), self.result(pending=True)); owner = live.feature_jobs['wallpaperScan']
        self.assertEqual(live.handle(request), self.result(False, 'This operation is already running', 2))
        self.assertIs(live.feature_jobs['wallpaperScan'], owner)
        self.assertEqual(len(live.feature_executor.jobs), 1)
        live.feature_executor.complete(); live.finish_features()
        self.assertEqual(live.last_result, self.result(message='Wallpaper library refreshed', sequence=3))
        self.assertFalse(live.feature_jobs)

    def test_caught_errors_preserve_old_library_truncate_result_and_clear_owner(self):
        for settings in (False, True):
            for error in (ValueError('bad folder'), OSError('x'*450), backend.CommandError('scanner unavailable')):
                with self.subTest(settings=settings, error=type(error).__name__):
                    live = self.configured(settings=settings)
                    original = dict(entries=[{'old': True}], folder='/old', truncated=True, error='old error')
                    live.wallpaper_library = copy.deepcopy(original)
                    with patch.object(backend, 'wallpaper_library', side_effect=error) as scan:
                        self.assertEqual(live.handle(dict(action='wallpaperScan', folder='/requested')), self.result(pending=True))
                        scan.assert_not_called(); live.feature_executor.complete()
                        self.assertEqual(live.snapshot()['lastResult'], self.result(pending=True))
                        done = live.snapshot()
                    self.assertEqual(done['lastResult'], self.result(False, str(error)[:400], 2))
                    self.assertEqual(done['wallpaperLibrary'], {**original, 'error': str(error)[:400]})
                    self.assertFalse(live.feature_jobs); scan.assert_called_once_with('/requested')

    def test_missing_folder_is_a_deferred_error_not_a_changed_admission_rule(self):
        live = self.configured(settings=True)
        self.assertEqual(live.handle(dict(action='wallpaperScan')), self.result(pending=True))
        live.feature_executor.complete(); live.finish_features()
        self.assertEqual(live.last_result, self.result(False, 'Choose a wallpaper folder first', 2))
        self.assertFalse(live.feature_jobs)

    def test_multiple_completions_preserve_insertion_order_and_sequence(self):
        live = self.configured(); future = Future(); future.set_result({'fixture': 'files'})
        live.feature_jobs['fileSearch'] = future
        live.handle(dict(action='wallpaperScan', folder=str(self.root))); live.feature_executor.complete()
        self.assertEqual(live.snapshot()['lastResult'], self.result(pending=True))
        self.assertEqual(live.snapshot()['lastResult'], dict(action='fileSearch', ok=True, message='File search completed', sequence=2))
        self.assertEqual(set(live.feature_jobs), {'wallpaperScan'})
        self.assertEqual(live.snapshot()['lastResult'], self.result(message='Wallpaper library refreshed', sequence=3))
        self.assertFalse(live.feature_jobs)

    def test_demo_ignores_user_folder_scans_bundled_only_and_never_queues_or_spawns(self):
        bundled = str(Path(backend.__file__).resolve().parents[1]/'assets/wallpapers')
        for settings in (False, True):
            live = self.configured(demo=True, settings=settings)
            value = dict(entries=[], folder=bundled, truncated=False, error='')
            with patch.object(backend, 'wallpaper_library', return_value=value) as scan, \
                 patch('subprocess.Popen', side_effect=AssertionError('demo spawn')), \
                 patch('os.replace', side_effect=AssertionError('demo write')):
                self.assertEqual(live.handle(dict(action='wallpaperScan', folder='/private/requested')),
                                 self.result(message='Demo preview: no system command executed'))
            scan.assert_called_once_with(bundled)
            self.assertEqual(live.snapshot()['wallpaperLibrary'], value)
            self.assertFalse(live.feature_jobs); self.assertFalse(live.feature_executor.jobs)
            self.assertEqual(live.runner.calls, []); self.assertFalse(self.preferences.path.exists())

    def test_direct_facades_keep_worker_scheduling_and_demo_none_return(self):
        live = self.configured()
        self.assertEqual(live.perform('wallpaperScan', {'folder': str(self.root)}), 'Working…')
        self.assertIn('wallpaperScan', live.feature_jobs)
        live.feature_executor.complete(); live.finish_features()
        demo = self.configured(demo=True)
        with patch.object(backend, 'wallpaper_library', return_value={}):
            self.assertIsNone(demo.perform_demo('wallpaperScan', {'folder': '/ignored'}))
        self.assertFalse(demo.feature_jobs)

    def test_shutdown_cancels_queued_scan_without_scanning_or_final_publication(self):
        live = self.configured(settings=True, manual=False); live.runner.close = Mock()
        gate = Event(); started = [Event(), Event()]
        self.addCleanup(gate.set)
        def occupy(ready): ready.set(); gate.wait(5)
        running = [live.feature_executor.submit(occupy, ready) for ready in started]
        for ready in started: self.assertTrue(ready.wait(2))
        read_fd, write_fd = os.pipe()
        with os.fdopen(read_fd, 'r') as source:
            os.write(write_fd, (json.dumps(dict(action='wallpaperScan', folder=str(self.root)))+'\n').encode())
            os.close(write_fd); frames = []
            with patch.object(backend, 'DesktopBackend', return_value=live), \
                 patch.object(backend.sys, 'stdin', source), patch.object(backend.signal, 'signal'), \
                 patch.object(backend, 'emit', side_effect=lambda b: frames.append(copy.deepcopy(b.snapshot()))), \
                 patch.object(backend, 'wallpaper_library', side_effect=AssertionError('cancelled scan executed')) as scan:
                self.assertEqual(backend.main(['--settings']), 0)
            self.assertEqual([frame['lastResult']['action'] for frame in frames], ['ready', 'wallpaperScan'])
            self.assertEqual(frames[-1]['lastResult'], self.result(pending=True))
            self.assertTrue(live.feature_jobs['wallpaperScan'].cancelled()); scan.assert_not_called()
            self.assertTrue(all(f.running() for f in running)); self.assertFalse(self.preferences.path.exists())
        gate.set()

    def test_running_scan_is_not_cancelled_and_manual_cancelled_finish_policy_is_unchanged(self):
        live = self.configured(manual=False); gate = Event(); ready = Event()
        self.addCleanup(gate.set)
        def scan(folder): ready.set(); gate.wait(5); return {'fixture': folder}
        with patch.object(backend, 'wallpaper_library', side_effect=scan):
            live.handle(dict(action='wallpaperScan', folder='/fixture')); self.assertTrue(ready.wait(2))
            future = live.feature_jobs['wallpaperScan']
            live.feature_executor.shutdown(wait=False, cancel_futures=True)
            self.assertFalse(future.cancelled()); gate.set()
            self.assertEqual(future.result(timeout=2), {'fixture': '/fixture'})
        other = self.configured(); other.handle(dict(action='wallpaperScan', folder='/cancelled'))
        cancelled = other.feature_jobs['wallpaperScan']; self.assertTrue(cancelled.cancel())
        with self.assertRaises(CancelledError): other.finish_features()
        self.assertIs(other.feature_jobs['wallpaperScan'], cancelled)
