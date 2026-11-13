// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: FileSearchState.qml (launcher layer, fan-in 1) — Q5 native file search owner
// and the fileOpen entry validation.
// REL: scripts/file_search.py + file_search_actions.py + window_actions.py::file_open –
// DEPRECATED(Q5->Q6); the messages and the section shape are frozen by
// tests/test_native_search_visualizer.py.
// INVARIANT: fixture modes (demo/preview, LME_SHELL_BACKEND_DEMO, standalone Settings)
// never spawn the worker — the backend keeps serving them.
// GOTCHA: the scandir core cannot leave Python (quickshell 0.3.2 has no directory
// listing), so the search runs in file_search.py --worker — one request line in, one
// result line out. A new search kills the previous worker (the cancel Event's native
// half). fileOpen validates against the live entries; the Python re-stat of the target
// (resolve + is_file) has no QML equivalent — a file moved after the search degrades to
// gio failing silently instead of 'File moved or became unavailable'.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root

    readonly property bool inert: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
        || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1" || Quickshell.env("LME_SHELL_SETTINGS") === "1"

    property var section: ({query: "", entries: [], truncated: false})
    property string pendingPath: ""
    property bool opening: false

    readonly property var handledActions: ["fileSearch", "fileOpen"]
    function handles(action) { return handledActions.includes(action); }
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        if (inert) return done(false, "File search is unavailable in this mode");
        if (action === "fileSearch") return search(request || {}, done, context);
        if (action === "fileOpen") return open(request || {}, done);
        return done(false, "Unknown file search action");
    }

    function search(request, done, context) {
        const preferences = (context && context.preferences) || {};
        if (!preferences.fileSearchEnabled) return done(false, "File search is disabled");
        const query = request.query;
        if (typeof query !== "string" || query.trim().length < 2 || query.trim().length > 160)
            return done(false, "File search needs 2\u2013160 characters");
        const folders = preferences.fileSearchRoots || [];
        section = {query: query.trim(), entries: [], truncated: false};
        // One worker at a time: a new search replaces (kills) the previous — the cancel
        // Event's native half.
        if (worker.running) worker.running = false;
        worker.query = query.trim();
        worker.folders = JSON.stringify(folders);
        worker.running = true;
        return done(true, "File search completed");
    }

    function open(request, done) {
        const path = request.path;
        if (typeof path !== "string" || !path)
            return done(false, "Search again before opening this file");
        const found = section.entries.some(entry => entry.path === path);
        if (!found) return done(false, "Search again before opening this file");
        if (opener.running) return done(false, "A file is already opening");
        opening = true;
        opener.command = ["gio", "open", "file://" + path];
        opener.running = true;
        return done(true, "Opened file");
    }

    property Process worker: Process {
        id: searchWorker
        property string query: ""
        property string folders: "[]"
        command: ["python3", "-u", Quickshell.shellPath("scripts/file_search.py"), "--worker"]
        stdinEnabled: true
        stdout: SplitParser { onRead: line => {
            try {
                const value = JSON.parse(line);
                if (value && Array.isArray(value.entries) && value.query === searchWorker.query)
                    root.section = value;
            } catch (error) { console.warn("Invalid file search result"); }
        } }
        stderr: SplitParser { onRead: line => console.warn("[file-search]", line) }
        onStarted: write(JSON.stringify({query: query, folders: JSON.parse(folders)}) + "\n")
        onExited: (code, status) => { if (code !== 0) console.warn("[file-search] worker exited", code); }
    }

    property Process opener: Process {
        id: fileOpener
        command: []
        stdinEnabled: false
        onExited: (code, status) => { root.opening = false; if (code !== 0) console.warn("[file-open] gio exited", code); }
    }
}
