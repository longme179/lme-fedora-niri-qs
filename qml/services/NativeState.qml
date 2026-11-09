// Role: NativeState.qml (shared layer, fan-in 1) — Q1 native-section composition for the merged system.
// REL: AudioState/PowerState/BluetoothState/NetworkState – native sections; SystemMerge.js – reference-stable merge.
// INVARIANT: the demo fixtures between the NATIVE_DEMO_SECTIONS markers are JSON and deep-equal the
// backend demo snapshot sections (tests/test_native_state.py parses and freezes both sides).
// Q1 A/B window: the backend keeps emitting the migrated sections; compareSections() warns on drift
// (rate-limited) so the owner can validate native values against backend values for a day (plan §5 Q1).
pragma Singleton
import QtQuick
import Quickshell
import "SystemMerge.js" as SystemMerge
import "PeripheralIdentity.js" as Peripheral

QtObject {
    id: root

    // Env-derived context, mirroring ShellState's flags (env is the per-process source of truth;
    // reading it here avoids a ShellState -> NativeState -> ShellState singleton creation cycle).
    readonly property bool demo: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
    readonly property bool settingsApp: Quickshell.env("LME_SHELL_SETTINGS") === "1"
    readonly property bool backendDemo: demo || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1"

    // A/B drift bookkeeping for the Q1 window (removed with the backend sections at Q6).
    property var abMismatches: ({})
    property var abLastWarn: ({})

    // The backend-independent section set. In demo mode the static fixtures serve every
    // section; the native singletons are not even referenced (no service connections).
    readonly property var baseSections: {
        if (demo) return demoSections;
        const bluetooth = BluetoothState.sectionFor(ShellState.preferences.bluetoothAdapter);
        return {audio: AudioState.state, microphone: AudioState.microphone,
                battery: PowerState.battery, powerProfile: PowerState.profile, powerProfiles: PowerState.profiles,
                bluetooth: bluetooth, peripheralBatteries: mergePeripherals(bluetooth.batteries),
                network: NetworkState.state};
    }

    function merge(backend) {
        if (settingsApp && !demo) return backend; // standalone Settings keeps the backend's empty system
        return SystemMerge.merge(backend, baseSections, compose);
    }

    // Backend-fed transitional keys: rfkill block flags (no native API) and the Wi-Fi scan
    // lists (bssid-keyed connect; Q3 moves them). Pure function of (backend, base).
    function compose(backend, base) {
        if (demo) return base;
        const bluetoothBackend = backend["bluetooth"] || {};
        const networkBackend = backend["network"] || {};
        return Object.assign({}, base, {
            bluetooth: Object.assign({}, base.bluetooth, {
                softBlocked: bluetoothBackend.softBlocked === true,
                hardBlocked: bluetoothBackend.hardBlocked === true}),
            network: Object.assign({}, base.network, {
                networks: networkBackend.networks || [], saved: networkBackend.saved || []})
        });
    }

    // Port of scripts/peripheral_battery.py::merge_batteries over the native inputs.
    function mergePeripherals(bluetooth) {
        const result = {};
        const disconnected = {};
        for (const device of bluetooth) {
            if (!device.connected) { disconnected[device.id] = true; continue; }
            result[device.id] = Peripheral.percentage(device.percentage) === null
                ? device : Object.assign({}, device, {percentage: Peripheral.percentage(device.percentage)});
        }
        for (const device of PowerState.upowerPeripherals) {
            if (disconnected[device.id] && !(device.id in result)) continue; // lingering HID node after disconnect
            if (!(device.id in result)) result[device.id] = device;
            else for (const key of ["percentage", "charging"])
                if (result[device.id][key] === null && device[key] !== null) result[device.id][key] = device[key];
        }
        return Object.values(result).sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase())
            || a.id.localeCompare(b.id));
    }

    // Q1 A/B window: compare the backend's still-emitted sections against the merged (native)
    // view; count and warn on drift, rate-limited per section. Transitions are expected while
    // the backend poll lags the event-driven values — the counters are the day-long signal.
    function compareSections(backend, native) {
        const mismatches = {};
        const pairs = [["audio", ["available", "volume", "muted"]],
                       ["microphone", ["available", "volume", "muted"]],
                       ["battery", ["available", "percent", "charging", "acOnline"]],
                       ["powerProfile", null],
                       ["bluetooth", ["available", "enabled", "adapter"]],
                       ["network", ["available", "enabled", "connected", "wifiConnected", "ssid", "strength"]]];
        for (const [section, fields] of pairs) {
            if (!(section in (backend || {})) || !(section in (native || {}))) continue;
            const left = backend[section], right = native[section];
            const differs = fields ? fields.some(field => left[field] !== right[field]) : left !== right;
            if (!differs) continue;
            mismatches[section] = 1;
            abMismatches[section] = (abMismatches[section] || 0) + 1;
            const now = Date.now();
            if (!abLastWarn[section] || now - abLastWarn[section] > 30000) {
                abLastWarn[section] = now;
                console.warn("[Q1 A/B] " + section + " drift: backend " + JSON.stringify(left)
                    + " vs native " + JSON.stringify(fields ? fields.map(field => right[field]) : right));
            }
        }
        if (Array.isArray((backend || {}).peripheralBatteries) && Array.isArray(native.peripheralBatteries)
                && backend.peripheralBatteries.length !== native.peripheralBatteries.length) {
            // Counts only: UPower and the sysfs scan can legitimately expose different peripherals.
            mismatches.peripheralBatteries = 1;
            abMismatches.peripheralBatteries = (abMismatches.peripheralBatteries || 0) + 1;
        }
        return mismatches;
    }

    // BEGIN NATIVE_DEMO_SECTIONS (JSON; tests/test_native_state.py parses this block)
    readonly property var demoSections: {
        "audio": {"available": true, "volume": 42, "muted": false},
        "microphone": {"available": true, "volume": 60, "muted": false},
        "battery": {"available": true, "percent": 82, "charging": false, "acOnline": false},
        "powerProfile": "balanced",
        "powerProfiles": ["power-saver", "balanced", "performance"],
        "bluetooth": {"available": true, "enabled": true, "softBlocked": false, "hardBlocked": false,
                      "adapter": "/org/bluez/hci0",
                      "adapters": [{"path": "/org/bluez/hci0", "name": "Laptop Bluetooth", "enabled": true}],
                      "devices": [{"path": "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF", "id": "bluetooth:AA:BB:CC:DD:EE:FF",
                                   "name": "Headphones", "kind": "headphones", "connected": true, "percentage": 58, "charging": null}]},
        "peripheralBatteries": [{"id": "bluetooth:AA:BB:CC:DD:EE:FF", "name": "Headphones", "kind": "headphones",
                                 "connected": true, "percentage": 58, "charging": null},
                                {"id": "power_supply:demo-keyboard", "name": "Wireless keyboard", "kind": "keyboard",
                                 "connected": true, "percentage": 18, "charging": false}],
        "network": {"available": true, "enabled": true, "connected": true, "ssid": "Home Wi-Fi", "strength": 88,
                    "device": "wlp1s0", "saved": [{"uuid": "demo-home", "name": "Home Wi-Fi"}],
                    "networks": [{"ssid": "Home Wi-Fi", "strength": 88, "connected": true, "secured": true, "security": "WPA2", "bssid": "AA:BB:CC:DD:EE:01"},
                                 {"ssid": "Guest", "strength": 62, "connected": false, "secured": true, "security": "WPA2", "bssid": "AA:BB:CC:DD:EE:02"}]}
    }
    // END NATIVE_DEMO_SECTIONS
}
