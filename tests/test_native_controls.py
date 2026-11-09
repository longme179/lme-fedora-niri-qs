"""Q3 native write-family contracts: audio/backlight controls, bluetooth and charge mode.
Contract: test_native_controls.py covers native_controls behavior/contracts; check imports for fixtures/helpers under test.
"""
import shutil  # Contract: test_native_controls.py (Q3 write families; headroom 0, trailing note)
import unittest
from pathlib import Path

import test_local_qml as qml_tests

ROOT = Path(__file__).resolve().parents[1]

AUDIO_STATE = ROOT / "qml/services/AudioState.qml"
BLUETOOTH_STATE = ROOT / "qml/services/BluetoothState.qml"
POWER_STATE = ROOT / "qml/services/PowerState.qml"
SHELL_STATE = ROOT / "qml/services/ShellState.qml"
AUDIO_ACTIONS = ROOT / "scripts/audio_actions.py"
CHARGE_ACTIONS = ROOT / "scripts/charge_actions.py"

ROUTER_LINE = "owner.perform(action, payload || {}, (ok, message) => nativeDone(action, ok, message), context)"
PANEL_GUARD = 'if ((action === "imageAnnotate" || action === "chargeMode") && !demo || ["networkConnect", "networkDisconnect", "networkHotspotStart", "networkEdit"].includes(action)) closePanels();'

# The user-facing messages the backend contract established (scripts/audio_actions.py,
# scripts/desktop_backend.py::set_bluetooth/set_charge, scripts/charge_actions.py); the native
# router must produce the same strings so the toast/dialog UX is identical.
PINNED_MESSAGES = [
    "Volume adjusted",
    "Mute toggled",
    "Microphone mute toggled",
    "Bluetooth turned ",
    "Bluetooth device connected",
    "Bluetooth device disconnected",
    "Unknown Bluetooth device or state",
    "An audio device operation is already running",
    "BlueZ did not confirm the requested power state. Check journalctl -b -u bluetooth and rfkill list bluetooth.",
    "Choose conservation (85) or maximum charge (100).",
    "A charge-mode change is already running.",
    "Changing charge mode; administrator authentication may be required",
    "Charge mode updated",
    "The kernel did not confirm the requested charge mode.",
    "Required command is unavailable: brightnessctl",
    "Required command is unavailable: pkexec",
]


def nonblank(path):
    return sum(bool(line.strip()) for line in path.read_text().splitlines())


class NativeControlsContractCase(unittest.TestCase):
    def test_backend_control_actions_stay_registered_as_the_fallback(self):
        for path in (AUDIO_ACTIONS, CHARGE_ACTIONS):
            source = path.read_text()
            self.assertIn("DEPRECATED(Q3->Q6)", source, str(path))
        controls = AUDIO_ACTIONS.read_text()
        self.assertIn("'volume': volume, 'mute': mute, 'micVolume': mic_volume, 'micMute': mic_mute", controls)
        self.assertIn("'brightness': brightness, 'bluetoothToggle'", controls)

    def test_audio_state_ports_the_control_writes(self):
        source = AUDIO_STATE.read_text()
        self.assertIn('readonly property var handledActions: ["volume", "mute", "micVolume", "micMute", "brightness"]', source)
        # PwNodeAudioIface writes on the same scale wpctl prints (the Q1 A/B window validated the read).
        self.assertIn("node.audio.muted = !node.audio.muted", source)
        self.assertIn("node.audio.volume = clampVolume", source)
        self.assertIn("function clampVolume(volume) { return Math.min(1, Math.max(0, volume)); }", source)
        # The backend's percentage() bounds and exact error strings.
        self.assertIn("function percent(value, minimum)", source)
        self.assertIn('"Value must be between " + minimum + " and 100"', source)
        # brightnessctl keeps the backend argv (no backlight API in quickshell 0.3.2; the read
        # stays backend-fed per the Q2 transitional keys).
        self.assertIn('["brightnessctl", "--class=backlight", "set", value + "%"]', source)
        self.assertIn('"Brightness "', source)

    def test_bluetooth_state_ports_device_and_toggle_writes(self):
        source = BLUETOOTH_STATE.read_text()
        self.assertIn('readonly property var handledActions: ["bluetoothToggle", "bluetoothDevice"]', source)
        # The org.bluez path contract from scripts/audio_actions.py::bluetooth_device.
        self.assertIn("\\/org\\/bluez\\/hci[0-9]+", source)
        self.assertIn("([0-9A-Fa-f]{2}_){5}[0-9A-Fa-f]{2}$", source)
        self.assertIn("item.enabled = enabling", source)
        self.assertIn("device.connected = wanted", source)
        # rfkill blocks have no native API: enabling through a block falls back to the registry
        # (its rfkill unblock dance); turning the radio off always routes natively.
        self.assertIn("function toggleRoutes(enabled, softBlocked, hardBlocked)", source)
        self.assertIn("softBlocked === true || hardBlocked === true", source)

    def test_power_state_ports_charge_mode(self):
        source = POWER_STATE.read_text()
        self.assertIn('readonly property var handledActions: ["chargeMode"]', source)
        # The privileged helper stays Python (plan §6 Polkit path); the port keeps its argv.
        self.assertIn('"pkexec", "--disable-internal-agent", "/usr/bin/python3", "-I", "/usr/local/libexec/lme-shell-charge"', source)
        # desktop_backend.py::set_charge's confirmation over the helper's printed JSON state.
        self.assertIn("state.mode !== desired", source)
        self.assertIn("state.limitPercent !== limit", source)
        self.assertIn("property bool chargeBusy: false", source)

    def test_shellstate_router_fans_out_to_the_write_services(self):
        source = SHELL_STATE.read_text()
        for service in ("NetworkState", "AudioState", "BluetoothState", "PowerState"):
            self.assertIn(f"if ({service}.handles(action)) return {service};", source)
        self.assertIn("owner.canRoute(action, payload || {}, context)", source)
        self.assertIn(ROUTER_LINE, source)
        self.assertIn("Pending.settled(pendingState, action)", source)
        # The polkit/external-agent closePanels guard moved ahead of both dispatch paths.
        self.assertIn(PANEL_GUARD, source)
        self.assertLess(source.index(PANEL_GUARD), source.index("function send(action, payload)"))

    def test_native_done_suppresses_routine_action_toasts(self):
        source = SHELL_STATE.read_text()
        # accept()'s routine list, extracted so the native path suppresses the same names.
        self.assertIn("readonly property var routineActions:", source)
        for action in ("volume", "mute", "micVolume", "micMute", "brightness", "bluetoothDevice"):
            self.assertIn(f'"{action}"', source)
        self.assertIn("!routineActions.includes(action)", source)

    def test_control_messages_match_the_backend_contract(self):
        source = AUDIO_STATE.read_text() + BLUETOOTH_STATE.read_text() + POWER_STATE.read_text() + SHELL_STATE.read_text()
        for message in PINNED_MESSAGES:
            self.assertIn(message, source, message)

    def test_service_files_stay_within_the_size_cap(self):
        for path in (AUDIO_STATE, BLUETOOTH_STATE, POWER_STATE):
            self.assertLessEqual(nonblank(path), 250, str(path))


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class NativeControlsQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_percent_validation_ports_the_backend_bounds(self):
        # Pure helper: scripts/desktop_backend.py::percentage() — bounds, round, exact errors.
        result = self.run_qml('import "qml/services"', '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const cases = [
                [AudioState.percent(50, 0), 50],
                [AudioState.percent(0, 0), 0],
                [AudioState.percent(100, 0), 100],
                [AudioState.percent(50.6, 0), 51],
                [AudioState.percent(101, 0), "Value must be between 0 and 100"],
                [AudioState.percent(100.4, 0), "Value must be between 0 and 100"],
                [AudioState.percent(-1, 0), "Value must be between 0 and 100"],
                [AudioState.percent(0, 1), "Value must be between 1 and 100"],
                [AudioState.percent(5, -100), 5],
                [AudioState.percent(-100, -100), -100],
                [AudioState.percent(-101, -100), "Value must be between -100 and 100"],
                [AudioState.percent(true, 0), "Value must be between 0 and 100"],
                [AudioState.percent("50", 0), "Value must be between 0 and 100"],
                [AudioState.percent(NaN, 0), "Value must be between 0 and 100"]];
            fixture.finish({cases: cases});
        }
    }''')
        for index, (actual, expected) in enumerate(result["cases"]):
            with self.subTest(case=index):
                self.assertEqual(actual, expected)

    def test_charge_admission_ports_the_backend_messages(self):
        # Pure helper: charge_actions.py's admission over the backend-fed charging section.
        result = self.run_qml('import "qml/services"', '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const ready = {canSet: true, reason: ""};
            const blocked = {canSet: false, reason: "Install the administrator charge helper. See docs/CHARGING.md."};
            const cases = [
                [PowerState.chargeProblem({value: 85}, ready, false), ""],
                [PowerState.chargeProblem({value: 100}, ready, false), ""],
                [PowerState.chargeProblem({value: 85.0}, ready, false), ""],
                [PowerState.chargeProblem({value: 42}, ready, false), "Choose conservation (85) or maximum charge (100)."],
                [PowerState.chargeProblem({value: true}, ready, false), "Choose conservation (85) or maximum charge (100)."],
                [PowerState.chargeProblem({value: "85"}, ready, false), "Choose conservation (85) or maximum charge (100)."],
                [PowerState.chargeProblem({value: 85.5}, ready, false), "Choose conservation (85) or maximum charge (100)."],
                [PowerState.chargeProblem({}, ready, false), "Choose conservation (85) or maximum charge (100)."],
                [PowerState.chargeProblem({value: 85}, ready, true), "A charge-mode change is already running."],
                [PowerState.chargeProblem({value: 85}, blocked, false), "Install the administrator charge helper. See docs/CHARGING.md."],
                [PowerState.chargeProblem({value: 85}, null, false), "Install the administrator charge helper. See docs/CHARGING.md."]];
            fixture.finish({cases: cases});
        }
    }''')
        for index, (actual, expected) in enumerate(result["cases"]):
            with self.subTest(case=index):
                self.assertEqual(actual, expected)

    def test_bluetooth_device_validation_ports_the_backend_rules(self):
        # Pure helper: scripts/audio_actions.py::bluetooth_device's path/state/membership rules.
        result = self.run_qml('import "qml/services"', '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const paths = ["/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"];
            const cases = [
                [BluetoothState.deviceProblem({path: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF", connected: true}, paths), ""],
                [BluetoothState.deviceProblem({path: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF", connected: false}, paths), ""],
                [BluetoothState.deviceProblem({path: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF", connected: "yes"}, paths), "Unknown Bluetooth device or state"],
                [BluetoothState.deviceProblem({path: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"}, paths), "Unknown Bluetooth device or state"],
                [BluetoothState.deviceProblem({path: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FG", connected: true}, paths), "Unknown Bluetooth device or state"],
                [BluetoothState.deviceProblem({path: "/org/bluez/hci0/dev_aa_bb_cc_dd_ee_ff", connected: true}, paths), "Unknown Bluetooth device or state"],
                [BluetoothState.deviceProblem({path: "/org/bluez/hci9/dev_AA_BB_CC_DD_EE_FF", connected: true}, paths), "Unknown Bluetooth device or state"],
                [BluetoothState.deviceProblem({path: "hci0", connected: true}, paths), "Unknown Bluetooth device or state"],
                [BluetoothState.deviceProblem({connected: true}, paths), "Unknown Bluetooth device or state"],
                [BluetoothState.deviceProblem(null, paths), "Unknown Bluetooth device or state"]];
            fixture.finish({cases: cases});
        }
    }''')
        for index, (actual, expected) in enumerate(result["cases"]):
            with self.subTest(case=index):
                self.assertEqual(actual, expected)

    def test_bluetooth_toggle_routing_respects_rfkill_blocks(self):
        # Pure helper: enabling through an rfkill block falls back to the backend registry
        # (it can unblock rfkill and retry); unknown flags route natively.
        result = self.run_qml('import "qml/services"', '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const cases = [
                [BluetoothState.toggleRoutes(true, false, false), true],
                [BluetoothState.toggleRoutes(true, true, false), true],
                [BluetoothState.toggleRoutes(true, true, true), true],
                [BluetoothState.toggleRoutes(false, false, false), true],
                [BluetoothState.toggleRoutes(false, true, false), false],
                [BluetoothState.toggleRoutes(false, false, true), false],
                [BluetoothState.toggleRoutes(false, undefined, undefined), true]];
            fixture.finish({cases: cases});
        }
    }''')
        for index, (actual, expected) in enumerate(result["cases"]):
            with self.subTest(case=index):
                self.assertEqual(actual, expected)

    def test_demo_controls_round_trip_through_the_backend(self):
        # Demo mode must keep the backend round-trip: the router never intercepts fixture
        # modes, and the demo registry still mutates its snapshot with the same validation.
        result = self.run_qml('import "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property bool dispatched: false
    property var seen: ({lastSequence: 0})
    Timer {
        interval: 150; running: true; repeat: true
        onTriggered: {
            fixture.ticks++;
            if (fixture.ticks > 130) { fixture.finish({timeout: fixture.phase, seen: fixture.seen}); return; }
            if (!ShellState.backendReady) return;
            const steps = [
                ["volume", {value: 40}], ["volume", {value: 101}], ["mute", {}], ["micVolume", {value: 70}],
                ["micMute", {}], ["brightness", {value: 60}], ["bluetoothToggle", {}],
                ["bluetoothDevice", {path: "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF", connected: false}],
                ["chargeMode", {value: 100}], ["chargeMode", {value: 42}],
                ["bluetoothDevice", {path: "not-a-path", connected: true}]];
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
                const system = ShellState.system;
                const bluetooth = system.bluetooth || {};
                fixture.seen["phase" + fixture.phase] = {
                    ok: result.ok, message: result.message || "",
                    audioVolume: (system.audio || {}).volume, audioMuted: (system.audio || {}).muted,
                    micVolume: (system.microphone || {}).volume, micMuted: (system.microphone || {}).muted,
                    brightness: (system.brightness || {}).percent, bluetoothEnabled: bluetooth.enabled,
                    headphones: (bluetooth.devices || [])[0] ? bluetooth.devices[0].connected : null,
                    chargeMode: (system.charging || {}).mode, chargeLimit: (system.charging || {}).limitPercent};
                fixture.dispatched = false;
                fixture.phase++;
            }
        }
    }''')
        self.assertNotIn("timeout", result, result)
        seen = result["seen"]
        self.assertEqual(seen["phase0"]["ok"], True)
        self.assertEqual(seen["phase0"]["audioVolume"], 40)
        self.assertEqual(seen["phase1"]["ok"], False)
        self.assertEqual(seen["phase1"]["message"], "Value must be between 0 and 100")
        self.assertIs(seen["phase2"]["audioMuted"], True)
        self.assertEqual(seen["phase3"]["micVolume"], 70)
        self.assertIs(seen["phase4"]["micMuted"], True)
        self.assertEqual(seen["phase5"]["brightness"], 60)
        self.assertIs(seen["phase6"]["bluetoothEnabled"], False)
        self.assertIs(seen["phase7"]["headphones"], False)
        self.assertEqual(seen["phase8"]["chargeMode"], "max")
        self.assertEqual(seen["phase8"]["chargeLimit"], 100)
        self.assertEqual(seen["phase9"]["ok"], False)
        self.assertEqual(seen["phase9"]["message"], "Choose conservation (85) or maximum charge (100).")
        self.assertEqual(seen["phase10"]["ok"], False)
        self.assertEqual(seen["phase10"]["message"], "Unknown Bluetooth device or state")
