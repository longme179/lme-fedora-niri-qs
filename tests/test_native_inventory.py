"""Q3 final leg: the inventory families (audio device actions, network plans/profiles) port to QML.
Contract: test_native_inventory.py covers native_inventory behavior/contracts; check imports for fixtures/helpers under test.
"""
import importlib  # Contract: test_native_inventory.py (Q3 inventory families; headroom 0, trailing note)
import json
import shutil
import unittest
from pathlib import Path

import test_local_qml as qml_tests

ROOT = Path(__file__).resolve().parents[1]

AUDIO_DEVICE_STATE = ROOT / "qml/services/AudioDeviceState.qml"
AUDIO_DEVICE_MODEL = ROOT / "qml/services/AudioDeviceModel.js"
NETWORK_INVENTORY_STATE = ROOT / "qml/services/NetworkInventoryState.qml"
NETWORK_MODEL = ROOT / "qml/services/NetworkModel.js"
NETWORK_PLANS = ROOT / "qml/services/NetworkPlans.js"
COMMAND_RUNNER = ROOT / "qml/services/CommandRunner.qml"
DIGEST = ROOT / "qml/services/Digest.js"
SHELL_STATE = ROOT / "qml/services/ShellState.qml"
NATIVE_STATE = ROOT / "qml/services/NativeState.qml"
QMkdir = ROOT / "qml/services/qmldir"
AUDIO_MIXER = ROOT / "qml/panels/AudioMixer.qml"
NETWORK_POPUP = ROOT / "qml/panels/NetworkConnectionsPopup.qml"
AUDIO_DEVICE_ACTIONS = ROOT / "scripts/audio_device_actions.py"
WIFI_ACTIONS = ROOT / "scripts/wifi_actions.py"

# The user-facing messages the backend contract established (scripts/audio_devices.py,
# scripts/audio_inventory.py, scripts/audio_pipewire.py, scripts/audio_device_actions.py,
# scripts/network_profiles.py, scripts/network_inventory.py, scripts/network_plans.py,
# scripts/wifi_actions.py::provide_connections); the native port must produce the same
# strings so the toast/dialog UX is identical.
PINNED_MESSAGES = [
    "Install pulseaudio-utils (pactl) to use ports, profiles and app outputs",
    "Audio devices refreshed",
    "Audio profile confirmed",
    "Audio port confirmed",
    "Application output confirmed",
    "Unable to confirm the requested audio change; showing the observed state",
    "Audio server changed; refresh devices before retrying",
    "Audio server changed while reading devices; refresh",
    "Audio server changed before confirmation; refresh",
    "Audio server returned invalid JSON",
    "Audio operation timed out; refresh to check the actual state",
    "Audio node changed or is ambiguous; refresh devices",
    "Invalid PipeWire inventory",
    "Audio server does not match the local PipeWire core; use Advanced audio settings",
    "Install NetworkManager/nmcli and systemd busctl to manage connections",
    "NetworkManager identity is unavailable",
    "NetworkManager changed during inspection; refresh",
    "Network connections refreshed",
    "Network editor opened",
    "Saved connection changed; refresh before editing",
    "Refresh network connections before retrying",
    "Review and confirm the hotspot warning first",
    "NetworkManager changed; refresh connections",
    "Saved connection disappeared or is unsupported; refresh",
    "The selected network adapter disappeared; refresh",
    "This profile is not compatible with the selected adapter",
    "This adapter is still changing; stop its connection or wait",
    "Connect the Ethernet cable first",
    "This hotspot profile is active on another adapter; stop it explicitly first",
    "Choose a saved WPA-PSK/SAE hotspot with shared IPv4 in Advanced network settings",
    "This adapter must support AP mode with hardware/software Wi-Fi enabled",
    "Activation changed or spans multiple adapters; refresh or use Advanced settings",
    "This profile is active on another adapter; disconnect it explicitly first",
    "Review the hotspot warning before starting it",
    "Wi-Fi or hotspot settings changed; review a fresh warning",
    "Connection is already active (NetworkManager)",
    "This profile is still changing; wait or stop its reported activation",
    "NetworkManager changed before confirmation; refresh",
    "Unable to confirm disconnection; showing observed state",
    "Selected connection disconnected",
    "Unable to confirm activation; showing observed state",
    "Hotspot settings changed during activation; check the observed state before retrying",
    "Hotspot active; Internet access is not verified",
    "Connection active (NetworkManager)",
    "Activation cancelled",
    "NetworkManager changed during cancellation; check actual connections",
    "Cancellation could not confirm disconnection; use Advanced network settings",
    "Activation cancelled.",
    "Activation cancelled. Previous Wi-Fi may need reconnecting.",
    "No network activation is running",
    "Activation already finished; check observed connections",
    "Cancellation requested; waiting for the observed outcome",
    "This operation is already running",
    "NetworkManager needs credentials or an authentication agent. Use Advanced network settings.",
    "NetworkManager denied permission. Check the session agent or Advanced network settings.",
    "The VPN plugin is unavailable. Install its NetworkManager plugin and use Advanced network settings.",
    "Network operation timed out. Refresh the observed state before retrying.",
    "NetworkManager could not complete the operation. Refresh or use Advanced network settings.",
]


def nonblank(path):
    return sum(bool(line.strip()) for line in path.read_text().splitlines())


class NativeInventoryContractCase(unittest.TestCase):
    def test_audio_device_state_ports_the_family(self):
        source = AUDIO_DEVICE_STATE.read_text()
        self.assertIn('readonly property var handledActions: ["audioDevicesRefresh", "audioPort", "audioProfile", "audioRoute"]', source)
        # pactl queries keep the backend argv (info + the four list groups), JSON parsed with
        # the exact invalid-JSON message; the read double-checks the server identity.
        self.assertIn('["pactl", "--format=json", "info"]', source)
        self.assertIn('["pactl", "--format=json", "list", "cards"]', source)
        self.assertIn('"Audio server changed while reading devices; refresh"', source)
        # The change flow: selection, the pw-tools route with its pactl fallback, the observed
        # read-back retry and the final confirmation with the exact failure message.
        self.assertIn("AudioDeviceModel.selection(", source)
        self.assertIn("AudioDeviceModel.routePlan(", source)
        self.assertIn("AudioDeviceModel.applyRouteArgv(", source)
        self.assertIn("AudioDeviceModel.observed(", source)
        self.assertIn('"Unable to confirm the requested audio change; showing the observed state"', source)
        # A missing pactl keeps the backend's install message, not the runner's generic one.
        self.assertIn('"Install pulseaudio-utils (pactl) to use ports, profiles and app outputs"', source)

    def test_network_inventory_state_ports_the_family(self):
        source = NETWORK_INVENTORY_STATE.read_text()
        self.assertIn('"networkRefresh", "networkConnect", "networkDisconnect", "networkHotspotPlan", "networkHotspotStart", "networkEdit", "networkCancel"', source)
        # The read sequence keeps the backend argv: the busctl identity pair, radio, device
        # show, connection listing and the per-profile detail batch.
        self.assertIn('"busctl", "--system", "--json=short", "call", "org.freedesktop.DBus"', source)
        self.assertIn('"nmcli", "-t", "-f", "WIFI-HW,WIFI", "general"', source)
        self.assertIn('"nmcli", "-t", "-m", "multiline", "-f", "DEVICE_FIELDS", "device", "show"', source)
        self.assertIn('"nmcli", "-t", "-f", "LIST_FIELDS", "connection", "show"', source)
        # Mutations keep the backend argv (--wait 15 up / --wait 5 down) and the cancel path
        # mirrors the Event-driven cancellation with its own stop-and-confirm reads.
        self.assertIn('"--wait", "15", "connection", "up", "uuid"', source)
        self.assertIn('"--wait", "5", "connection", "down", "apath"', source)
        self.assertIn('"No network activation is running"', source)
        self.assertIn('"Cancellation requested; waiting for the observed outcome"', source)
        # The operation projection keeps the panel contract (cancellable/cancelling keys).
        self.assertIn("cancellable", source)
        self.assertIn("cancelling", source)
        # networkEdit spawns the system editor detached (the backend's spawn).
        self.assertIn("nm-connection-editor", source)

    def test_command_runner_ports_the_backend_error_shapes(self):
        source = COMMAND_RUNNER.read_text()
        # Argv only (no shell), queued dispatch, watchdog timeouts, output caps and the
        # command_runner.py error strings the families surface.
        self.assertIn("function dispatch(name, argv, timeout, cap, done)", source)
        self.assertIn('"Required command is unavailable: " + request.name', source)
        self.assertIn('request.name + " timed out"', source)
        self.assertIn('request.name + " failed (" + code + ")"', source)
        self.assertIn('"output exceeds " + request.cap + " bytes"', source)
        self.assertIn("environment: ({LC_ALL: \"C\"})", source)

    def test_shellstate_router_fans_out_to_the_inventory_services(self):
        source = SHELL_STATE.read_text()
        for service in ("NetworkInventoryState", "AudioDeviceState"):
            self.assertIn(f"if ({service}.handles(action)) return {service};", source)
        # The inventory families' pending gates: one audio operation at a time (bluetoothDevice
        # included), and the connection actions block each other including refresh/plan.
        self.assertIn("function inventoryBusy(action)", source)
        self.assertIn('"An audio device operation is already running"', source)
        self.assertIn('["networkRefresh", "networkConnect", "networkDisconnect", "networkHotspotPlan", "networkHotspotStart", "networkEdit"]', source)
        # The on-demand sections surface like apps/usage: merged properties the panels read.
        self.assertIn("readonly property var audioDevices: NativeState.audioDevices(snapshot.audioDevices)", source)
        self.assertIn("readonly property var networkConnections: NativeState.networkConnections(snapshot.networkConnections)", source)
        # networkCancel is not routine (its message toasts), the refresh/plan actions are.
        self.assertNotIn('"networkCancel", ', source.split("routineActions")[1].split("]")[0])

    def test_sections_gate_through_nativestate_and_the_panels_read_them(self):
        native = NATIVE_STATE.read_text()
        self.assertIn("function audioDevices(backendSection)", native)
        self.assertIn("function networkConnections(backendSection)", native)
        # Fixture modes pass the backend through (the demo registry owns its state).
        self.assertLess(native.index("function audioDevices"), native.index("AudioDeviceState.section"))
        self.assertIn("NetworkInventoryState.projection", native)
        mixer = AUDIO_MIXER.read_text()
        self.assertIn("ShellState.audioDevices", mixer)
        self.assertNotIn("ShellState.snapshot.audioDevices", mixer)
        popup = NETWORK_POPUP.read_text()
        self.assertIn("ShellState.networkConnections", popup)
        self.assertNotIn("ShellState.snapshot.networkConnections", popup)
        qmldir = QMkdir.read_text()
        self.assertIn("singleton AudioDeviceState 1.0 AudioDeviceState.qml", qmldir)
        self.assertIn("singleton NetworkInventoryState 1.0 NetworkInventoryState.qml", qmldir)

    def test_backend_families_stay_registered_as_the_fallback(self):
        for path, marker in ((AUDIO_DEVICE_ACTIONS, "ACTIONS="), (WIFI_ACTIONS, "provide_connections")):
            source = path.read_text()
            self.assertIn("DEPRECATED(Q3->Q6)", str(source), str(path))
        devices = AUDIO_DEVICE_ACTIONS.read_text()
        self.assertIn("'audioDevicesRefresh','audioPort','audioProfile','audioRoute'", devices)

    def test_inventory_messages_match_the_backend_contract(self):
        source = (AUDIO_DEVICE_STATE.read_text() + AUDIO_DEVICE_MODEL.read_text()
                  + NETWORK_INVENTORY_STATE.read_text() + NETWORK_MODEL.read_text()
                  + NETWORK_PLANS.read_text() + SHELL_STATE.read_text())
        for message in PINNED_MESSAGES:
            self.assertIn(message, source, message)

    def test_service_files_stay_within_the_size_cap(self):
        for path in (AUDIO_DEVICE_STATE, NETWORK_INVENTORY_STATE, COMMAND_RUNNER):
            self.assertLessEqual(nonblank(path), 250, str(path))
        for path in (AUDIO_DEVICE_MODEL, NETWORK_MODEL, NETWORK_PLANS, DIGEST):
            self.assertLessEqual(nonblank(path), 250, str(path))

    def test_digest_module_pins_the_python_hashes(self):
        source = DIGEST.read_text()
        self.assertIn("function sha256hex(text)", source)
        self.assertIn("function pyJson(value)", source)
        # The K constants of FIPS 180-4 (parity anchor, not magic numbers).
        self.assertIn("0x428a2f98", source)


def audio_documents():
    from audio_device_fixture import documents
    return documents()


def audio_python_model():
    data = audio_documents()
    module = importlib.import_module("audio_inventory")
    return module.normalize(data["info"], data["cards"], data["sinks"], data["sources"], data["sink-inputs"])


def network_state():
    from network_fixture import data, device_text, profile_text, connection_text
    state = data()
    return state, device_text(state), profile_text(state), connection_text(state)


def network_python_model():
    state, devices, details, listing = network_state()
    inventory = importlib.import_module("network_inventory")
    from desktop_backend import split_nmcli
    rows = inventory.connections(listing, split_nmcli)
    return inventory.inventory("f" * 64, devices, rows, details, ":".join(state["radio"]), split_nmcli)


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class NativeInventoryQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_sha256_and_pyjson_match_python_digests(self):
        # Pure helpers: hashlib.sha256 + json.dumps parity (the server ids and hotspot plan
        # tokens must byte-match the backend during the A/B window).
        result = self.run_qml('import "qml/services"', '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const cases = [
                [Digest.sha256hex(""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
                [Digest.sha256hex("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"],
                [Digest.sha256hex("h\\u00e9llo \\u2192 \\u00fcn\\u00efcode \\"quoted\\""),
                 "839fbdf067acb5807c4ee97555eab491e0c53fc2bfe3d201e416adb1aeaa33f0"],
                [Digest.pyJson(["unix:/private/pulse/native", "1234:abcd", "PulseAudio (on PipeWire 1.4.2)"]),
                 '["unix:/private/pulse/native", "1234:abcd", "PulseAudio (on PipeWire 1.4.2)"]'],
                [Digest.sha256hex(Digest.pyJson(["unix:/private/pulse/native", "1234:abcd", "PulseAudio (on PipeWire 1.4.2)"])),
                 "cde292ca9b41a08dc90d3b4f9f6d0544f70f0c7e1d2e30576d4c325d6a44eae3"],
                [Digest.sha256hex("a".repeat(32) + "/:1.25"), "3e41be555ace14f45b9d695e748508493058929b8aa98a6fefcc553bba38a9c9"]];
            fixture.finish({cases: cases});
        }
    }''')
        for index, (actual, expected) in enumerate(result["cases"]):
            with self.subTest(case=index):
                self.assertEqual(actual, expected)

    def test_audio_model_matches_the_python_normalize(self):
        # Parity: the frozen private-bus pactl fixture normalized by the QML port must equal
        # audio_inventory.normalize's model (compared structurally in Python).
        import json as serializer
        body = '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const data = %s;
            const model = AudioDeviceModel.normalize(data.info, data.cards, data.sinks, data.sources, data["sink-inputs"]);
            fixture.finish({model: model});
        }
    }''' % serializer.dumps(audio_documents())
        result = self.run_qml('import "qml/services"', body)
        self.assertEqual(result["model"], audio_python_model())

    def test_audio_selection_validation_matches_the_backend_rules(self):
        # Parity: audio_inventory.py::selection's exact errors and argv plans, computed by the
        # Python module and the QML port over the same frozen fixture.
        import json as serializer
        module = importlib.import_module("audio_inventory")
        data = audio_documents()
        model = module.normalize(data["info"], data["cards"], data["sinks"], data["sources"], data["sink-inputs"])
        attempts = [
            ("audioProfile", {"serverId": model["serverId"], "cardId": model["cards"][0]["id"], "profile": "output:stereo"}),
            ("audioProfile", {"serverId": model["serverId"], "cardId": model["cards"][0]["id"], "profile": "output:absent"}),
            ("audioProfile", {"serverId": model["serverId"], "cardId": model["cards"][0]["id"], "profile": "no-such-profile"}),
            ("audioProfile", {"serverId": "x" * 64, "cardId": model["cards"][0]["id"], "profile": "output:stereo"}),
            ("audioProfile", {"serverId": model["serverId"], "cardId": "card/9/9", "profile": "output:stereo"}),
            ("audioPort", {"serverId": model["serverId"], "deviceId": model["sinks"][1]["id"], "port": "headphones"}),
            ("audioPort", {"serverId": model["serverId"], "deviceId": model["sinks"][1]["id"], "port": "headphones-absent"}),
            ("audioPort", {"serverId": model["serverId"], "deviceId": model["sources"][0]["id"], "port": "mic"}),
            ("audioRoute", {"serverId": model["serverId"], "streamId": model["streams"][0]["id"], "sinkId": model["sinks"][1]["id"]}),
            ("audioRoute", {"serverId": model["serverId"], "streamId": model["streams"][0]["id"], "sinkId": "sink/9/9"}),
            ("audioRoute", {"serverId": model["serverId"], "streamId": "stream/9/9", "sinkId": model["sinks"][1]["id"]}),
            ("bogus", {}),
            ("audioProfile", {}),
        ]
        expected = []
        for action, request in attempts:
            try:
                expected.append(list(module.selection(model, action, request)["argv"]))
            except Exception as error:  # noqa: BLE001 - the backend surfaces ValueError strings
                expected.append(str(error))
        body = '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const data = %s;
            const model = AudioDeviceModel.normalize(data.info, data.cards, data.sinks, data.sources, data["sink-inputs"]);
            const attempts = %s;
            const cases = [];
            for (const step of attempts) {
                try { cases.push(AudioDeviceModel.selection(model, step[0], step[1]).argv); }
                catch (error) { cases.push(String(error)); }
            }
            fixture.finish({cases: cases});
        }
    }''' % (serializer.dumps(data), serializer.dumps(attempts))
        result = self.run_qml('import "qml/services"', body)
        for index, (actual, wanted) in enumerate(zip(result["cases"], expected)):
            with self.subTest(case=index):
                self.assertEqual(actual, wanted)

    def test_network_model_matches_the_python_inventory(self):
        # Parity: the frozen secret-free nmcli fixture parsed by the QML port must equal
        # network_inventory.inventory's model (compared structurally in Python).
        import json as serializer
        state, devices, details, listing = network_state()
        body = '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const rows = NetworkModel.connections(%s);
            const model = NetworkModel.inventory("%s", %s, rows, %s, %s);
            fixture.finish({model: model});
        }
    }''' % (serializer.dumps(listing), "f" * 64, serializer.dumps(devices), serializer.dumps(details), serializer.dumps(":".join(state["radio"])))
        result = self.run_qml('import "qml/services"', body)
        self.assertEqual(result["model"], network_python_model())

    def test_network_plans_token_matches_the_backend_hotspot_plan(self):
        # Parity: the hotspot plan token is sha256 over Python's exact json.dumps formatting —
        # the QML pyJson + sha256 stack must reproduce it byte for byte.
        import json as serializer
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        inventory = importlib.import_module("network_inventory")
        plans = importlib.import_module("network_plans")
        model = inventory.demo_inventory()
        request = {"serverId": model["serverId"], "uuid": model["profiles"][2]["uuid"], "deviceId": model["devices"][0]["id"]}
        expected = plans.hotspot_plan(model, request)
        body = '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const model = %s;
            const request = %s;
            const plan = NetworkPlans.hotspotPlan(model, request);
            fixture.finish({plan: plan});
        }
    }''' % (serializer.dumps(model), serializer.dumps(request))
        result = self.run_qml('import "qml/services"', body)
        self.assertEqual(result["plan"], expected)

    def test_demo_inventory_dispatches_round_trip_through_the_backend(self):
        # Demo mode must keep the backend round-trip: the router never intercepts fixture
        # modes, and the demo registry fills the sections with its own inventory.
        result = self.run_qml('import "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property bool dispatched: false
    property var seen: ({lastSequence: 0})
    Timer {
        interval: 150; running: true; repeat: true
        onTriggered: {
            fixture.ticks++;
            if (fixture.ticks > 130) { fixture.finish({timeout: true, seen: fixture.seen}); return; }
            if (!ShellState.backendReady) return;
            const steps = [["audioDevicesRefresh", {}],
                ["audioProfile", {serverId: "0".repeat(64), cardId: "card/1/101", profile: "headset"}],
                ["networkRefresh", {}]];
            const result = ShellState.lastResult || {};
            const busy = Object.keys(ShellState.pendingActions).length > 0;
            if (fixture.phase >= steps.length) { fixture.finish({seen: fixture.seen}); return; }
            if (!fixture.dispatched && !busy) {
                ShellState.run(steps[fixture.phase][0], steps[fixture.phase][1]);
                fixture.dispatched = true;
                return;
            }
            if (fixture.dispatched && !busy && result.action === steps[fixture.phase][0]
                    && result.sequence > fixture.seen.lastSequence) {
                fixture.seen.lastSequence = result.sequence;
                fixture.seen["phase" + fixture.phase] = {
                    ok: result.ok, message: result.message || "",
                    cards: (ShellState.snapshot.audioDevices || {}).cards ? ShellState.snapshot.audioDevices.cards.length : null,
                    profiles: (ShellState.snapshot.networkConnections || {}).profiles
                        ? ShellState.snapshot.networkConnections.profiles.length : null};
                fixture.dispatched = false;
                fixture.phase++;
            }
        }
    }''')
        self.assertNotIn("timeout", result, result)
        seen = result["seen"]
        self.assertEqual(seen["phase0"]["ok"], True)
        self.assertEqual(seen["phase0"]["message"], "Demo preview: no system command executed")
        self.assertEqual(seen["phase0"]["cards"], 1)
        self.assertEqual(seen["phase1"]["ok"], False)
        self.assertEqual(seen["phase1"]["message"], "Invalid audio device request; refresh devices")
        self.assertEqual(seen["phase2"]["ok"], True)
        self.assertEqual(seen["phase2"]["message"], "Demo preview: no system command executed")
        self.assertEqual(seen["phase2"]["profiles"], 4)


if __name__ == "__main__":
    unittest.main()
