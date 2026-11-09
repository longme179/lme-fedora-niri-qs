// Role: MonitorState.qml (systemMonitor layer, fan-in 2) — native /proc sampling for cpu, memory and
// the monitor panel (plan Q2). REL: Quickshell.Io.FileView – /proc/stat, /proc/meminfo, /proc/net/dev.
// INVARIANT: the section shapes mirror scripts/desktop_backend.py::cpu_memory() and scripts/system_monitor.py
// (tests/test_native_files.py freezes the math). Cadence stays 2 s — the backend --interval default
// (no A6 change). Known fidelity edges: /proc/<pid> iteration and the hwmon/thermal globs have no
// quickshell 0.3.2 counterpart (no directory listing API), so the process table and temperature stay
// backend-fed through NativeState (DEPRECATED(Q2->Q6)); monitor cores use the always-on 2 s stat
// windows, so the first sample after reopening the panel is fresh rather than interval-averaged.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root

    // Env-derived context, mirroring NativeState's flags (avoids a ShellState creation cycle).
    readonly property bool settingsApp: Quickshell.env("LME_SHELL_SETTINGS") === "1"
    readonly property bool backendDemo: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
        || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1"
    readonly property bool nativeMode: !settingsApp && !backendDemo  // 'native' is a reserved QML keyword

    // The System monitor panel is open: gates /proc/net/dev sampling and the history window,
    // mirroring the backend's monitor_enabled action.
    property bool enabled: false

    property var systemFields: ({cpu: null, memoryPercent: null, memoryUsedGiB: null, memoryTotalGiB: null})
    property var coreRows: []
    property var interfaceRows: []
    property var history: []
    property real sampledAt: 0
    property string monitorError: ""
    property var statTotals: null  // {total: [total, idle], cores: {NAME: [total, idle]}}
    property var netTotals: ({})   // {name: [received, sent]}

    readonly property var section: ({cores: coreRows, interfaces: interfaceRows, history: history,
                                    sampledAt: sampledAt, error: monitorError})

    // The system poll: 2 s, matching the backend's --interval default (plan §5 Q2, no A6 change).
    // procfs has no inotify — watchChanges stays false and the timer drives reload()s.
    property Timer poll: Timer {
        interval: 2000; running: root.nativeMode; repeat: true
        onTriggered: root.tick()
    }
    property ElapsedTimer netClock: ElapsedTimer {}  // the net window: restarted only on monitor ticks
    property real netInterval: 0                      // the interval the in-flight net read should use

    property FileView statView: FileView {
        path: root.nativeMode ? "/proc/stat" : ""
        watchChanges: false; printErrors: false
        onLoaded: root.ingestStat(text())
    }
    property FileView memView: FileView {
        path: root.nativeMode ? "/proc/meminfo" : ""
        watchChanges: false; printErrors: false
        onLoaded: root.ingestMem(text())
    }
    property FileView netView: FileView {
        path: root.nativeMode && root.enabled ? "/proc/net/dev" : ""
        watchChanges: false; printErrors: false
        onLoaded: root.ingestNet(text())
    }

    // Re-enabling keeps the net window running since the previous monitor session (like the Python
    // monitor's persisted previous_time): the path-change auto-load gets no window (null rates), the
    // first tick's window spans the gap, so re-opened counters resume without a spike.
    onEnabledChanged: if (nativeMode && enabled) netInterval = 0

    function tick() {
        if (enabled) {
            // The completed net window: history pairs this interval's rates with the same window's
            // cpu/memory (both were ingested during the previous tick).
            const elapsed = netClock.restart();
            netInterval = elapsed;
            pushHistory(elapsed > 0 ? elapsed : 0);
            netView.reload();
        }
        statView.reload();
        memView.reload();
    }

    function ingestStat(text) {
        const parsed = parseStat(text, statTotals);
        statTotals = parsed.totals;
        systemFields = Object.assign({}, systemFields, {cpu: parsed.cpu});
        if (enabled) coreRows = parsed.cores;
        monitorError = parsed.cores.length ? "" : "CPU statistics are unavailable.";
    }

    function ingestMem(text) {
        systemFields = Object.assign({}, systemFields, parseMeminfo(text));
    }

    function ingestNet(text) {
        const parsed = parseNetDev(text, netTotals, netInterval);
        netTotals = parsed.totals;
        if (enabled) interfaceRows = parsed.interfaces;
    }

    // Port of desktop_backend.py::cpu_memory + system_monitor.py core rows over one /proc/stat read.
    function parseStat(text, previous) {
        let aggregate = null;
        const cores = {}, rows = [];
        for (const line of text.split("\n")) {
            const fields = line.trim().split(/\s+/);
            if (!fields.length || !fields[0].startsWith("cpu")) continue;
            const values = fields.slice(1, 9).map(value => Number(value));
            if (values.length < 8 || values.some(value => !Number.isFinite(value))) continue;
            const total = values.reduce((sum, value) => sum + value, 0);
            const idle = values[3] + values[4];
            if (fields[0] === "cpu") { aggregate = [total, idle]; continue; }
            const name = fields[0].toUpperCase();
            const old = previous && previous.cores ? previous.cores[name] : null;
            rows.push({name: name, percent: percentBetween(total, idle, old)});
            cores[name] = [total, idle];
        }
        const oldAggregate = previous ? previous.total : null;
        return {cpu: aggregate ? percentBetween(aggregate[0], aggregate[1], oldAggregate) : null,
                cores: rows, totals: {total: aggregate, cores: cores}};
    }

    function percentBetween(total, idle, old) {
        if (!old || !(total > old[0])) return null;
        return round1(Math.max(0, Math.min(100, 100 * (1 - (idle - old[1]) / (total - old[0])))));
    }

    // Port of desktop_backend.py::cpu_memory's meminfo half.
    function parseMeminfo(text) {
        const data = {};
        for (const line of text.split("\n")) {
            const match = /^(\S+):\s+(\d+)/.exec(line);
            if (match) data[match[1]] = Number(match[2]);
        }
        const total = data.MemTotal || 0;
        const available = data.MemAvailable;
        if (total > 0 && available !== undefined) {
            const used = Math.max(0, total - available);
            return {memoryPercent: round1(100 * used / total),
                    memoryUsedGiB: round2(used / 1048576), memoryTotalGiB: round2(total / 1048576)};
        }
        return {memoryPercent: null, memoryUsedGiB: null, memoryTotalGiB: null};
    }

    // Port of system_monitor.py's /proc/net/dev half (lo excluded, clamped deltas over the interval).
    function parseNetDev(text, previous, elapsed) {
        const interfaces = [], totals = {};
        for (const line of text.split("\n")) {
            const index = line.indexOf(":");
            if (index < 0) continue;
            const name = line.slice(0, index).trim();
            if (!name || name === "lo") continue;
            const fields = line.slice(index + 1).trim().split(/\s+/).map(value => Number(value));
            if (fields.length < 9 || fields.some(value => !Number.isFinite(value))) continue;
            const old = previous ? previous[name] : null;
            interfaces.push({name: name,
                download: old && elapsed > 0 ? Math.max(0, fields[0] - old[0]) / elapsed : null,
                upload: old && elapsed > 0 ? Math.max(0, fields[8] - old[1]) / elapsed : null});
            totals[name] = [fields[0], fields[8]];
        }
        return {interfaces: interfaces, totals: totals};
    }

    // Port of system_monitor.py's history sample (maxlen 60, nulls coalesced to 0 like the sum()).
    function pushHistory(elapsed) {
        const interfaces = interfaceRows;
        let download = 0, upload = 0;
        for (const item of interfaces) { download += item.download || 0; upload += item.upload || 0; }
        history = history.concat([{cpu: systemFields.cpu, memory: systemFields.memoryPercent,
                                   download: elapsed > 0 ? download : null, upload: elapsed > 0 ? upload : null}]);
        if (history.length > 60) history = history.slice(history.length - 60);
        sampledAt = Date.now() / 1000;
    }

    function round1(value) { return Math.round(value * 10) / 10; }
    function round2(value) { return Math.round(value * 100) / 100; }
}
