"""Feature contracts with fake hardware; no real mode or network changes."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from test_backend import Fixture, FakeRunner, backend
from desktop_features import calculate, wallpaper_library, CONTROL_MODULES
from display_control import normalized_outputs, validate_layout, current_layout, watch, read_json, write_json, DisplayControl

OUTPUT = {"eDP-1": {"make": "Lenovo", "model": "Panel", "current_mode": 1,
    "modes": [{"width": 1920, "height": 1080, "refresh_rate": hz * 1000} for hz in (60, 120)],
    "logical": {"x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1}}}

class UpgradesCase(Fixture, unittest.TestCase):
    def test_profiles_apply_atomically_and_preserve_unrelated_preferences(self):
        live = self.make_backend()
        self.preferences.update({"accent": "#ff80bf", "opacity": .8, "density": "compact", "animations": False})
        self.assertTrue(live.handle({"action": "appearanceSave", "name": "Focus"})["ok"])
        self.assertTrue(live.handle({"action": "appearanceApply", "name": "Dracula"})["ok"])
        self.assertEqual(self.preferences.values["opacity"], .9)
        self.preferences.set("barFontSize", 16)
        self.assertTrue(live.handle({"action": "appearanceApply", "name": "Focus"})["ok"])
        saved = backend.Preferences(self.preferences.path).values
        self.assertEqual((saved["accent"], saved["density"], saved["animations"], saved["barFontSize"]), ("#ff80bf", "compact", False, 16))
        self.assertFalse(live.handle({"action": "appearanceDelete", "name": "Dracula"})["ok"])
        self.assertTrue(live.handle({"action": "appearanceDelete", "name": "Focus"})["ok"])
        self.assertFalse(live.handle({"action": "appearanceSave", "name": "  "})["ok"])

    def test_control_layout_and_rules_validate_before_writing(self):
        value = copy.deepcopy(backend.DEFAULT_PREFERENCES["controlLayout"])
        value.reverse(); value[0].update(enabled=False, size="half")
        self.preferences.set("controlLayout", value)
        self.assertEqual(backend.Preferences(self.preferences.path).values["controlLayout"], value)
        for malformed in [value[:-1], [value[0]] * len(value), [dict(m, size="huge") for m in value]]:
            with self.assertRaises(ValueError): self.preferences.set("controlLayout", malformed)
        self.assertEqual(set(m["id"] for m in value), set(CONTROL_MODULES))
        self.preferences.set("notificationMutedApps", ["Music", "Music"])
        self.assertEqual(self.preferences.values["notificationMutedApps"], ["Music"])
        for value in [True, -2, float("nan")]:
            with self.assertRaises(ValueError): self.preferences.set("dndUntil", value)

    def test_notification_restart_keeps_text_and_drops_transients_and_actions(self):
        live = self.make_backend()
        entry = {"id": "1", "appName": "App", "summary": "Hello", "body": "A full notification body", "timestamp": 1,
                 "urgency": 1, "actions": [{"identifier": "open"}], "active": True, "popup": True}
        self.assertTrue(live.handle({"action": "notificationSave", "entries": [entry, dict(entry, id="2", transient=True)]})["ok"])
        loaded = self.make_backend().notification_history
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["body"], entry["body"])
        self.assertEqual(loaded[0]["actions"], [])
        self.assertFalse(loaded[0]["popup"] or loaded[0]["active"])
        self.assertEqual(live.notification_path.stat().st_mode & 0o777, 0o600)
        live.notification_path.write_text("bad json")
        self.assertEqual(self.make_backend().notification_history, [])

    def test_wallpaper_scan_filters_names_and_does_not_follow_external_symlinks(self):
        directory = self.root / "images"; directory.mkdir()
        (directory / "photo #1.png").write_bytes(b"png")
        (directory / "ignore.txt").write_text("text")
        outside = self.root / "outside.jpg"; outside.write_bytes(b"jpeg")
        (directory / "external.jpg").symlink_to(outside)
        result = wallpaper_library(str(directory))
        self.assertEqual([e["name"] for e in result["entries"]], ["photo #1.png"])
        self.assertIn("%23", result["entries"][0]["url"])
        with self.assertRaises(ValueError): wallpaper_library(str(directory / "missing"))

    def test_calculator_precedence_and_rejection_of_code_and_expensive_expressions(self):
        self.assertEqual(calculate("(2 + 3) × 4 ^ 2"), "80")
        self.assertEqual(calculate("-8 / 2 + 1.5"), "-2.5")
        for expr in ["__import__('os').system('id')", "1/0", "9**999", "1e100", "True+1", "(-1)**.5"]:
            with self.assertRaises(ValueError): calculate(expr)
        live = self.make_backend()
        result = live.handle({"action": "calculate", "query": "3+4"})
        self.assertEqual((result["query"], result["message"]), ("3+4", "7"))

    def wifi_backend(self):
        runner = FakeRunner(available=("nmcli",))
        live = self.make_backend(runner)
        state = {"available": True, "enabled": True, "device": "wlp1s0", "networks": [{"ssid": "Home:5G", "bssid": "AA:BB:CC:DD:EE:FF", "enterprise": False}], "saved": [{"uuid": "safe-uuid", "name": "Home"}]}
        live.network = lambda: state
        return live, runner

    def test_wifi_operations_use_adapter_and_validate_network_ids(self):
        live, runner = self.wifi_backend()
        calls = []
        def run(name, *args, **kwargs): calls.append((name, args, kwargs)); return ""
        runner.run = run
        live.wifi_action("wifiConnect", {"bssid": "AA:BB:CC:DD:EE:FF", "password": "a test password"})
        name, args, options = calls[-1]
        self.assertIn("--ask", args)
        self.assertNotIn("a test password", args)
        self.assertEqual(options["input"], "a test password\n")
        self.assertEqual(args[-2:], ("ifname", "wlp1s0"))
        live.wifi_action("wifiScan", {})
        self.assertIn("rescan", calls[-1][1])
        live.wifi_action("wifiSaved", {"uuid": "safe-uuid"})
        live.wifi_action("wifiForget", {"uuid": "safe-uuid"})
        live.wifi_action("wifiDisconnect", {})
        for request in [{"bssid": "unknown"}, {"bssid": "AA:BB:CC:DD:EE:FF", "password": "bad\npassword"}, {"device": "other", "bssid": "AA:BB:CC:DD:EE:FF"}]:
            with self.assertRaises(ValueError): live.wifi_action("wifiConnect", request)
        with self.assertRaises(ValueError): live.wifi_action("wifiForget", {"uuid": "other"})

    def test_background_completions_each_clear_their_pending_action(self):
        live, runner = self.wifi_backend()
        result = live.handle({"action": "wifiScan"})
        self.assertTrue(result["pending"])
        self.assertTrue(live.handle({"action": "wallpaperScan", "folder": str(self.root)})["pending"])
        for future in live.feature_jobs.values(): future.result(timeout=2)
        live.result_unemitted = False; live.finish_features()
        first = live.last_result["action"]
        self.assertFalse(live.last_result.get("pending", False))
        live.finish_features()
        self.assertNotEqual(first, live.last_result["action"])
        self.assertFalse(live.feature_jobs)

    def test_password_never_appears_in_command_error(self):
        runner = backend.CommandRunner(); runner.commands["nmcli"] = "/usr/bin/nmcli"
        result = subprocess.CompletedProcess([], 1, "", "Failed: secret-value")
        with patch("desktop_backend.subprocess.run", return_value=result):
            with self.assertRaises(backend.CommandError) as error: runner.run("nmcli", "--ask", input="secret-value\n")
        self.assertNotIn("secret-value", str(error.exception))

    def test_demo_new_features_do_not_mutate_disk_or_hardware(self):
        live = self.make_backend(demo=True)
        for action in [{"action": "appearanceSave", "name": "Demo"}, {"action": "displayRefresh"}, {"action": "wallpaperScan", "folder": str(self.root)}, {"action": "wifiScan"}, {"action": "notificationSave", "entries": []}, {"action": "calculate", "query": "2+2"}]:
            self.assertTrue(live.handle(action)["ok"], action)
        self.assertEqual(live.runner.calls, [])
        self.assertFalse(self.preferences.path.exists())
        self.assertFalse(live.notification_path.exists())

class DisplayCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "preview.json"
        self.original = current_layout(normalized_outputs(OUTPUT))
        self.layout = [dict(self.original[0], refresh=60000, scale=1.25, x=100)]
        self.payload = {"token": "test", "socket": "", "original": self.original, "layout": self.layout}

    def test_mode_validation_checks_attached_outputs_and_fractional_refresh(self):
        outputs = normalized_outputs(OUTPUT)
        self.assertEqual(validate_layout(self.layout, outputs)[0]["refresh"], 60000)
        for item in [dict(self.layout[0], refresh=144000), dict(self.layout[0], name="missing"), dict(self.layout[0], scale=float("nan")), dict(self.layout[0], x=True)]:
            with self.assertRaises(ValueError): validate_layout([item], outputs)
        fractional = copy.deepcopy(OUTPUT); fractional["eDP-1"]["modes"][0]["refresh_rate"] = 59940
        self.assertEqual(normalized_outputs(fractional)[0]["modes"][0]["refresh"], 59940)

    def test_timer_reverts_every_changed_field_without_initiating_process(self):
        calls = []
        watch(self.path, self.payload, lambda *args: calls.append(args), duration=.05)
        self.assertEqual(read_json(self.path, {})["status"], "reverted")
        self.assertEqual(calls[0][-1], "1920x1080@60.000")
        self.assertEqual(calls[-3][-1], "1920x1080@120.000")
        self.assertEqual(calls[-1][-2:], ("0", "0"))

    def test_clock_adjustment_cannot_extend_the_revert_timeout(self):
        calls = []
        with patch("display_control.time.time", return_value=42):
            watch(self.path, self.payload, lambda *args: calls.append(args), duration=.05)
        self.assertEqual(read_json(self.path, {})["status"], "reverted")
        self.assertEqual(len(calls), 6)

    def test_confirmation_keeps_changes_and_second_worker_cannot_overwrite_preview(self):
        calls = []
        thread = threading.Thread(target=watch, args=(self.path, self.payload, lambda *args: calls.append(args)), kwargs={"duration": 3})
        thread.start()
        try:
            end = time.monotonic() + 2
            while read_json(self.path, {}).get("status") != "pending" and time.monotonic() < end: time.sleep(.01)
            other = dict(self.payload, token="other")
            watch(self.path, other, lambda *args: self.fail("Second preview touched hardware"), duration=.01)
            self.assertEqual(read_json(self.path, {})["token"], "test")
            state = read_json(self.path, {}); state["status"] = "confirmed"; write_json(self.path, state)
            thread.join(3)
            self.assertFalse(thread.is_alive()); self.assertEqual(len(calls), 3)
        finally:
            thread.join(4)

    def test_partial_apply_failure_restores_mode_scale_position(self):
        calls = []
        def run(*args):
            calls.append(args)
            if len(calls) == 2: raise RuntimeError("Scale failed")
        watch(self.path, self.payload, run, duration=.05)
        self.assertEqual(read_json(self.path, {})["error"], "Scale failed")
        self.assertEqual(calls[-3][-1], "1920x1080@120.000")
        self.assertEqual(calls[-2][-1], "1")

    def test_expired_or_wrong_session_confirmation_is_rejected(self):
        control = DisplayControl(FakeRunner(), Path(self.temp.name))
        write_json(control.path, dict(self.payload, status="pending", deadline=time.time()-1))
        with self.assertRaises(ValueError): control.decide("test", True)
        write_json(control.path, dict(self.payload, status="pending", deadline=time.time()+10, socket="other-session"))
        with self.assertRaises(ValueError): control.decide("test", True)

@unittest.skipUnless(os.environ.get('LME_TEST_DISPLAY_WATCHDOG') == '1', 'Enable the detached fake-niri preview test explicitly')
class DetachedDisplayCase(unittest.TestCase):
    def test_watchdog_restores_after_the_initiating_process_exits(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            fake = directory / 'niri'
            calls = directory / 'calls.jsonl'
            fake.write_text('#!/usr/bin/env python3\nimport os,sys,json\n'
                'if sys.argv[1:]==["msg","--json","outputs"]: print('+repr(json.dumps(OUTPUT))+')\n'
                'else:\n with open(os.environ["LME_FAKE_NIRI_LOG"],"a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n')
            fake.chmod(0o700)
            env = dict(os.environ, PATH=str(directory)+os.pathsep+os.environ['PATH'], XDG_RUNTIME_DIR=str(directory), LME_FAKE_NIRI_LOG=str(calls), NIRI_SOCKET='fake-private-session')
            repo = Path(__file__).resolve().parents[1]
            layout = [dict(current_layout(normalized_outputs(OUTPUT))[0], refresh=60000)]
            code = 'from desktop_backend import CommandRunner; from display_control import DisplayControl; DisplayControl(CommandRunner()).start('+repr(layout)+')'
            initiator = subprocess.run([sys.executable, '-c', code], cwd=repo/'scripts', env=env, capture_output=True, text=True, timeout=6)
            self.assertEqual(initiator.returncode, 0, initiator.stderr)
            # The initiating Python process is gone; only the independent watcher remains.
            state_path = directory / 'lme-shell/display-preview.json'
            end = time.monotonic() + 25
            while time.monotonic() < end and read_json(state_path, {}).get('status') not in {'reverted','error'}: time.sleep(.2)
            self.assertEqual(read_json(state_path, {}).get('status'), 'reverted')
            operations = [json.loads(line) for line in calls.read_text().splitlines()]
            self.assertEqual(operations[0][-1], '1920x1080@60.000')
            self.assertEqual(operations[-3][-1], '1920x1080@120.000')
