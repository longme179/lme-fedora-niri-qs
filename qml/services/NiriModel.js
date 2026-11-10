// Role: NiriModel.js (shared layer) — niri workspace/window state machine (Q4 session families).
// REL: scripts/niri_events.py – the event cache this ports verbatim: the IGNORED set, the
// bounded 8 MiB buffer, one-key event objects, and every handler's validation rules (an
// unknown/malformed/out-of-order event invalidates the cache instead of corrupting it).
// INVARIANT: seed() is the only path to valid=true (events are deltas over an authoritative
// read — WorkspacesChanged never marks the cache valid), exactly like the backend's poll
// loop that reseeds from `niri msg` whenever the stream is not serving. Pure functions over
// a state object; the owning singleton reassigns the returned reference.
.pragma library

var IGNORED = {"KeyboardLayoutsChanged": true, "KeyboardLayoutSwitched": true, "OverviewOpenedOrClosed": true,
    "ConfigLoaded": true, "ScreenshotCaptured": true, "CastsChanged": true, "CastStartedOrChanged": true,
    "CastStopped": true, "TouchpadToggled": true};

function isObject(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function isInt(value) { return typeof value === "number" && Number.isInteger(value); }

// scripts/niri_events.py::read_niri_state's normalization: both reads must be arrays of
// objects or the state is unavailable; workspaces sort by (output, idx, id) with codepoint
// ordering like Python's tuple key (localeCompare would reorder DP-1/eDP-1 differently).
function fromReads(workspaces, windows) {
    if (!Array.isArray(workspaces) || !Array.isArray(windows)
            || !workspaces.every(isObject) || !windows.every(isObject))
        return {available: false, workspaces: [], windows: []};
    const rows = workspaces.slice();
    rows.sort(function (a, b) {
        return compare(String(a.output || ""), String(b.output || ""))
            || (Number(a.idx || 0) - Number(b.idx || 0)) || (Number(a.id || 0) - Number(b.id || 0));
    });
    return {available: true, workspaces: rows, windows: windows.slice()};
}

function compare(left, right) {
    if (left < right) return -1;
    if (left > right) return 1;
    return 0;
}

function initial() {
    return {revision: 0, valid: false, streaming: false, workspaces: [], windows: [], buffer: ""};
}

// The mutators return a fresh object reference (sharing the mutated arrays) so QML var
// property reassignment always notifies — bindings on cache.valid/streaming stay live.
function connect(state) { state.streaming = true; return invalidate(state); }
function close(state) { state.streaming = false; return invalidate(state); }
function invalidate(state) { state.valid = false; state.buffer = ""; return Object.assign({}, state); }

function seed(state, snapshot) {
    state.workspaces = (snapshot && snapshot.workspaces || []).slice();
    state.windows = (snapshot && snapshot.windows || []).slice();
    state.valid = snapshot && snapshot.available === true;
    state.revision += 1;
    return Object.assign({}, state);
}

function snapshot(state) {
    if (!(state.valid && state.streaming)) return null;
    return {available: true, workspaces: state.workspaces, windows: state.windows};
}

// GOTCHA: bounded buffer; oversized/malformed stream invalidates instead of unbounded growth.
function feed(state, data) {
    state.buffer += data;
    if (state.buffer.length > 8 * 1024 * 1024) return invalidate(state);
    let split = state.buffer.indexOf("\n");
    while (split >= 0) {
        const line = state.buffer.slice(0, split);
        state.buffer = state.buffer.slice(split + 1);
        if (line.trim()) apply(state, line);
        split = state.buffer.indexOf("\n");
    }
    return Object.assign({}, state);
}

function apply(state, line) {
    let event;
    try { event = JSON.parse(line); }
    catch (error) { return invalidate(state); }
    if (!isObject(event) || Object.keys(event).length !== 1) return invalidate(state);
    const name = Object.keys(event)[0], payload = event[name];
    if (IGNORED[name]) return state;
    const handler = HANDLERS[name];
    if (!handler || !isObject(payload) || !handler(state, payload)) return invalidate(state);
    return state;
}

var HANDLERS = {
    WorkspacesChanged: function (state, payload) {
        const rows = payload.workspaces;
        if (!Array.isArray(rows) || !rows.every(isObject)) return false;
        state.workspaces = rows;
        state.workspaces.sort(function (a, b) {
            return compare(String(a.output || ""), String(b.output || ""))
                || (Number(a.idx || 0) - Number(b.idx || 0)) || (Number(a.id || 0) - Number(b.id || 0));
        });
        state.revision += 1; return true;
    },
    WorkspaceActivated: function (state, payload) {
        const ident = payload.id, focused = payload.focused;
        if (!isInt(ident) || typeof focused !== "boolean") return false;
        const target = state.workspaces.find(function (item) { return item.id === ident; });
        if (target === undefined) return false;
        for (const item of state.workspaces) {
            if (item.output === target.output) item.is_active = item.id === ident;
            if (focused) item.is_focused = item.id === ident;
        }
        state.revision += 1; return true;
    },
    WorkspaceActiveWindowChanged: function (state, payload) {
        const ident = payload.workspace_id, active = payload.active_window_id;
        if (!isInt(ident) || (active !== null && active !== undefined && !isInt(active))) return false;
        const target = state.workspaces.find(function (item) { return item.id === ident; });
        if (target === undefined) return false;
        target.active_window_id = active === undefined ? null : active;
        state.revision += 1; return true;
    },
    WorkspaceUrgencyChanged: function (state, payload) {
        const ident = payload.id, urgent = payload.urgent;
        if (!isInt(ident) || typeof urgent !== "boolean") return false;
        const target = state.workspaces.find(function (item) { return item.id === ident; });
        if (target === undefined) return false;
        target.is_urgent = urgent;
        state.revision += 1; return true;
    },
    WindowsChanged: function (state, payload) {
        const rows = payload.windows;
        if (!Array.isArray(rows) || !rows.every(isObject)) return false;
        state.windows = rows;
        state.revision += 1; return true;
    },
    WindowOpenedOrChanged: function (state, payload) {
        const window = payload.window;
        if (!isObject(window) || !isInt(window.id)) return false;
        const ident = window.id;
        const index = state.windows.findIndex(function (item) { return item.id === ident; });
        if (index >= 0) state.windows[index] = window;
        else state.windows.push(window);
        if (window.is_focused) focusWindow(state, ident);
        state.revision += 1; return true;
    },
    WindowClosed: function (state, payload) {
        const ident = payload.id;
        if (!isInt(ident) || !state.windows.some(function (item) { return item.id === ident; })) return false;
        state.windows = state.windows.filter(function (item) { return item.id !== ident; });
        state.revision += 1; return true;
    },
    WindowFocusChanged: function (state, payload) {
        const ident = payload.id;
        if (ident !== null && ident !== undefined && !isInt(ident)) return false;
        focusWindow(state, ident === undefined ? null : ident);
        state.revision += 1; return true;
    },
    WindowFocusTimestampChanged: function (state, payload) {
        const ident = payload.id;
        if (!isInt(ident)) return false;
        const target = state.windows.find(function (item) { return item.id === ident; });
        if (target === undefined) return false;
        target.focus_timestamp = payload.focus_timestamp;
        state.revision += 1; return true;
    },
    WindowLayoutsChanged: function (state, payload) {
        const changes = payload.changes;
        if (!Array.isArray(changes)) return false;
        for (const change of changes) {
            if (!Array.isArray(change) || change.length !== 2 || !isInt(change[0])) return false;
            const target = state.windows.find(function (item) { return item.id === change[0]; });
            if (target === undefined) return false;
            target.layout = change[1];
        }
        state.revision += 1; return true;
    }
};

function focusWindow(state, ident) {
    for (const item of state.windows) item.is_focused = item.id === ident;
}
