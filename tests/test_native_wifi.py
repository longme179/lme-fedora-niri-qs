"""Q3 native wifi contracts: scan lists, saved profiles, action routing.
Contract: test_native_wifi.py covers native_wifi behavior/contracts; check imports for fixtures/helpers under test.
"""
import shutil  # Contract: test_native_wifi.py (Q3 wifi families; headroom 0, trailing note)
import subprocess
import unittest
from pathlib import Path

import test_local_qml as qml_tests

ROOT = Path(__file__).resolve().parents[1]

NETWORK_STATE = ROOT / "qml/services/NetworkState.qml"
SHELL_STATE = ROOT / "qml/services/ShellState.qml"
NATIVE_STATE = ROOT / "qml/services/NativeState.qml"
PENDING = ROOT / "qml/services/ActionPending.js"
WIFI_ACTIONS = ROOT / "scripts/wifi_actions.py"

# wifi_actions.py ACTIONS — the backend registry stays registered as the fallback and the
# canonical error source while the Q3 A/B window is open (plan §5 Q3 mechanism).
FALLBACK_ACTIONS = "('wifiScan', 'wifiConnect', 'wifiSaved', 'wifiDisconnect', 'wifiForget')"

# The user-facing messages the backend contract established (wifi_actions.py + wifi_auth.py);
# the native router must produce the same strings so the toast/dialog UX is identical.
PINNED_MESSAGES = [
    "No Wi-Fi adapter is available",
    "Network is no longer visible; scan again",
    "Saved network is no longer available",
    "Enterprise Wi-Fi needs a certificate or account. Use Advanced network settings.",
    "Invalid Wi-Fi password",
    "WPA/WPA2 passwords need 8–63 bytes or 64 hexadecimal digits.",
    "This operation is already running",
    "Wi-Fi toggled",
    "Wi-Fi disconnected",
    "Saved network removed",
    "Wi-Fi connected",
    "Enter a Wi-Fi password to connect.",
    "Wi-Fi needs a valid password. Check it and try again.",
    "Wi-Fi authentication did not finish. Check the password or signal and try again.",
    "Wi-Fi connection timed out. Check the signal and try again.",
]


def nonblank(path):
    return sum(bool(line.strip()) for line in path.read_text().splitlines())


class NativeWifiContractCase(unittest.TestCase):
    def test_backend_wifi_actions_stay_registered_as_the_fallback(self):
        source = WIFI_ACTIONS.read_text()
        self.assertIn(FALLBACK_ACTIONS, source)
        self.assertIn("DEPRECATED(Q3->Q6)", source)

    def test_backend_scan_lists_are_marked_deprecated(self):
        source = (ROOT / "scripts/desktop_backend.py").read_text()
        self.assertGreaterEqual(source.count("DEPRECATED(Q3->Q6)"), 2)

    def test_network_state_maps_the_scan_list_in_the_backend_shape(self):
        source = NETWORK_STATE.read_text()
        # The list comes from the wifi device's model (quickshell dedupes by SSID, matching
        # the backend's nmcli dedupe), rescaled from the 0-1 signalStrength fraction.
        self.assertIn("wifi.networks.values", source)
        self.assertIn("Math.round(network.signalStrength * 100)", source)
        # Backend ordering: connected first, then by descending strength, capped at 60.
        self.assertIn("b.strength - a.strength", source)
        self.assertIn("slice(0, 60)", source)
        # quickshell exposes no BSSID — the native item keeps the key (shape parity) as "".
        self.assertIn('bssid: ""', source)
        for field in ("ssid", "strength", "connected", "security", "secured", "enterprise"):
            self.assertIn(field + ":", source)

    def test_network_state_enumerates_saved_profiles_from_nmsettings(self):
        source = NETWORK_STATE.read_text()
        self.assertIn("network.nmSettings", source)
        self.assertIn("settings.uuid", source)
        self.assertIn("settings.id", source)

    def test_scanner_runs_only_while_a_consumer_is_watching(self):
        source = NETWORK_STATE.read_text()
        self.assertIn("property bool watching: false", source)
        self.assertIn("scannerEnabled = true", source)
        self.assertIn("scannerEnabled = false", source)
        self.assertIn("function applyScanner()", source)

    def test_shellstate_routes_wifi_actions_natively_in_real_sessions(self):
        source = SHELL_STATE.read_text()
        # The router gate: fixture modes always keep the backend round-trip; the fan-out
        # owns the wifi leg (generalized across the Q3 write families in the same phase).
        self.assertIn("if (NetworkState.handles(action)) return NetworkState;", source)
        # Native dispatch reserves the same pending slot and resolves it locally.
        self.assertIn("Pending.settled(pendingState, action)", source)
        self.assertIn("owner.perform(action, payload || {}, (ok, message) => nativeDone(action, ok, message), context)", source)
        # Fallback when quickshell's NetworkManager backend or adapter is absent.
        self.assertIn("owner.canRoute(action, payload || {}, context)", source)
        # watchWifi drives the native scanner alongside the backend's A/B copy.
        self.assertIn("NetworkState.watching = watching", source)

    def test_shellstate_blocks_concurrent_wifi_mutations(self):
        source = SHELL_STATE.read_text()
        self.assertIn('readonly property var nativeMutationActions: ["wifiConnect", "wifiSaved", "wifiDisconnect", "wifiForget", "wifiToggle", "networkConnect", "networkDisconnect", "networkHotspotStart", "networkEdit"]', source)
        self.assertIn("nativeMutationActions.some(name => pendingActions[name])", source)

    def test_actionpending_gains_a_local_settled_primitive(self):
        source = PENDING.read_text()
        self.assertIn("function settled(state, action)", source)
        self.assertIn("delete local[action]", source)
        self.assertIn("delete pending[action]", source)

    def test_native_state_drops_the_backend_network_overlay(self):
        source = NATIVE_STATE.read_text()
        self.assertNotIn("networks: networkBackend.networks", source)
        self.assertNotIn("saved: networkBackend.saved", source)

    def test_ab_compare_covers_the_wifi_lists(self):
        source = NATIVE_STATE.read_text()
        self.assertIn("[Q3 A/B]", source)
        self.assertIn('"networks"', source)
        self.assertIn('"saved"', source)

    def test_wifi_error_messages_match_the_backend_contract(self):
        source = NETWORK_STATE.read_text() + SHELL_STATE.read_text()
        for message in PINNED_MESSAGES:
            self.assertIn(message, source, message)

    def test_service_files_stay_within_the_size_cap(self):
        # NetworkState rides the default 250 cap; ShellState carries the router behind the
        # run() facade per plan §5 Q3 and its ratchet ceiling is bumped consciously in
        # config/architecture.json (checked by scripts/check_architecture.py).
        self.assertLessEqual(nonblank(NETWORK_STATE), 250)


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class NativeWifiQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml

    def test_security_names_and_password_rules_port_the_backend_contract(self):
        # Pure helpers: the security enum mapping and the wifi_actions.py password
        # validation (8-63 UTF-8 bytes or 64 hex digits for WPA/WPA2; WPA3/SAE exempt).
        result = self.run_qml('import "qml/services"\nimport Quickshell.Networking', '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const cases = [
                [NetworkState.securityName(WifiSecurityType.Wpa2Psk), "WPA2"],
                [NetworkState.securityName(WifiSecurityType.Sae), "WPA3"],
                [NetworkState.securityName(WifiSecurityType.Wpa2Eap), "WPA2 Enterprise"],
                [NetworkState.securityName(WifiSecurityType.StaticWep), "WEP"],
                [NetworkState.securityName(WifiSecurityType.Owe), "OWE"],
                [NetworkState.securityName(WifiSecurityType.Open), ""],
                [NetworkState.isSecured(WifiSecurityType.Open), false],
                [NetworkState.isSecured(WifiSecurityType.Unknown), false],
                [NetworkState.isSecured(WifiSecurityType.Wpa2Psk), true],
                [NetworkState.isEnterprise(WifiSecurityType.Wpa2Eap), true],
                [NetworkState.isEnterprise(WifiSecurityType.Leap), true],
                [NetworkState.isEnterprise(WifiSecurityType.Wpa2Psk), false],
                [NetworkState.passwordProblem("short", WifiSecurityType.Wpa2Psk, true).length > 0, true],
                [NetworkState.passwordProblem("12345678", WifiSecurityType.Wpa2Psk, true), ""],
                [NetworkState.passwordProblem("a".repeat(63), WifiSecurityType.Wpa2Psk, true), ""],
                [NetworkState.passwordProblem("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", WifiSecurityType.Wpa2Psk, true), ""],
                [NetworkState.passwordProblem("g".repeat(64), WifiSecurityType.Wpa2Psk, true).length > 0, true],
                [NetworkState.passwordProblem("àààà", WifiSecurityType.Wpa2Psk, true), ""],
                [NetworkState.passwordProblem("ààà", WifiSecurityType.Wpa2Psk, true).length > 0, true],
                [NetworkState.passwordProblem("abc", WifiSecurityType.Sae, true), ""],
                [NetworkState.passwordProblem("abc", WifiSecurityType.Wpa2Psk, false), ""],
                [NetworkState.passwordProblem("x".repeat(129), WifiSecurityType.Wpa2Psk, true), "Invalid Wi-Fi password"]];
            fixture.finish({cases: cases});
        }
    }''')
        for index, (actual, expected) in enumerate(result["cases"]):
            with self.subTest(case=index):
                self.assertEqual(actual, expected)

    def test_native_section_gates_the_lists_on_watching(self):
        # Native mode without a NetworkManager connection (harness bus): the section keeps
        # the backend key shape with empty lists and the scanner stays off (A6).
        result = self.run_qml('import "qml/services"', '''
    Timer {
        interval: 300; running: true; repeat: false
        onTriggered: fixture.finish({section: NetworkState.state, watching: NetworkState.watching})
    }''', environment={"LME_SHELL_DEMO": "0"})
        section = result["section"]
        for key in ("available", "enabled", "connected", "wifiConnected", "ssid", "strength",
                    "device", "networks", "saved"):
            self.assertIn(key, section)
        self.assertEqual(section["networks"], [])
        self.assertEqual(section["saved"], [])
        self.assertIs(result["watching"], False)

    def test_demo_wifi_actions_round_trip_through_the_backend(self):
        # Demo mode must keep the backend round-trip: the router never intercepts fixture
        # modes, and the demo registry still mutates its snapshot.
        result = self.run_qml('import "qml/services"', '''
    property int ticks: 0
    property bool requested: false
    Timer {
        interval: 200; running: true; repeat: true
        onTriggered: {
            fixture.ticks++;
            if (ShellState.backendReady && !fixture.requested) {
                fixture.requested = true;
                ShellState.run("wifiConnect", {device: "wlp1s0", bssid: "AA:BB:CC:DD:EE:02", ssid: "Guest", password: ""});
            }
            const network = ShellState.system.network || {};
            if (network.ssid === "Guest" || fixture.ticks >= 40)
                fixture.finish({ssid: network.ssid, connected: network.connected,
                                action: ShellState.wifiResult ? ShellState.wifiResult.action : null,
                                ok: ShellState.wifiResult ? ShellState.wifiResult.ok : null,
                                pending: ShellState.pendingActions.wifiConnect === true});
        }
    }''')
        self.assertEqual(result["ssid"], "Guest")
        self.assertIs(result["connected"], True)
        self.assertEqual(result["action"], "wifiConnect")
        self.assertIs(result["ok"], True)
        self.assertIs(result["pending"], False)

    def test_ab_compare_counts_the_wifi_lists(self):
        result = self.run_qml('import "qml/services"', '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            NativeState.abMismatches = {};
            const backend = {system: {network: {networks: [{}, {}, {}], saved: [{}, {}]}}};
            const native = {network: {networks: [{}, {}], saved: [{}, {}]}};
            const mismatches = NativeState.compareSections(backend, native, []);
            fixture.finish({keys: Object.keys(mismatches).sort(),
                            networks: NativeState.abMismatches.networks || 0,
                            saved: NativeState.abMismatches.saved || 0});
        }
    }''')
        self.assertEqual(result["keys"], ["networks"])
        self.assertEqual(result["networks"], 1)
        self.assertEqual(result["saved"], 0)

    def test_ab_compare_bands_the_network_strength(self):
        # GOTCHA: the backend samples strength through its nmcli poll, the native side
        # through the live Networking model — the same network jitters a few points
        # between those instants (65 vs 71 observed on the owner's machine across a
        # 12.5 h day: 92 rate-limited drift lines with every other field equal). Like
        # cpu/memoryPercent (deliberately not compared), strength is a cross-instant
        # sample: the compare bands it by 8 so the counter stays a parity signal —
        # #116's 0-1 scale class (65 vs 1) and real flag/ssid changes still mismatch.
        result = self.run_qml('import "qml/services"', '''
    Timer {
        interval: 100; running: true; repeat: false
        onTriggered: {
            const base = {available: true, enabled: true, connected: true,
                          wifiConnected: true, ssid: "KimHoangTuan 5g", device: "wlo1"};
            const backend = {system: {network: Object.assign({}, base, {strength: 65})}};
            const jitter = NativeState.compareSections(
                backend, {network: Object.assign({}, base, {strength: 71})}, []);
            const scale = NativeState.compareSections(
                backend, {network: Object.assign({}, base, {strength: 1})}, []);
            const offline = NativeState.compareSections(
                backend, {network: Object.assign({}, base, {strength: null, wifiConnected: false, ssid: null})}, []);
            const bothNull = NativeState.compareSections(
                {system: {network: Object.assign({}, base, {strength: null})}},
                {network: Object.assign({}, base, {strength: null})}, []);
            fixture.finish({jitter: Object.keys(jitter).sort(), scale: Object.keys(scale).sort(),
                            offline: Object.keys(offline).sort(), bothNull: Object.keys(bothNull).sort()});
        }
    }''')
        self.assertEqual(result["jitter"], [])
        self.assertEqual(result["scale"], ["network"])
        self.assertEqual(result["offline"], ["network"])
        self.assertEqual(result["bothNull"], [])
