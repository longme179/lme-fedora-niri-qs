"""Battery-saver round trips with fake niri, backlight and profile providers."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from battery_saver import BatterySaver
from display_control import normalized_outputs, read_json


class BatterySaverCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "battery-saver.json"
        self.outputs = normalized_outputs({
            "eDP-1": {"modes": [{"width": 1920, "height": 1080, "refresh_rate": 120000},
                                  {"width": 1920, "height": 1080, "refresh_rate": 59940}],
                      "current_mode": 0, "logical": {"scale": 1.25, "x": -1400, "y": 50}},
            "HDMI-A-1": {"modes": [{"width": 1920, "height": 1080, "refresh_rate": 60000}],
                         "current_mode": None},
        })
        self.light = {"device": "amdgpu_bl1", "current": 837, "maximum": 1001}
        self.profile = "performance"
        self.available_profiles = ["power-saver", "balanced", "performance"]
        self.calls = []
        self.controller = self.make_controller()

    def make_controller(self):
        return BatterySaver(SimpleNamespace(run=self.run_hardware), self.path, outputs=lambda: copy.deepcopy(self.outputs),
                            read_brightness=lambda: copy.deepcopy(self.light), set_brightness=self.set_brightness,
                            read_profile=lambda: self.profile, profiles=lambda: list(self.available_profiles),
                            set_profile=self.set_profile)

    @property
    def panel(self):
        return next(output for output in self.outputs if output["name"] == "eDP-1")

    def run_hardware(self, *args):
        self.assertTrue(self.path.exists(), "Original values must be durable before mutations")
        self.calls.append(args)
        name, action, value = args[3:6]
        if action == "mode":
            output = next(output for output in self.outputs if output["name"] == name)
            output["current"] = next(mode for mode in output["modes"]
                                     if f'{mode["width"]}x{mode["height"]}@{mode["refresh"] / 1000:.3f}' == value)

    def set_brightness(self, value):
        self.assertTrue(self.path.exists(), "Original values must be durable before mutations")
        self.calls.append(("brightness", value["current"]))
        if value["device"] != self.light["device"]:
            raise ValueError("Original backlight is unavailable")
        self.light = copy.deepcopy(value)

    def set_profile(self, value):
        self.assertTrue(self.path.exists(), "Original values must be durable before mutations")
        self.calls.append(("profile", value))
        self.profile = value

    def test_exact_round_trip_preserves_fractional_mode_scale_position_and_disabled_output(self):
        before = copy.deepcopy(self.outputs)
        enabled = self.controller.toggle(True)
        self.assertTrue(enabled["active"])
        self.assertFalse(enabled["busy"])
        self.assertEqual(enabled["error"], "")
        self.assertEqual(self.panel["current"]["refresh"], 59940)
        self.assertEqual(self.light["current"], 700)
        self.assertEqual(self.profile, "power-saver")
        self.assertIn(("niri", "msg", "output", "eDP-1", "scale", "1.25"), self.calls)
        self.assertIn(("niri", "msg", "output", "eDP-1", "position", "set", "-1400", "50"), self.calls)
        self.assertFalse(any("HDMI-A-1" in call for call in self.calls))
        self.light["current"] = 950  # The user remains free to raise brightness while enabled.
        self.assertTrue(self.controller.snapshot()["active"])
        self.assertEqual(self.light["current"], 950)
        self.assertFalse(self.controller.toggle(False)["active"])
        self.assertEqual(self.outputs, before)
        self.assertEqual(self.light["current"], 837)
        self.assertEqual(self.profile, "performance")

    def test_restart_and_repeated_enable_do_not_recapture_or_enforce_again(self):
        self.controller.toggle(True)
        saved = self.path.read_bytes()
        self.calls.clear()
        self.light["current"] = 920
        restarted = self.make_controller()
        self.assertTrue(restarted.snapshot()["active"])
        restarted.toggle(True, 25)
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.light["current"], 920)
        restarted.toggle(False)
        self.assertEqual(self.light["current"], 837)

    def test_nominal_60hz_modes_keep_the_exact_driver_timing_and_restore_120hz(self):
        for refresh in (59940, 60000, 60003, 60059, 60499):
            with self.subTest(refresh=refresh):
                self.panel['modes'][0]['refresh'] = 120002
                self.panel['modes'][1]['refresh'] = refresh
                self.panel['current'] = self.panel['modes'][0]
                self.calls.clear()
                self.assertEqual(self.controller.toggle(True)['error'], '')
                self.assertEqual(self.panel['current']['refresh'], refresh)
                self.assertIn(('niri', 'msg', 'output', 'eDP-1', 'mode', f'1920x1080@{refresh / 1000:.3f}'), self.calls)
                self.assertFalse(self.controller.toggle(False)['active'])
                self.assertEqual(self.panel['current']['refresh'], 120002)

    def test_an_existing_nominal_60hz_mode_is_kept_and_higher_rates_are_not_misclassified(self):
        self.panel['modes'][1]['refresh'] = 60003
        self.panel['current'] = self.panel['modes'][1]
        state = self.controller.toggle(True)
        self.assertFalse(any('no supported lower mode' in warning for warning in state['warnings']))
        self.assertFalse(any(call[0] == 'niri' for call in self.calls))
        self.controller.toggle(False)
        for refresh in (60500, 61000, 75000):
            with self.subTest(refresh=refresh):
                self.panel['modes'][1]['refresh'] = refresh
                self.panel['current'] = self.panel['modes'][0]
                self.calls.clear()
                state = self.controller.toggle(True)
                self.assertTrue(any('no supported lower mode' in warning for warning in state['warnings']))
                self.assertEqual(self.panel['current']['refresh'], 120000)
                self.assertFalse(any(call[0] == 'niri' for call in self.calls))
                self.controller.toggle(False)

    def test_accepted_but_ignored_display_commands_are_reported_and_keep_restore_data(self):
        self.controller.runner = SimpleNamespace(run=lambda *args: self.calls.append(args))
        with patch('battery_saver.time.monotonic', side_effect=[0, 2]):
            state = self.controller.toggle(True)
        self.assertIn('did not confirm', state['error'])
        self.assertTrue(state['active'])
        self.assertEqual(read_json(self.path, {})['pending']['displays'], ['eDP-1'])
        self.assertFalse(self.controller.toggle(False)['active'])

    def test_an_ignored_restore_keeps_the_display_pending_until_it_is_confirmed(self):
        self.controller.toggle(True)
        self.controller.runner = SimpleNamespace(run=lambda *args: self.calls.append(args))
        with patch('battery_saver.time.monotonic', side_effect=[0, 2]):
            state = self.controller.toggle(False)
        self.assertTrue(state['active'])
        self.assertIn('did not confirm', state['error'])
        self.assertEqual(read_json(self.path, {})['pending']['displays'], ['eDP-1'])
        self.controller.runner = SimpleNamespace(run=self.run_hardware)
        self.assertFalse(self.controller.toggle(False)['active'])

    def test_mode_readback_tolerates_a_delayed_compositor_update(self):
        before = copy.deepcopy(self.outputs)
        count = 0
        def outputs():
            nonlocal count
            count += 1
            return copy.deepcopy(before if count == 2 else self.outputs)
        self.controller.outputs = outputs
        with patch('battery_saver.time.sleep') as wait:
            self.assertEqual(self.controller.toggle(True)['error'], '')
        self.assertGreaterEqual(count, 3)
        wait.assert_called_once_with(.1)

    def test_only_modified_resources_are_restored_and_low_brightness_is_never_raised(self):
        self.panel["current"] = self.panel["modes"][1]
        self.light["current"] = 300
        self.profile = "power-saver"
        self.controller.toggle(True)
        self.assertEqual(self.calls, [])
        self.light["current"] = 410
        self.controller.toggle(False)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.light["current"], 410)

    def test_missing_original_output_and_profile_keep_restore_retryable_without_touching_new_outputs(self):
        self.controller.toggle(True)
        old_outputs = copy.deepcopy(self.outputs)
        self.outputs = normalized_outputs({
            "DP-3": {"modes": [{"width": 2560, "height": 1440, "refresh_rate": 144000}],
                     "current_mode": 0, "logical": {"scale": 1, "x": 0, "y": 0}},
        })
        self.available_profiles = ["power-saver", "balanced"]
        self.calls.clear()
        result = self.controller.toggle(False)
        self.assertTrue(result["active"])
        self.assertIn("restore pending", result["error"])
        self.assertEqual(self.calls, [("brightness", 837)])
        self.assertEqual(read_json(self.path, {})["pending"],
                         {"displays": ["eDP-1"], "brightness": False, "profile": True})
        self.outputs = old_outputs
        self.available_profiles.append("performance")
        self.assertFalse(self.controller.toggle(False)["active"])
        self.assertEqual(self.profile, "performance")

    def test_disabled_original_output_is_not_implicitly_enabled_during_restore(self):
        self.controller.toggle(True)
        self.panel.update(current=None, enabled=False)
        self.calls.clear()
        self.assertTrue(self.controller.toggle(False)["active"])
        self.assertFalse(any(call[0] == "niri" for call in self.calls))

    def test_new_niri_session_discards_expired_display_overrides_but_restores_global_settings(self):
        with patch.dict("os.environ", NIRI_SOCKET="/run/user/1000/niri-old.sock"):
            self.controller.toggle(True)
        self.calls.clear()
        self.outputs = []
        with patch.dict("os.environ", NIRI_SOCKET="/run/user/1000/niri-new.sock"):
            saved = self.path.read_bytes()
            self.assertIn("temporary display caps expired", self.make_controller().snapshot()["warnings"][0])
            self.assertEqual(self.path.read_bytes(), saved)
            self.assertEqual(self.calls, [])
            result = self.make_controller().toggle(False)
        self.assertFalse(result["active"])
        self.assertEqual(result["error"], "")
        self.assertIn("previous niri session ended", result["warnings"][0])
        self.assertFalse(any(call[0] == "niri" for call in self.calls))
        self.assertEqual(self.light["current"], 837)
        self.assertEqual(self.profile, "performance")

    def test_unsupported_cap_and_missing_hardware_leave_visual_mode_available_with_warnings(self):
        self.panel["modes"] = self.panel["modes"][:1]
        self.available_profiles = ["balanced"]
        self.controller.read_brightness = lambda: None
        result = self.controller.toggle(True)
        self.assertTrue(result["active"])
        self.assertEqual(len(result["warnings"]), 3)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.controller.toggle(False)["active"])

    def test_apply_failure_retains_original_data_and_can_restore_after_restart(self):
        def fail(value):
            raise RuntimeError("Backlight denied")
        self.controller.set_brightness = fail
        result = self.controller.toggle(True)
        self.assertTrue(result["active"])
        self.assertIn("Backlight denied", result["error"])
        self.assertEqual(read_json(self.path, {})["original"]["brightness"]["current"], 837)
        self.assertFalse(self.make_controller().toggle(False)["active"])
        self.assertEqual(self.profile, "performance")

    def test_denied_unchanged_values_do_not_leave_restore_stuck(self):
        def fail(*args):
            raise RuntimeError("Operation denied")
        self.controller.runner = SimpleNamespace(run=fail)
        self.controller.set_brightness = fail
        self.controller.set_profile = fail
        self.assertIn("Operation denied", self.controller.toggle(True)["error"])
        self.assertFalse(self.controller.toggle(False)["active"])
        self.assertEqual(self.calls, [])

    def test_crash_mid_apply_leaves_journal_for_restore(self):
        def interrupt(*args):
            self.assertEqual(read_json(self.path, {})["original"]["profile"], "performance")
            raise SystemExit()
        self.controller.runner = type("InterruptedRunner", (), {"run": staticmethod(interrupt)})()
        with self.assertRaises(SystemExit):
            self.controller.toggle(True)
        self.assertTrue(self.make_controller().snapshot()["active"])
        self.assertFalse(self.make_controller().toggle(False)["active"])
        self.assertEqual(self.light["current"], 837)

    def test_corrupt_or_invalid_restore_journal_is_never_overwritten(self):
        self.controller.toggle(True)
        valid = json.loads(self.path.read_text())
        for value in ["{truncated", [], {**valid, "active": 1},
                      {**valid, "pending": {**valid["pending"], "brightness": "yes"}},
                      {**valid, "original": {**valid["original"], "profile": "unsafe"}},
                      {**valid, "original": {**valid["original"], "brightness": {"device": "x", "current": -2, "maximum": 100}}}]:
            with self.subTest(value=value):
                saved = value if isinstance(value, str) else json.dumps(value)
                self.path.write_text(saved)
                self.calls.clear()
                self.assertIn("restore data", self.controller.snapshot()["error"])
                for enabled in (False, True):
                    with self.assertRaises(ValueError):
                        self.controller.toggle(enabled)
                self.assertEqual(self.path.read_text(), saved)
                self.assertEqual(self.calls, [])

    def test_separate_instances_serialize_and_snapshot_does_not_block(self):
        started, finish = threading.Event(), threading.Event()
        original_set = self.controller.set_profile
        def delayed_set(value):
            started.set()
            self.assertTrue(finish.wait(2))
            original_set(value)
        self.controller.set_profile = delayed_set
        thread = threading.Thread(target=self.controller.toggle, args=(True,))
        thread.start()
        try:
            self.assertTrue(started.wait(2))
            second = self.make_controller()
            self.assertTrue(second.snapshot()["busy"])
            self.assertTrue(second.snapshot()["active"])
        finally:
            finish.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        calls = list(self.calls)
        self.make_controller().toggle(True)
        self.assertEqual(self.calls, calls)
        self.assertFalse(self.make_controller().snapshot()["busy"])

    def test_invalid_target_or_boolean_does_not_touch_hardware_or_create_journal(self):
        for enabled, target in [(1, 70), (True, False), (True, float("nan")), (True, 0), (True, 101)]:
            with self.subTest(enabled=enabled, target=target), self.assertRaises(ValueError):
                self.controller.toggle(enabled, target)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.calls, [])

    def test_display_caps_never_raise_a_lower_resolution_or_refresh(self):
        for width, height, refresh, modes, expected in [
            (1280, 720, 120000, [(1920, 1080, 60000), (1280, 720, 60000)], (1280, 720, 60000)),
            (3840, 2160, 30000, [(1920, 1080, 60000), (1920, 1080, 30000)], (1920, 1080, 30000)),
            (1280, 720, 120000, [(1920, 1080, 60000)], (1280, 720, 120000)),
        ]:
            with self.subTest(width=width, height=height, refresh=refresh, modes=modes):
                self.outputs = normalized_outputs({"eDP-1": {"current_mode": 0,
                    "modes": [{"width": w, "height": h, "refresh_rate": r}
                              for w, h, r in [(width, height, refresh), *modes]],
                    "logical": {"scale": 1, "x": 0, "y": 0}}})
                self.controller.toggle(True)
                self.assertEqual(tuple(self.panel["current"][key] for key in ("width", "height", "refresh")), expected)
                self.controller.toggle(False)

    def test_guard_rejects_concurrent_writes_and_active_or_pending_restore(self):
        with self.controller.guard():
            self.assertTrue(self.make_controller().snapshot()["busy"])
            with self.assertRaisesRegex(ValueError, "changing settings"):
                with self.make_controller().guard():
                    self.fail("A competing writer acquired the journal lock")
        self.controller.toggle(True)
        with self.assertRaisesRegex(ValueError, "Turn off Battery saver"):
            with self.make_controller().guard():
                self.fail("An active saver allowed a conflicting write")
        self.outputs = []
        self.controller.toggle(False)
        with self.assertRaisesRegex(ValueError, "Turn off Battery saver"):
            with self.make_controller().guard():
                self.fail("An incomplete restore allowed a conflicting write")

    def test_recording_guard_allows_active_mode_but_never_concurrent_transitions(self):
        self.controller.toggle(True)
        with self.controller.guard(allow_active=True):
            self.assertTrue(self.make_controller().snapshot()["busy"])
            with self.assertRaisesRegex(ValueError, "changing settings"):
                with self.make_controller().guard(allow_active=True):
                    self.fail("A recording startup raced another transition")
        self.assertTrue(self.controller.snapshot()["active"])

    def test_preflight_runs_inside_lock_before_enable_or_restore_mutations(self):
        def reject(enabled, state):
            self.assertTrue(self.make_controller().snapshot()["busy"])
            raise ValueError("Conflicting operation")
        with self.assertRaisesRegex(ValueError, "Conflicting operation"):
            self.controller.toggle(True, preflight=reject)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.calls, [])
        self.controller.toggle(True)
        saved, calls = self.path.read_bytes(), list(self.calls)
        with self.assertRaisesRegex(ValueError, "Conflicting operation"):
            self.controller.toggle(False, preflight=reject)
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertEqual(self.calls, calls)


if __name__ == "__main__":
    unittest.main()
