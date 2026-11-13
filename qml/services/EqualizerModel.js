// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: EqualizerModel.js (equalizer layer, fan-in 1) — pure contracts for the Q5 native
// equalizer: the staging math, the daemon report parsing and the set argv.
// REL: scripts/equalizer_actions.py (PRESETS/normalize/state_from_daemon_line/preset_for_gains/
// _daemon_set/saved_view) – DEPRECATED(Q5->Q6); frozen by tests/test_native_equalizer.py.
// INVARIANT: every message matches the Python source verbatim; the revert view keeps the
// committed bands with the current live values (restoreLastSavedEqualizer).
.pragma library

var DYNAMICS = ["off", "balanced", "night"];
var PRESETS = {
    "Flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Bass": [5, 7, 5, 2, 1, 0, 0, 0, 1, 2],
    "Treble": [-2, -1, 0, 1, 2, 3, 4, 5, 6, 6],
    "Vocal": [-2, -1, 1, 3, 5, 5, 4, 2, 1, 0],
    "Pop": [2, 4, 2, 0, 1, 2, 4, 2, 1, 2],
    "Rock": [5, 4, 2, -1, -2, -1, 2, 4, 5, 6],
    "Jazz": [3, 3, 1, 1, 1, 1, 2, 1, 2, 3],
    "Classic": [0, 1, 2, 2, 2, 2, 1, 2, 3, 4]
};

function defaultState() {
    return {b1: 0, b2: 0, b3: 0, b4: 0, b5: 0, b6: 0, b7: 0, b8: 0,
            b9: 0, b10: 0, preset: "Flat", pending: false, balance: 0,
            mono: false, swap: false, dynamics: "off", dyneq: false};
}

// Accept only a complete, well-typed eq_state document (the normalize port).
function normalize(state) {
    if (!state || typeof state !== "object") return null;
    const result = {};
    for (let index = 1; index <= 10; index++) {
        const value = Number(state["b" + index]);
        if (!Number.isFinite(value) || value < -12 || value > 12) return null;
        result["b" + index] = value;
    }
    const balance = Number(state.balance);
    if (!Number.isFinite(balance) || balance < -1 || balance > 1) return null;
    result.balance = balance;
    for (const key of ["mono", "swap", "dyneq"]) {
        if (typeof state[key] !== "boolean") return null;
        result[key] = state[key];
    }
    if (!DYNAMICS.includes(state.dynamics)) return null;
    result.dynamics = state.dynamics;
    result.pending = state.pending === true;
    result.preset = typeof state.preset === "string" && state.preset.length > 0 ? state.preset : "Flat";
    return result;
}

function bandError(value) {
    if (typeof value !== "number" || !Number.isInteger(value) || value < 1 || value > 10)
        return "Band must be an integer between 1 and 10";
    return "";
}

function gainError(value) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < -12 || value > 12)
        return "Equalizer gain is out of range";
    return "";
}

function balanceError(value) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < -1 || value > 1)
        return "Balance must be between -1 and 1";
    return "";
}

function flagError(value) {
    if (typeof value !== "boolean") return "Equalizer switches must be boolean";
    return "";
}

function dynamicsError(value) {
    if (!DYNAMICS.includes(value)) return "Unknown dynamics mode";
    return "";
}

function presetForGains(state) {
    const gains = [];
    for (let index = 1; index <= 10; index++) gains.push(String(state["b" + index]));
    for (const name in PRESETS) {
        const values = PRESETS[name];
        let same = true;
        for (let index = 0; index < 10; index++)
            if (String(values[index]) !== gains[index]) { same = false; break; }
        if (same) return name;
    }
    return "Custom";
}

// Seed an eq_state from the daemon's 17-token `ctl get` report.
function stateFromDaemonLine(line) {
    const tokens = String(line || "").trim().split(/\s+/);
    if (tokens.length !== 17 || tokens[0] !== "set") return null;
    const gains = [];
    for (let index = 1; index <= 10; index++) {
        const value = Number(tokens[index]);
        if (!Number.isFinite(value) || value < -12 || value > 12) return null;
        gains.push(value);
    }
    const balance = Number(tokens[11]);
    if (!Number.isFinite(balance) || balance < -1 || balance > 1) return null;
    for (const index of [12, 13, 15, 16])
        if (!["0", "1", "true", "false"].includes(tokens[index])) return null;
    if (!DYNAMICS.includes(tokens[14])) return null;
    const flag = token => token === "1" || token === "true";
    const state = defaultState();
    for (let index = 0; index < 10; index++) state["b" + (index + 1)] = gains[index];
    state.preset = presetForGains(state);
    state.balance = balance;
    state.mono = flag(tokens[12]);
    state.swap = flag(tokens[13]);
    state.dynamics = tokens[14];
    state.dyneq = flag(tokens[16]);
    return state;
}

// The full-state push argv (audio_ctl port).
function daemonSetArgs(state) {
    const args = ["serpantinum-audio", "ctl", "set"];
    for (let index = 1; index <= 10; index++) args.push(String(state["b" + index]));
    args.push(String(state.balance), state.mono ? "1" : "0", state.swap ? "1" : "0",
              state.dynamics, "0", state.dyneq ? "1" : "0");
    return args;
}

// Revert target: committed bands, current live values (restoreLastSavedEqualizer).
function savedView(committed, state) {
    const base = Object.assign({}, committed || state);
    for (const key of ["balance", "mono", "swap", "dynamics", "dyneq"]) base[key] = state[key];
    base.pending = false;
    base.preset = presetForGains(base);
    return base;
}
