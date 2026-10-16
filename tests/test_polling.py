"""Controlled hardware polling: no live devices or network mutations."""
import json
import unittest
from unittest.mock import patch

from test_backend import Fixture, FakeRunner, backend

RADIO = ("nmcli", "radio", "wifi")
SUMMARY = ("nmcli", "-t", "-m", "multiline", "-f", backend.NETWORK_SUMMARY_FIELDS, "device", "show")
NETWORKS = ("nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY,BSSID,DEVICE", "device", "wifi", "list", "--rescan", "no")
SAVED = ("nmcli", "-t", "-f", "UUID,TYPE,NAME", "connection", "show")


class PollingCase(Fixture, unittest.TestCase):
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
        runner = FakeRunner({("pw-dump",): "[]"})
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
