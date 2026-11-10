// Role: MirrorState.qml (shared layer) — native display mirroring (Q4 display/mirror
// families; plan §5 Q4: display_mirror/display_layout keep their plan→apply shape — the
// mirror stays a wl-mirror window that never rewrites the niri output layout).
// REL: scripts/display_mirror.py – the child ownership this ports: the wl-mirror argv
// (fullscreen-output, fit scaling, the shell's title), the start validation over the
// enabled output names, the stop/exit error tails from stderr, the mirroringEnabled
// re-check and the disconnect re-check (a mirrored display disabled or gone stops the
// mirror). scripts/mirror_actions.py::live – the exact action messages; the Settings
// forwarding path keeps the shell as the single owner through shell.qml's IPC.
// INVARIANT: every dispatch settles exactly once through done(ok, message) with the
// backend's strings; the section keeps {active, source, target, error, available}.
// GOTCHA: quickshell 0.3.2 has no which() — the availability discovery is the spawn
// itself (FailedToStart surfaces as the install message after a short grace), where the
// backend pre-checked runner.available(); the section's available stays optimistic until
// a start proves otherwise. GOTCHA: a stop must not run the exit handler's error path —
// the stopping flag marks an owned teardown.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "DisplayModel.js" as DisplayModel

QtObject {
    id: root

    property var section: ({active: false, source: "", target: "", error: "", available: true})
    property string source: ""
    property string target: ""
    property string error: ""
    property bool available: true
    property bool stopping: false
    property bool starting: false
    property var tail: ""           // the last 2000 characters of the child's stderr
    property var preferences: ({})  // the router context's copy, refreshed per dispatch

    property CommandRunner tools: CommandRunner { id: runner }

    property Process child: Process {
        id: mirror
        command: []
        stdinEnabled: false
        stderr: SplitParser { onRead: line => root.childStderr(line) }
        onExited: code => root.childExited(code)
        onRunningChanged: if (!running && !root.stopping && mirror.command.length)
            root.childFailedToStart()
    }

    // The backend re-checked the child on its 2 s poll (desktop_backend.py's state loop);
    // the shell's snapshot hook (ShellState.accept) drives this with the same cadence.
    readonly property var handledActions: ["mirrorRefresh", "mirrorStart", "mirrorStop"]
    function handles(action) { return handledActions.includes(action); }
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        try {
            if (context && context.preferences) preferences = context.preferences;
            if (action === "mirrorStop") return stopMirror(done);
            if (action === "mirrorRefresh") return recheck(preferences, () => done(true, "Mirror refreshed"));
            return start(request, done);
        } catch (error) { done(false, String(error)); }
    }

    function start(request, done) {
        if (mirror.command.length || starting) return done(false, "Stop the current mirror before starting another.");
        if (!preferences || preferences.mirroringEnabled === false)
            return done(false, "Display mirroring is disabled");
        starting = true;  // a start in flight counts as busy, like the backend's serialized request loop
        runner.dispatch("niri", ["niri", "msg", "--json", "outputs"], 3000, 16777216, (ok, text, error) => {
            starting = false;
            if (!ok) return done(false, error);
            let outputs = [];
            try {
                const normalized = DisplayModel.normalizedOutputs(JSON.parse(text));
                if (normalized) outputs = normalized;
            } catch (parseError) {}
            const names = {};
            for (const output of outputs)
                if (output.enabled) names[output.name] = true;
            const source = request && request.source, target = request && request.target;
            if (typeof source !== "string" || typeof target !== "string" || source === target
                    || !names[source] || !names[target]
                    || [source, target].some(name => name.startsWith("-") || name.length > 128
                        || Array.from(name).some(character => character.charCodeAt(0) < 32)))
                return done(false, "Choose two different, active niri displays.");
            root.source = source; root.target = target; root.tail = ""; root.error = "";
            mirror.command = ["wl-mirror", "--fullscreen-output", target, "--scaling", "fit",
                              "--title", "LME Display Mirror", source];
            stopping = false;
            mirror.running = true;
            publish(true);  // active from the spawn, like the backend's Popen
            // A missing binary surfaces as FailedToStart within milliseconds; a real start
            // outlives the grace (the backend's Popen raised synchronously on a missing tool).
            grace.restart();
            done(true, "Mirror started on " + target);
        });
    }

    property Timer grace: Timer {
        interval: 150
        onTriggered: if (mirror.running) {
            available = true;
            publish(true);
        }
    }
    function stopMirror(done) {
        grace.stop();
        if (mirror.running) { stopping = true; mirror.running = false; }
        else { mirror.command = []; }
        root.source = ""; root.target = ""; root.error = "";  // display_mirror.py::stop clears the info
        publish(false);
        if (done) done(true, "Mirror stopped");
    }

    // display_mirror.py::state — the disconnect and disable re-checks over a fresh read.
    // The hook call passes the current preferences with no done callback (the backend's
    // poll stopped the child silently); the mirrorRefresh action acknowledges with its
    // own message.
    function recheck(preferencesValue, done) {
        if (preferencesValue) preferences = preferencesValue;
        if (!mirror.running) { publish(false); if (done) done(true, "Mirror refreshed"); return; }
        if (!preferences || preferences.mirroringEnabled === false) {
            stopMirror(null);
            if (done) done(true, "Mirror refreshed");
            return;
        }
        runner.dispatch("niri", ["niri", "msg", "--json", "outputs"], 3000, 16777216, (ok, text, error) => {
            if (ok) {
                let outputs = [];
                try {
                    const normalized = DisplayModel.normalizedOutputs(JSON.parse(text));
                    if (normalized) outputs = normalized;
                } catch (parseError) {}
                const names = {};
                for (const output of outputs)
                    if (output.enabled) names[output.name] = true;
                if (!names[source] || !names[target]) {
                    stopMirror(null);
                    root.error = "A mirrored display was disconnected or disabled.";  // set after the stop's clear
                    publish(false);
                    if (done) done(true, "Mirror refreshed");
                    return;
                }
            }
            publish(mirror.running);
            if (done) done(true, "Mirror refreshed");
        });
    }

    function childStderr(line) {
        tail = (tail + line + "\n").slice(-2000);
    }

    function childExited(code) {
        grace.stop();
        mirror.command = [];
        root.stopping = false;
        const died = root.source !== "" || root.target !== "";
        root.source = ""; root.target = "";
        if (died) error = "Mirror stopped: " + (tail.trim() || String(code));
        publish(false);
    }
    function childFailedToStart() {
        grace.stop();
        mirror.command = [];
        available = false;
        error = "Install wl-mirror to mirror onto a connected display.";
        publish(false);
    }

    function publish(active) {
        section = {active: active, source: active ? root.source : "", target: active ? root.target : "",
                   error: error, available: available};
    }
}
