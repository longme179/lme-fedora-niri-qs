"""Q1 native-state contracts: frozen section shapes, merge wiring, A/B comparison.
Contract: test_native_state.py covers native_state behavior/contracts; check imports for fixtures/helpers under test.
"""
import json  # Contract: test_native_state.py (Q1 native sections; headroom 0, trailing note)
import os
import shutil
import subprocess
import unittest
from pathlib import Path

import test_local_qml as qml_tests

ROOT = Path(__file__).resolve().parents[1]

# The backend demo snapshot is the frozen contract for every section the QML
# side now serves natively (docs/QML_FIRST_MIGRATION_PLAN.md §5 Q1). If a shape
# here changes on purpose, the QML demo fixtures must change in the same PR.
FROZEN = {
    "audio": {"available": True, "volume": 42, "muted": False},
    "microphone": {"available": True, "volume": 60, "muted": False},
    "battery": {"available": True, "percent": 82, "charging": False, "acOnline": False},
    "powerProfile": "balanced",
    "powerProfiles": ["power-saver", "balanced", "performance"],
    "bluetooth": {"available": True, "enabled": True, "softBlocked": False, "hardBlocked": False,
                  "adapter": "/org/bluez/hci0",
                  "adapters": [{"path": "/org/bluez/hci0", "name": "Laptop Bluetooth", "enabled": True}],
                  "devices": [{"path": "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF", "id": "bluetooth:AA:BB:CC:DD:EE:FF",
                               "name": "Headphones", "kind": "headphones", "connected": True, "percentage": 58, "charging": None}]},
    "peripheralBatteries": [{"id": "bluetooth:AA:BB:CC:DD:EE:FF", "name": "Headphones", "kind": "headphones",
                             "connected": True, "percentage": 58, "charging": None},
                            {"id": "power_supply:demo-keyboard", "name": "Wireless keyboard", "kind": "keyboard",
                             "connected": True, "percentage": 18, "charging": False}],
    "network": {"available": True, "enabled": True, "connected": True, "ssid": "Home Wi-Fi", "strength": 88,
                "device": "wlp1s0", "saved": [{"uuid": "demo-home", "name": "Home Wi-Fi"}],
                "networks": [{"ssid": "Home Wi-Fi", "strength": 88, "connected": True, "secured": True, "security": "WPA2", "bssid": "AA:BB:CC:DD:EE:01"},
                             {"ssid": "Guest", "strength": 62, "connected": False, "secured": True, "security": "WPA2", "bssid": "AA:BB:CC:DD:EE:02"}]},
}

SERVICES = ("qml/services/AudioState.qml", "qml/services/PowerState.qml", "qml/services/NetworkState.qml",
            "qml/services/NativeState.qml", "qml/services/SystemMerge.js", "qml/services/PeripheralIdentity.js")


def nonblank(path):
    return sum(bool(line.strip()) for line in (ROOT/path).read_text().splitlines())


def backend_demo_system():
    environment = dict(os.environ, PYTHONPATH=str(ROOT/"scripts"))
    result = subprocess.run(["python3", "scripts/desktop_backend.py", "--demo", "--once"],
                            capture_output=True, text=True, timeout=60, cwd=ROOT, env=environment, check=True)
    return json.loads(result.stdout)["system"]


class NativeSectionContractCase(unittest.TestCase):
    def test_backend_demo_sections_are_frozen(self):
        system = backend_demo_system()
        for section, expected in FROZEN.items():
            with self.subTest(section=section):
                self.assertEqual(system.get(section), expected)

    def test_fixture_modes_pass_the_backend_system_through(self):
        # The demo backend is stateful (audio/power/network actions mutate its snapshot) and
        # development tests inject hardware state through it — native sections must not override.
        source = (ROOT/"qml/services/NativeState.qml").read_text()
        self.assertIn("if (backendDemo || settingsApp) return null;", source)
        self.assertIn("if (backendDemo || settingsApp) return SystemMerge.merge(backend, null, passthrough)", source)
        self.assertNotIn("NATIVE_DEMO_SECTIONS", source)

    def test_new_service_files_exist_within_the_size_cap(self):
        for path in SERVICES:
            with self.subTest(path=path):
                self.assertTrue((ROOT/path).is_file(), path)
                self.assertLessEqual(nonblank(path), 250)

    def test_qmldir_registers_the_new_singletons(self):
        qmldir = (ROOT/"qml/services/qmldir").read_text()
        for name in ("AudioState", "PowerState", "NetworkState", "NativeState"):
            self.assertIn(f"singleton {name} 1.0", qmldir)

    def test_shellstate_reads_system_through_the_native_merge(self):
        source = (ROOT/"qml/services/ShellState.qml").read_text()
        self.assertIn("NativeState.merge(snapshot.system", source)
        self.assertNotIn('Identity.keep(next, snapshot, "system"', source)
        self.assertNotIn("oldAudio", source)
        self.assertIn("NativeState.compareSections(", source)
        self.assertRegex(source, r"target:\s*AudioState")
        self.assertIn("function onOsd(", source)

    def test_bluetooth_state_section_has_no_shellstate_system_backreference(self):
        # BluetoothState is created while ShellState.system's binding evaluates;
        # reading ShellState.system from it would be a binding loop.
        source = (ROOT/"qml/services/BluetoothState.qml").read_text()
        self.assertNotIn("ShellState.system", source)

    def test_backend_section_builders_are_marked_deprecated(self):
        source = (ROOT/"scripts/desktop_backend.py").read_text()
        self.assertGreaterEqual(source.count("DEPRECATED(Q1"), 3)

    def test_merge_helper_caches_by_backend_content_and_section_references(self):
        source = (ROOT/"qml/services/SystemMerge.js").read_text()
        self.assertIn("JSON.stringify(backend)", source)
        self.assertIn("sameSections", source)

    def test_powerstate_rescales_quickshells_01_upower_percentage(self):
        # Quickshell 0.3.2 normalizes the UPower D-Bus Percentage (0-100) into
        # a 0-1 fraction (DBusDataTransform<PowerPercentage> applies *0.01) —
        # the same fraction convention as Pipewire volume, wifi signalStrength
        # and Bluetooth battery, which Q1 already rescaled by 100. Both UPower
        # read sites must go through percent100() or the bar renders an 80%
        # battery as Math.round(0.8) = 1%.
        source = (ROOT/"qml/services/PowerState.qml").read_text()
        self.assertIn("function percent100(", source)
        self.assertIn("percent: percent100(device.percentage)", source)
        self.assertIn("percentage: Peripheral.percentage(percent100(device.percentage))", source)


@unittest.skipUnless(shutil.which("quickshell"), "Quickshell is required for native QML checks")
class NativeStateQmlCase(unittest.TestCase):
    run_qml = qml_tests.LocalQmlCase.run_qml
    def test_demo_sections_flow_through_the_merged_system(self):
        result = self.run_qml('import "qml/services"', '''
    property int phase: 0
    property int ticks: 0
    property var first: null
    Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
            fixture.ticks++;
            if (fixture.phase === 0 && ShellState.backendReady) { fixture.first = ShellState.system; fixture.phase = 1; }
            else if (fixture.phase === 1 && fixture.ticks > 28) fixture.phase = 2;
            else if (fixture.phase === 2) {
                fixture.finish({stable: fixture.first === ShellState.system,
                                audio: ShellState.system.audio, microphone: ShellState.system.microphone,
                                battery: ShellState.system.battery, bluetooth: ShellState.system.bluetooth,
                                network: ShellState.system.network, powerProfile: ShellState.system.powerProfile,
                                powerProfiles: ShellState.system.powerProfiles,
                                peripheralBatteries: ShellState.system.peripheralBatteries,
                                mismatches: NativeState.compareSections(
                                    {"audio": {"available": true, "volume": 7, "muted": false}},
                                    {"audio": ShellState.system.audio})});
            }
        }
    }''')
        for section, expected in FROZEN.items():
            with self.subTest(section=section):
                self.assertEqual(result[section], expected)
        # Content-equal backend polls must reuse the same merged object.
        self.assertTrue(result["stable"])
        # A doctored backend section must be counted as a mismatch.
        self.assertEqual(result["mismatches"], {"audio": 1})

    def test_percent100_maps_the_quickshell_fraction_to_the_backend_scale(self):
        # Behavioral twin of the source contract above: percent100() is the
        # boundary between Quickshell's 0-1 UPower fraction and the backend's
        # frozen 0-100 percent contract.
        result = self.run_qml('import "qml/services"', '''
    Component.onCompleted: {
        fixture.finish({eighty: PowerState.percent100(0.8), full: PowerState.percent100(1),
                        empty: PowerState.percent100(0), bad: PowerState.percent100(NaN),
                        absent: PowerState.percent100(undefined)});
    }''')
        self.assertEqual(result, {"eighty": 80, "full": 100, "empty": 0, "bad": None, "absent": None})
