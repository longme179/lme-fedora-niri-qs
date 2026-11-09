// Role: ActionPending.js (shared layer, fan-in 1).
// Shared component/helper; keep API stable for wide QML reuse.
.pragma library

function initial() {
    return {serial: 0, local: {}, acknowledged: 0, active: [], negotiated: false, pending: {}};
}

function sent(state, action) {
    const serial = state.serial + 1;
    if (!Number.isSafeInteger(serial)) throw new Error("Desktop request counter exhausted. Restart the shell.");
    return Object.assign({}, state, {serial, local: Object.assign({}, state.local, {[action]: serial}),
        pending: Object.assign({}, state.pending, {[action]: true})});
}

function received(state, metadata, result) {
    if (metadata === undefined && !state.negotiated) {
        const local = Object.assign({}, state.local), pending = Object.assign({}, state.pending);
        if (result && !result.pending) { delete local[result.action]; delete pending[result.action]; }
        return {state: Object.assign({}, state, {local, pending}), invalid: false};
    }
    if (!metadata || !Number.isSafeInteger(metadata.acknowledged)
            || metadata.acknowledged < state.acknowledged || metadata.acknowledged < 0
            || !Array.isArray(metadata.active)
            || metadata.active.some(action => typeof action !== "string" || !action)
            || new Set(metadata.active).size !== metadata.active.length)
        return {state, invalid: true};
    const local = {}, pending = {};
    for (const action of metadata.active) pending[action] = true;
    for (const action of Object.keys(state.local)) {
        if (state.local[action] > metadata.acknowledged) {
            local[action] = state.local[action]; pending[action] = true;
        }
    }
    return {state: Object.assign({}, state, {local, pending, acknowledged: metadata.acknowledged,
        active: metadata.active, negotiated: true}), invalid: false};
}

// Q3 native router: settle a locally-served action. The backend never sees the request, so
// its acknowledged/active metadata must not be waited for — the mirror of the pre-negotiation
// branch above (tests/test_native_wifi.py).
function settled(state, action) {
    const local = Object.assign({}, state.local), pending = Object.assign({}, state.pending);
    delete local[action]; delete pending[action];
    return Object.assign({}, state, {local, pending});
}
