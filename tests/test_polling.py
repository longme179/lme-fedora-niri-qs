"""Controlled hardware polling: no live devices or network mutations."""
import json
import unittest
from unittest.mock import patch

from test_backend import Fixture, FakeRunner, backend


class PollingCase(Fixture, unittest.TestCase):
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
