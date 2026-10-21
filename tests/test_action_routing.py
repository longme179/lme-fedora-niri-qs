"""Registry-only contracts; N/A until the M6 infrastructure exists."""
import importlib.util
import unittest
from unittest.mock import Mock, patch

from test_backend import Fixture, backend


@unittest.skipUnless(importlib.util.find_spec('backend_actions'), 'M6 registry absent; registry-only routing N/A')
class RegisteredRoutingCase(Fixture, unittest.TestCase):
    def test_explicit_provider_list_registers_without_reading_preferences_or_projecting_state(self):
        from backend_actions import ActionRegistry
        from launchpad_actions import LaunchpadCapabilities, provide
        read = Mock(); run = Mock(); snapshot = Mock(return_value={})
        registry = ActionRegistry()
        project = registry.provide([(provide, LaunchpadCapabilities(read, run, snapshot))])
        read.assert_not_called(); run.assert_not_called(); snapshot.assert_not_called()
        self.assertIsNotNone(registry.get('launchpadRun'))
        self.assertEqual(project(), {'launchpadJobs': {}})

    def test_host_does_not_try_either_legacy_tree_after_registered_errors(self):
        from backend_actions import ActionRegistry, ActionSpec
        for demo in (False, True):
            for settings in (False, True):
                live = self.make_backend(demo=demo); live.settings_only = settings
                self.addCleanup(live.charge_executor.shutdown); self.addCleanup(live.feature_executor.shutdown)
                operation = Mock(side_effect=ValueError('provider failure'))
                live.actions = ActionRegistry([ActionSpec('launchpadRun', {'shell', 'settings'}, operation, operation)])
                with patch.object(live, 'perform') as legacy, patch.object(live, 'perform_demo') as legacy_demo:
                    self.assertEqual(live.handle({'action': 'launchpadRun'}),
                        dict(ok=False, action='launchpadRun', message='provider failure', sequence=1))
                operation.assert_called_once_with({'action': 'launchpadRun'})
                legacy.assert_not_called(); legacy_demo.assert_not_called()

    def test_host_rejects_context_before_even_initializing_the_demo_snapshot(self):
        from backend_actions import ActionRegistry, ActionSpec
        for demo in (False, True):
            live = self.make_backend(demo=demo); live.settings_only = True
            self.addCleanup(live.charge_executor.shutdown); self.addCleanup(live.feature_executor.shutdown)
            operation = Mock()
            live.actions = ActionRegistry([ActionSpec('launchpadRun', {'shell'}, operation, operation)])
            with patch.object(live, 'demo_snapshot') as snapshot:
                self.assertEqual(live.handle({'action': 'launchpadRun', 'context': 'shell', 'demo': False}),
                    dict(ok=False, action='launchpadRun', message='This action is unavailable in the settings app', sequence=1))
            operation.assert_not_called(); snapshot.assert_not_called()

    def test_registration_batch_is_atomic_and_worker_execution_is_not_implemented(self):
        from backend_actions import ActionRegistry, ActionSpec
        operation = Mock()
        first = ActionSpec('first', {'shell'}, operation, operation)
        registry = ActionRegistry([first])
        with self.assertRaisesRegex(ValueError, 'Duplicate action owner: first'):
            registry.register([ActionSpec('second', {'shell'}, operation, operation), first])
        self.assertIsNone(registry.get('second'))
        with self.assertRaisesRegex(ValueError, 'Only synchronous actions are supported'):
            registry.register([ActionSpec('worker', {'shell'}, operation, operation, execution='worker')])
        self.assertIsNone(registry.get('worker')); operation.assert_not_called()

    def test_provider_reads_the_current_preference_values_and_passes_only_existing_run_arguments(self):
        from backend_actions import ActionRegistry
        from launchpad_actions import LaunchpadCapabilities, provide
        current = dict(launchpadEnabled=True, launchpadEntries={'old': {}}, terminal='kitty')
        read = Mock(side_effect=lambda: current); run = Mock(return_value='Launched')
        specs, project = provide(LaunchpadCapabilities(read, run, Mock(return_value={})))
        registry = ActionRegistry(specs)
        current = dict(launchpadEnabled=True, launchpadEntries={'new': {}}, terminal='foot')
        request = dict(id='new', mode='terminal')
        self.assertEqual(registry.dispatch('launchpadRun', request, context='shell', demo=False), 'Launched')
        run.assert_called_once_with('new', {'new': {}}, 'foot', 'terminal')
        read.assert_called_once_with()
        current['launchpadEnabled'] = False
        self.assertIsNone(registry.dispatch('launchpadRun', request, context='settings', demo=True))
        self.assertEqual(read.call_count, 1)
        self.assertEqual(project(), {'launchpadJobs': {}})
