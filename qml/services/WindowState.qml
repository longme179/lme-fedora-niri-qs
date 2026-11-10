// Role: WindowState.qml (shared layer) — compositor window/workspace actions (Q4 session
// families; plan §5 Q4 family 5).
// REL: scripts/window_actions.py – the four live handlers this ports: focusWindow and
// nativeOverview as one-shot `niri msg action` argv (command_runner.py's timeout/output
// contract through CommandRunner), moveWindow and workspace through NiriIpc's action
// round-trip with the backend's validation order — moveWindow refreshes before checking,
// workspace checks the merged lists first and refreshes only on a miss. `launch` already
// routes through LauncherState (Q2); `fileOpen` stays on the backend until the Q5 search
// entries own its validation. desktop_backend.py::identifier is the ID contract.
// INVARIANT: every dispatch settles exactly once through done(ok, message) with the
// backend's exact strings; the actions queue through the shared runners (no busy gate —
// the backend serialized them the same way, so rapid workspace switches never block).
pragma Singleton
import QtQuick

QtObject {
    id: root

    property CommandRunner tools: CommandRunner { id: runner }

    readonly property var handledActions: ["focusWindow", "moveWindow", "nativeOverview", "workspace"]
    function handles(action) { return handledActions.includes(action); }
    // The service produces the backend's canonical errors itself (a missing niri binary or
    // NIRI_SOCKET surfaces through CommandRunner/NiriIpc's exact strings), so real sessions
    // always route here; fixture modes never reach the router.
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        try {
            if (action === "focusWindow") return focus(request, done);
            if (action === "nativeOverview") return overview(done);
            if (action === "moveWindow") return move(request, done);
            if (action === "workspace") return workspace(request, done, context);
            done(false, "Unknown window action");
        } catch (error) { done(false, String(error)); }
    }

    // desktop_backend.py::identifier — a non-negative numeric ID.
    function identifier(value) {
        if (typeof value !== "number" || !Number.isInteger(value) || value < 0)
            throw "A non-negative numeric ID is required";
        return String(value);
    }

    function focus(request, done) {
        const id = identifier(request && request.id);
        runner.dispatch("niri", ["niri", "msg", "action", "focus-window", "--id", id], 3000, 16777216,
            (ok, text, error) => done(ok, ok ? "Window focused" : error));
    }

    function overview(done) {
        runner.dispatch("niri", ["niri", "msg", "action", "toggle-overview"], 3000, 16777216,
            (ok, text, error) => done(ok, ok ? "Native overview toggled" : error));
    }

    function move(request, done) {
        const windowId = Number(identifier(request && request.id));
        const workspaceId = Number(identifier(request && request.workspaceId));
        refresh(niri => {
            if (!niri.windows.some(item => item.id === windowId)
                    || !niri.workspaces.some(item => item.id === workspaceId))
                return done(false, "Window or workspace is no longer available");
            NiriIpc.act({MoveWindowToWorkspace: {window_id: windowId, reference: {Id: workspaceId}, focus: false}},
                (ok, error) => done(ok, ok ? "Window moved to workspace" : error));
        });
    }

    function workspace(request, done, context) {
        const id = identifier(request && request.id);
        const current = context && context.niri ? context.niri : {workspaces: []};
        if (current.workspaces.some(item => String(item.id) === id))
            return activate(id, done);
        refresh(niri => {
            if (niri.workspaces.some(item => String(item.id) === id)) activate(id, done);
            else done(false, "Workspace is no longer available");
        });
    }

    function activate(id, done) {
        NiriIpc.act({FocusWorkspace: {reference: {Id: Number(id)}}},
            (ok, error) => done(ok, ok ? "Workspace focused" : error));
    }

    // desktop_backend.py::refresh_action_niri — a fresh Workspaces/Windows read pair; an
    // unavailable read yields the empty model so the membership checks fail exactly like
    // the backend's `niri_state()` fallback.
    function refresh(ok) {
        NiriIpc.reads(model => ok(model || {available: false, workspaces: [], windows: []}));
    }
}
