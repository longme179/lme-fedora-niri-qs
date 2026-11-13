// Role: ClipboardState.qml (clipboard layer) — owns clipboard history UI state and the native flows.
// INVARIANT: watcher lifecycle stays main-shell scoped; Settings/demo must not start capture.
// REL: scripts/clipboard.py (one-shot actions + the capture worker); scripts/clipboard_watch.py
//      (flock + PR_SET_PDEATHSIG wl-paste supervisor — quickshell SIGKILLs its children on
//      normal exit and the kernel SIGTERMs the wrapper when the shell dies any other way,
//      probed on quickshell 0.3.2, 2026-11-13); qml/panels/ClipboardPanel.qml – consumer UI.
// The Q5 native port retired the JSON-lines serve daemon: every action is a one-shot
// subcommand through the tool Process, and the messages are frozen by the local suite.
// The Q6 refresh fix: the capture worker announces each commit as one JSON line on the
// watcher's stdout pipe (noteWatcherOutput → eventDebounce → runSearch); monitoring
// derives from ShellState's panel routing, and the 2 s repeat poll is the fallback.
pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    property bool started: false
    property bool ready: ShellState.demo
    property int restartAttempts: 0
    property var state: ({entries: [], available: false, capturing: false, paused: false, total: 0, error: ""})
    property var demoEntries: [
        {id: "demo-note", kind: "text", preview: "One thing at a time.\nA little more space for your next idea.", pinned: true, bytes: 70, image: ""},
        {id: "demo-link", kind: "text", preview: "https://github.com/longme179/lme-fedora-niri-qs", pinned: false, bytes: 51, image: ""},
        {id: "demo-image", kind: "image", preview: "PNG image · Dracula", pinned: false, bytes: 8240, image: "file://" + Quickshell.shellPath("assets/wallpapers/liquid-dracula.png")},
        {id: "demo-command", kind: "text", preview: "qs -c lme-shell", pinned: false, bytes: 14, image: ""}
    ]
    property string query: ""
    property string filter: "all"
    property string message: ""
    property bool messageError: false
    property bool copyPending: false
    property bool searching: false
    property int pendingSearches: 0
    property bool demoPaused: false
    property var lastResult: null
    // The panel host (SlideLoader) parks closed panels off-screen WITHOUT toggling the
    // item's visible (a visible flip costs ~800 ms on a retained tree), so a panel-side
    // visible hookup can never fire — derive the open state from the shell's panel
    // routing instead. Gates the revision poll and the on-open refresh.
    property bool monitoring: ShellState.catalogPanelOpen && ShellState.panelKind === "clipboard"
    property bool watchersSuspended: false  // engine-test isolation: never spawn real watchers
    property int lastRevision: -1
    property int resultSequence: 0
    signal copied()
    signal searched(bool success)
    readonly property var entries: ShellState.demo ? demoEntries.filter(item => (filter === "all" || item.kind === filter) && item.preview.toLowerCase().includes(query.toLowerCase())) : state.entries || []
    readonly property bool paused: ShellState.demo ? demoPaused : state.paused === true
    readonly property bool available: ShellState.demo || state.available === true
    readonly property bool capturing: ShellState.demo ? !demoPaused : state.capturing === true
    readonly property int total: ShellState.demo ? demoEntries.length : state.total || 0
    readonly property string directory: (Quickshell.env("XDG_STATE_HOME")
        || (Quickshell.env("HOME") + "/.local/state")) + "/lme-shell/clipboard"
    readonly property var baseArgs: ["python3", "-u", Quickshell.shellPath("scripts/clipboard.py"), "--directory", directory]

    // ---- the action tool (one-shot Process + watchdog + queue) -------------------------
    property var runner  // (argv, seconds, done) => void — done(ok, stdout); tests inject
    property var toolQueue: []
    property bool toolBusy: false
    property Process tool: Process {
        id: clip
        stdinEnabled: false
        property var reply: null
        property string collected: ""
        property bool startedOnce: false
        property bool timedOut: false
        stdout: SplitParser { onRead: line => { clip.collected += line + "\n"; } }
        stderr: SplitParser { onRead: line => { } }
        onStarted: startedOnce = true
        onExited: (code, status) => {
            toolWatchdog.stop();
            const done = clip.reply;
            clip.reply = null;
            const ok = code === 0 && clip.startedOnce && !clip.timedOut;
            root.toolBusy = false;
            if (done) done(ok, clip.collected);
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

    // ---- the capture watchers ----------------------------------------------------------
    property bool stoppingText: false
    property bool stoppingImage: false
    function watcherCommand(kind) {
        return ["python3", Quickshell.shellPath("scripts/clipboard_watch.py"),
                "--parent", String(Quickshell.processId), "--kind", kind, "--directory", directory];
    }
    property Process textWatcher: Process {
        stdinEnabled: false
        stdout: SplitParser { onRead: line => root.noteWatcherOutput(line) }
        onExited: (code, status) => root.watcherDied("text", root.stoppingText)
    }
    property Process imageWatcher: Process {
        stdinEnabled: false
        stdout: SplitParser { onRead: line => root.noteWatcherOutput(line) }
        onExited: (code, status) => root.watcherDied("image", root.stoppingImage)
    }
    function noteWatcherOutput(line) {
        const text = String(line || "").trim();
        if (!text) return;
        // The worker's post-commit announcement rides the same pipe; anything else is
        // the supervisor's or wl-paste's own error text and keeps the old error surface.
        const parsed = text.startsWith("{") ? parseReply(text) : null;
        if (parsed && parsed.revision !== undefined) { eventDebounce.restart(); return; }
        state = Object.assign({}, state, {error: text});
    }
    function wantedKinds() {
        if (watchersSuspended || !started || ShellState.demo || ShellState.settingsApp) return [];
        if (ShellState.preferences.clipboardEnabled === false || state.paused === true) return [];
        return ShellState.preferences.clipboardImages === false ? ["text"] : ["text", "image"];
    }
    function syncWatchers() {
        const wanted = wantedKinds();
        const wantText = wanted.includes("text"), wantImage = wanted.includes("image");
        if (wantText && !textWatcher.running) { stoppingText = false; textWatcher.command = watcherCommand("text"); textWatcher.running = true; }
        if (!wantText && textWatcher.running) { stoppingText = true; textWatcher.running = false; }
        if (wantImage && !imageWatcher.running) { stoppingImage = false; imageWatcher.command = watcherCommand("image"); imageWatcher.running = true; }
        if (!wantImage && imageWatcher.running) { stoppingImage = true; imageWatcher.running = false; }
        const capturing = (wantText || wantImage) && (!wantText || textWatcher.running) && (!wantImage || imageWatcher.running);
        if (state.capturing !== capturing) state = Object.assign({}, state, {capturing: capturing});
    }
    function watcherDied(kind, stopping) {
        if (stopping || !started || ShellState.demo || ShellState.settingsApp) return;
        // The serve daemon's capture-failure surface, message for message.
        state = Object.assign({}, state, {capturing: false,
            error: "Clipboard capture stopped. Check Wayland data-control support and the session."});
        if (restartAttempts < 3) { restartAttempts++; retryTimer.restart(); }
    }
    property Timer retryTimer: Timer { interval: 5000; onTriggered: root.syncWatchers() }
    property Timer poll: Timer {
        interval: 2000
        repeat: true
        running: root.monitoring && root.ready && !ShellState.demo && !ShellState.settingsApp
        onTriggered: root.refreshState()
    }

    // ---- the capture event (the worker announces its commit on the watcher pipe) --------
    // clipboard.py --capture prints {"revision": N} after every store; wl-paste --watch
    // forwards the worker's stdout (probed live 2026-11-13), so the event rides the pipe
    // the watchers already own — no polling, no file watching (quickshell 0.3.2's file
    // watcher never reloads on change), no Wayland focus dependency (the clipboard
    // signal needs a focused surface). The debounce coalesces copy bursts into one search.
    property Timer eventDebounce: Timer {
        interval: 250
        onTriggered: if (root.ready && !ShellState.demo && !ShellState.settingsApp) root.runSearch()
    }
    onMonitoringChanged: if (monitoring && ready) refreshState()

    // ---- state sync and search ---------------------------------------------------------
    function refreshState() {
        runTool(baseArgs.concat("--state"), 8, (ok, text) => {
            const parsed = parseReply(text);
            if (!ok || !parsed || parsed.ok !== true) {
                if (!ready) { message = "Clipboard state could not be read."; messageError = true; }
                return;
            }
            const fresh = !ready;
            state = Object.assign({}, state, {available: parsed.available === true, paused: parsed.paused === true,
                                              total: parsed.total || 0});
            restartAttempts = 0;
            if (fresh) { ready = true; message = ""; messageError = false; }
            if (parsed.revision !== lastRevision) {
                const changed = lastRevision >= 0;
                lastRevision = parsed.revision;
                if (changed || fresh) runSearch();  // fresh entries on capture while the panel is open
            }
            syncWatchers();
        });
    }
    function runSearch() {
        pendingSearches++; searching = true;
        runTool(baseArgs.concat(["--search", query, filter]), 8, (ok, text) => {
            pendingSearches = Math.max(0, pendingSearches - 1);
            const parsed = parseReply(text);
            const good = ok && parsed && parsed.ok === true;
            if (good) {
                let entries = parsed.entries || [];
                if (JSON.stringify(entries) === JSON.stringify(state.entries)) entries = state.entries;
                state = Object.assign({}, state, {entries: entries, total: parsed.total || 0});
                if (parsed.revision !== undefined) lastRevision = parsed.revision;
            } else {
                query = ""; filter = "all";  // the serve loop reset an invalid search
            }
            searching = pendingSearches > 0;
            if (!searching) searched(good);
        });
    }

    // ---- the panel interface (unchanged surface) ---------------------------------------
    function start() {
        if (!ShellState.demo && !ShellState.settingsApp) { started = true; refreshState(); }
    }
    function search(value, kind) {
        query = value; filter = kind;
        if (ShellState.demo) searched(true);
        else if (ready) runSearch();
    }
    function send(action, payload) {
        if (ShellState.demo) {
            if (action === "copy") { message = "Demo · clipboard unchanged"; copied(); }
            else if (action === "pin") demoEntries = demoEntries.map(item => item.id === payload.id ? Object.assign({}, item, {pinned: !item.pinned}) : item).sort((a, b) => Number(b.pinned) - Number(a.pinned));
            else if (action === "delete") demoEntries = demoEntries.filter(item => item.id !== payload.id);
            else if (action === "clear") demoEntries = payload.includePinned ? [] : demoEntries.filter(item => item.pinned);
            else if (action === "pause") demoPaused = payload.value;
            return;
        }
        if (!ready) { message = "Clipboard service is unavailable."; messageError = true; return; }
        let argv = baseArgs;
        if (action === "copy") { copyPending = true; argv = baseArgs.concat(["--copy", payload.id]); }
        else if (action === "pin") argv = baseArgs.concat(["--pin", payload.id]);
        else if (action === "delete") argv = baseArgs.concat(["--delete", payload.id]);
        else if (action === "clear") argv = baseArgs.concat(["--clear", payload.includePinned ? "true" : "false"]);
        else if (action === "pause") argv = baseArgs.concat(["--pause", payload.value ? "true" : "false"]);
        else { message = "Clipboard service is unavailable."; messageError = true; return; }
        runTool(argv, 8, (ok, text) => {
            const parsed = parseReply(text);
            const good = ok && parsed && parsed.ok === true;
            const note = (parsed && parsed.message) || (good ? "" : "Clipboard operation failed. Check the Wayland session and local storage.");
            resultSequence++;
            lastResult = {action: action, ok: good, message: note, sequence: resultSequence};
            message = note; messageError = !good;
            if (good) {
                state = Object.assign({}, state, {paused: parsed.paused === true, total: parsed.total || 0});
                if (action === "pause") syncWatchers();
                if (parsed.revision !== undefined && parsed.revision !== lastRevision) { lastRevision = parsed.revision; runSearch(); }
            }
            if (action === "copy") { copyPending = false; if (good) copied(); }
        });
    }
}
