// Role: StorageState.qml (Q6 leg 1) — the shell's single-writer preferences surface.
// REL: scripts/prefs_store.py (the locked, validated one-shot write — the SAME Preferences
//      semantics the backend runs, reused until leg 2 re-homes them and leg 3 retires the
//      backend); qml/services/WeatherState.qml (the first native consumer: weatherSelect);
//      qml/services/EqualizerState.qml + ClipboardState.qml (the FileView + queued-tool
//      pattern this mirrors).
// The settings document reads through a FileView with watchChanges — the shell stays current
// with the backend's own writes through the A/B window — and every native write is a one-shot
// prefs_store run, so the settings.lock flock, the reload-under-lock merge and the fsync are
// exactly the backend's path: the two writers coordinate on the lock until the sweep.
// INVARIANT: demo/preview and Settings-in-demo never persist — callers gate that (WeatherState's
// storageWriter default); this service is the dumb queued writer, like clipboard.py's role.
pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    property var runner  // (argv, seconds, done) => void — done(ok, stdout); tests inject
    property var toolQueue: []
    property bool toolBusy: false
    property var values: null  // the watched document; null until the first successful load
    signal applied(var values)  // the applied payload (not the whole document)
    readonly property string settingsPath: (Quickshell.env("XDG_CONFIG_HOME")
        || (Quickshell.env("HOME") + "/.config")) + "/lme-shell/settings.json"
    readonly property var baseArgs: ["python3", "-u", Quickshell.shellPath("scripts/prefs_store.py"),
                                     "--path", settingsPath]

    property FileView documentReader: FileView {
        path: root.settingsPath
        watchChanges: true
        printErrors: false
        onLoaded: {
            let parsed = null;
            try { parsed = JSON.parse(String(text)); } catch (error) { parsed = null; }
            if (parsed && typeof parsed === "object") root.values = parsed;
        }
    }

    // ---- the writer tool (one-shot Process + watchdog + queue — the eq/clipboard pattern) ----
    property Process tool: Process {
        id: store
        stdinEnabled: false
        property var reply: null
        property string collected: ""
        property bool startedOnce: false
        property bool timedOut: false
        stdout: SplitParser { onRead: line => { store.collected += line + "\n"; } }
        stderr: SplitParser { onRead: line => { } }
        onStarted: startedOnce = true
        onExited: (code, status) => {
            toolWatchdog.stop();
            const done = store.reply;
            store.reply = null;
            const ok = code === 0 && store.startedOnce && !store.timedOut;
            root.toolBusy = false;
            if (done) done(ok, store.collected);
            root.pumpTool();
        }
    }
    property Timer toolWatchdog: Timer { onTriggered: { tool.timedOut = true; tool.reply = null; tool.running = false; root.toolBusy = false; root.pumpTool(); } }
    function runTool(argv, seconds, done) {
        if (runner) return runner(argv, seconds, done);
        if (toolBusy) { toolQueue.push([argv, seconds, done]); return; }
        toolBusy = true;
        tool.reply = done;
        tool.collected = "";
        tool.startedOnce = false;
        tool.timedOut = false;
        tool.command = argv;
        tool.running = true;
        toolWatchdog.interval = seconds * 1000;
        toolWatchdog.restart();
    }
    function pumpTool() {
        if (toolBusy || !toolQueue.length) return;
        const next = toolQueue.shift();
        runTool(next[0], next[1], next[2]);
    }
    function parseReply(text) {
        const lines = String(text || "").split("\n").filter(line => line.length > 0);
        if (!lines.length) return null;
        try { return JSON.parse(lines[lines.length - 1]); } catch (_) { return null; }
    }

    function apply(values, done) {
        runTool(baseArgs.concat(["--set", JSON.stringify(values || {})]), 8, (ok, text) => {
            const parsed = parseReply(text);
            if (!ok || !parsed || parsed.ok !== true) {
                if (done) done(false, parsed && parsed.message
                    ? parsed.message : "Settings could not be written. Check the session and local storage.");
                return;
            }
            if (done) done(true, parsed.message || "Settings updated");
            applied(values);
        });
    }
}
