// Role: NiriState.qml (shared layer) — native niri workspaces/windows section (Q4 session
// families; plan §5 Q4: "niri IPC moves to Socket").
// REL: scripts/niri_events.py – the cache this replaces; scripts/desktop_backend.py's event
// loop – the lifecycle this ports: subscribe once with the bare "EventStream" request, skip
// the {"Ok":...} ack, then feed every line to NiriModel; a dropped or erroring stream backs
// off 5 s (the backend's next_event_retry) and Workspaces/Windows reads reseed the cache at
// the backend's 2 s cadence while the stream is not serving. NiriIpc serves the short-lived
// request round-trips; the first fill after the ack does not wait for the poll tick.
// GOTCHA (Q4 real-machine lesson, second engine run): the subscribe line must be written
// from connectedChanged(true) — setting `connected = true` only opens the socket, and the
// niri IPC protocol never speaks first, so without the write the stream sits silent and
// the section degrades to the 2 s polled reads (the bug the event-stream engine case
// caught; the backend subscribes via its `niri msg --json event-stream` child).
// INVARIANT: the published section keeps the backend shape {available, workspaces, windows}
// and only changes identity when the model revision or the serving path moves (reference
// stability for delegate bindings). seed() alone marks the cache valid — events are deltas,
// so an invalid cache re-reads through NiriIpc before it serves again, exactly like the
// backend's `snapshot() or niri_state()` poll path. Fixture modes never start sockets.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "NiriModel.js" as NiriModel

QtObject {
    id: root

    // Env-derived context mirroring NativeState's flags (the per-process source of truth;
    // reading it here avoids a creation-order dependency on ShellState).
    readonly property bool settingsApp: Quickshell.env("LME_SHELL_SETTINGS") === "1"
    readonly property bool backendDemo: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
        || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1"
    readonly property string socketPath: Quickshell.env("NIRI_SOCKET") || ""
    readonly property bool live: !backendDemo && !settingsApp && socketPath !== ""

    property var cache: NiriModel.initial()
    property var section: ({available: false, workspaces: [], windows: []})
    property var lastRead: null       // the latest Workspaces/Windows read (serves while the stream is down)
    property var published: null
    property int publishedRevision: -1
    property bool streamWanted: false
    property bool acknowledged: false
    property bool reseeding: false

    property Socket stream: Socket {
        id: streamSocket
        path: root.socketPath
        connected: false
        parser: SplitParser { onRead: line => root.streamLine(line) }
        onConnectedChanged: {
            if (connected && root.streamWanted) {
                // The subscription request goes out the moment the connection is up —
                // the bare JSON line, exactly like NiriIpc's request writes.
                streamSocket.write('"EventStream"\n');
                streamSocket.flush();
            } else if (!connected) {
                root.streamDown();
            }
        }
        onError: error => root.streamDown()
    }

    // While the stream is not serving (starting up, invalidated by an unknown event, or
    // down), re-read at the backend's 2 s poll cadence; a healthy stream needs no timer.
    property Timer reseed: Timer {
        interval: 2000; repeat: true
        running: root.live && !root.reseeding && !(root.acknowledged && root.cache.valid && root.cache.streaming)
        onTriggered: root.reseedNow()
    }
    property Timer retry: Timer {
        interval: 5000
        onTriggered: root.startStream()
    }

    Component.onCompleted: if (live) startStream()

    function startStream() {
        if (!live || streamWanted) return;
        acknowledged = false;
        cache = NiriModel.connect(cache);
        publish();
        streamWanted = true;
        stream.connected = true;
    }

    function streamDown() {
        if (!streamWanted) return;
        streamWanted = false;
        stream.connected = false;
        cache = NiriModel.close(cache);
        publish();
        reseedNow();
        retry.restart();
    }

    function streamLine(line) {
        if (!streamWanted) return;
        if (!acknowledged) {
            acknowledged = true;
            let reply = null;
            try { reply = JSON.parse(line); } catch (error) {}
            if (!reply || typeof reply !== "object" || Array.isArray(reply) || !("Ok" in reply)) return streamDown();
            reseedNow();  // the first fill does not wait for the poll tick
            return;
        }
        cache = NiriModel.feed(cache, line + "\n");
        publish();
    }

    function reseedNow() {
        if (reseeding || !live) return;
        reseeding = true;
        NiriIpc.reads(model => {
            reseeding = false;
            lastRead = model;
            if (model.available === true) cache = NiriModel.seed(cache, model);
            publish();
        });
    }

    // snapshot() || lastRead || unavailable — the backend's `niri_cache.snapshot() or
    // niri_state()` shape, with identity changing only when the revision or the serving
    // path moves so niri bindings stay quiet while nothing changed.
    function publish() {
        const fresh = NiriModel.snapshot(cache);
        const chosen = fresh || lastRead || {available: false, workspaces: [], windows: []};
        if (chosen === published) return;
        if (fresh && cache.revision === publishedRevision) return;
        published = chosen;
        publishedRevision = fresh ? cache.revision : -1;
        section = chosen;
    }
}
