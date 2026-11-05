pragma Singleton

import QtQuick
import "../services"

Singleton {
    id: root

    // Serpantinum MusicEqualizerState port: optimistic applies, staging, lightning.
    property var eqData: defaultState()
    property var savedEqData: defaultState()
    property string loadStatus: ""
    property bool audioTestRunning: false
    property real lastLocalUpdate: 0

    readonly property var presets: ({
        "Flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "Bass": [5, 7, 5, 2, 1, 0, 0, 0, 1, 2],
        "Treble": [-2, -1, 0, 1, 2, 3, 4, 5, 6, 6],
        "Vocal": [-2, -1, 1, 3, 5, 5, 4, 2, 1, 0],
        "Pop": [2, 4, 2, 0, 1, 2, 4, 2, 1, 2],
        "Rock": [5, 4, 2, -1, -2, -1, 2, 4, 5, 6],
        "Jazz": [3, 3, 1, 1, 1, 1, 2, 1, 2, 3],
        "Classic": [0, 1, 2, 2, 2, 2, 1, 2, 3, 4]
    })

    function defaultState() {
        return {b1: 0, b2: 0, b3: 0, b4: 0, b5: 0, b6: 0, b7: 0, b8: 0, b9: 0, b10: 0,
                preset: "Flat", pending: false, balance: 0, mono: false, swap: false,
                dynamics: "off", dyneq: false};
    }

    function validState(value) {
        if (!value || typeof value !== "object")
            return null;
        const state = {};
        for (let index = 1; index <= 10; index++) {
            const gain = Number(value["b" + index]);
            if (!Number.isFinite(gain) || gain < -12 || gain > 12)
                return null;
            state["b" + index] = gain;
        }
        const balance = Number(value.balance);
        if (!Number.isFinite(balance) || balance < -1 || balance > 1)
            return null;
        state.balance = balance;
        for (const key of ["mono", "swap", "dyneq"]) {
            if (typeof value[key] !== "boolean")
                return null;
            state[key] = value[key];
        }
        if (!["off", "balanced", "night"].includes(value.dynamics))
            return null;
        state.dynamics = value.dynamics;
        state.pending = value.pending === true;
        state.preset = typeof value.preset === "string" && value.preset.length > 0 ? value.preset : "Flat";
        return state;
    }

    function hydrate(message) {
        let parsed = null;
        try { parsed = validState(JSON.parse(String(message || ""))); }
        catch (error) { parsed = null; }
        if (!parsed)
            return;
        eqData = parsed;
        if (!parsed.pending)
            savedEqData = Object.assign({}, parsed);
        loadStatus = "";
    }

    function send(action, payload) {
        if (ShellState.backendReady)
            ShellState.run(action, payload);
    }

    function refresh() {
        send("eqGet");
    }

    function applyPreset(name) {
        const values = presets[name];
        if (!values)
            return;
        const next = Object.assign({}, eqData);
        for (let index = 0; index < 10; index++)
            next["b" + (index + 1)] = values[index];
        next.preset = name;
        next.pending = false;
        eqData = next;
        savedEqData = Object.assign({}, next);
        lastLocalUpdate = Date.now();
        triggerLightning();
        send("eqPreset", {name: name});
    }

    function setBand(band, value) {
        const next = Object.assign({}, eqData);
        next["b" + band] = value;
        next.preset = "Custom";
        next.pending = true;
        eqData = next;
        lastLocalUpdate = Date.now();
        send("eqSetBand", {band: band, value: value});
    }

    function commit() {
        if (!eqData.pending || eqData.dyneq === true)
            return;
        const next = Object.assign({}, eqData);
        next.pending = false;
        eqData = next;
        savedEqData = Object.assign({}, next);
        lastLocalUpdate = Date.now();
        triggerLightning();
        send("eqApply");
    }

    function revertPending() {
        if (!eqData.pending)
            return;
        eqData = Object.assign({}, savedEqData);
        lastLocalUpdate = Date.now();
        send("eqRevert");
    }

    function setBalance(value) {
        const clamped = Math.max(-1, Math.min(1, Number(value)));
        if (!Number.isFinite(clamped))
            return;
        const next = Object.assign({}, eqData);
        next.balance = Math.round(clamped * 100) / 100;
        eqData = next;
        savedEqData = Object.assign({}, next);
        lastLocalUpdate = Date.now();
        send("eqBalance", {value: next.balance});
    }

    function setFlag(name, value) {
        if (!["mono", "swap", "dyneq"].includes(name))
            return;
        const next = Object.assign({}, eqData);
        next[name] = value === true;
        eqData = next;
        savedEqData = Object.assign({}, next);
        lastLocalUpdate = Date.now();
        send(name === "mono" ? "eqMono" : name === "swap" ? "eqSwap" : "eqDyneq", {value: next[name]});
    }

    function setDynamics(value) {
        if (!["off", "balanced", "night"].includes(value))
            return;
        const next = Object.assign({}, eqData);
        next.dynamics = value;
        eqData = next;
        savedEqData = Object.assign({}, next);
        lastLocalUpdate = Date.now();
        send("eqDynamics", {value: value});
    }

    function resetAudio() {
        const next = Object.assign({}, eqData);
        next.balance = 0;
        next.mono = false;
        next.swap = false;
        next.dynamics = "off";
        eqData = next;
        savedEqData = Object.assign({}, next);
        lastLocalUpdate = Date.now();
        send("eqReset");
    }

    Timer {
        id: testTimer
        interval: 3200
        onTriggered: root.audioTestRunning = false
    }

    function toggleTest() {
        if (audioTestRunning) {
            send("eqTestStop");
            audioTestRunning = false;
            testTimer.stop();
        } else {
            send("eqTest");
            audioTestRunning = true;
            testTimer.restart();
        }
    }

    property real eqLightningProgress: 0.0
    property real eqLightningFade: 1.0

    SequentialAnimation {
        id: lightningAnim
        running: false
        ScriptAction { script: { root.eqLightningFade = 0.0; root.eqLightningProgress = 0.0; } }
        NumberAnimation {
            target: root; property: "eqLightningProgress"
            from: 0.0; to: 10.0; duration: 650; easing.type: Easing.OutSine
        }
        PauseAnimation { duration: 150 }
        NumberAnimation {
            target: root; property: "eqLightningFade"
            from: 0.0; to: 1.0; duration: 800; easing.type: Easing.OutQuad
        }
        ScriptAction { script: root.eqLightningProgress = 0.0 }
    }

    function triggerLightning() {
        // Theme.animations without importing the theme singleton (services stay theme-free).
        if (!ShellState.batterySaverActive && ShellState.preferences.animations !== false)
            lightningAnim.restart();
    }

    Connections {
        target: ShellState
        function onLastResultChanged() {
            const result = ShellState.lastResult;
            if (!result)
                return;
            if (result.action === "eqGet") {
                if (!result.ok) {
                    loadStatus = String(result.message || "Equalizer is unavailable");
                    return;
                }
                // Our own writes can still be in flight; let them settle first.
                if (Date.now() - lastLocalUpdate < 2000)
                    return;
                hydrate(result.message);
                return;
            }
            if (!["eqApply", "eqRevert", "eqPreset", "eqSetBand", "eqBalance", "eqMono",
                  "eqSwap", "eqDyneq", "eqDynamics", "eqReset", "eqStart"].includes(result.action))
                return;
            if (!result.ok) {
                loadStatus = String(result.message || "Equalizer change failed");
                // The backend keeps its last accepted state; re-read it as the truth.
                lastLocalUpdate = 0;
                refresh();
            } else {
                loadStatus = "";
            }
        }
    }
}
