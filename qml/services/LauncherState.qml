// Role: LauncherState.qml (launcher layer, fan-in 3) — native app list, launch history store, app launch (plan Q2).
// REL: Quickshell.DesktopEntries – applications/byId/execute(); Quickshell.Io.FileView – launcher.json store.
// INVARIANT: the apps list and usage scores mirror the backend's apps/launcherUsage sections
// (scripts/desktop_backend.py::Applications.scan + scripts/launcher_history.py; tests/test_native_files.py
// freezes the shapes and decay). Known fidelity edges (A/B window catches both): quickshell exposes no
// OnlyShowIn/NotShowIn/TryExec, so the native list can be a small superset of the backend's; Exec field
// codes are stripped rather than expanded; ids keep the backend's ".desktop" suffix for history continuity.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root

    // Env-derived context, mirroring NativeState's flags (reading env here avoids a
    // ShellState -> LauncherState -> ShellState singleton creation cycle).
    readonly property bool settingsApp: Quickshell.env("LME_SHELL_SETTINGS") === "1"
    readonly property bool backendDemo: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
        || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1"
    readonly property bool nativeMode: !settingsApp && !backendDemo  // 'native' is a reserved QML keyword

    // scripts/launcher_history.py constants (launch-score decay adapted from Serpantinum; THIRD_PARTY.md).
    readonly property real halfLifeDays: 7
    readonly property real launchSecondsPerEvent: 90
    readonly property int retentionDays: 60
    readonly property int maxApps: 256

    property var store: ({})   // validated {app: {last, days}} from the history file
    property string error: ""  // mirrors the backend launcherHistoryError surface
    property var recordQueue: [] // launches awaiting the next fresh read (read-modify-write, like the flock'd Python)

    readonly property string storePath: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/lme-shell/launcher.json"

    // The native app list; null in every fixture mode so DesktopEntries is never even
    // referenced there (no desktop scan in demo/tests/Settings).
    readonly property var apps: {
        if (!nativeMode) return null;
        return mapApplications(DesktopEntries.applications.values);
    }

    // Port of Applications.scan's output shape and ordering (name casefold, then id).
    function mapApplications(values) {
        const apps = [];
        for (let index = 0; index < values.length; index++) {
            const entry = values[index];
            if (!entry.name || !entry.command || !entry.command.length) continue; // backend drops nameless/no-exec entries
            apps.push({id: entry.id + ".desktop", name: entry.name, icon: entry.icon || "",
                       terminal: entry.runInTerminal === true, genericName: entry.genericName || "",
                       comment: entry.comment || "", keywords: Array.from(entry.keywords || [])});
        }
        apps.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()) || a.id.localeCompare(b.id));
        return apps;
    }

    // Port of launcher_history.py::snapshot — decayed scores over the validated store.
    function usage(rankingEnabled) {
        if (!nativeMode || rankingEnabled === false) return {};
        const now = Date.now() / 1000;
        const today = utcDay(now);
        const scores = {};
        for (const app in store) {
            const item = store[app];
            let weight = 0;
            for (const day in item.days) {
                const age = Math.max(0, Math.round((today - daySeconds(day)) / 86400));
                weight += item.days[day] * Math.pow(0.5, age / halfLifeDays);
            }
            scores[app] = {score: weight * launchSecondsPerEvent, last: Math.min(now, item.last)};
        }
        return scores;
    }

    // Port of launcher_history.py::record — bounded, validated, atomic store update.
    // The write waits for a fresh read (the Python side held an flock around read+write).
    function record(app) {
        if (!nativeMode || !validAppId(app)) return;
        recordQueue.push(app);
        storeView.reload();
    }

    function clear() {
        if (!nativeMode) return;
        recordQueue = [];
        store = {};
        storeView.setText('{"schema":1,"apps":{}}');
    }

    // Native launch: fixture modes keep the backend round-trip (demo preview, pending UX);
    // real sessions resolve the entry by id and detach it from the shell process.
    function launch(id) {
        if (!nativeMode) { ShellState.run("launch", {id: id}); return; }
        const entry = DesktopEntries.byId(String(id || "").replace(/\.desktop$/, ""));
        if (!entry || !entry.name) {
            ShellState.statusMessage = "Application is no longer available; refresh the launcher";
            ShellState.statusError = true; ShellState.statusTimer.restart();
            return;
        }
        if (entry.runInTerminal === true) {
            // Same wrap as window_actions.py::launch: the configured terminal plus the entry command.
            terminalProcess.command = [ShellState.preferences.terminal || "kitty", "-e"].concat(Array.from(entry.command));
            terminalProcess.startDetached();
        } else {
            entry.execute(); // Quickshell execDetached: survives the shell (no SIGKILL-on-destroy trap)
        }
        if (ShellState.preferences.launcherRanking !== false) record(id);
    }

    property Process terminalProcess: Process { command: [] }

    property FileView storeView: FileView {
        path: root.nativeMode ? root.storePath : ""
        atomicWrites: true; blockWrites: true; watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: {
            root.error = "";
            const next = root.parseStore(text());
            root.store = next;
            if (root.recordQueue.length) root.applyRecords(next, root.recordQueue);
        }
        onLoadFailed: error => {
            if (error === FileViewError.FileNotFound) { // first launch on a machine
                root.store = {};
                if (root.recordQueue.length) root.applyRecords({}, root.recordQueue);
            } else if (root.nativeMode) root.error = "Usage history could not be read: " + FileViewError.toString(error);
        }
        onSaveFailed: error => { root.error = "Usage history could not be saved: " + FileViewError.toString(error); }
    }

    // Port of launcher_history.py::read — every bound and cap the Python side enforces.
    function parseStore(text) {
        let raw;
        try { raw = JSON.parse(text); } catch (error) { return {}; }
        if (!raw || raw.schema !== 1 || typeof raw !== "object" || !raw.apps || typeof raw.apps !== "object") return {};
        const today = utcDay(Date.now() / 1000);
        const result = {};
        let count = 0;
        for (const app in raw.apps) {
            if (count >= maxApps * 2) break;
            count++;
            const item = raw.apps[app];
            if (!validAppId(app) || !item || typeof item !== "object") continue;
            const last = item.last, days = item.days;
            if (typeof last !== "number" || !(last >= 0) || last > 253402300799 || !days || typeof days !== "object") continue;
            const valid = {};
            for (const day in days) {
                const dayCount = days[day];
                if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !Number.isInteger(dayCount) || dayCount < 1 || dayCount > 1000000) continue;
                const age = Math.round((today - daySeconds(day)) / 86400);
                if (age < retentionDays) valid[day] = dayCount; // python keeps future-stamped days too (age < 60); NaN fails the test
            }
            const keys = Object.keys(valid).sort().reverse().slice(0, retentionDays);
            if (keys.length) result[app] = {last: last, days: Object.fromEntries(keys.map(key => [key, valid[key]]))};
        }
        const ordered = Object.keys(result).sort((a, b) => result[b].last - result[a].last).slice(0, maxApps);
        return Object.fromEntries(ordered.map(app => [app, result[app]]));
    }

    // Port of launcher_history.py::record's mutation — read-fresh, stamp every queued launch, re-cap, write.
    function applyRecords(current, queue) {
        const now = Date.now() / 1000;
        const today = dayKey(now);
        const apps = Object.assign({}, current);
        for (const app of queue) {
            const item = apps[app] || {last: now, days: {}};
            const days = Object.assign({}, item.days);
            days[today] = Math.min(1000000, (days[today] || 0) + 1);
            apps[app] = {last: now, days: days};
        }
        recordQueue = [];
        const ordered = Object.keys(apps).sort((a, b) => apps[b].last - apps[a].last).slice(0, maxApps);
        const capped = Object.fromEntries(ordered.map(app => [app, apps[app]]));
        store = capped;
        storeView.setText(JSON.stringify({schema: 1, apps: capped}));
    }

    function validAppId(app) {
        return typeof app === "string" && app.length >= 1 && app.length <= 512
            && !Array.from(app).some(character => character.charCodeAt(0) < 32
                || (character.charCodeAt(0) >= 0xd800 && character.charCodeAt(0) <= 0xdfff));
    }

    function utcDay(seconds) {
        return Math.floor(seconds / 86400) * 86400;
    }

    function daySeconds(day) {
        return Date.parse(day + "T00:00:00Z") / 1000;  // NaN for invalid keys (python's fromisoformat ValueError)
    }

    function dayKey(seconds) {
        return new Date(seconds * 1000).toISOString().slice(0, 10);
    }
}
