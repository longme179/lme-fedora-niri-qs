"""Real QML/backend protocol with simulated command boundaries on private Wayland."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


FAKE_BACKEND = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["LME_TEST_REPO"] + "/scripts")
import desktop_backend as backend
from display_control import write_json

state_path = Path(os.environ["LME_TEST_HARDWARE"])
def escape(value): return str(value).replace("\\", "\\\\").replace(":", "\\:")

class Runner:
    def available(self, name): return name in {"nmcli", "busctl", "wpctl", "pw-dump"}
    def executable(self, name): raise backend.CommandError("Unexpected executable: " + name)
    def spawn(self, argv): raise backend.CommandError("Unexpected spawn")
    def run(self, name, *args, **kwargs):
        with open(os.environ["LME_TEST_COMMANDS"], "a") as log: log.write(json.dumps([name, *args]) + "\n")
        state = json.loads(state_path.read_text())
        def save(): write_json(state_path, state); return ""
        if name == "wpctl": return "Volume: 0.5"
        if name == "pw-dump": return "[]"
        if name == "nmcli":
            if not state["networkUp"]: raise backend.CommandError("NetworkManager stopped")
            if args == ("radio", "wifi"): return "enabled"
            if args[-2:] == ("device", "show"):
                return "\n".join(["GENERAL.DEVICE:" + state["device"], "GENERAL.TYPE:wifi",
                    "GENERAL.STATE:" + ("100 (connected)" if state["connected"] else "30 (disconnected)"),
                    "AP[1].IN-USE:" + ("*" if state["connected"] else ""),
                    "AP[1].SSID:" + escape(state["ssid"]), "AP[1].SIGNAL:84"])
            if "list" in args:
                return ("yes" if state["connected"] else "no") + ":" + escape(state["ssid"]) + ":84:WPA2:AA\\:BB\\:CC\\:DD\\:EE\\:FF:" + state["device"]
            if args == ("-t", "-f", "UUID,TYPE,NAME", "connection", "show"): return "saved-id:802-11-wireless:Saved profile"
            if "disconnect" in args: state["connected"] = False; return save()
            if "up" in args: state["connected"] = True; return save()
        if name == "busctl":
            if "org.bluez" in args:
                if not state["bluezUp"]: raise backend.CommandError("BlueZ stopped")
                if "GetManagedObjects" in args:
                    objects = {}
                    for index in [0, 1]:
                        path = "/org/bluez/hci" + str(index)
                        objects[path] = {"org.bluez.Adapter1": {"Alias": "Adapter " + str(index), "Powered": state["powered"]}}
                        objects[path + "/dev_AA_BB_CC_DD_EE_FF"] = {"org.bluez.Device1": {"Alias": "Headset", "Paired": True, "Connected": False}}
                    return json.dumps({"data": [objects]})
                if "Powered" in args: state["powered"] = args[-1] == "true"; return save()
            else:
                if not state["powerUp"]: raise backend.CommandError("Power-profile service stopped")
                if "set-property" in args: state["profile"] = args[-1]; return save()
                if args[-1] == "ActiveProfile": return 's "' + state["profile"] + '"'
                if args[-1] == "Profiles": return 'aa{sv} 2 1 "Profile" s "balanced" 1 "Profile" s "power-saver"'
        raise backend.CommandError("Unexpected fake command: " + str((name, args)))

constructor = backend.DesktopBackend
def isolated_backend(**kwargs):
    kwargs.update(runner=Runner(), apps=backend.Applications([]), weather_fetch=False, manage_idle=False,
                  proc=state_path.parent / "proc", sysfs=state_path.parent / "sys")
    return constructor(**kwargs)
backend.DesktopBackend = isolated_backend
raise SystemExit(backend.main())
'''


@unittest.skipUnless(os.environ.get("LME_TEST_POLLING_UI") == "1", "requires private Wayland and D-Bus session")
class NativePollingCase(unittest.TestCase):
    def test_live_protocol_panel_lifecycle_operations_devices_and_reconnect(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode="w+") as log:
            root = Path(directory)
            for name in ("qml", "scripts", "config", "assets"):
                (root / name).symlink_to(repo / name, target_is_directory=True)
            hardware = root / "hardware.json"; commands = root / "commands.jsonl"
            values = dict(networkUp=True, bluezUp=True, powerUp=True, powered=True, connected=True,
                          device="wlan0", ssid="Home:5G", profile="balanced")
            def update(**changes):
                values.update(changes)
                temporary = hardware.with_suffix(".new")
                temporary.write_text(json.dumps(values)); temporary.replace(hardware)
            update()
            script = root / "backend.py"; script.write_text(FAKE_BACKEND)
            binary = root / "bin/python3"; binary.parent.mkdir()
            binary.write_text(f"""#!{sys.executable}
import os, sys
from pathlib import Path
args = sys.argv[1:]
if len(args) > 1 and args[0] == "-u" and Path(args[1]).name == "desktop_backend.py":
    args[1] = {str(script)!r}
os.execv({sys.executable!r}, [{sys.executable!r}, *args])
""")
            binary.chmod(0o700)
            entry = root / "shell.qml"
            entry.write_text('''//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/panels"
import "qml/services"
ShellRoot {
    id: root
    property string mode: ""
    property int disconnects: 0
    Connections { target: ShellState; function onBackendReadyChanged() { if (!ShellState.backendReady) root.disconnects++; } }
    FloatingWindow {
        implicitWidth: 1000; implicitHeight: 1000
        Loader { anchors.fill: parent; active: !!root.mode; sourceComponent: root.mode === "wifi" ? wifi : center }
    }
    Component { id: wifi; WifiPanel {} }
    Component { id: center; ControlCenter {} }
    IpcHandler {
        target: "pollingFixture"
        function navigate(mode: string): void { ShellState.controlTab = 2; root.mode = mode; }
        function action(request: string): void { const data = JSON.parse(request); ShellState.run(data.action, data); }
        function restart(): void { ShellState.backend.running = false; }
        function state(): string { return JSON.stringify({ready: ShellState.backendReady, system: ShellState.system,
            last: ShellState.lastResult, wifiResult: ShellState.wifiResult, pending: ShellState.pendingActions,
            consumers: ShellState.wifiConsumers.length, disconnects: root.disconnects}); }
    }
}''')
            env = dict(os.environ, PATH=str(binary.parent) + os.pathsep + os.environ["PATH"],
                       LME_SHELL_DEMO="0", LME_SHELL_PREVIEW="0", LME_SHELL_BACKEND_DEMO="0",
                       LME_TEST_REPO=str(repo), LME_TEST_HARDWARE=str(hardware), LME_TEST_COMMANDS=str(commands),
                       XDG_CONFIG_HOME=str(root / "home"), XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"),
                       DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(root / "no-system-bus"))
            process = subprocess.Popen(["quickshell", "-p", str(entry)], env=env, stdout=log, stderr=log)
            def ipc(method, *args):
                return subprocess.check_output(["quickshell", "-p", str(entry), "ipc", "call", "pollingFixture", method, *args],
                                               env=env, text=True, timeout=5).strip()
            def wait(predicate, timeout=12):
                deadline = time.monotonic() + timeout; state = {}
                while time.monotonic() < deadline:
                    try: state = json.loads(ipc("state"))
                    except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired): pass
                    if predicate(state): return state
                    time.sleep(.08)
                log.seek(0); self.fail(str(state) + "\n" + log.read())
            def calls():
                return [json.loads(line) for line in commands.read_text().splitlines()] if commands.exists() else []
            def detailed():
                return sum("list" in call or "UUID,TYPE,NAME" in call for call in calls())
            def action(name, **data):
                ipc("action", json.dumps(dict(action=name, **data)))
                return wait(lambda s: (s.get("last") or {}).get("action") == name and not s["last"].get("pending"))
            try:
                state = wait(lambda s: s.get("ready"))
                self.assertEqual(state["system"]["network"]["networks"], [])
                self.assertEqual(detailed(), 0)
                ipc("navigate", "wifi")
                wait(lambda s: s["consumers"] == 1 and len(s["system"]["network"]["saved"]) == 1)
                ipc("navigate", "")
                wait(lambda s: s["consumers"] == 0 and not s["system"]["network"]["networks"])
                count = detailed(); summaries = sum("device" in c and "show" in c for c in calls())
                wait(lambda s: sum("device" in c and "show" in c for c in calls()) > summaries)
                self.assertEqual(detailed(), count, "Closed widgets must stop detailed queries")
                ipc("navigate", "devices")
                wait(lambda s: s["consumers"] == 1 and bool(s["system"]["network"]["networks"]))
                update(device="wlan1", ssid="Changed:5G")
                action("setting", key="bluetoothAdapter", value="/org/bluez/hci1")
                state = wait(lambda s: s["system"]["network"]["device"] == "wlan1" and s["system"]["bluetooth"]["adapter"] == "/org/bluez/hci1")
                self.assertEqual(state["system"]["network"]["ssid"], "Changed:5G")
                state = action("wifiDisconnect")
                self.assertTrue(state["last"]["ok"]); self.assertFalse(state["system"]["network"]["wifiConnected"])
                state = action("wifiSaved", uuid="saved-id")
                self.assertTrue(state["last"]["ok"]); self.assertTrue(state["system"]["network"]["wifiConnected"])
                state = action("bluetoothToggle")
                self.assertTrue(state["last"]["ok"]); self.assertFalse(state["system"]["bluetooth"]["enabled"])
                state = action("powerProfile", value="power-saver")
                self.assertTrue(state["last"]["ok"]); self.assertEqual(state["system"]["powerProfile"], "power-saver")
                # Preserve mutations made by the fake command worker before external changes.
                values.update(json.loads(hardware.read_text()))
                update(networkUp=False, bluezUp=False, powerUp=False)
                wait(lambda s: not s["system"]["network"]["available"] and not s["system"]["bluetooth"]["available"] and s["system"]["powerProfile"] is None)
                update(networkUp=True, bluezUp=True, powerUp=True)
                wait(lambda s: s["system"]["network"]["wifiConnected"] and s["system"]["bluetooth"]["available"] and s["system"]["powerProfile"] == "power-saver")
                ipc("restart")
                state = wait(lambda s: s["disconnects"] > 0 and s["ready"] and s["consumers"] == 1 and bool(s["system"]["network"]["networks"]))
                self.assertEqual(state["system"]["bluetooth"]["adapter"], "/org/bluez/hci1")
                ipc("navigate", "")
                wait(lambda s: s["consumers"] == 0 and not s["system"]["network"]["saved"])
            finally:
                process.terminate(); process.wait(timeout=6)
            log.seek(0); output = log.read()
            for error in ("ReferenceError", "TypeError", "Failed to load configuration", "Unable to assign"):
                self.assertNotIn(error, output)
