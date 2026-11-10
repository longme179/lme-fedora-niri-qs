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

    // Backend-fed transitional keys: rfkill block flags (no native API) and the Q2 file gaps —
    // temperature and brightness need hwmon/backlight directory globs and the process table needs
    // /proc/<pid> iteration, none of which quickshell 0.3.2 can do (no directory listing API); they
    // stay backend-sourced until the Process machinery lands (DEPRECATED(Q2->Q6)). The Wi-Fi scan
    // lists moved to NetworkState in Q3 (networks/saved ride in the native section). Pure
    // function of (backend, base).
    function compose(backend, base) {
        const bluetoothBackend = backend["bluetooth"] || {};
        return Object.assign({}, base, {
            tempC: backend.tempC !== undefined ? backend.tempC : null,
            brightness: backend.brightness !== undefined ? backend.brightness : {available: false, percent: null},
            charging: backend.charging,
            bluetooth: Object.assign({}, base.bluetooth, {
                softBlocked: bluetoothBackend.softBlocked === true,
                hardBlocked: bluetoothBackend.hardBlocked === true})
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

    // Q3 inventory families: the on-demand sections ride natively after their first dispatch;
    // fixture modes pass the backend through (the demo registry owns its state). No A/B count
    // compare — these sections only populate on dispatch, so the backend copy stays empty
    // while native serves (documented deviation; the owner's panel checklist is the signal).
    function audioDevices(backendSection) {
        if (backendDemo || settingsApp) return backendSection || {};
        return AudioDeviceState.section || backendSection || {};
    }

    function networkConnections(backendSection) {
        if (backendDemo || settingsApp) return backendSection || {};
        return NetworkInventoryState.projection;
    }

    // Q4 keybinds: the on-demand viewer section rides natively after keybindRefresh;
    // fixture modes pass the backend through (the demo registry reads the bundled config).
    function keybinds(backendSection) {
        if (backendDemo || settingsApp) return backendSection || {path: "", bindings: [], errors: []};
        return KeybindsState.section || backendSection || {path: "", bindings: [], errors: []};
    }

    // Q4 niri: the event-stream section (NiriState.qml) serves once it is available; until
    // then the backend's poll copy stands in (exactly the snapshot() || niri_state() shape).
    // The drag pin freezes the last served reference like Identity.keep did, so a drag never
    // re-renders delegates; reference stability otherwise comes from NiriState.publish.
    property var lastNiri: null
    function niri(backendNiri, dragging) {
        if (backendDemo || settingsApp) return backendNiri || {available: false, windows: [], workspaces: []};
        const fallback = backendNiri || {available: false, windows: [], workspaces: []};
        if (dragging) return lastNiri || fallback;
        const native = NiriState.section;
        if (native && native.available === true) { lastNiri = native; return native; }
        return fallback;
    }

    // Q4 display/mirror + night-light/idle legs: the same gating pattern — fixture modes
    // pass the backend section through (the Settings preview flow and the demo registry
    // own their state there); real sessions serve the native section with the backend copy
    // as the stand-in until the first dispatch/sync populates it. No A/B compare entries
    // for these sections: like the Q3/Q4 on-demand families, the backend copy stays empty
    // while native serves — the owner's panel checklist is the parity signal.
    function displays(backendSection) {
        if (backendDemo || settingsApp) return backendSection || {outputs: [], preview: {}};
        return DisplayState.section || backendSection || {outputs: [], preview: {}};
    }

    function mirror(backendSection) {
        if (backendDemo || settingsApp) return backendSection || {};
        return MirrorState.section || backendSection || {};
    }

    function nightLight(backendSection) {
        if (backendDemo || settingsApp) return backendSection || {};
        return NightLightState.section || backendSection || {};
    }

    function idle(backendSection) {
        if (backendDemo || settingsApp) return backendSection || {};
        return IdleState.section || backendSection || {};
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
    function compareSections(backendSnapshot, native, nativeApps, nativeNiri, dragging) {
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
        // Q3 wifi lists. Counts only: scan timing jitters the network list between the backend's
        // last nmcli read and the live model, and saved profiles in hotspot (ap) mode are a known
        // quickshell 0.3.2 gap — count drift is the day-long signal for the owner.
        const backendNetwork = (backend || {}).network || {}, nativeNetwork = (native || {}).network || {};
        for (const key of ["networks", "saved"]) {
            const left = backendNetwork[key], right = nativeNetwork[key];
            if (!Array.isArray(left) || !Array.isArray(right) || left.length === right.length) continue;
            mismatches[key] = 1;
            abMismatches[key] = (abMismatches[key] || 0) + 1;
            const now = Date.now();
            if (!abLastWarn[key] || now - abLastWarn[key] > 30000) {
                abLastWarn[key] = now;
                console.warn("[Q3 A/B] " + key + " drift: backend " + left.length + " vs native " + right.length
                    + " (scan timing; hotspot-mode saved profiles are a known native edge)");
            }
        }
        // Q4 niri lists. Counts only, and skipped while dragging (the pin freezes the native
        // reference): the event-driven native section leads the backend's poll copy, so
        // transient +/-1 windows during open/close bursts are the expected shape.
        if (!dragging) {
            const backendNiri = (backendSnapshot || {}).niri || null;
            if (backendNiri && nativeNiri && backendNiri.available === true && nativeNiri.available === true) {
                for (const key of ["windows", "workspaces"]) {
                    const left = backendNiri[key], right = nativeNiri[key];
                    if (!Array.isArray(left) || !Array.isArray(right) || left.length === right.length) continue;
                    const label = key === "windows" ? "niriWindows" : "niriWorkspaces";
                    mismatches[label] = 1;
                    abMismatches[label] = (abMismatches[label] || 0) + 1;
                    const now = Date.now();
                    if (!abLastWarn[label] || now - abLastWarn[label] > 30000) {
                        abLastWarn[label] = now;
                        console.warn("[Q4 A/B] niri " + key + " drift: backend " + left.length + " vs native " + right.length
                            + " (the native event stream leads the backend's poll copy)");
                    }
                }
            }
        }
        return mismatches;
    }
}
