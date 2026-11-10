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
// and niri JSON replies make the two equal in practice). GOTCHA (Q4 real-machine lesson,
// first engine run): quickshell 0.3.2 must not reuse one Socket across requests — flipping
// `connected` false→true while the previous connection is still tearing down never
// re-emits connectedChanged, the queued write is lost, the request stalls on the watchdog
// and the abandoned teardown segfaults the engine. Every request therefore builds its own
// Socket (the backend's fresh-connection protocol, literally) and retires it with a
// deferred destroy so the teardown finishes undisturbed.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "NiriModel.js" as NiriModel

QtObject {
    id: root

    readonly property string socketPath: Quickshell.env("NIRI_SOCKET") || ""
    property var queue: []              // [{line, done}]
    property var current: null          // the in-flight request
    property var client: null           // the in-flight Socket

    property Component requestSocket: Component {
        Socket {
            id: sock
            property var entry: null     // this connection's {line, done}
            property bool settled: false
            path: root.socketPath
            parser: SplitParser { onRead: line => root.lineRead(sock, line) }
            onError: error => root.failed(sock, "The niri action failed")
            onConnectedChanged: if (connected && sock.entry) {
                // lib.rs/niri-ipc: write one JSON request line, then flush.
                sock.write(sock.entry.line);
                sock.flush();
            }
        }
    }

    property Timer watchdog: Timer {
        interval: 3000
        onTriggered: if (client) root.failed(client, "timed out")
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
        current = entry;
        const socket = requestSocket.createObject(root, {entry: entry});
        if (!socket) {  // defensive: the INVARIANT still settles exactly once
            current = null;
            entry.done(false, null, "The niri action failed");
            if (queue.length) start(queue.shift());
            return;
        }
        watchdog.restart();
        client = socket;
        socket.connected = true;  // the write happens on connection
    }

    function lineRead(socket, line) {
        if (socket !== client || !socket.entry || socket.settled) return;
        socket.settled = true;
        if (line.length > 1048576) return finish(socket, false, null, "The niri reply was too large");
        let reply;
        try { reply = JSON.parse(line); }
        catch (error) { return finish(socket, false, null, "Invalid niri reply"); }
        if (!reply || typeof reply !== "object" || Array.isArray(reply)) return finish(socket, false, null, "Invalid niri reply");
        if (!("Ok" in reply))
            return finish(socket, false, null, typeof reply.Err === "string" ? reply.Err : "The niri action failed");
        finish(socket, true, reply.Ok, "");
    }

    function failed(socket, message) {
        if (socket !== client || !socket.entry || socket.settled) return;
        socket.settled = true;
        finish(socket, false, null, message);
    }

    function finish(socket, ok, value, error) {
        const entry = socket.entry;
        socket.entry = null;
        if (socket === client) { current = null; client = null; watchdog.stop(); }
        socket.connected = false;
        socket.destroy(1000);  // deferred: the teardown must not race the engine's socket loop
        if (entry) entry.done(ok, value, error);
        if (!current && queue.length) start(queue.shift());
    }
}
