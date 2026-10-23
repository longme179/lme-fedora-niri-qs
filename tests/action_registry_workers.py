"""Worker registration contracts are N/A before the single M7b pilot exists."""
import importlib.util
from unittest.mock import Mock, patch
import unittest
from backend_actions import ActionRegistry, ActionSpec
from test_backend import Fixture

WORKERS = importlib.util.find_spec('wallpaper_actions') is not None


@unittest.skipUnless(WORKERS, 'M7b worker registry absent on baseline; worker-specific contract N/A')
class WorkerRegistryCase(Fixture, unittest.TestCase):
    def test_duplicate_and_incomplete_worker_ownership_reject_atomically_without_execution(self):
        work = Mock(); complete = Mock(); queue = Mock()
        spec = ActionSpec('wallpaperScan', {'shell', 'settings'}, work, work, execution='worker', complete=complete)
        registry = ActionRegistry([spec], start_feature=queue)
        with self.assertRaisesRegex(ValueError, 'Duplicate action owner: wallpaperScan'): registry.register([spec])
        with self.assertRaisesRegex(ValueError, 'Only synchronous actions are supported'):
            registry.register([ActionSpec('missingComplete', {'shell'}, work, work, execution='worker')])
        self.assertIsNone(registry.get('missingComplete'))
        work.assert_not_called(); complete.assert_not_called(); queue.assert_not_called()

    def test_context_precedes_delegation_and_demo_never_queues(self):
        work = Mock(); demo = Mock(); complete = Mock(); queue = Mock(return_value='Working…')
        spec = ActionSpec('wallpaperScan', {'shell'}, work, demo, execution='worker', complete=complete)
        registry = ActionRegistry([spec], start_feature=queue)
        for preview in (False, True):
            with self.assertRaisesRegex(ValueError, 'This action is unavailable in the settings app'):
                registry.dispatch('wallpaperScan', {}, context='settings', demo=preview)
        work.assert_not_called(); demo.assert_not_called(); queue.assert_not_called()
        registry.dispatch('wallpaperScan', {'folder': '/ignored'}, context='shell', demo=True)
        demo.assert_called_once_with({'folder': '/ignored'}); queue.assert_not_called()
        self.assertEqual(registry.dispatch('wallpaperScan', {'folder': '/fixture'}, context='shell', demo=False), 'Working…')
        name, operation = queue.call_args.args
        self.assertEqual(name, 'wallpaperScan'); work.assert_not_called()
        operation(); work.assert_called_once_with({'folder': '/fixture'}); complete.assert_not_called()

    def test_registered_start_and_completion_errors_never_fall_back(self):
        live = self.make_backend()
        self.addCleanup(live.charge_executor.shutdown); self.addCleanup(live.feature_executor.shutdown)
        with patch.object(live, 'start_feature', side_effect=ValueError('start failed')) as start, \
             patch.object(live, 'perform', side_effect=AssertionError('legacy start fallback')):
            result = live.handle(dict(action='wallpaperScan', folder='/ignored'))
        self.assertEqual(result, dict(ok=False, action='wallpaperScan', message='start failed', sequence=1))
        start.assert_called_once()
        self.assertFalse(live.feature_jobs)
        # The existing executor owns completion; a worker failure does not invoke the demo handler.
        with patch.object(live, 'perform_demo', side_effect=AssertionError('legacy demo fallback')):
            live.demo = True
            self.assertTrue(live.handle(dict(action='wallpaperScan'))['ok'])

    def test_completion_callback_only_installs_state_and_legacy_async_ids_stay_legacy(self):
        from wallpaper_actions import WallpaperScanCapabilities, provide
        scan = Mock(); current = Mock(return_value={'entries': ['old']}); install = Mock()
        specs, project = provide(WallpaperScanCapabilities(scan, current, install))
        spec, = specs
        scan.assert_not_called(); current.assert_not_called(); install.assert_not_called()
        self.assertEqual(project(), {})
        self.assertEqual(spec.execution, 'worker'); self.assertTrue(callable(spec.complete))
        value = {'entries': ['new']}; self.assertIsNone(spec.complete(value)); install.assert_called_once_with(value)
        install.reset_mock(); error = ValueError('failed')
        self.assertIsNone(spec.complete(error)); install.assert_called_once_with({'entries': ['old'], 'error': 'failed'})
        live = self.make_backend()
        self.addCleanup(live.charge_executor.shutdown); self.addCleanup(live.feature_executor.shutdown)
        for demo in (False, True):
            live.demo = demo
            for action in ('wallpaperNext', 'wallpaperUnknown'):
                target = 'perform_demo' if demo else 'perform'
                with patch.object(live, target, return_value='legacy') as legacy:
                    self.assertTrue(live.handle(dict(action=action))['ok'])
                legacy.assert_called_once_with(action, {'action': action})
