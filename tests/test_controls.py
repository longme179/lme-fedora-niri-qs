"""Bluetooth regressions and stable-ID workspace moves, without laptop hardware."""
import json
import os
import socket
import threading
import unittest
from unittest.mock import patch

from test_backend import backend, FakeRunner, Fixture


MANAGED = ("busctl", "--system", "--json=short", "call", "org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
ADAPTER = "/org/bluez/hci0"
WRITE = ("busctl", "--system", "set-property", "org.bluez", ADAPTER, "org.bluez.Adapter1", "Powered", "b", "true")


class BluezRunner(FakeRunner):
    def __init__(self, fail=False, soft=False, missing=False):
        super().__init__(available={"busctl", "rfkill"})
        self.powered = False
        self.fail, self.soft, self.missing = fail, soft, missing

    def run(self, name, *args, **kwargs):
        self.calls.append((name, *args))
        if (name, *args) == MANAGED:
            objects = {} if self.missing else {ADAPTER: {"org.bluez.Adapter1": {"Alias": {"type": "s", "data": "Laptop"}, "Powered": {"type": "b", "data": self.powered}}}}
            return json.dumps({"type": "a{oa{sa{sv}}}", "data": [objects]})
        if args and "set-property" in args:
            if self.fail or self.soft:
                raise backend.CommandError("org.bluez.Error.Failed: Failed to power on")
            self.powered = args[-1] == "true"
        elif name == "rfkill":
            self.soft = False
        return ""


class ControlsCase(Fixture, unittest.TestCase):
    def test_bluez_sets_and_verifies_power_on_selected_adapter(self):
        runner = BluezRunner()
        result = self.make_backend(runner).handle({"action": "bluetoothToggle"})
        self.assertTrue(result["ok"], result)
        self.assertIn(WRITE, runner.calls)
        self.assertFalse(any(call[0] == "bluetoothctl" for call in runner.calls))
        self.assertTrue(runner.powered)

    def test_bluez_power_failure_is_not_reported_as_success(self):
        result = self.make_backend(BluezRunner(fail=True)).handle({"action": "bluetoothToggle"})
        self.assertFalse(result["ok"])
        self.assertIn("BlueZ", result["message"])

    def test_soft_block_recovery_is_scoped_to_bluetooth(self):
        self.put("sys/class/rfkill/rfkill4/type", "bluetooth")
        self.put("sys/class/rfkill/rfkill4/soft", "1")
        self.put("sys/class/rfkill/rfkill4/hard", "0")
        self.put("sys/class/rfkill/rfkill2/type", "wlan")
        self.put("sys/class/rfkill/rfkill2/soft", "1")
        runner = BluezRunner(soft=True)
        self.assertTrue(self.make_backend(runner).handle({"action": "bluetoothToggle"})["ok"])
        self.assertIn(("rfkill", "unblock", "4"), runner.calls)
        self.assertNotIn(("rfkill", "unblock", "2"), runner.calls)

    def test_hardware_block_does_not_attempt_writes(self):
        self.put("sys/class/rfkill/rfkill0/type", "bluetooth")
        self.put("sys/class/rfkill/rfkill0/hard", "1")
        runner = BluezRunner()
        result = self.make_backend(runner).handle({"action": "bluetoothToggle"})
        self.assertFalse(result["ok"])
        self.assertIn("hardware-blocked", result["message"])
        self.assertNotIn(WRITE, runner.calls)

    def test_adapter_service_without_controller_is_unavailable(self):
        live = self.make_backend(BluezRunner(missing=True))
        self.assertFalse(live.bluetooth()["available"])
        self.assertFalse(live.handle({"action": "bluetoothToggle"})["ok"])

    def test_cli_zero_exit_failure_is_detected(self):
        runner = FakeRunner({("bluetoothctl", "show"): "Controller AA:BB:CC:DD:EE:FF\nPowered: no",
                             ("bluetoothctl", "--timeout", "10", "power", "on"): "Failed to set power on: org.bluez.Error.Failed"})
        result = self.make_backend(runner).handle({"action": "bluetoothToggle"})
        self.assertFalse(result["ok"])
        self.assertIn("Failed", result["message"])

    def test_unconfirmed_power_change_is_an_error(self):
        runner = FakeRunner({("bluetoothctl", "show"): "Controller AA:BB:CC:DD:EE:FF\nPowered: no",
                             ("bluetoothctl", "--timeout", "10", "power", "on"): "Changing power on succeeded"})
        with patch.object(backend.time, "sleep"):
            result = self.make_backend(runner).handle({"action": "bluetoothToggle"})
        self.assertFalse(result["ok"])
        self.assertIn("did not confirm", result["message"])

    def test_workspaces_follow_output_and_numeric_index_not_response_order(self):
        workspaces = [{"id": 80, "idx": 3, "output": "eDP-1"}, {"id": 9, "idx": 1, "output": "eDP-1"},
                      {"id": 90, "idx": 2, "output": "eDP-1"}]
        live = self.make_backend(FakeRunner({("niri", "msg", "--json", "workspaces"): json.dumps(workspaces),
                                            ("niri", "msg", "--json", "windows"): "[]"}))
        self.assertEqual([item["id"] for item in live.niri_state()["workspaces"]], [9, 90, 80])

    def test_move_uses_stable_workspace_id_and_does_not_change_focus(self):
        path = str(self.root / "niri.sock")
        server = socket.socket(socket.AF_UNIX)
        server.bind(path); server.listen(1); server.settimeout(3)
        self.addCleanup(server.close)
        received = []
        def reply():
            with server.accept()[0] as client:
                with client.makefile("rb") as stream:
                    received.append(json.loads(stream.readline()))
                client.sendall(b'{"Ok":{"Handled":null}}\n')
        worker = threading.Thread(target=reply, daemon=True); worker.start()
        live = self.make_backend(FakeRunner({("niri", "msg", "--json", "workspaces"): '[{"id":90,"idx":2}]',
                                            ("niri", "msg", "--json", "windows"): '[{"id":42,"workspace_id":9}]'}))
        with patch.dict(os.environ, {"NIRI_SOCKET": path}):
            result = live.handle({"action": "moveWindow", "id": 42, "workspaceId": 90})
        worker.join(3)
        self.assertTrue(result["ok"], result)
        self.assertEqual(received, [{"Action": {"MoveWindowToWorkspace": {"window_id": 42, "reference": {"Id": 90}, "focus": False}}}])

    def test_stale_or_invalid_window_move_does_not_mutate_session(self):
        live = self.make_backend(FakeRunner({("niri", "msg", "--json", "workspaces"): '[{"id":90,"idx":2}]',
                                            ("niri", "msg", "--json", "windows"): "[]"}))
        for ident in (True, "42; reboot", 42):
            self.assertFalse(live.handle({"action": "moveWindow", "id": ident, "workspaceId": 90})["ok"])

    def test_demo_move_and_microphone_controls_never_touch_machine(self):
        live = self.make_backend(demo=True)
        self.assertTrue(live.handle({"action": "moveWindow", "id": 1, "workspaceId": 2})["ok"])
        self.assertEqual(live.snapshot()["niri"]["windows"][0]["workspace_id"], 2)
        self.assertTrue(live.handle({"action": "micMute"})["ok"])
        self.assertTrue(live.snapshot()["system"]["microphone"]["muted"])
        self.assertEqual(live.runner.calls, [])
        self.assertFalse(self.preferences.path.exists())

    def test_tasks_roundtrip_validated_private_preferences(self):
        tasks = [{"id": "123-456", "text": "Write the release notes", "done": False}]
        self.preferences.set("tasks", tasks)
        self.assertEqual(backend.Preferences(self.preferences.path).values["tasks"], tasks)
        self.assertEqual(self.preferences.path.stat().st_mode & 0o777, 0o600)
        for value in ([{"id": "x", "text": "", "done": False}], tasks * 2, "not a list"):
            with self.assertRaises(ValueError):
                self.preferences.set("tasks", value)

    def test_bluetooth_device_path_cannot_invoke_other_dbus_objects(self):
        live = self.make_backend(BluezRunner())
        for path in ("/org/bluez/hci0", "/org/freedesktop/login1", "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"):
            self.assertFalse(live.handle({"action": "bluetoothDevice", "path": path, "connected": True})["ok"])
