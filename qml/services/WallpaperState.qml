// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: WallpaperState.qml (wallpaper layer, fan-in 1) — Q5 native wallpaper daemon owner
// and playlist scheduler.
// REL: scripts/wallpaper.py::Wallpapers – DEPRECATED(Q5->Q6); due()/advance()/restore() semantics
// and messages are frozen by tests/test_native_wallpaper.py.
// INVARIANT: fixture modes (demo/preview, LME_SHELL_BACKEND_DEMO, standalone Settings) never
// spawn awww or touch preferences — sync() is inert and the backend keeps serving them.
// The in-QML busy guard replaces the Python flock's in-process half (one awww operation at a
// time); user-initiated shared saves delegate to the backend 'wallpaper' action, which stays
// atomic under its flock (the setting action refuses the 'wallpaper' key by design).
// GOTCHA: ShellState injects writeSetting/runAction at each sync (services stay ShellState-free;
// composition stays acyclic). The shared playlist rotation (output '') rides the backend action
// end to end; per-output rotations apply natively and persist through the setting token write.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "WallpaperModel.js" as Wallpaper

QtObject {
    id: root

    property var runner        // (args, seconds, done) => void — done(ok, stdout); tests inject
    property var spawner       // () => void — spawn awww-daemon --no-cache
    property var clock
    property var writeSetting  // (key, value, token) => void — injected by ShellState.accept
    property var runAction     // (action, payload) => void — injected by ShellState.accept
    readonly property bool inert: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
        || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1" || Quickshell.env("LME_SHELL_SETTINGS") === "1"

    property var machine: ({connected: null, applied: {}, signature: null, cursor: null,
                           deadline: null, remaining: null, wasPaused: false, retryAt: 0})
    property var lastPreferences: ({})
    property bool powerSaving: false
    property bool busy: false
    property var statusResult: ({available: true, running: false, query: "", error: ""})
    property string daemonError: ""

    function now() { return clock ? clock() : Date.now() / 1000; }
    function current(output) {
        const outputs = lastPreferences.wallpaperOutputs || {};
        return output ? (outputs[output] || lastPreferences.wallpaper || "") : (lastPreferences.wallpaper || "");
    }

    // ---- awww plumbing -------------------------------------------------------------
    // The default one-shot transport: a queued awww invocation with a watchdog timer (the
    // Python run() timeouts become kills of the running process).
    property Process tool: Process {
        id: awww
        stdinEnabled: false
        property var reply: null
        property string collected: ""
        stdout: SplitParser { onRead: line => { awww.collected += line + "\n"; } }
        stderr: SplitParser { onRead: line => { } }
        onExited: (code, status) => {
            watchdog.stop();
            const done = awww.reply;
            awww.reply = null;
            root.busy = false;
            if (done) done(code === 0, awww.collected);
            root.flush();
        }
    }
    property Timer watchdog: Timer {
        onTriggered: {
            awww.reply = null;
            awww.running = false;  // the watchdog kill: the queued job settles as a failure
            root.busy = false;
            root.flush();
        }
    }
    property var queue: []
    function runTool(args, seconds, done) {
        if (runner) return runner(args, seconds, done);
        if (busy) { queue.push([args, seconds, done]); return; }
        busy = true;
        tool.reply = done;
        tool.collected = "";
        tool.command = ["awww"].concat(args);
        tool.running = true;
        watchdog.interval = seconds * 1000;
        watchdog.restart();
    }
    function flush() {
        if (busy || !queue.length) return;
        const next = queue.shift();
        runTool(next[0], next[1], next[2]);
    }

    // ready(): query; on failure spawn the daemon once and poll for 4 s (the Python deadline).
    function ready(done, deadline, spawned) {
        const limit = deadline !== undefined ? deadline : now() + 4;
        runTool(["query"], 1.2, (ok, text) => {
            if (ok) return done(true, text);
            if (now() >= limit) return done(false, "awww-daemon did not become ready. Check your Wayland session.");
            if (!spawned) { if (spawner) spawner(); else spawnDaemon(); spawned = true; }
            retryTimer.restart();
            retryTimer.callback = () => ready(done, limit, true);
        });
    }
    property Timer retryTimer: Timer { interval: 100; property var callback: null; onTriggered: if (callback) callback() }

    function spawnDaemon() {
        daemon.command = ["awww-daemon", "--no-cache"];
        daemon.running = true;
    }
    property Process daemon: Process {
        command: []
        stdinEnabled: false
        stderr: SplitParser { onRead: line => console.warn("[awww-daemon]", line) }
    }

    // ---- the scheduler (ShellState.accept drives this at the poll cadence) ---------
    function sync(preferences, outputs, saving, writeSetting, runAction) {
        lastPreferences = preferences || {};
        if (writeSetting) root.writeSetting = writeSetting;
        if (runAction) root.runAction = runAction;
        if (inert) return;
        powerSaving = saving === true;
        const plan = Wallpaper.plan(machine, lastPreferences, outputs || [], now(), powerSaving);
        machine = plan.state;
        if (!plan.job || busy) return;
        if (plan.job.kind === "restore") executeRestore(plan.job.outputs);
        else if (plan.job.kind === "advance") executeAdvance(plan.job.output, true, null);
    }

    function executeRestore(names) {
        busy = true;
        ready((ok, text) => {
            if (!ok) { busy = false; return; }
            // Another agent may have just started a transition; don't cancel it.
            const displayed = Wallpaper.queryImages(text);
            const pending = names.slice();
            const step = () => {
                if (!pending.length) { busy = false; return; }
                const name = pending.shift();
                const path = current(name);
                if (displayed[name] === path) { machine.applied[name] = path; step(); return; }
                applyImage(path, [name], false, ok2 => { if (ok2) machine.applied[name] = path; step(); });
            };
            step();
        });
    }

    function applyImage(path, targets, animate, done) {
        const args = Wallpaper.imageArguments(path, lastPreferences, animate && !powerSaving)
            .concat(targets.length ? ["--outputs", targets.join(",")] : []);
        runTool(args, 15, ok => done(ok));
    }

    function executeAdvance(output, automatic, done) {
        const preferences = lastPreferences;
        if (automatic && (powerSaving || preferences.wallpaperPlaylistEnabled !== true
                || preferences.wallpaperPlaylistPaused === true || preferences.wallpaperPlaylistOutput !== output))
            return done ? done(true, "") : undefined;
        busy = true;
        ready((ok, text) => {
            if (!ok) {
                if (done) done(false, "awww-daemon did not become ready. Check your Wayland session.");
                busy = false; return;
            }
            const connected = Wallpaper.queryOutputs(text);
            if (output && connected.size && !connected.has(output)) { busy = false; return done ? done(false, "Choose a valid display name") : undefined; }
            const spot = output || preferences.wallpaperPlaylistOutput || "";
            if (spot && connected.size && !connected.has(spot)) { busy = false; return done ? done(true, "") : undefined; }
            const target = spot === "" ? [] : [spot];
            const result = (() => {
                try { return Wallpaper.advanceChoices(preferences, spot, machine.cursor, current(spot), preferences.wallpaperPlaylistShuffle === true); }
                catch (failure) { return {note: String(failure.message || failure), choices: []}; }
            })();
            if (!result.choices.length) { busy = false; return done ? done(true, result.note || "The playlist has no available images") : undefined; }
            const choices = result.choices.slice();
            const attempt = () => {
                if (!choices.length) { busy = false; return done ? done(false, "No wallpaper could be applied") : undefined; }
                const path = choices.shift();
                machine.cursor = [spot, path, current(spot)];
                if (!spot) {
                    // Shared rotation: the backend 'wallpaper' action validates, applies and
                    // saves atomically under its flock — the setting action refuses the
                    // 'wallpaper' key, so the native side never applies it itself.
                    if (runAction) runAction("wallpaper", {path: path, output: ""});
                    busy = false;
                    if (done) done(true, "Wallpaper updated");
                    return;
                }
                applyImage(path, target, true, ok2 => {
                    if (!ok2) return attempt();
                    machine.applied[spot] = path;
                    if (writeSetting) writeSetting("wallpaperOutputs", path, spot);
                    busy = false;
                    if (done) done(true, "Wallpaper updated");
                });
            };
            attempt();
        });
    }

    // ---- Q5 action surface ----------------------------------------------------------
    readonly property var handledActions: ["wallpaperStatus", "wallpaperEnsure", "wallpaperNext"]
    function handles(action) { return handledActions.includes(action); }
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        if (busy) return done(false, "A wallpaper change is already running");
        if (action === "wallpaperStatus") {
            busy = true;
            ready((ok, text) => {
                busy = false;
                statusResult = {available: true, running: ok, query: ok ? text : "", error: ok ? "" : text};
                done(ok, ok ? "Wallpaper daemon checked" : "awww-daemon did not become ready. Check your Wayland session.");
            });
            return;
        }
        if (action === "wallpaperEnsure") {
            busy = true;
            ready(ok => { busy = false; done(ok, ok ? "Wallpaper daemon ready" : "awww-daemon did not become ready. Check your Wayland session."); });
            return;
        }
        if (action === "wallpaperNext") {
            const output = request && request.output !== undefined ? request.output : undefined;
            return executeAdvance(output === undefined || output === null ? (lastPreferences.wallpaperPlaylistOutput || "") : output, false, done);
        }
        return done(false, "Unknown wallpaper action");
    }
}
