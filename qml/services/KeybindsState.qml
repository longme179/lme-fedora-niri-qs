// Role: KeybindsState.qml (shared layer) — native niri keybinding viewer (Q4 session
// families).
// REL: scripts/keybind_actions.py + scripts/niri_keybinds.py::read_keybinds – the action
// this ports: the preference path (niriConfigPath), then NIRI_CONFIG, then
// XDG_CONFIG_HOME/niri/config.kdl; the traversal itself runs in KeybindsModel.js over a
// FileView that reads one file at a time (reload() for a repeated path), bounded by the
// model's own include/size caps. The installed section keeps the backend shape
// {path, bindings, errors} exactly (tests/test_native_session.py freezes parity against
// the Python parser); keybindRefresh keeps its message. Fixture modes never reach here
// (the router gates them out, the demo registry reads the bundled config itself).
// INVARIANT: one traversal at a time — a dispatch while another is mid-walk re-uses the
// settled section only after the walk finishes; every dispatch settles exactly once.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "KeybindsModel.js" as KeybindsModel

QtObject {
    id: root

    property var section: ({path: "", bindings: [], errors: []})
    property var traversal: null
    property var pending: null      // the active done callback
    property string reading: ""

    readonly property var handledActions: ["keybindRefresh"]
    function handles(action) { return handledActions.includes(action); }
    // The service produces the backend's canonical errors itself (the model formats the
    // parser's exact strings), so real sessions always route here.
    function canRoute(action, payload, context) { return true; }

    property FileView reader: FileView {
        watchChanges: false
        printErrors: false
        onLoaded: root.ingest(text())
        onLoadFailed: error => root.ingestError()
    }

    function perform(action, request, done, context) {
        const preferences = context && context.preferences ? context.preferences : {};
        const configured = String(preferences.niriConfigPath || "");
        const home = Quickshell.env("HOME") || "";
        const raw = configured || Quickshell.env("NIRI_CONFIG") || "";
        const fallback = (Quickshell.env("XDG_CONFIG_HOME") || (home ? home + "/.config" : "")) + "/niri/config.kdl";
        traversal = KeybindsModel.start(raw || fallback, home);
        pending = done;
        step();
    }

    function step() {
        if (!traversal) return;
        const path = KeybindsModel.nextRead(traversal);
        if (path === null) {
            section = KeybindsModel.finish(traversal);
            traversal = null;
            const done = pending;
            pending = null;
            reading = "";
            if (done) done(true, "Keybindings refreshed");
            return;
        }
        reading = path;
        if (reader.path === path) reader.reload();
        else reader.path = path;
    }

    function ingest(text) {
        if (!traversal) return;
        traversal = KeybindsModel.ingest(traversal, text);
        step();
    }

    function ingestError() {
        if (!traversal) return;
        traversal = KeybindsModel.ingestError(traversal, "FileNotFound");
        step();
    }
}
