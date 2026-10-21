"""Freeze Launchpad's dispatch boundary before moving its single synchronous action."""
from concurrent.futures import Future
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from test_backend import Fixture, backend

REGISTRY = importlib.util.find_spec('backend_actions') is not None
DEMO_MESSAGE = 'Demo preview: no system command executed'
CONTEXT_MESSAGE = 'This action is unavailable in the settings app'


class LaunchpadDispatchCase(Fixture, unittest.TestCase):
    def entry(self, **changes):
        return dict(name='Saved task', command='/bin/echo "a b"', kind='command',
                    terminal=False, cwd=str(self.root), **changes)

    def configured(self, demo=False, settings=False):
        self.preferences.values.update(launchpadEnabled=True, launchpadEntries={'saved': self.entry()}, terminal='kitty')
        live = self.make_backend(demo=demo)
        live.settings_only = settings
        self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.feature_executor.shutdown)
        return live

    def result(self, action, ok, message, sequence):
        return dict(action=action, ok=ok, message=message, sequence=sequence)

    def test_shell_settings_live_demo_and_terminal_modes_keep_messages_argv_and_jobs(self):
        for demo in (False, True):
            for settings in (False, True):
                for mode in (None, 'background', 'terminal'):
                    with self.subTest(demo=demo, settings=settings, mode=mode):
                        live = self.configured(demo, settings)
                        process = Mock(); process.poll.return_value = None
                        with patch.dict(os.environ, XDG_STATE_HOME=str(self.root/'state')), \
                             patch('launchpad.shutil.which', side_effect=lambda name: '/usr/bin/kitty' if name == 'kitty' else name), \
                             patch('launchpad.time.time', return_value=123), \
                             patch('launchpad.subprocess.Popen', return_value=process) as spawn:
                            reply = live.handle(dict(action='launchpadRun', id='saved', mode=mode))
                            if demo:
                                self.assertEqual(reply, self.result('launchpadRun', True, DEMO_MESSAGE, 1))
                                spawn.assert_not_called()
                                self.assertNotIn('launchpadJobs', live.snapshot())
                                self.assertEqual(live.feature_snapshot()['launchpadJobs'], {})
                                continue
                            log = self.root/'state/lme-shell/launchpad/saved.log'
                            message = 'Launched Saved task' + (' in terminal' if mode == 'terminal' else ' · log: '+str(log))
                            self.assertEqual(reply, self.result('launchpadRun', True, message, 1))
                            args, kwargs = spawn.call_args
                            expected = ['/bin/echo', 'a b']
                            if mode == 'terminal':
                                expected = ['/usr/bin/kitty', '-e', '/bin/bash', '-c',
                                    '"$@"; code=$?; printf "\\nExit status: %s\\n" "$code"; read -r -p "Press Enter to close…"; exit "$code"', 'launchpad', *expected]
                            self.assertEqual(args, (expected,))
                            self.assertEqual(kwargs, dict(cwd=self.root, stdin=backend.subprocess.DEVNULL,
                                stdout=kwargs['stdout'], stderr=kwargs['stdout'], start_new_session=True))
                            self.assertEqual(log.stat().st_mode & 0o777, 0o600)
                            self.assertEqual(live.feature_snapshot()['launchpadJobs'], {'saved': dict(
                                running=True, exitCode=None, started=123, log=str(log), terminal=mode == 'terminal')})
                            process.poll.return_value = 7
                            self.assertEqual(live.feature_snapshot()['launchpadJobs']['saved']['exitCode'], 7)

    def test_invalid_id_mode_disabled_live_and_permissive_demo_exact_sequence(self):
        for demo in (False, True):
            for settings in (False, True):
                with self.subTest(demo=demo, settings=settings):
                    live = self.configured(demo, settings)
                    requests = [dict(id='missing'), dict(id='saved', mode='wrong')]
                    errors = ['This Launchpad command no longer exists', 'Choose background or terminal']
                    with patch('launchpad.subprocess.Popen') as spawn:
                        for sequence, (payload, error) in enumerate(zip(requests, errors), 1):
                            self.assertEqual(live.handle(dict(action='launchpadRun', **payload)),
                                self.result('launchpadRun', demo, DEMO_MESSAGE if demo else error, sequence))
                        self.preferences.values['launchpadEnabled'] = False
                        self.assertEqual(live.handle(dict(action='launchpadRun', id='saved')),
                            self.result('launchpadRun', demo, DEMO_MESSAGE if demo else 'Launchpad is disabled', 3))
                        spawn.assert_not_called()

    def test_demo_has_zero_processes_and_zero_disk_writes_even_with_bad_payloads(self):
        for settings in (False, True):
            live = self.configured(demo=True, settings=settings)
            before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
            with patch('subprocess.Popen', side_effect=AssertionError('demo spawned')), \
                 patch('os.open', side_effect=AssertionError('demo opened a writable fd')), \
                 patch('os.mkdir', side_effect=AssertionError('demo mkdir')), \
                 patch('os.replace', side_effect=AssertionError('demo replace')), \
                 patch('io.open', side_effect=AssertionError('demo file IO')):
                for sequence, payload in enumerate(({}, {'id': []}, {'id': 'saved', 'mode': {} }), 1):
                    self.assertEqual(live.handle(dict(action='launchpadRun', **payload)),
                        self.result('launchpadRun', True, DEMO_MESSAGE, sequence))
                    self.assertTrue(hasattr(live, '_demo_state'))
            self.assertEqual(live.runner.calls, [])
            self.assertEqual(live.runner.spawns, [])
            self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_current_preferences_are_read_on_each_run_and_errors_are_truncated_once(self):
        live = self.configured()
        current = dict(self.preferences.values, terminal='foot', launchpadEntries={'new': self.entry()})
        self.preferences.values = current
        # Observe the controller via a real missing ID, rather than replacing provider capabilities.
        self.assertEqual(live.handle(dict(action='launchpadRun', id='saved')),
                         self.result('launchpadRun', False, 'This Launchpad command no longer exists', 1))
        with patch('launchpad.entries', side_effect=ValueError('x'*450)):
            self.assertEqual(live.handle(dict(action='launchpadRun', id='new')),
                             self.result('launchpadRun', False, 'x'*400, 2))

    def test_unknown_ids_and_unregistered_prefixes_keep_live_and_demo_legacy_routes(self):
        for demo in (False, True):
            for settings in (False, True):
                live = self.configured(demo, settings)
                for sequence, action in enumerate(('notAnAction', 'launchpadRunExtra', 'gowallUnknown'), 1):
                    permitted = demo and not settings and action == 'gowallUnknown'
                    error = CONTEXT_MESSAGE if settings else 'Unknown action: '+action
                    self.assertEqual(live.handle(dict(action=action)),
                        self.result(action, permitted, DEMO_MESSAGE if permitted else error, sequence))
                if settings:
                    self.assertEqual(live.handle(dict(action='volume', value=20)),
                                     self.result('volume', False, CONTEXT_MESSAGE, 4))

    def test_ack_precedes_each_completed_background_job_and_snapshot_shape_is_stable(self):
        live = self.configured()
        futures = []
        for name in ('fileSearch', 'wallpaperScan'):
            future = Future(); future.set_result({'fixture': name}); futures.append(future)
            live.feature_jobs[name] = future
        reply = live.handle(dict(action='launchpadRun', id='missing'))
        self.assertEqual(reply, self.result('launchpadRun', False, 'This Launchpad command no longer exists', 1))
        first = live.snapshot()
        self.assertEqual(first['lastResult'], reply)
        self.assertEqual(set(live.feature_jobs), {'fileSearch', 'wallpaperScan'})
        self.assertEqual(live.snapshot()['lastResult'], self.result('fileSearch', True, 'File search completed', 2))
        self.assertEqual(live.snapshot()['lastResult'], self.result('wallpaperScan', True, 'Wallpaper library refreshed', 3))
        self.assertEqual(list(live.feature_snapshot()), ['batterySaver', 'imageUtilities', 'launchpadJobs',
            'preferences', 'lastResult', 'launcherUsage', 'launcherHistoryError', 'mirror', 'recorder', 'fileSearch',
            'palettePreview', 'wallpaperLibrary', 'wallpaperTransitions', 'wallpaperDaemon', 'displays', 'idle',
            'keybinds', 'platform', 'nightLight', 'capture'])

    def test_job_limit_remains_per_controller_and_duplicate_job_message_is_unchanged(self):
        live = self.configured()
        self.preferences.values['launchpadEntries'] = {str(i): self.entry() for i in range(9)}
        process = Mock(); process.poll.return_value = None
        with patch.dict(os.environ, XDG_STATE_HOME=str(self.root/'state')), \
             patch('launchpad.shutil.which', side_effect=lambda name: name), \
             patch('launchpad.subprocess.Popen', return_value=process) as spawn:
            for i in range(8): self.assertTrue(live.handle(dict(action='launchpadRun', id=str(i)))['ok'])
            self.assertEqual(live.handle(dict(action='launchpadRun', id='0')),
                             self.result('launchpadRun', False, 'This command is already running', 9))
            self.assertEqual(live.handle(dict(action='launchpadRun', id='8')),
                             self.result('launchpadRun', False, 'Up to eight Launchpad commands can run at once', 10))
            other = self.make_backend()
            self.addCleanup(other.charge_executor.shutdown); self.addCleanup(other.feature_executor.shutdown)
            self.assertTrue(other.handle(dict(action='launchpadRun', id='8'))['ok'])
            self.assertEqual(spawn.call_count, 9)


@unittest.skipUnless(REGISTRY, 'M6 registry absent on unmodified main; registry-specific contract N/A')
class RegistryContractCase(unittest.TestCase):
    def test_duplicate_ownership_is_rejected_without_executing_registration(self):
        from backend_actions import ActionRegistry, ActionSpec
        operation = Mock()
        spec = ActionSpec('launchpadRun', {'shell', 'settings'}, operation, operation)
        registry = ActionRegistry([spec])
        with self.assertRaisesRegex(ValueError, 'Duplicate action owner: launchpadRun'):
            registry.register([spec])
        operation.assert_not_called()

    def test_context_is_rejected_before_live_or_demo_selection(self):
        from backend_actions import ActionRegistry, ActionSpec
        operation = Mock()
        registry = ActionRegistry([ActionSpec('private', {'shell'}, operation, operation)])
        for demo in (False, True):
            with self.assertRaisesRegex(ValueError, '^'+CONTEXT_MESSAGE+'$'):
                registry.dispatch('private', {}, context='settings', demo=demo)
        operation.assert_not_called()

    def test_registered_errors_propagate_without_trying_another_handler(self):
        from backend_actions import ActionRegistry, ActionSpec
        live = Mock(side_effect=ValueError('provider failed')); demo = Mock()
        registry = ActionRegistry([ActionSpec('launchpadRun', {'shell'}, live, demo)])
        with self.assertRaisesRegex(ValueError, '^provider failed$'):
            registry.dispatch('launchpadRun', {}, context='shell', demo=False)
        live.assert_called_once_with({}); demo.assert_not_called()

    def test_provider_registration_is_inert_and_projection_is_lazy(self):
        from launchpad_actions import LaunchpadCapabilities, provide
        from backend_actions import ActionRegistry
        values = Mock(); run = Mock(); snapshot = Mock(return_value={'saved': {'running': False}})
        specs, project = provide(LaunchpadCapabilities(values, run, snapshot))
        registry = ActionRegistry(specs)
        values.assert_not_called(); run.assert_not_called(); snapshot.assert_not_called()
        self.assertEqual(project(), {'launchpadJobs': {'saved': {'running': False}}})
        self.assertIsNotNone(registry.get('launchpadRun'))
        self.assertIsNone(registry.get('launchpadRunExtra'))
