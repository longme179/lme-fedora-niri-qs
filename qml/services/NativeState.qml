// Role: NativeState.qml (shared layer, fan-in 1) — Q1/Q2 native-section composition for the merged system.
// REL: AudioState/PowerState/BluetoothState/NetworkState – Q1 native sections; MonitorState – Q2 file-sourced
// system fields; LauncherState – Q2 apps/usage; SystemMerge.js – reference-stable merge.
// INVARIANT: fixture modes (demo/preview, LME_SHELL_BACKEND_DEMO, standalone Settings) pass the backend
// system through unchanged — the demo backend is STATEFUL (audio/power/network actions mutate its
// snapshot) and development tests inject hardware state through it; native sections engage only in the
// real session (tests/test_native_state.py + tests/test_native_files.py freeze the shapes both sides keep).
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
    // backendDemo includes demo/preview; settingsApp is the standalone Settings entry.
    readonly property bool settingsApp: Quickshell.env("LME_SHELL_SETTINGS") === "1"
    readonly property bool backendDemo: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
        || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1"

    // A/B drift bookkeeping for the Q1 window (removed with the backend sections at Q6).
    property var abMismatches: ({})
    property var abLastWarn: ({})

    // The backend-independent section set; null in every fixture mode so the native services
    // are never even referenced there (no service connections in demo/tests/Settings).
    readonly property var baseSections: {
        if (backendDemo || settingsApp) return null;
        const bluetooth = BluetoothState.sectionFor(ShellState.preferences.bluetoothAdapter);
        const fields = MonitorState.systemFields; // Q2: reading it here keys the merge cache to the monitor tick
        return {audio: AudioState.state, microphone: AudioState.microphone,
                battery: PowerState.battery, powerProfile: PowerState.profile, powerProfiles: PowerState.profiles,
                bluetooth: bluetooth, peripheralBatteries: mergePeripherals(bluetooth.batteries),
                network: NetworkState.state,
                cpu: fields.cpu, memoryPercent: fields.memoryPercent,
                memoryUsedGiB: fields.memoryUsedGiB, memoryTotalGiB: fields.memoryTotalGiB};
    }

    function merge(backend) {
        if (backendDemo || settingsApp) return SystemMerge.merge(backend, null, passthrough);
        return SystemMerge.merge(backend, baseSections, compose);
    }

    function passthrough(backend, base) { return {}; }

    // Backend-fed transitional keys: rfkill block flags (no native API) and the Wi-Fi scan
    // lists (bssid-keyed connect; Q3 moves them), plus the Q2 file gaps — temperature and brightness
    // need hwmon/backlight directory globs and the process table needs /proc/<pid> iteration, none of
    // which quickshell 0.3.2 can do (no directory listing API); they stay backend-sourced until the
    // Process machinery lands (DEPRECATED(Q2->Q6)). Pure function of (backend, base).
    function compose(backend, base) {
        const bluetoothBackend = backend["bluetooth"] || {};
        const networkBackend = backend["network"] || {};
        return Object.assign({}, base, {
            tempC: backend.tempC !== undefined ? backend.tempC : null,
            brightness: backend.brightness !== undefined ? backend.brightness : {available: false, percent: null},
            charging: backend.charging,
            bluetooth: Object.assign({}, base.bluetooth, {
                softBlocked: bluetoothBackend.softBlocked === true,
                hardBlocked: bluetoothBackend.hardBlocked === true}),
            network: Object.assign({}, base.network, {
                networks: networkBackend.networks || [], saved: networkBackend.saved || []})
        });
    }

    // Q2 top-level keys: the app list and usage scores come from LauncherState in real sessions;
    // fixture modes pass the backend values through (the demo backend owns the demo apps).
    function apps(backendApps) {
        if (backendDemo || settingsApp) return backendApps || [];
        return LauncherState.apps || [];
    }

    function usage(backendUsage, rankingEnabled) {
        if (backendDemo || settingsApp) return backendUsage || {};
        return LauncherState.usage(rankingEnabled);
    }

    // Q2 monitor section: native cores/interfaces/history over the backend's process table
    // (kept backend-fed — /proc/<pid> iteration has no quickshell 0.3.2 counterpart).
    function monitor(backendMonitor) {
        if (backendDemo || settingsApp) return backendMonitor || {};
        const backend = backendMonitor || {};
        return Object.assign({}, MonitorState.section, {
            processes: backend.processes || [], processCount: backend.processCount || 0});
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
    // ShellState gates this to real sessions (not demo/backendDemo/settings).
    function compareSections(backendSnapshot, native, nativeApps) {
        const backend = backendSnapshot && backendSnapshot.system !== undefined ? backendSnapshot.system : backendSnapshot;
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
        // Q2 file families. memoryTotalGiB is stable (exact compare); cpu/memoryPercent sample at
        // different instants so they are deliberately not compared. The apps count is expected to
        // drift up: quickshell cannot filter OnlyShowIn/NotShowIn/TryExec (no such properties).
        if (backend && backend.memoryTotalGiB !== undefined && native.memoryTotalGiB !== backend.memoryTotalGiB) {
            mismatches.memoryTotalGiB = 1;
            abMismatches.memoryTotalGiB = (abMismatches.memoryTotalGiB || 0) + 1;
        }
        const backendApps = backendSnapshot && Array.isArray(backendSnapshot.apps) ? backendSnapshot.apps : null;
        if (backendApps && Array.isArray(nativeApps) && backendApps.length !== nativeApps.length) {
            mismatches.apps = 1;
            abMismatches.apps = (abMismatches.apps || 0) + 1;
            const now = Date.now();
            if (!abLastWarn.apps || now - abLastWarn.apps > 30000) {
                abLastWarn.apps = now;
                console.warn("[Q2 A/B] apps drift: backend " + backendApps.length + " vs native " + nativeApps.length
                    + " (quickshell cannot filter OnlyShowIn/NotShowIn/TryExec)");
            }
        }
        return mismatches;
    }
}
