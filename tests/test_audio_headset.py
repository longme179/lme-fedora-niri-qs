"""W1 characterization: retain existing control/context/persistence contracts."""
import copy
import unittest

from test_backend import Fixture, FakeRunner


class AudioBaselineCase(Fixture, unittest.TestCase):
    def live(self, **kwargs):
        runner = FakeRunner(available={'wpctl', 'brightnessctl'})
        live = self.make_backend(runner, **kwargs)
        self.addCleanup(live.charge_executor.shutdown)
        self.addCleanup(live.feature_executor.shutdown)
        return live, runner

    def test_startup_does_not_query_audio_inventory_or_start_an_audio_helper(self):
        for demo in (False, True):
            with self.subTest(demo=demo):
                live, runner = self.live(demo=demo)
                self.assertFalse(any(call[0] in {'pactl', 'pw-dump'} for call in runner.calls))
                self.assertEqual(runner.spawns, [])
                self.assertEqual(live.feature_jobs, {})

    def test_existing_output_microphone_and_backlight_commands_preserve_preferences(self):
        live, runner = self.live()
        before = copy.deepcopy(self.preferences.values)
        for action, request, command in [
            ('volume', {'value': 35}, ('wpctl', 'set-volume', '--limit', '1.0', '@DEFAULT_AUDIO_SINK@', '35%')),
            ('mute', {}, ('wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', 'toggle')),
            ('micVolume', {'value': 42}, ('wpctl', 'set-volume', '--limit', '1.0', '@DEFAULT_AUDIO_SOURCE@', '42%')),
            ('micMute', {}, ('wpctl', 'set-mute', '@DEFAULT_AUDIO_SOURCE@', 'toggle')),
            ('brightness', {'value': 70}, ('brightnessctl', '--class=backlight', 'set', '70%')),
        ]:
            with self.subTest(action=action):
                self.assertTrue(live.handle(dict(action=action, **request))['ok'])
                self.assertEqual(runner.calls[-1], command)
        self.assertEqual(self.preferences.values, before)
        self.assertFalse(self.preferences.path.exists())

    def test_settings_admission_precedes_demo_or_hardware_execution(self):
        for demo in (False, True):
            live, runner = self.live(demo=demo); live.settings_only = True
            result = live.handle({'action': 'volume', 'value': 35})
            self.assertEqual(result, dict(ok=False, action='volume', sequence=1,
                message='This action is unavailable in the settings app'))
            self.assertEqual(runner.calls, []); self.assertEqual(runner.spawns, [])

    def test_demo_changes_only_its_in_memory_audio_and_invalid_live_input_recovers(self):
        demo, runner = self.live(demo=True)
        self.assertTrue(demo.handle({'action': 'volume', 'value': 55})['ok'])
        self.assertEqual(demo.demo_snapshot()['system']['audio']['volume'], 55)
        self.assertEqual(runner.calls, []); self.assertEqual(runner.spawns, [])
        live, runner = self.live()
        result = live.handle({'action': 'micVolume', 'value': 101})
        self.assertFalse(result['ok']); self.assertEqual(runner.calls, [])
        self.assertTrue(live.handle({'action': 'mute'})['ok'])
        self.assertFalse(self.preferences.path.exists())
