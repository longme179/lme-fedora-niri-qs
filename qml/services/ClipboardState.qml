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
    property var state: ({entries: [], available: false, capturing: false, paused: false, total: 0})
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
    signal copied()
    signal searched(bool success)
    readonly property var entries: ShellState.demo ? demoEntries.filter(item => (filter === "all" || item.kind === filter) && item.preview.toLowerCase().includes(query.toLowerCase())) : state.entries || []
    readonly property bool paused: ShellState.demo ? demoPaused : state.paused === true
    readonly property bool available: ShellState.demo || state.available === true
    readonly property bool capturing: ShellState.demo ? !demoPaused : state.capturing === true
    readonly property int total: ShellState.demo ? demoEntries.length : state.total || 0

    function start() { if (!ShellState.demo && !ShellState.settingsApp) started = true; }
    function search(value, kind) {
        query = value; filter = kind;
        if (ShellState.demo) searched(true);
        else if (ready && backend.running) { pendingSearches++; searching = true; send("search", {query: value, kind: kind}); }
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
        if (!ready || !backend.running) { message = "Clipboard service is unavailable."; messageError = true; return; }
        if (action === "copy") copyPending = true;
        backend.write(JSON.stringify(Object.assign({}, payload || {}, {action: action})) + "\n");
    }
    function accept(data) {
        try {
            const next = JSON.parse(data);
            if (!Array.isArray(next.entries)) return;
            if (JSON.stringify(next.entries) === JSON.stringify(state.entries)) next.entries = state.entries;
            const first = !ready;
            state = next; ready = true; restartAttempts = 0;
            if (first) { message = ""; messageError = false; if (query || filter !== "all") search(query, filter); }
            if (next.lastResult && (!lastResult || next.lastResult.sequence !== lastResult.sequence)) {
                lastResult = next.lastResult;
                if (lastResult.action === "copy") copyPending = false;
                if (lastResult.action === "search") {
                    pendingSearches = Math.max(0, pendingSearches - 1); searching = pendingSearches > 0;
                    if (!searching) searched(lastResult.ok);
                }
                message = lastResult.message || ""; messageError = !lastResult.ok;
                if (lastResult.action === "copy" && lastResult.ok) copied();
            }
        } catch (_) { message = "Clipboard state could not be read."; messageError = true; }
    }
    property Process backend: Process {
        command: ["python3", Quickshell.shellPath("scripts/clipboard.py")]
        running: root.started && !ShellState.demo && !ShellState.settingsApp
        stdinEnabled: true
        stdout: SplitParser { onRead: data => root.accept(data) }
        onExited: {
            root.ready = false; root.copyPending = false; root.searching = false;
            root.pendingSearches = 0; root.lastResult = null;
            root.message = "Clipboard service stopped. Check the shell log."; root.messageError = true;
            if (root.started && root.restartAttempts < 3) { root.restartAttempts++; root.restart.restart(); }
        }
    }
    property Timer restart: Timer { interval: 1200; onTriggered: root.backend.running = true }
}
