pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import "EqualizerModel.js" as Equalizer
import "../services"

Singleton {
    id: root

    // Serpantinum MusicEqualizerState port: optimistic applies, staging, lightning.
    property var eqData: defaultState()
    property var savedEqData: defaultState()
    property string loadStatus: ""
    property bool audioTestRunning: false
    property real lastLocalUpdate: 0

    readonly property var presets: Equalizer.PRESETS

    function validState(value) { return Equalizer.normalize(value); }  // the normalize port
    function defaultState() { return Equalizer.defaultState(); }

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

    // ---- Q5 leg 3b: the native action surface -----------------------------------------
    // REL: scripts/equalizer_actions.py::provide – DEPRECATED(Q5->Q6); the staging semantics
    // (pending/committed views, push's commit_bands rule, the revert view) and the messages
    // are frozen by tests/test_native_equalizer.py. The eq_state document reads through a
    // FileView and writes through scripts/json_store.py (quickshell 0.3.2 has no file-write
    // API); the daemon runner is the WallpaperState tool pattern (one-shot Process, watchdog,
    // queue); the test tone ships as assets/equalizer-test.wav (synthesis needs file writes;
    // regenerate deterministically with scripts/regen_equalizer_test_tone.py).
    // GOTCHA: the shell is the document's only writer (the settings app has no eq actions),
    // so the in-memory stateDocument is authoritative after the first load. available()
    // checks become spawn failures: a binary that never started reads as 'unavailable', and
    // a pw-play that cannot start surfaces through the tone process exiting immediately
    // (audioTestRunning self-heals) instead of a synchronous error.

    readonly property var dynamicsModes: Equalizer.DYNAMICS
    readonly property var handledActions: ["eqStart", "eqStop", "eqStatus", "eqGet", "eqSetBand", "eqApply",
        "eqRevert", "eqPreset", "eqBalance", "eqMono", "eqSwap", "eqDyneq", "eqDynamics",
        "eqReset", "eqTest", "eqTestStop"]
    function handles(action) { return handledActions.includes(action); }
    function canRoute(action, payload, context) { return true; }

    property var runner        // (argv, seconds, done) => void — done(ok, stdout); tests inject
    property var storeWriter   // (document, done) => void — done(ok); tests inject
    property var stateDocument: null
    property bool documentSeen: false
    property var committed: null  // push's committed bands view — the revert target
    readonly property string documentPath: (Quickshell.env("XDG_STATE_HOME")
        || (Quickshell.env("HOME") + "/.local/state")) + "/lme-shell/equalizer.json"

    property FileView documentReader: FileView {
        path: root.documentPath
        printErrors: false
        onLoaded: {
            let parsed = null;
            try { parsed = root.validState(JSON.parse(String(text))); } catch (error) { parsed = null; }
            root.stateDocument = parsed || root.defaultState();
            root.documentSeen = true;
        }
    }

    // ---- the daemon transport (queued one-shot Process + watchdog) --------------------
    property var toolQueue: []
    property bool toolBusy: false
    property Process tool: Process {
        id: serp
        stdinEnabled: false
        property var reply: null
        property string collected: ""
        property bool startedOnce: false
        property bool timedOut: false
        stdout: SplitParser { onRead: line => { serp.collected += line + "\n"; } }
        stderr: SplitParser { onRead: line => { } }
        onStarted: startedOnce = true
        onExited: (code, status) => {
            toolWatchdog.stop();
            const done = serp.reply;
            serp.reply = null;
            const ok = code === 0 && serp.startedOnce && !serp.timedOut;
            root.toolBusy = false;
            if (done) done(ok, serp.collected, serp.timedOut);
            root.pumpTool();
        }
    }
    property Timer toolWatchdog: Timer { onTriggered: { tool.timedOut = true; tool.reply = null; tool.running = false; root.toolBusy = false; root.pumpTool(); } }
    function runTool(argv, seconds, done) {
        if (runner) return runner(argv, seconds, done);
        if (toolBusy) { toolQueue.push([argv, seconds, done]); return; }
        toolBusy = true;
        tool.reply = done;
        tool.collected = "";
        tool.startedOnce = false;
        tool.timedOut = false;
        tool.command = argv;
        tool.running = true;
        toolWatchdog.interval = seconds * 1000;
        toolWatchdog.restart();
    }
    function pumpTool() {
        if (toolBusy || !toolQueue.length) return;
        const next = toolQueue.shift();
        runTool(next[0], next[1], next[2]);
    }

    // ---- the document store (json_store.py helper, serialized) ------------------------
    property var storeQueue: []
    property bool storeBusy: false
    property Process storeTool: Process {
        id: storer
        stdinEnabled: true
        property var document: null
        property var reply: null
        command: ["python3", "-u", Quickshell.shellPath("scripts/json_store.py"), "--path", root.documentPath]
        stdout: SplitParser { onRead: line => { } }
        stderr: SplitParser { onRead: line => console.warn("[eq-store]", line) }
        onStarted: { write(JSON.stringify(document) + "\n"); }
        onExited: (code, status) => {
            storeBusy = false;
            const done = storer.reply;
            storer.reply = null;
            if (done) done(code === 0);
            pumpStore();
        }
    }
    function persist(state, done) {
        stateDocument = state;
        documentSeen = true;
        if (storeWriter) return storeWriter(state, done);
        storeQueue.push([state, done]);
        pumpStore();
    }
    function pumpStore() {
        if (storeBusy || !storeQueue.length) return;
        const next = storeQueue.shift();
        storeBusy = true;
        storeTool.document = next[0];
        storeTool.reply = next[1] || null;
        storeTool.running = true;
    }

    function ensureDocument(done) {
        if (documentSeen) return done(stateDocument);
        // First-use hydration: prefer the daemon's own report (seed_from_daemon).
        runTool(["serpantinum-audio", "ctl", "get"], 10, (ok, text) => {
            const seeded = ok ? Equalizer.stateFromDaemonLine(text) : null;
            const state = seeded || Equalizer.defaultState();
            persist(state, () => done(state));
        });
    }

    function daemonSet(state, done) {
        const args = Equalizer.daemonSetArgs(state);
        runTool(args, 10, ok => {
            if (ok) return done(true);
            // Every push retries once after an auto-start so a stopped daemon never blocks the UI.
            runTool(["serpantinum-audio", "start"], 10, () => runTool(args, 10, ok2 => done(ok2)));
        });
    }

    function push(state, commitBands, then) {
        daemonSet(state, ok => {
            if (!ok) return then(false);
            persist(state, () => {
                if (commitBands || committed === null)
                    committed = Object.assign({}, state, {pending: false});
                else
                    for (const key of ["balance", "mono", "swap", "dynamics", "dyneq"])
                        committed[key] = state[key];
                then(true);
            });
        });
    }

    function toneStop() { if (tone.running) tone.running = false; }
    property Process tone: Process {
        stdinEnabled: false
        onExited: (code, status) => { root.audioTestRunning = false; }
    }
    readonly property string toneProperties: JSON.stringify(
        {"application.id": "lme-shell-audio-test", "application.name": "LME Shell audio test", "media.role": "music"})
    function startTone(done) {
        runTool(["serpantinum-audio", "start"], 10, () => {
            runTool(["pw-dump", "-n", "Node"], 4, (ok, text) => {
                const target = ok && String(text).indexOf("serpantinum_sink") >= 0 ? ["--target=serpantinum_sink"] : [];
                tone.command = ["pw-play"].concat(target)
                    .concat(["-P", toneProperties, Quickshell.shellPath("assets/equalizer-test.wav")]);
                tone.running = true;
                done(true);
            });
        });
    }

    function perform(action, request, done, context) {
        request = request || {};
        if (action === "eqGet")
            return ensureDocument(state => done(true, JSON.stringify(state)));
        if (action === "eqStart")
            return runTool(["serpantinum-audio", "start"], 10, (ok, text) =>
                ok ? done(true, String(text).trim()) : done(false, "serpantinum-audio is unavailable"));
        if (action === "eqStop") {
            toneStop();
            return runTool(["serpantinum-audio", "ctl", "quit"], 10, (ok, text, timedOut) => {
                if (ok) return done(true, String(text).trim());
                if (timedOut) return done(false, "serpantinum-audio ctl quit timed out");
                return done(true, "Equalizer stopped");  // already-gone daemons are a stop, not an error
            });
        }
        if (action === "eqStatus")
            return runTool(["serpantinum-audio", "ctl", "ping"], 10, (ok, ping) =>
                runTool(["serpantinum-audio", "ctl", "status"], 10, (ok2, status) =>
                    ok && ok2 ? done(true, String(ping).trim() + "\n" + String(status).trim())
                              : done(false, "serpantinum-audio is unavailable")));
        if (action === "eqSetBand") {
            const band = Equalizer.bandError(request.band), gain = Equalizer.gainError(request.value);
            if (band) return done(false, band);
            if (gain) return done(false, gain);
            return ensureDocument(state => {
                const next = Object.assign({}, state);
                next["b" + request.band] = request.value;
                next.preset = "Custom";
                next.pending = true;
                persist(next, () => done(true, ""));  // staging persists without a daemon push
            });
        }
        if (action === "eqApply")
            return ensureDocument(state => {
                const next = Object.assign({}, state, {pending: false});
                push(next, true, ok => done(ok, ""));
            });
        if (action === "eqRevert")
            return ensureDocument(state => {
                push(Equalizer.savedView(committed, state), true, ok => done(ok, ""));
            });
        if (action === "eqPreset") {
            const values = presets[request.name];
            if (!values) return done(false, "Unknown equalizer preset");
            return ensureDocument(state => {
                const next = Object.assign({}, state);
                for (let index = 0; index < 10; index++) next["b" + (index + 1)] = values[index];
                next.preset = request.name;
                next.pending = false;
                push(next, true, ok => done(ok, ""));
            });
        }
        if (action === "eqBalance") {
            const message = Equalizer.balanceError(request.value);
            if (message) return done(false, message);
            return ensureDocument(state => {
                const next = Object.assign({}, state, {balance: Math.round(request.value * 100) / 100});
                push(next, false, ok => done(ok, ""));
            });
        }
        if (action === "eqMono" || action === "eqSwap" || action === "eqDyneq") {
            const message = Equalizer.flagError(request.value);
            if (message) return done(false, message);
            const key = action.slice(2).toLowerCase();
            return ensureDocument(state => {
                const next = Object.assign({}, state);
                next[key] = request.value;
                push(next, false, ok => done(ok, ""));
            });
        }
        if (action === "eqDynamics") {
            const message = Equalizer.dynamicsError(request.value);
            if (message) return done(false, message);
            return ensureDocument(state => {
                const next = Object.assign({}, state, {dynamics: request.value});
                push(next, false, ok => done(ok, ""));
            });
        }
        if (action === "eqReset") {
            toneStop();
            return ensureDocument(state => {
                const next = Object.assign({}, state, {balance: 0, mono: false, swap: false, dynamics: "off"});
                push(next, false, ok => done(ok, ""));
            });
        }
        if (action === "eqTest")
            return startTone(() => done(true, "Channel test playing"));
        if (action === "eqTestStop") {
            toneStop();
            return done(true, "Channel test stopped");
        }
        return done(false, "Unknown equalizer action: " + action);
    }
}
