// Role: IdleState.qml (shared layer) — native idle profiles (Q4 night-light/idle
// families; plan §5 Q4).
// REL: scripts/idle_control.py::IdleControl.sync and idle_command – the swayidle
// ownership this ports: the AC/battery profile selection, the signature that restarts
// the child only on change, the availability gate over the profile's required tools,
// the exact swayidle argv (shlex-joined command strings — swayidle runs them through
// sh -c) and the close-time power-on-monitors restore. scripts/idle_actions.py – the
// idleRefresh/idleInhibit messages. The lock/sleep/client helpers stay in
// idle_control.py (flock + ready-fd + PDEATHSIG are outside quickshell 0.3.2's API
// surface — the same infra-helper pattern as the pkexec charge helper).
// INVARIANT: the section keeps {enabled, running, paused, source, profile, available,
// error}; an exited child is never respawned until the signature changes. GOTCHA: the
// availability probe runs through the helper asynchronously — an enable holds one sync
// round while it settles, so the install message stays exact. GOTCHA: the backend
// surfaces any swayidle stderr as the section error (its own behavior) — ported as-is.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root

    readonly property string helper: Quickshell.shellPath("scripts/idle_control.py")

    property var section: ({enabled: false, running: false, paused: false, source: "ac",
                            profile: {}, available: true, error: ""})
    property string signature: ""
    property string error: ""
    property string tail: ""           // the last 400 characters of the child's stderr
    property bool paused: false
    property bool stopping: false
    property bool probeSettled: false
    property var probeMissing: []
    property string probedNames: ""
    property var lastPreferences: ({})
    property bool lastAcOnline: true

    property CommandRunner tools: CommandRunner { id: runner }

    property Process client: Process {
        id: swayidle
        command: []
        stdinEnabled: false
        stderr: SplitParser { onRead: line => root.childStderr(line) }
        onExited: code => root.childExited()
        onRunningChanged: if (!running && !root.stopping && swayidle.command.length)
            root.childExited()
    }

    readonly property var handledActions: ["idleRefresh", "idleInhibit"]
    function handles(action) { return handledActions.includes(action); }
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        try {
            if (action === "idleInhibit") {
                if (!request || typeof request.value !== "boolean")
                    return done(false, "Idle inhibit must be boolean");
                syncPaused(lastPreferences, lastAcOnline, request.value);
                return done(true, request.value ? "Idle paused" : "Idle resumed");
            }
            ensureProbe(requiredNames(preferencesProfile(lastPreferences, lastAcOnline),
                                      (lastPreferences || {}).idleLockBeforeSleep === true));
            done(true, "Idle profile refreshed");
        } catch (failure) { done(false, String(failure)); }
    }

    // The snapshot hook's entry point: IdleState.sync(preferences, acOnline).
    function sync(preferences, acOnline) { syncPaused(preferences, acOnline, paused); }

    function syncPaused(preferences, acOnline, pausedValue) {
        paused = pausedValue === true;
        lastPreferences = preferences || {};
        lastAcOnline = acOnline === true;
        const profile = preferencesProfile(lastPreferences, lastAcOnline);
        const lockBeforeSleep = lastPreferences.idleLockBeforeSleep === true;
        if (!profile) return;  // a malformed profile keeps the previous section (the backend's loader validates)
        ensureProbe(requiredNames(profile, lockBeforeSleep));
        const signature = [lastPreferences.idleEnabled === true, paused, lastAcOnline ? "ac" : "battery",
                           profile.display, profile.lock, profile.suspend, lockBeforeSleep].join("\u0000");
        if (signature !== root.signature && !((lastPreferences.idleEnabled === true) && !paused && !probeSettled)) {
            // The enable decision holds one sync round while the probe settles.
            close();
            root.signature = signature;
            error = "";
            if (lastPreferences.idleEnabled === true && !paused) {
                if (probeMissing.length) {
                    error = "Install " + probeMissing.join(", ") + " to enable this idle profile.";
                } else {
                    swayidle.command = ["python3", helper, "--parent", String(Quickshell.processId), "client"]
                        .concat(idleCommand(profile, lockBeforeSleep));
                    stopping = false;
                    swayidle.running = true;
                }
            }
        }
        publish(profile);
    }

    function preferencesProfile(preferences, acOnline) {
        const profiles = (preferences || {}).idleProfiles;
        if (!profiles || typeof profiles !== "object") return null;
        const profile = profiles[acOnline ? "ac" : "battery"];
        return (profile && typeof profile === "object") ? profile : null;
    }

    function requiredNames(profile, lockBeforeSleep) {
        const required = ["swayidle", "niri"];
        if (profile.lock || lockBeforeSleep) required.push("swaylock");
        if (profile.suspend) required.push("systemctl");
        return required;
    }

    // scripts/idle_control.py::idle_command — the swayidle argv. The timeout commands are
    // single shlex-joined strings (swayidle runs them through sh -c); shlex.quote's rule
    // (safe unless a character falls outside the portable set) is reproduced exactly.
    function shellQuote(words) {
        const safe = /^[A-Za-z0-9@%+=:,./_-]+$/;
        return words.map(word => safe.test(word) ? word : "'" + String(word).replace(/'/g, "'\\''") + "'").join(" ");
    }

    function idleCommand(profile, lockBeforeSleep) {
        const lock = shellQuote(["python3", helper, "lock"]);
        const argv = ["swayidle", "-w"];
        if (profile.lock)
            argv.push("timeout", String(profile.lock * 60), lock);
        if (profile.display) {
            argv.push("timeout", String(profile.display * 60),
                      shellQuote(["niri", "msg", "action", "power-off-monitors"]),
                      "resume",
                      shellQuote(["niri", "msg", "action", "power-on-monitors"]));
        }
        if (profile.suspend) {
            const sleep = ["python3", helper, "sleep"];
            if (lockBeforeSleep) sleep.push("--lock");
            argv.push("timeout", String(profile.suspend * 60), shellQuote(sleep));
        }
        if (lockBeforeSleep) argv.push("before-sleep", lock);
        argv.push("after-resume", shellQuote(["niri", "msg", "action", "power-on-monitors"]));
        return argv;
    }

    // The availability probe through the session helper; re-run when the profile's
    // required set changes (the backend re-checked each sync, caching only misses).
    function ensureProbe(names) {
        const key = names.join(" ");
        if (key === probedNames && (probeSettled || key === "")) return;
        probedNames = key;
        probeSettled = false;
        runner.dispatch("python3", ["python3", helper, "probe"].concat(names), 3000, 8388608, (ok, text, error) => {
            probeSettled = true;
            const missing = ok ? String(text || "").trim() : "?";
            probeMissing = missing ? missing.split(/\s+/).filter(Boolean) : [];
            if (section.source)
                publish(preferencesProfile(lastPreferences, lastAcOnline));
        });
    }

    function childStderr(line) {
        tail = (tail + line + "\n").slice(-400);
        error = tail.trim();
        if (section.source)
            publish(preferencesProfile(lastPreferences, lastAcOnline));
    }

    function childExited() {
        if (swayidle.command.length) {
            swayidle.command = [];
            if (!stopping)
                error = "swayidle stopped: " + tail.trim();
        }
        stopping = false;
        publish(preferencesProfile(lastPreferences, lastAcOnline));
    }

    // IdleControl.close — stopping the child restores the displays (best-effort, like the
    // backend's swallowed RuntimeError/OSError).
    function close() {
        if (swayidle.running) {
            stopping = true;
            swayidle.running = false;
            runner.dispatch("niri", ["niri", "msg", "action", "power-on-monitors"], 3000, 16777216, () => {});
        }
        swayidle.command = [];
        tail = "";
    }

    Component.onDestruction: close()

    function publish(profile) {
        const source = lastAcOnline ? "ac" : "battery";
        section = {enabled: lastPreferences.idleEnabled === true, running: swayidle.running,
                   paused: paused, source: source, profile: profile || {},
                   available: probeSettled ? probeMissing.length === 0 : true,
                   error: error};
    }
}
