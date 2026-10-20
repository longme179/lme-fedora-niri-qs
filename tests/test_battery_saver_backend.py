"""Exercise the public saver action using fake hardware and real restore journals."""
import json
import fcntl
import threading
import time
import unittest
from unittest.mock import patch

from test_backend import Fixture, FakeRunner, backend
from test_features import ManualExecutor
from settings_transfer import document


class SaverHardware(FakeRunner):
    def __init__(self, root):
        super().__init__(available=("niri", "brightnessctl", "powerprofilesctl"))
        self.root = root
        self.profile = "performance"
        self.outputs = {"eDP-1": {"current_mode": 0,
            "modes": [{"width": 1920, "height": 1080, "refresh_rate": rate} for rate in (120000, 60000)],
            "logical": {"scale": 1.25, "x": 0, "y": 30}}}

    def run(self, name, *args, **kwargs):
        super().run(name, *args, **kwargs)
        if name == "niri" and args == ("msg", "--json", "outputs"):
            return json.dumps(self.outputs)
        if name == "niri" and args[:2] == ("msg", "output"):
            output, operation = self.outputs[args[2]], args[3]
            if operation == "mode":
                output["current_mode"] = next(index for index, mode in enumerate(output["modes"])
                    if args[4] == f'{mode["width"]}x{mode["height"]}@{mode["refresh_rate"] / 1000:.3f}')
            return ""
        if name == "powerprofilesctl":
            if args == ("get",): return self.profile
            if args == ("list",): return "power-saver:\nbalanced:\nperformance:\n"
            if args[0] == "set": self.profile = args[1]
        if name == "brightnessctl" and args[:3] == ("--class=backlight", "--device", "amdgpu_bl1"):
            (self.root / "sys/class/backlight/amdgpu_bl1/brightness").write_text(args[4])
        return ""


class BatterySaverBackendCase(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.put("sys/class/backlight/amdgpu_bl1/brightness", "837")
        self.put("sys/class/backlight/amdgpu_bl1/max_brightness", "1001")
        self.hardware = SaverHardware(self.root)
        self.live = self.make_backend(self.hardware)
        self.configure(self.live)

    def configure(self, live):
        self.addCleanup(live.feature_executor.shutdown, wait=True)
        self.addCleanup(live.charge_executor.shutdown, wait=True)
        live.display_control.directory = self.root / "runtime"
        live.display_control.path = live.display_control.directory / "display-preview.json"
        live.recording = lambda: {"active": False}
        return live

    def complete(self, live, enabled):
        reply = live.handle({"action": "batterySaver", "enabled": enabled})
        self.assertTrue(reply["ok"], reply)
        self.assertTrue(reply.get("pending"), reply)
        job = live.feature_jobs["batterySaver"]
        try:
            job.result(timeout=3)
        except (ValueError, OSError):
            pass
        live.finish_features()
        self.assertNotIn("batterySaver", live.feature_jobs)
        return live.last_result

    def manual_executor(self):
        self.live.feature_executor.shutdown(wait=True)
        self.live.feature_executor = ManualExecutor()
        return self.live.feature_executor

    def test_action_round_trip_preserves_preferences_exports_and_invalidates_readbacks(self):
        self.preferences.update({"surfaceStyle": "liquid", "animations": True, "opacity": .83,
            "popupBlur": True, "barBlur": True, "batterySaverBrightness": 60})
        saved = self.preferences.path.read_bytes()
        portable = document(self.preferences.values, "preset")
        self.live.power_cache = {"powerProfile": "performance"}
        self.live.system_cache = {"brightness": {"percent": 84}}
        result = self.complete(self.live, True)
        self.assertTrue(result["ok"], result)
        self.assertTrue(self.live.saver_snapshot()["active"])
        self.assertIsNone(self.live.power_cache)
        self.assertIsNone(self.live.system_cache)
        self.assertEqual(self.hardware.profile, "power-saver")
        self.assertEqual(self.live.brightness(raw=True)["current"], 600)
        self.assertEqual(self.hardware.outputs["eDP-1"]["current_mode"], 1)
        self.assertTrue(self.live.handle({"action": "brightness", "value": 90})["ok"])
        self.assertTrue(self.complete(self.live, False)["ok"])
        self.assertEqual(self.live.brightness(raw=True)["current"], 837)
        self.assertEqual(self.hardware.profile, "performance")
        self.assertEqual(self.hardware.outputs["eDP-1"]["current_mode"], 0)
        self.assertEqual(self.preferences.path.read_bytes(), saved)
        self.assertEqual(document(self.preferences.values, "preset"), portable)
        self.assertNotIn("batterySaver", portable["settings"])

    def test_settings_backend_observes_and_restores_shared_journal_after_main_backend_restart(self):
        self.assertTrue(self.complete(self.live, True)["ok"])
        settings = self.configure(backend.DesktopBackend(runner=self.hardware,
            preferences=backend.Preferences(self.preferences.path), apps=backend.Applications([]),
            proc=self.root / "proc", sysfs=self.root / "sys", settings_only=True, weather_fetch=False))
        self.assertTrue(settings.snapshot()["batterySaver"]["active"])
        before = self.live.battery_saver.path.read_bytes()
        self.assertTrue(self.complete(settings, True)["ok"])
        self.assertEqual(self.live.battery_saver.path.read_bytes(), before)
        self.assertTrue(self.complete(settings, False)["ok"])
        self.assertFalse(self.live.saver_snapshot()["active"])
        self.assertEqual(self.live.brightness(raw=True)["current"], 837)
        self.assertEqual(self.hardware.profile, "performance")

    def test_lenovo_driver_timings_switch_to_60003_mhz_and_restore_120002_mhz(self):
        output = self.hardware.outputs['eDP-1']
        output['modes'] = [dict(width=1920, height=1080, refresh_rate=rate) for rate in (120002, 60003)]
        output['modes'] += [dict(width=width, height=height, refresh_rate=120002)
                            for width, height in ((1680, 1050), (1280, 1024), (1280, 720), (640, 480))]
        output['logical'].update(scale=1.0, x=1280, y=0)
        self.assertTrue(self.complete(self.live, True)['ok'])
        self.assertEqual(output['current_mode'], 1)
        self.assertIn(('niri', 'msg', 'output', 'eDP-1', 'mode', '1920x1080@60.003'), self.hardware.calls)
        self.assertEqual(self.live.displays['outputs'][0]['current']['refresh'], 60003)
        self.assertTrue(self.complete(self.live, False)['ok'])
        self.assertEqual(output['current_mode'], 0)
        self.assertIn(('niri', 'msg', 'output', 'eDP-1', 'mode', '1920x1080@120.002'), self.hardware.calls)
        self.assertEqual(output['logical'], {'scale': 1.0, 'x': 1280, 'y': 0})

    def test_ignored_mode_changes_report_an_action_error_and_keep_the_original(self):
        original = self.hardware.run
        def ignore(name, *args, **kwargs):
            if name == 'niri' and args[:2] == ('msg', 'output'):
                self.hardware.calls.append((name, *args))
                return 'Output was found; settings applied'
            return original(name, *args, **kwargs)
        with patch.object(self.hardware, 'run', side_effect=ignore):
            reply = self.complete(self.live, True)
        self.assertFalse(reply['ok'])
        self.assertIn('did not confirm', reply['message'])
        self.assertTrue(self.live.saver_snapshot()['active'])
        saved = json.loads(self.live.battery_saver.path.read_text())
        self.assertEqual(saved['original']['displays'][0]['refresh'], 120000)
        self.assertEqual(saved['pending']['displays'], ['eDP-1'])
        self.assertTrue(self.complete(self.live, False)['ok'])

    def test_unsupported_panels_report_limitations_without_forcing_a_custom_mode(self):
        self.hardware.outputs['eDP-1']['modes'] = self.hardware.outputs['eDP-1']['modes'][:1]
        reply = self.complete(self.live, True)
        self.assertTrue(reply['ok'])
        self.assertIn('limitations', reply['message'])
        self.assertTrue(self.live.saver_snapshot()['warnings'])
        self.assertFalse(any(call[:3] == ('niri', 'msg', 'output') for call in self.hardware.calls))
        self.assertTrue(self.complete(self.live, False)['ok'])

    def test_startup_restore_keeps_saver_modes_and_respects_a_transition_lock(self):
        self.preferences.set('displayLayout', [{'name': 'eDP-1', 'width': 1920, 'height': 1080,
            'refresh': 120000, 'scale': 1.25, 'x': 0, 'y': 30}])
        self.assertTrue(self.complete(self.live, True)['ok'])
        saved = self.live.battery_saver.path.read_bytes()
        self.hardware.calls.clear()
        with patch.object(backend, 'DesktopBackend', return_value=self.live):
            self.assertEqual(backend.main(['--restore-displays']), 0)
        self.assertEqual(self.hardware.calls, [])
        self.assertEqual(self.hardware.outputs['eDP-1']['current_mode'], 1)
        self.assertEqual(self.live.battery_saver.path.read_bytes(), saved)
        self.assertTrue(self.complete(self.live, False)['ok'])
        self.hardware.calls.clear()
        with self.live.battery_saver.guard(), patch.object(backend, 'DesktopBackend', return_value=self.live):
            self.assertEqual(backend.main(['--restore-displays']), 1)
        self.assertEqual(self.hardware.calls, [])

    def test_expired_preview_does_not_block_saver_forever(self):
        preview = {'preview': {'status': 'pending', 'deadline': time.time() - 60}}
        with patch.object(self.live.display_control, 'snapshot', return_value=preview):
            self.assertTrue(self.complete(self.live, True)['ok'])
        self.assertTrue(self.live.saver_snapshot()['active'])

    def test_activation_reads_the_latest_brightness_target_from_settings(self):
        other = backend.Preferences(self.preferences.path)
        other.set('batterySaverBrightness', 80)
        self.assertEqual(self.live.preferences.values['batterySaverBrightness'], 70)
        self.assertTrue(self.complete(self.live, True)['ok'])
        self.assertEqual(self.live.brightness(raw=True)['current'], 800)

    def test_invalid_requests_and_corrupt_journal_do_not_mutate_hardware(self):
        for value in (None, 1, "true", [], {}):
            result = self.live.handle({"action": "batterySaver", "enabled": value})
            self.assertFalse(result["ok"], result)
        self.assertEqual(self.hardware.calls, [])
        self.live.battery_saver.path.parent.mkdir(parents=True, exist_ok=True)
        self.live.battery_saver.path.write_text("{incomplete")
        result = self.complete(self.live, True)
        self.assertFalse(result["ok"])
        self.assertIn("restore data", result["message"])
        self.assertEqual(self.live.battery_saver.path.read_text(), "{incomplete")
        self.assertFalse(self.live.saver_snapshot()["active"])
        self.assertTrue(all(call == ("niri", "msg", "--json", "outputs") for call in self.hardware.calls))

    def test_pending_preview_and_active_or_queued_recording_reject_enable_before_work_starts(self):
        for status in ("applying", "pending", "reverting"):
            with self.subTest(status=status), patch.object(self.live.display_control, "snapshot", return_value={"preview": {"status": status}}):
                reply = self.live.handle({"action": "batterySaver", "enabled": True})
                self.assertFalse(reply["ok"])
                self.assertIn("display preview", reply["message"])
        self.live.recording = lambda: {"active": True}
        reply = self.live.handle({"action": "batterySaver", "enabled": True})
        self.assertFalse(reply["ok"])
        self.assertIn("recording", reply["message"])
        self.live.recording = lambda: {"active": False}
        self.live.feature_jobs["recordStart"] = object()
        try:
            reply = self.live.handle({"action": "batterySaver", "enabled": True})
            self.assertFalse(reply["ok"])
            self.assertIn("recording", reply["message"])
        finally:
            self.live.feature_jobs.pop("recordStart")
        self.assertFalse(self.live.battery_saver.path.exists())

    def test_active_saver_blocks_display_previews_and_manual_power_profile_changes(self):
        self.complete(self.live, True)
        self.hardware.calls.clear()
        for request in ({"action": "displayApply", "layout": []}, {"action": "powerProfile", "value": "balanced"}):
            reply = self.live.handle(request)
            self.assertFalse(reply["ok"])
            self.assertIn("Turn off Battery saver", reply["message"])
        self.assertEqual(self.hardware.calls, [])

    def test_raw_backlight_uses_cli_selected_device_with_multiple_backlights_and_checks_restore_bounds(self):
        self.put("sys/class/backlight/other/max_brightness", "255")
        responses = {("brightnessctl", "--class=backlight", "-m"):
            "kbd,leds,3,30%,10\ninvalid,backlight,999,99%,10\namdgpu_bl1,backlight,837,84%,1001\n"}
        runner = FakeRunner(responses)
        live = self.configure(self.make_backend(runner))
        original = {"device": "amdgpu_bl1", "current": 837, "maximum": 1001}
        self.assertEqual(live.brightness(raw=True), original)
        live.restore_brightness(original)
        self.assertEqual(runner.calls[-1], ("brightnessctl", "--class=backlight", "--device", "amdgpu_bl1", "set", "837"))
        for value in ({**original, "device": "../other"}, {**original, "current": -1},
                      {**original, "current": True}, {**original, "maximum": 1000}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                live.restore_brightness(value)

    def test_async_partial_failure_reports_error_keeps_restore_data_and_supports_retry(self):
        self.complete(self.live, True)
        original_set = self.live.battery_saver.set_profile
        def fail(value):
            raise backend.CommandError("Profile service disconnected")
        self.live.battery_saver.set_profile = fail
        result = self.complete(self.live, False)
        self.assertFalse(result["ok"])
        self.assertIn("Profile service disconnected", result["message"])
        self.assertTrue(self.live.saver_snapshot()["active"])
        self.assertIn("restore pending", self.live.saver_snapshot()["error"])
        self.assertEqual(self.live.brightness(raw=True)["current"], 837)
        self.live.battery_saver.set_profile = original_set
        self.assertTrue(self.complete(self.live, False)["ok"])
        self.assertFalse(self.live.saver_snapshot()["active"])
        self.assertEqual(self.hardware.profile, "performance")

    def test_off_during_recording_rejects_without_changing_restore_journal(self):
        self.complete(self.live, True)
        saved = self.live.battery_saver.path.read_bytes()
        self.hardware.calls.clear()
        self.live.recording = lambda: {"active": True}
        result = self.live.handle({"action": "batterySaver", "enabled": False})
        self.assertFalse(result["ok"])
        self.assertIn("Stop screen recording", result["message"])
        self.assertEqual(self.live.battery_saver.path.read_bytes(), saved)
        self.assertTrue(self.live.saver_snapshot()["active"])
        self.assertEqual(self.hardware.calls, [])

    def test_queued_saver_blocks_conflicting_actions_before_worker_starts(self):
        executor = self.manual_executor()
        self.assertTrue(self.live.handle({"action": "batterySaver", "enabled": True})["pending"])
        self.assertFalse(self.live.battery_saver.path.exists())
        self.hardware.calls.clear()
        for request in ({"action": "displayApply", "layout": []},
                        {"action": "powerProfile", "value": "balanced"},
                        {"action": "recordStart", "mode": "output", "output": "eDP-1"}):
            with self.subTest(request=request):
                result = self.live.handle(request)
                self.assertFalse(result["ok"])
                self.assertIn("Wait for Battery saver", result["message"])
        self.assertEqual(self.hardware.calls, [])
        self.assertEqual(set(self.live.feature_jobs), {"batterySaver"})
        executor.complete()
        self.live.finish_features()
        self.assertTrue(self.live.saver_snapshot()["active"])

    def test_preflight_rechecks_conflicts_when_queued_worker_eventually_starts(self):
        executor = self.manual_executor()
        for conflict in ("preview", "recording"):
            with self.subTest(conflict=conflict):
                self.live.recording = lambda: {"active": False}
                self.assertTrue(self.live.handle({"action": "batterySaver", "enabled": True})["pending"])
                if conflict == "preview":
                    with patch.object(self.live.display_control, "snapshot", return_value={"preview": {"status": "pending"}}):
                        executor.complete()
                        self.live.finish_features()
                else:
                    self.live.recording = lambda: {"active": True}
                    executor.complete()
                    self.live.finish_features()
                self.assertFalse(self.live.last_result["ok"])
                self.assertFalse(self.live.battery_saver.path.exists())
                self.assertFalse(self.live.saver_snapshot()["active"])

    def test_other_backend_lock_blocks_conflicting_actions_without_waiting(self):
        other = self.configure(self.make_backend(self.hardware))
        with other.battery_saver.guard():
            self.hardware.calls.clear()
            for request in ({"action": "displayApply", "layout": []},
                            {"action": "powerProfile", "value": "balanced"},
                            {"action": "recordStart", "mode": "output", "output": "eDP-1"}):
                with self.subTest(request=request):
                    result = self.live.handle(request)
                    self.assertFalse(result["ok"])
                    self.assertIn("Battery saver", result["message"])
            self.assertEqual(self.hardware.calls, [])

    def test_recording_after_saver_off_survives_a_settings_status_probe(self):
        self.assertTrue(self.complete(self.live, True)['ok'])
        self.assertTrue(self.complete(self.live, False)['ok'])
        executor = self.manual_executor()
        self.live.niri_state = lambda: {'available': True, 'workspaces': [{'output': 'eDP-1'}]}
        other = self.configure(self.make_backend(self.hardware))
        other.settings_only = True
        reading, release = threading.Event(), threading.Event()
        flock = fcntl.flock

        def pause_reader(stream, operation):
            try:
                flock(stream, operation)
            except BlockingIOError:
                release.set()
                raise
            if threading.current_thread() is reader:
                reading.set()
                release.wait(2)

        reader = threading.Thread(target=other.saver_snapshot)
        with patch.object(self.live.recorder, 'start', return_value='Recording requested') as start:
            reply = self.live.handle({'action': 'recordStart', 'mode': 'output', 'output': 'eDP-1'})
            self.assertTrue(reply.get('pending'), reply)
            with patch('battery_saver.fcntl.flock', side_effect=pause_reader):
                reader.start()
                try:
                    self.assertTrue(reading.wait(2))
                    executor.complete()
                    self.live.finish_features()
                    self.assertTrue(self.live.last_result['ok'], self.live.last_result)
                    start.assert_called_once()
                finally:
                    release.set()
                    reader.join(3)
        self.assertFalse(reader.is_alive())
        self.assertFalse(self.live.saver_snapshot()['active'])

    def test_cross_backend_activation_and_finished_transition_invalidate_system_caches(self):
        other = self.configure(self.make_backend(self.hardware))
        self.live.system_cache = {"brightness": {"percent": 84}}
        self.live.power_cache = {"powerProfile": "performance"}
        other.battery_saver.toggle(True)
        self.assertTrue(self.live.saver_snapshot()["active"])
        self.assertIsNone(self.live.system_cache)
        self.assertIsNone(self.live.power_cache)
        self.assertTrue(self.live.wallpapers.power_saving)
        other.battery_saver.toggle(False)
        self.assertFalse(self.live.saver_snapshot()["active"])
        self.assertFalse(self.live.wallpapers.power_saving)
        with other.battery_saver.guard():
            self.assertTrue(self.live.saver_snapshot()["busy"])
            self.live.system_cache = {"brightness": {"percent": 84}}
            self.live.power_cache = {"powerProfile": "performance"}
        self.assertFalse(self.live.saver_snapshot()["busy"])
        self.assertIsNone(self.live.system_cache)
        self.assertIsNone(self.live.power_cache)


if __name__ == "__main__":
    unittest.main()
