// Role: NiriIpc.qml (shared layer) — niri IPC request/response client (Q4 session families;
// plan §5 Q4: "niri IPC moves to Socket").
// REL: scripts/desktop_backend.py::niri_action – the exact protocol this ports: a fresh
// connection per request, {"Action": ...} + newline with compact JSON, one reply line capped
// at 1 MiB, the 3 s timeout surfacing as the TimeoutError string, and the error strings.
// Workspaces/Windows read requests reuse the same round-trip (the backend used two `niri
// msg` invocations; a second connection per request keeps the replies unambiguous).
// INVARIANT: every dispatched request settles exactly once through done(ok, value, error);
// requests queue one deep so concurrent dispatches serialize like the backend's
// single-threaded request loop. GOTCHA: SplitParser delivers whole lines without the
// newline; the 1 MiB cap is measured in characters (the backend counts bytes — ASCII CLI
// and niri JSON replies make the two equal in practice).
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "NiriModel.js" as NiriModel

QtObject {
    id: root

    readonly property string socketPath: Quickshell.env("NIRI_SOCKET") || ""
    property var queue: []              // [{line, done}]
    property var current: null
    property bool settled: false

    property Socket client: Socket {
        path: root.socketPath
        connected: false
        parser: SplitParser { onRead: line => root.lineRead(line) }
        onError: error => root.failed("The niri action failed")
        onConnectedChanged: if (connected && root.current) {
            // lib.rs/niri-ipc: write one JSON request line, then flush.
            client.write(root.current.line);
            client.flush();
        }
    }
    property Timer watchdog: Timer {
        interval: 3000
        onTriggered: root.failed("timed out")
    }

    // The action round-trip: done(ok, errorMessage) — scripts/window_actions.py's
    // capabilities.niri_action consumers only need the outcome, the reply payload is "Handled".
    function act(action, done) {
        request(JSON.stringify({Action: action}) + "\n", (ok, value, error) => done(ok, error));
    }

    // The reseed/validation read pair (backend: refresh_niri over `niri msg --json`), on two
    // separate connections exactly like the backend's two CLI invocations.
    function reads(done) {
        request('"Workspaces"\n', (okWorkspaces, workspaces) => {
            request('"Windows"\n', (okWindows, windows) => {
                done(okWorkspaces && okWindows ? NiriModel.fromReads(workspaces, windows)
                    : {available: false, workspaces: [], windows: []});
            });
        });
    }

    function request(line, done) {
        if (!socketPath) {
            done(false, null, "NIRI_SOCKET is unavailable. Run the shell inside the niri session.");
            return;
        }
        const entry = {line: line, done: done};
        if (current) { queue.push(entry); return; }
        start(entry);
    }

    function start(entry) {
        current = entry; settled = false;
        watchdog.restart();
        client.connected = true;  // the write happens on connection
    }

    function lineRead(line) {
        if (settled || !current) return;
        settled = true; watchdog.stop();
        if (line.length > 1048576) return finish(false, null, "The niri reply was too large");
        let reply;
        try { reply = JSON.parse(line); }
        catch (error) { return finish(false, null, "Invalid niri reply"); }
        if (!reply || typeof reply !== "object" || Array.isArray(reply)) return finish(false, null, "Invalid niri reply");
        if (!("Ok" in reply))
            return finish(false, null, typeof reply.Err === "string" ? reply.Err : "The niri action failed");
        finish(true, reply.Ok, "");
    }

    function failed(message) {
        if (settled || !current) return;
        settled = true;
        finish(false, null, message);
    }

    function finish(ok, value, error) {
        const entry = current;
        current = null; settled = false;
        watchdog.stop();
        client.connected = false;
        if (entry) entry.done(ok, value, error);
        if (queue.length) start(queue.shift());
    }
}
