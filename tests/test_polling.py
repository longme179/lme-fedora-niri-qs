"""Controlled hardware polling: no live devices or network mutations."""
import json
import unittest
from unittest.mock import patch

from action_test_helpers import complete_action, bluez_runner
from test_backend import Fixture, FakeRunner, backend

RADIO = ("nmcli", "radio", "wifi")
SUMMARY = ("nmcli", "-t", "-m", "multiline", "-f", backend.NETWORK_SUMMARY_FIELDS, "device", "show")
NETWORKS = ("nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY,BSSID,DEVICE", "device", "wifi", "list", "--rescan", "no")
SAVED = ("nmcli", "-t", "-f", "UUID,TYPE,NAME", "connection", "show")
BLUEZ = ("busctl", "--system", "--json=short", "call", "org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
MODERN, LEGACY = backend.POWER_PROFILE_SERVICES


def profile_query(service, name):
    return ("busctl", "--system", "get-property", *service, name)


class PollingCase(Fixture, unittest.TestCase):
    def hardware_runner(self):
        return bluez_runner(BLUEZ, MODERN)

    def wifi_runner(self):
        return FakeRunner({RADIO: "enabled", SUMMARY:
            "GENERAL.DEVICE:wlan0\nGENERAL.TYPE:wifi\nGENERAL.STATE:100 (connected)\n"
            "AP[1].IN-USE:\nAP[1].SSID:Other\nAP[1].SIGNAL:90\n"
            "AP[2].IN-USE:*\nAP[2].SSID:Home\\:5G\nAP[2].SIGNAL:84",
            NETWORKS: "yes:Home\\:5G:84:WPA2:AA\\:BB\\:CC\\:DD\\:EE\\:FF:wlan0\nno:Other:90:--:11\\:22\\:33\\:44\\:55\\:66:wlan0",
            SAVED: "safe-uuid:802-11-wireless:My profile"})

    def test_privacy_has_its_own_cadence_even_during_forced_hardware_samples(self):
        runner = FakeRunner({("pw-dump",): "[]"})
        live = self.make_backend(runner)
        with patch.object(backend.time, "monotonic") as clock:
            for stamp in [100, 100.1, 102, 104.9]:
                clock.return_value = stamp
                live.system_cache = None
                self.assertTrue(live.snapshot()["system"]["privacy"]["available"])
            self.assertEqual(runner.calls.count(("pw-dump",)), 1)
            clock.return_value = 105
            live.snapshot()
            self.assertEqual(runner.calls.count(("pw-dump",)), 2)

    def test_privacy_disable_reenable_failure_and_pipewire_reconnect(self):
        node = {"id": 7, "type": "PipeWire:Interface:Node", "info": {"state": "running",
                "props": {"media.class": "Stream/Input/Audio", "application.name": "Meeting"}}}
        runner = FakeRunner({("pw-dump",): json.dumps([node])})
        live = self.make_backend(runner)
        with patch.object(backend.time, "monotonic", return_value=100) as clock:
            self.assertEqual(live.snapshot()["system"]["privacy"]["captures"][0]["id"], 7)
            self.preferences.update({"privacyIndicators": False, "dndWhileSharing": False})
            self.assertEqual(live.snapshot()["system"]["privacy"]["captures"], [])
            self.assertEqual(runner.calls.count(("pw-dump",)), 1)
            self.preferences.set("dndWhileSharing", True)
            runner.responses[("pw-dump",)] = backend.CommandError("PipeWire disconnected")
            self.assertFalse(live.snapshot()["system"]["privacy"]["available"])
            self.assertEqual(live.privacy()["captures"], [])
            node["id"] = 8
            runner.responses[("pw-dump",)] = json.dumps([node])
            clock.return_value = 105
            self.assertEqual(live.snapshot()["system"]["privacy"]["captures"][0]["id"], 8)
            self.assertEqual(runner.calls.count(("pw-dump",)), 3)

    def test_privacy_refreshes_after_actions_and_recording_completion(self):
        runner = FakeRunner({("pw-dump",): "[]"}, available=("wpctl",))
        live = self.make_backend(runner)
        with patch.object(backend.time, "monotonic", return_value=100), patch.object(live, "perform", return_value="Done"):
            live.snapshot()
            for action in ["refresh", "micMute", "recordStart", "recordStop", "mirrorStart", "mirrorStop"]:
                runner.calls.clear()
                self.assertTrue(live.handle({"action": action})["ok"])
                live.snapshot()
                self.assertIn(("pw-dump",), runner.calls)
            from concurrent.futures import Future
            job = Future(); job.set_result("Recording started")
            live.feature_jobs["recordStart"] = job
            runner.calls.clear()
            live.snapshot()
            self.assertIn(("pw-dump",), runner.calls)

    def test_wifi_lists_only_follow_subscription_and_refresh_on_open_close(self):
        runner = self.wifi_runner(); live = self.make_backend(runner)
        with patch.object(backend.time, "monotonic", return_value=100) as clock:
            network = live.snapshot()["system"]["network"]
            self.assertEqual((network["ssid"], network["strength"], network["wifiConnected"]), ("Home:5G", 84, True))
            self.assertEqual((network["networks"], network["saved"]), ([], []))
            self.assertEqual(runner.calls, [RADIO, SUMMARY])
            self.assertTrue(live.handle({"action": "wifiWatch", "enabled": True})["ok"])
            network = live.snapshot()["system"]["network"]
            self.assertEqual([n["ssid"] for n in network["networks"]], ["Home:5G", "Other"])
            self.assertEqual(network["saved"][0]["uuid"], "safe-uuid")
            runner.calls.clear()
            live.handle({"action": "wifiWatch", "enabled": True}); live.snapshot()
            self.assertEqual(runner.calls, [])
            live.handle({"action": "wifiWatch", "enabled": False})
            network = live.snapshot()["system"]["network"]
            self.assertEqual((network["networks"], network["saved"]), ([], []))
            self.assertEqual(runner.calls, [RADIO, SUMMARY])
            runner.calls.clear(); clock.return_value = 102; live.snapshot()
            self.assertEqual(runner.calls, [RADIO, SUMMARY])

    def test_wifi_summary_handles_device_changes_disconnect_and_service_reconnect(self):
        runner = self.wifi_runner(); live = self.make_backend(runner)
        live.handle({"action": "wifiWatch", "enabled": True})
        with patch.object(backend.time, "monotonic", return_value=100) as clock:
            live.snapshot()
            runner.responses[SUMMARY] = "GENERAL.DEVICE:wlan1\nGENERAL.TYPE:wifi\nGENERAL.STATE:100 (connected)\nAP[1].IN-USE:*\nAP[1].SSID:New\\\\name\nAP[1].SIGNAL:65"
            runner.responses[NETWORKS] = "yes:New\\\\name:65:WPA3:11\\:22\\:33\\:44\\:55\\:66:wlan1\nno:Stale:80:--:AA:wlan0"
            clock.return_value = 102
            network = live.snapshot()["system"]["network"]
            self.assertEqual((network["device"], network["ssid"], network["strength"]), ("wlan1", "New\\name", 65))
            self.assertEqual([n["ssid"] for n in network["networks"]], ["New\\name"])
            with self.assertRaises(ValueError): live.wifi_action("wifiScan", {"device": "wlan0"})
            runner.responses[RADIO] = "disabled"
            runner.responses[SUMMARY] = "GENERAL.DEVICE:wlan1\nGENERAL.TYPE:wifi\nGENERAL.STATE:20 (unavailable)\nGENERAL.DEVICE:eth0\nGENERAL.TYPE:ethernet\nGENERAL.STATE:100 (connected)"
            clock.return_value = 104
            network = live.snapshot()["system"]["network"]
            self.assertEqual((network["connected"], network["wifiConnected"], network["ssid"], network["strength"]), (True, False, "Ethernet", None))
            self.assertEqual(network["networks"], [])
            runner.responses[RADIO] = backend.CommandError("NetworkManager stopped")
            clock.return_value = 106
            network = live.snapshot()["system"]["network"]
            self.assertFalse(network["available"])
            self.assertEqual((network["device"], network["networks"], network["saved"]), ("", [], []))
            runner.responses.update(self.wifi_runner().responses)
            clock.return_value = 108
            self.assertEqual(live.snapshot()["system"]["network"]["ssid"], "Home:5G")

    def test_wifi_subscription_validation_and_late_action_completion(self):
        from concurrent.futures import Future
        runner = self.wifi_runner(); live = self.make_backend(runner)
        for value in [None, 1, "true"]:
            self.assertFalse(live.handle({"action": "wifiWatch", "enabled": value})["ok"])
        with patch.object(backend.time, "monotonic", return_value=100):
            live.handle({"action": "wifiWatch", "enabled": True}); live.snapshot()
            live.handle({"action": "wifiWatch", "enabled": False}); live.snapshot()
            runner.responses[SUMMARY] = "GENERAL.DEVICE:wlan0\nGENERAL.TYPE:wifi\nGENERAL.STATE:30 (disconnected)"
            for action in ["wifiScan", "wifiConnect", "wifiSaved", "wifiDisconnect", "wifiForget"]:
                for failed in [False, True]:
                    job = Future()
                    if failed: job.set_exception(backend.CommandError("Connection failed"))
                    else: job.set_result("Completed")
                    live.feature_jobs[action] = job
                    runner.calls.clear()
                    state = live.snapshot()
                    self.assertEqual(state["lastResult"]["ok"], not failed)
                    self.assertFalse(state["system"]["network"]["wifiConnected"])
                    self.assertEqual(state["system"]["network"]["networks"], [])
                    self.assertEqual(runner.calls, [RADIO, SUMMARY])
        settings = backend.DesktopBackend(runner=runner, preferences=self.preferences, settings_only=True, weather_fetch=False)
        self.assertFalse(settings.handle({"action": "wifiWatch", "enabled": True})["ok"])
        self.assertFalse(settings.wifi_watching)

    def test_stale_ap_rows_cannot_overwrite_the_connection_summary(self):
        runner = self.wifi_runner(); live = self.make_backend(runner)
        runner.responses[SUMMARY] = "GENERAL.DEVICE:wlan0\nGENERAL.TYPE:wifi\nGENERAL.STATE:30 (disconnected)"
        state = live.network(details=True)
        self.assertEqual((state["connected"], state["wifiConnected"], state["ssid"], state["strength"]), (False, False, "", None))
        self.assertFalse(any(row["connected"] for row in state["networks"]))
        runner.responses[SUMMARY] = "GENERAL.DEVICE:wlan0\nGENERAL.TYPE:wifi\nGENERAL.STATE:100 (connected)\nAP[1].IN-USE:*\nAP[1].SSID:Roamed\nAP[1].SIGNAL:72"
        state = live.network(details=True)
        self.assertEqual((state["ssid"], state["strength"]), ("Roamed", 72))
        self.assertFalse(any(row["connected"] for row in state["networks"]))

    def test_bluez_and_profiles_have_independent_cadence_and_panel_refresh(self):
        runner, _ = self.hardware_runner(); live = self.make_backend(runner)
        with patch.object(backend.time, "monotonic", return_value=100) as clock:
            for stamp in [100, 102, 104.9]:
                clock.return_value = stamp; live.snapshot()
            for call in [BLUEZ, profile_query(MODERN, "ActiveProfile"), profile_query(MODERN, "Profiles")]:
                self.assertEqual(runner.calls.count(call), 1)
            clock.return_value = 105; live.snapshot()
            for call in [BLUEZ, profile_query(MODERN, "ActiveProfile"), profile_query(MODERN, "Profiles")]:
                self.assertEqual(runner.calls.count(call), 2)
            runner.calls.clear(); clock.return_value = 105.1
            self.assertTrue(live.handle({"action": "controlsRefresh"})["ok"])
            live.snapshot()
            self.assertEqual(runner.calls, [BLUEZ, profile_query(MODERN, "ActiveProfile"), profile_query(MODERN, "Profiles")])
            runner.calls.clear()
            with patch.object(live, "perform", return_value="Done"):
                for action in ["volume", "micVolume", "brightness", "wifiToggle"]:
                    live.handle({"action": action}); live.snapshot()
            self.assertEqual(runner.calls, [])

    def test_bluez_adapter_selection_removal_and_service_reconnect(self):
        runner, objects = self.hardware_runner(); live = self.make_backend(runner)
        with patch.object(backend.time, "monotonic", return_value=100) as clock:
            self.assertEqual(live.snapshot()["system"]["bluetooth"]["adapter"], "/org/bluez/hci0")
            live.handle({"action": "setting", "key": "bluetoothAdapter", "value": "/org/bluez/hci1"})
            state = live.snapshot()["system"]["bluetooth"]
            self.assertEqual(state["adapter"], "/org/bluez/hci1")
            self.assertEqual(state["devices"][0]["name"], "Headset 1")
            old_device = "/org/bluez/hci1/dev_AA_BB_CC_DD_EE_FF"
            del objects["/org/bluez/hci1"]; del objects[old_device]
            runner.responses[BLUEZ] = json.dumps({"data": [objects]})
            clock.return_value = 105
            state = live.snapshot()["system"]["bluetooth"]
            self.assertEqual(state["adapter"], "/org/bluez/hci0")
            self.assertFalse(complete_action(live, {"action": "bluetoothDevice", "path": old_device, "connected": True})["ok"])
            runner.responses[BLUEZ] = backend.CommandError("BlueZ disconnected")
            clock.return_value = 110
            state = live.snapshot()["system"]["bluetooth"]
            self.assertFalse(state["available"]); self.assertEqual(state["devices"], [])
            runner.responses[BLUEZ] = json.dumps({"data": [objects]})
            clock.return_value = 115
            self.assertTrue(live.snapshot()["system"]["bluetooth"]["available"])

    def test_profile_provider_restart_changes_active_and_capabilities_together(self):
        runner, _ = self.hardware_runner(); live = self.make_backend(runner)
        with patch.object(backend.time, "monotonic", return_value=100) as clock:
            live.snapshot()
            runner.responses[profile_query(MODERN, "ActiveProfile")] = backend.CommandError("Service stopped")
            runner.responses[profile_query(LEGACY, "ActiveProfile")] = 's "power-saver"'
            runner.responses[profile_query(LEGACY, "Profiles")] = 'aa{sv} 2 1 "Profile" s "balanced" 1 "Profile" s "power-saver"'
            clock.return_value = 105
            system = live.snapshot()["system"]
            self.assertEqual((system["powerProfile"], system["powerProfiles"]), ("power-saver", ["power-saver", "balanced"]))
            self.assertEqual(live.power_profile_provider, ("dbus", *LEGACY))
            runner.responses[profile_query(LEGACY, "ActiveProfile")] = backend.CommandError("Service stopped")
            clock.return_value = 110
            system = live.snapshot()["system"]
            self.assertEqual((system["powerProfile"], system["powerProfiles"]), (None, []))
            runner.responses[profile_query(MODERN, "ActiveProfile")] = 's "performance"'
            runner.responses[profile_query(MODERN, "Profiles")] = 'aa{sv} 1 1 "Profile" s "performance"'
            clock.return_value = 115
            system = live.snapshot()["system"]
            self.assertEqual((system["powerProfile"], system["powerProfiles"]), ("performance", ["performance"]))

    def test_bluez_and_profile_actions_invalidate_even_after_partial_failure(self):
        runner, objects = self.hardware_runner(); live = self.make_backend(runner)
        path = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
        disconnect = ("busctl", "--system", "call", "org.bluez", path, "org.bluez.Device1", "Disconnect")
        failed_profile = ("busctl", "--system", "set-property", *MODERN, "ActiveProfile", "s", "performance")
        runner.responses[disconnect] = backend.CommandError("Disconnected before failure")
        runner.responses[failed_profile] = backend.CommandError("Changed before failure")
        original = runner.run
        def write(name, *args, **kwargs):
            if args[:3] == ("--system", "set-property", "org.bluez"):
                objects[args[3]]["org.bluez.Adapter1"]["Powered"] = args[-1] == "true"
            if args[:3] == ("--system", "call", "org.bluez") and args[-1] in {"Connect", "Disconnect"}:
                objects[args[3]]["org.bluez.Device1"]["Connected"] = args[-1] == "Connect"
            if args[:2] == ("--system", "set-property") and args[2] == MODERN[0]:
                runner.responses[profile_query(MODERN, "ActiveProfile")] = 's "' + args[-1] + '"'
            runner.responses[BLUEZ] = json.dumps({"data": [objects]})
            return original(name, *args, **kwargs)
        runner.run = write
        with patch.object(backend.time, "monotonic", return_value=100):
            live.snapshot()
            for enabled in [False, True]:
                self.assertTrue(live.handle({"action": "bluetoothToggle"})["ok"])
                self.assertEqual(live.snapshot()["system"]["bluetooth"]["enabled"], enabled)
            for connected in [True, False]:
                result = complete_action(live, {"action": "bluetoothDevice", "path": path, "connected": connected})
                self.assertEqual(result["ok"], connected)
                self.assertEqual(live.snapshot()["system"]["bluetooth"]["devices"][0]["connected"], connected)
            for profile, ok in [("power-saver", True), ("performance", False)]:
                self.assertEqual(live.handle({"action": "powerProfile", "value": profile})["ok"], ok)
                self.assertEqual(live.snapshot()["system"]["powerProfile"], profile)

    def test_closed_panels_keep_probe_counts_bounded_over_thirty_seconds(self):
        hardware, _ = self.hardware_runner()
        runner = self.wifi_runner()
        runner.responses.update(hardware.responses)
        runner.responses.update({("pw-dump",): "[]", ("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"): "Volume: 0.5",
            ("wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"): "Volume: 0.5"})
        runner.names.update({"pw-dump", "busctl", "wpctl"})
        live = self.make_backend(runner)
        with patch.object(backend.time, "monotonic") as clock:
            for stamp in range(100, 131, 2):
                clock.return_value = stamp
                live.snapshot()
        self.assertEqual(runner.calls.count(RADIO), 16)
        self.assertEqual(runner.calls.count(SUMMARY), 16)
        self.assertNotIn(NETWORKS, runner.calls); self.assertNotIn(SAVED, runner.calls)
        for call in [BLUEZ, profile_query(MODERN, "ActiveProfile"), profile_query(MODERN, "Profiles"), ("pw-dump",)]:
            self.assertLessEqual(runner.calls.count(call), 6)
        self.assertEqual(sum(call[0] == "wpctl" for call in runner.calls), 32)
        self.assertLessEqual(len(runner.calls), 88)

    def test_volume_drag_reads_only_the_changed_control_until_the_regular_sample(self):
        query = ("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
        runner = self.wifi_runner()
        runner.responses[query] = "Volume: 0.3"; runner.names.add("wpctl")
        live = self.make_backend(runner)
        with patch.object(backend.time, "monotonic", return_value=100) as clock:
            live.snapshot(); runner.calls.clear()
            for index, value in enumerate(range(40, 50)):
                clock.return_value = 100 + index / 10
                self.assertTrue(live.handle({"action": "volume", "value": value})["ok"])
                runner.responses[query] = f"Volume: {value / 100}"
                self.assertEqual(live.snapshot()["system"]["audio"]["volume"], value)
            self.assertEqual(len(runner.calls), 20)  # Ten writes and ten sink readbacks.
            self.assertTrue(all(call[0] == "wpctl" for call in runner.calls))
            self.assertEqual(runner.calls.count(query), 10)
            self.assertEqual(live.last_system_sample, 100)
            runner.responses[SUMMARY] = "GENERAL.DEVICE:wlan1\nGENERAL.TYPE:wifi\nGENERAL.STATE:30 (disconnected)"
            clock.return_value = 102
            self.assertEqual(live.snapshot()["system"]["network"]["device"], "wlan1")
            self.assertEqual(runner.calls.count(SUMMARY), 1)

    def test_control_readbacks_handle_partial_failures_without_refreshing_wifi_lists(self):
        sink = ("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
        source = ("wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@")
        backlight = ("brightnessctl", "--class=backlight", "-m")
        cases = [
            ("volume", {"value": 63}, ("wpctl", "set-volume", "--limit", "1.0", "@DEFAULT_AUDIO_SINK@", "63%"), sink, "Volume: 0.63", "audio", "volume", 63),
            ("mute", {}, ("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"), sink, "Volume: 0.63 [MUTED]", "audio", "muted", True),
            ("micVolume", {"value": 34}, ("wpctl", "set-volume", "--limit", "1.0", "@DEFAULT_AUDIO_SOURCE@", "34%"), source, "Volume: 0.34", "microphone", "volume", 34),
            ("micMute", {}, ("wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"), source, "Volume: 0.34 [MUTED]", "microphone", "muted", True),
            ("brightness", {"value": 72}, ("brightnessctl", "--class=backlight", "set", "72%"), backlight, "panel,backlight,72,72%,100", "brightness", "percent", 72),
        ]
        runner = self.wifi_runner(); runner.names.update({"wpctl", "brightnessctl"})
        live = self.make_backend(runner)
        live.handle({"action": "wifiWatch", "enabled": True})
        with patch.object(backend.time, "monotonic", return_value=100):
            live.snapshot()
            for action, payload, write, query, output, field, key, expected in cases:
                for failed in (False, True):
                    with self.subTest(action=action, failed=failed):
                        runner.calls.clear()
                        runner.responses[write] = backend.CommandError("Partially applied") if failed else ""
                        runner.responses[query] = output
                        self.assertEqual(live.handle({"action": action, **payload})["ok"], not failed)
                        self.assertEqual(live.snapshot()["system"][field][key], expected)
                        self.assertEqual(runner.calls, [write, query])
            runner.names.remove("wpctl")
            self.assertFalse(live.handle({"action": "volume", "value": 60})["ok"])
            self.assertFalse(live.snapshot()["system"]["audio"]["available"])
            runner.names.add("wpctl")
            runner.responses[cases[0][2]] = ""
            self.assertTrue(live.handle({"action": "volume", "value": 63})["ok"])
            self.assertTrue(live.snapshot()["system"]["audio"]["available"])
