"""Backend contract tests: no live session or system mutations required."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

SPEC = importlib.util.spec_from_file_location("desktop_backend", Path(__file__).resolve().parents[1] / "scripts/desktop_backend.py")
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


class FakeRunner:
    def __init__(self, responses=None, available=()):
        self.responses = responses or {}
        self.names = set(available) | {call[0] for call in self.responses}
        self.calls = []
        self.spawns = []

    def available(self, name):
        return name in self.names

    def executable(self, name):
        if not self.available(name):
            raise backend.CommandError(f"Required command is unavailable: {name}")
        return f"/usr/bin/{name}"

    def run(self, name, *args, **kwargs):
        self.calls.append((name, *args))
        if not self.available(name):
            raise backend.CommandError(f"Required command is unavailable: {name}")
        response = self.responses.get((name, *args), "")
        if isinstance(response, Exception):
            raise response
        return response

    def spawn(self, argv):
        self.spawns.append(argv)


class Fixture:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.preferences = backend.Preferences(self.root / "config/settings.json")

    def make_backend(self, runner=None, demo=False):
        return backend.DesktopBackend(runner=runner or FakeRunner(), preferences=self.preferences,
                                      apps=backend.Applications([]), proc=self.root / "proc",
                                      sysfs=self.root / "sys", demo=demo, weather_fetch=False)

    def put(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class BackendCase(Fixture, unittest.TestCase):

    def test_unavailable_hardware_is_not_fabricated(self):
        live = self.make_backend()
        state = live.snapshot()
        self.assertIsNone(state["system"]["cpu"])
        self.assertIsNone(state["system"]["memoryPercent"])
        self.assertIsNone(state["system"]["tempC"])
        self.assertFalse(state["system"]["battery"]["available"])
        self.assertFalse(state["system"]["audio"]["available"])
        self.assertFalse(state["system"]["brightness"]["available"])
        self.assertFalse(state["niri"]["available"])
        self.assertEqual(live.runner.calls, [])

    def test_real_cpu_deltas_and_memory(self):
        self.put("proc/stat", "cpu 100 0 50 850 0 0 0 0 99 0\n")
        self.put("proc/meminfo", "MemTotal: 8388608 kB\nMemAvailable: 6291456 kB\n")
        live = self.make_backend()
        self.assertIsNone(live.cpu_memory()["cpu"])
        self.put("proc/stat", "cpu 120 0 60 920 0 0 0 0 110 0\n")
        result = live.cpu_memory()
        self.assertEqual(result["cpu"], 30.0)
        self.assertEqual(result["memoryPercent"], 25.0)
        self.assertEqual(result["memoryUsedGiB"], 2.0)
        self.assertEqual(result["memoryTotalGiB"], 8.0)

    def test_cpu_sensor_skips_nvidia(self):
        self.put("sys/class/hwmon/hwmon0/name", "nvidia")
        self.put("sys/class/hwmon/hwmon0/temp1_input", "97000")
        self.put("sys/class/hwmon/hwmon1/name", "k10temp")
        self.put("sys/class/hwmon/hwmon1/temp1_label", "Tctl")
        self.put("sys/class/hwmon/hwmon1/temp1_input", "48500")
        self.assertEqual(self.make_backend().temperature(), 48.5)

    def test_battery_is_read_from_sysfs(self):
        self.put("sys/class/power_supply/BAT0/type", "Battery")
        self.put("sys/class/power_supply/BAT0/capacity", "73")
        self.put("sys/class/power_supply/BAT0/status", "Charging")
        self.assertEqual(self.make_backend().battery(), {"available": True, "percent": 73, "charging": True, "acOnline": True})

    def test_nmcli_escaped_ssid_and_no_rescan(self):
        runner = FakeRunner({
            ("nmcli", "radio", "wifi"): "enabled",
            ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"): "wlp1s0:wifi:connected:Home\\:5G",
            ("nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY,BSSID,DEVICE", "device", "wifi", "list", "--rescan", "no"): "yes:Home\\:5G:84:WPA2:AA\\:BB\\:CC\\:DD\\:EE\\:FF:wlp1s0",
        })
        network = self.make_backend(runner).network()
        self.assertEqual(network["ssid"], "Home:5G")
        self.assertEqual(network["strength"], 84)
        self.assertTrue(network["connected"])
        self.assertIn("--rescan", runner.calls[-1])
        self.assertEqual(runner.calls[-1][-1], "no")

    def test_wired_connection_does_not_claim_wifi_is_connected(self):
        runner = FakeRunner({
            ("nmcli", "radio", "wifi"): "disabled",
            ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"): "enp1s0:ethernet:connected:Wired\nwlp1s0:wifi:unavailable:",
        })
        state = self.make_backend(runner).network()
        self.assertTrue(state["connected"])
        self.assertFalse(state["wifiConnected"])
        self.assertEqual(state["ssid"], "Ethernet")

    def test_backlight_does_not_target_keyboard_led(self):
        runner = FakeRunner({("brightnessctl", "--class=backlight", "-m"): "amdgpu_bl1,backlight,128,50%,255"})
        live = self.make_backend(runner)
        self.assertEqual(live.brightness(), {"available": True, "percent": 50})
        self.assertTrue(live.handle({"action": "brightness", "value": 63})["ok"])
        self.assertEqual(runner.calls[-1], ("brightnessctl", "--class=backlight", "set", "63%"))

    def test_preferences_are_atomic_validated_and_private(self):
        self.preferences.set("accent", "#ABCDEF")
        self.preferences.set("opacity", 0.85)
        saved = backend.Preferences(self.preferences.path)
        self.assertEqual(saved.values["accent"], "#abcdef")
        self.assertEqual(saved.values["opacity"], 0.85)
        self.assertEqual(self.preferences.path.stat().st_mode & 0o777, 0o600)
        before = self.preferences.path.read_bytes()
        for key, value in [("opacity", float("nan")), ("opacity", True), ("animations", "yes"),
                           ("accent", "red; reboot"), ("terminal", "kitty; reboot"), ("unknown", True),
                           ("language", "vi")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.preferences.set(key, value)
        self.assertEqual(before, self.preferences.path.read_bytes())
        self.assertEqual(list(self.preferences.path.parent.glob(".settings-*")), [])

    def test_malformed_preferences_recover_without_overwriting_file(self):
        path = self.put("invalid/settings.json", "broken { json")
        settings = backend.Preferences(path)
        self.assertEqual(settings.values, backend.DEFAULT_PREFERENCES)
        self.assertEqual(path.read_text(), "broken { json")

    def test_action_arguments_are_not_shell_commands(self):
        runner = FakeRunner(available={"wpctl", "niri", "systemctl"})
        live = self.make_backend(runner)
        for request in [
            {"action": "volume", "value": "50; reboot"},
            {"action": "brightness", "value": 0},
            {"action": "focusWindow", "id": "1; reboot"},
            {"action": "focusWindow", "id": True},
            {"action": "powerProfile", "value": "balanced; reboot"},
            {"action": "setting", "key": "terminal", "value": "$(touch /tmp/unsafe)"},
            {"action": "openSettings", "target": "audio; reboot"},
            {"action": "shell", "value": "reboot"},
        ]:
            with self.subTest(request=request):
                self.assertFalse(live.handle(request)["ok"])
        self.assertEqual(runner.calls, [])
        self.assertEqual(runner.spawns, [])

    def test_actual_audio_actions_and_failure_status(self):
        runner = FakeRunner(available={"wpctl"})
        live = self.make_backend(runner)
        self.assertTrue(live.handle({"action": "volume", "value": 42})["ok"])
        self.assertEqual(runner.calls[-1], ("wpctl", "set-volume", "--limit", "1.0", "@DEFAULT_AUDIO_SINK@", "42%"))
        self.assertTrue(live.handle({"action": "mute"})["ok"])
        self.assertEqual(runner.calls[-1], ("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"))
        runner.responses[runner.calls[-1]] = backend.CommandError("PipeWire is unavailable")
        result = live.handle({"action": "mute"})
        self.assertFalse(result["ok"])
        self.assertIn("PipeWire", result["message"])

    def test_repeated_actions_have_distinct_results_but_polling_does_not(self):
        live = self.make_backend(demo=True)
        first = live.handle({"action": "mute"})
        second = live.handle({"action": "mute"})
        self.assertEqual(first["message"], second["message"])
        self.assertEqual(second["sequence"], first["sequence"] + 1)
        self.assertEqual(live.snapshot()["lastResult"], second)
        self.assertEqual(live.snapshot()["lastResult"], second)

    def test_focus_event_bursts_reuse_telemetry_but_controls_refresh_it(self):
        volume_query = ("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
        runner = FakeRunner({volume_query: "Volume: 0.42"})
        live = self.make_backend(runner)
        live.snapshot()
        live.snapshot()
        self.assertEqual(runner.calls.count(volume_query), 1)
        self.assertTrue(live.handle({"action": "volume", "value": 55})["ok"])
        runner.responses[volume_query] = "Volume: 0.55"
        self.assertEqual(live.snapshot()["system"]["audio"]["volume"], 55)
        self.assertEqual(runner.calls.count(volume_query), 2)

    def test_workspace_id_resolves_index_on_correct_output(self):
        runner = FakeRunner(available={"niri"})
        live = self.make_backend(runner)
        live.niri = {"available": True, "workspaces": [{"id": 14, "idx": 2, "output": "HDMI-A-1"}], "windows": []}
        self.assertTrue(live.handle({"action": "workspace", "id": 14})["ok"])
        self.assertEqual(runner.calls, [("niri", "msg", "action", "focus-monitor", "HDMI-A-1"),
                                        ("niri", "msg", "action", "focus-workspace", "2")])

    def test_destructive_actions_only_on_explicit_request(self):
        runner = FakeRunner(available={"systemctl", "niri"})
        live = self.make_backend(runner)
        live.snapshot()
        self.assertFalse(any(call[0] == "systemctl" for call in runner.calls))
        runner.calls.clear()
        live.preferences.set("idleLockBeforeSleep", False)
        for action in ("suspend", "reboot", "poweroff"):
            self.assertTrue(live.handle({"action": action})["ok"])
        self.assertEqual(runner.calls, [("systemctl", "suspend"), ("systemctl", "reboot"), ("systemctl", "poweroff")])

    def test_demo_never_executes_or_saves_even_power_actions(self):
        runner = FakeRunner(available=backend.TOOLS)
        live = self.make_backend(runner, demo=True)
        for action in ("lock", "suspend", "reboot", "poweroff", "logout", "screenshot"):
            self.assertTrue(live.handle({"action": action})["ok"])
        self.assertTrue(live.handle({"action": "setting", "key": "animations", "value": False})["ok"])
        self.assertFalse(live.snapshot()["preferences"]["animations"])
        self.assertFalse(self.preferences.path.exists())
        self.assertEqual(runner.calls, [])
        self.assertEqual(runner.spawns, [])

    def test_demo_controls_update_state_without_touching_system(self):
        live = self.make_backend(demo=True)
        for request in [{"action": "volume", "value": 55}, {"action": "mute"},
                        {"action": "workspace", "id": 3}, {"action": "wifiToggle"}]:
            self.assertTrue(live.handle(request)["ok"])
        state = live.snapshot()
        self.assertEqual(state["system"]["audio"]["volume"], 55)
        self.assertTrue(state["system"]["audio"]["muted"])
        self.assertFalse(state["system"]["network"]["enabled"])
        self.assertTrue(state["niri"]["workspaces"][2]["is_focused"])
        self.assertFalse(live.handle({"action": "anything"})["ok"])
        self.assertEqual(live.runner.calls, [])

    def test_screenshot_uses_native_niri_protocol(self):
        runner = FakeRunner(available={"niri"})
        live = self.make_backend(runner)
        with patch.object(backend.time, "sleep") as delay:
            self.assertTrue(live.handle({"action": "screenshot"})["ok"])
            delay.assert_called_once_with(0.2)
        self.assertEqual(runner.calls[0][:4], ("niri", "msg", "action", "screenshot-screen"))
        self.assertEqual(runner.calls[0][4:], ('--path', live.capture.state['path']))
        self.assertEqual(live.capture.state['status'], 'pending')
        live.capture.close()

    def test_fedora_tuned_profile_uses_modern_standard_dbus_api(self):
        service = backend.POWER_PROFILE_SERVICES[0]
        query = ("busctl", "--system", "get-property", *service, "ActiveProfile")
        runner = FakeRunner({query: 's "balanced"'})
        live = self.make_backend(runner)
        self.assertEqual(live.snapshot()["system"]["powerProfile"], "balanced")
        self.assertTrue(live.handle({"action": "powerProfile", "value": "power-saver"})["ok"])
        self.assertEqual(runner.calls[-1], ("busctl", "--system", "set-property", *service, "ActiveProfile", "s", "power-saver"))
        self.assertFalse(any(call[0] == "powerprofilesctl" for call in runner.calls))

    def test_power_profile_falls_back_to_legacy_api_and_caches_endpoint(self):
        modern, legacy = backend.POWER_PROFILE_SERVICES
        modern_query = ("busctl", "--system", "get-property", *modern, "ActiveProfile")
        legacy_query = ("busctl", "--system", "get-property", *legacy, "ActiveProfile")
        runner = FakeRunner({modern_query: backend.CommandError("Name not provided"), legacy_query: 's "performance"'})
        live = self.make_backend(runner)
        self.assertEqual(live.power_profile(), "performance")
        self.assertEqual(live.power_profile(), "performance")
        self.assertEqual(runner.calls.count(modern_query), 1)
        self.assertTrue(live.handle({"action": "powerProfile", "value": "balanced"})["ok"])
        self.assertEqual(runner.calls[-1], ("busctl", "--system", "set-property", *legacy, "ActiveProfile", "s", "balanced"))

    def test_power_profile_cli_remains_supported_without_busctl(self):
        runner = FakeRunner({("powerprofilesctl", "get"): "balanced"})
        live = self.make_backend(runner)
        self.assertEqual(live.power_profile(), "balanced")
        self.assertTrue(live.handle({"action": "powerProfile", "value": "performance"})["ok"])
        self.assertEqual(runner.calls[-1], ("powerprofilesctl", "set", "performance"))

    def test_busctl_binary_without_profile_service_is_not_a_capability(self):
        queries = [("busctl", "--system", "get-property", *service, "ActiveProfile")
                   for service in backend.POWER_PROFILE_SERVICES]
        runner = FakeRunner({query: backend.CommandError("Service unknown") for query in queries})
        live = self.make_backend(runner)
        self.assertIsNone(live.snapshot()["system"]["powerProfile"])
        self.assertFalse(live.handle({"action": "powerProfile", "value": "balanced"})["ok"])
        self.assertFalse(any("set-property" in call for call in runner.calls))

    def test_malformed_profile_values_are_unavailable(self):
        modern, legacy = backend.POWER_PROFILE_SERVICES
        modern_query = ("busctl", "--system", "get-property", *modern, "ActiveProfile")
        legacy_query = ("busctl", "--system", "get-property", *legacy, "ActiveProfile")
        for output in ['s "balanced', 'u 1', 's "balanced" "extra"', 's "$(reboot)"']:
            with self.subTest(output=output):
                runner = FakeRunner({modern_query: output, legacy_query: 's "unsupported"'})
                self.assertIsNone(self.make_backend(runner).power_profile())

    def test_dbus_profile_authorization_failure_is_reported_without_retrying_writes(self):
        modern, legacy = backend.POWER_PROFILE_SERVICES
        modern_query = ("busctl", "--system", "get-property", *modern, "ActiveProfile")
        legacy_query = ("busctl", "--system", "get-property", *legacy, "ActiveProfile")
        write = ("busctl", "--system", "set-property", *modern, "ActiveProfile", "s", "balanced")
        runner = FakeRunner({modern_query: 's "power-saver"', legacy_query: 's "power-saver"',
                             write: backend.CommandError("Interactive authorization required")})
        live = self.make_backend(runner)
        result = live.handle({"action": "powerProfile", "value": "balanced"})
        self.assertFalse(result["ok"])
        self.assertIn("authorization", result["message"])
        self.assertEqual(sum("set-property" in call for call in runner.calls), 1)
        self.assertNotIn(legacy_query, runner.calls)

    def test_wallpaper_path_remains_one_argument(self):
        runner = FakeRunner(available={"awww"})
        live = self.make_backend(runner)
        path = self.put("images/picture $(touch unsafe);.png", "image fixture")
        self.assertTrue(live.handle({"action": "wallpaper", "path": str(path)})["ok"])
        self.assertEqual(runner.calls[-1][2], str(path))
        self.assertEqual(self.preferences.values["wallpaper"], str(path))
        self.assertFalse((self.root / "unsafe").exists())

    def test_command_runner_reports_missing_timeout_and_exit_status(self):
        with patch.object(backend.shutil, "which", return_value="/usr/bin/test-command"):
            runner = backend.CommandRunner()
        with patch.object(backend.subprocess, "run", side_effect=subprocess.TimeoutExpired("wpctl", 3)):
            with self.assertRaisesRegex(backend.CommandError, "timed out"):
                runner.run("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
        completed = subprocess.CompletedProcess(["wpctl"], 7, "", "No session")
        with patch.object(backend.subprocess, "run", return_value=completed) as command:
            with self.assertRaisesRegex(backend.CommandError, "failed \\(7\\): No session"):
                runner.run("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "40%")
            self.assertIsInstance(command.call_args.args[0], list)
            self.assertNotIn("shell", command.call_args.kwargs)
        runner.commands["wpctl"] = None
        with self.assertRaisesRegex(backend.CommandError, "unavailable"):
            runner.run("wpctl", "get-volume")


class DesktopEntryCase(Fixture, unittest.TestCase):
    def desktop(self, relative, **values):
        content = "[Desktop Entry]\n" + "\n".join(f"{key}={value}" for key, value in values.items())
        return self.put(relative, content)

    def test_hidden_override_nodisplay_tryexec_and_desktop_visibility(self):
        self.desktop("user/app.desktop", Type="Application", Hidden="true", Name="Hidden", Exec="true")
        self.desktop("system/app.desktop", Type="Application", Name="System", Exec="true")
        self.desktop("system/private.desktop", Type="Application", NoDisplay="true", Name="Private", Exec="true")
        self.desktop("system/missing.desktop", Type="Application", TryExec="definitely-no-such-executable", Name="Missing", Exec="true")
        self.desktop("system/hypr.desktop", Type="Application", OnlyShowIn="Hyprland;", Name="Hypr-only", Exec="true")
        self.desktop("system/niri.desktop", Type="Application", OnlyShowIn="niri;", Name="Visible", Exec="true", Terminal="true")
        apps = backend.Applications([self.root / "user", self.root / "system"])
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "niri"}):
            result = apps.scan()
        self.assertEqual([app["id"] for app in result], ["niri.desktop"])
        self.assertTrue(result[0]["terminal"])

    def test_localized_name_and_desktop_escapes(self):
        self.desktop("apps/nested/example.desktop", **{
            "Type": "Application", "Name": "Default", "Name[en_US]": r"Example\sApplication",
            "Exec": 'example "%c" %i %U', "Icon": "example-icon",
            "GenericName": "Application", "GenericName[en_US]": "Document Editor",
            "Keywords[en_US]": "notes;documents;writing;", "Comment": r"Edit\syour documents",
        })
        apps = backend.Applications([self.root / "apps"])
        with patch.dict(os.environ, {"LANG": "en_US.UTF-8", "LC_ALL": "", "LC_MESSAGES": ""}):
            result = apps.scan()
        self.assertEqual(result[0]["id"], "nested-example.desktop")
        self.assertEqual(result[0]["name"], "Example Application")
        self.assertEqual(result[0]["genericName"], "Document Editor")
        self.assertEqual(result[0]["keywords"], ["notes", "documents", "writing"])
        self.assertEqual(result[0]["comment"], "Edit your documents")
        self.assertEqual(apps.entries[result[0]["id"]]["argv"], ["example", "Example Application", "--icon", "example-icon"])

    def test_exec_preserves_literals_without_shell_expansion(self):
        value = 'example "two words" "$(touch /tmp/unsafe)" "%%" %f %F %u %U "%c" %k'
        result = backend.desktop_exec(value, "A; reboot", "", "/tmp/a b.desktop")
        self.assertEqual(result, ["example", "two words", "$(touch /tmp/unsafe)", "%", "A; reboot", "/tmp/a b.desktop"])
        self.assertEqual(backend.desktop_exec(r'example "C:\\\\folder"', "", "", ""), ["example", "C:\\folder"])
        for invalid in ("example %z", "example %", "example --files=%F", 'example "unterminated'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                backend.desktop_exec(invalid, "Example", "icon", "/tmp/app.desktop")

    def test_launch_uses_known_entry_not_caller_path(self):
        path = self.desktop("apps/safe.desktop", Type="Application", Name="Safe", Exec="echo harmless")
        runner = FakeRunner(available={"gio"})
        live = backend.DesktopBackend(runner=runner, preferences=self.preferences,
                                      apps=backend.Applications([self.root / "apps"]),
                                      proc=self.root / "proc", sysfs=self.root / "sys")
        self.assertFalse(live.handle({"action": "launch", "id": "../../malicious.desktop"})["ok"])
        self.assertEqual(runner.calls, [])
        self.assertTrue(live.handle({"action": "launch", "id": "safe.desktop"})["ok"])
        self.assertEqual(runner.calls, [("gio", "launch", str(path.resolve()))])

    def test_terminal_app_honors_user_choice_even_with_gio_installed(self):
        self.desktop("apps/console.desktop", Type="Application", Name="Console", Terminal="true",
                     Exec='console-tool "two words" %U')
        self.preferences.set("terminal", "foot")
        runner = FakeRunner(available={"gio"})
        live = backend.DesktopBackend(runner=runner, preferences=self.preferences,
                                      apps=backend.Applications([self.root / "apps"]),
                                      proc=self.root / "proc", sysfs=self.root / "sys")
        with patch.object(backend.shutil, "which", return_value="/usr/bin/foot") as lookup:
            self.assertTrue(live.handle({"action": "launch", "id": "console.desktop"})["ok"])
            lookup.assert_called_once_with("foot")
        self.assertEqual(runner.spawns, [["/usr/bin/foot", "-e", "console-tool", "two words"]])
        self.assertEqual(runner.calls, [])
        with patch.object(backend.shutil, "which", return_value=None):
            result = live.handle({"action": "launch", "id": "console.desktop"})
        self.assertFalse(result["ok"])
        self.assertIn("configured terminal", result["message"])
        self.assertEqual(len(runner.spawns), 1)


if __name__ == "__main__":
    unittest.main()
