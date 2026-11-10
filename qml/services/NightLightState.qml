// Role: NightLightState.qml (shared layer) — native Night Light (Q4 night-light/idle
// families; plan §5 Q4).
// REL: scripts/night_light.py::NightLight – the wlsunset ownership this ports: the
// signature (wanted, temperature) that restarts the child only on change, the argv
// (-T temperature+1, -t temperature, the fixed 06:00/18:00 so manual mode never leaves a
// midnight gap), the exit/stderr error surfaces and the section shape. The sync is driven
// by the shell's snapshot hook (ShellState.accept) at the backend's 2 s poll cadence with
// the resolved weather place; scripts/night_light_actions.py::live's retry path maps to
// the nightLightRefresh action (signature invalidation + resync).
// INVARIANT: the section keeps {enabled, active, running, available, temperature, mode,
// start, end, error}; an exited child is never respawned until the signature changes
// (the backend's own rule — retryNightLight is the explicit escape hatch). GOTCHA:
// quickshell 0.3.2 has no which() — availability comes from the idle_control.py probe
// helper, settled asynchronously before the first spawn decision (the enable holds one
// sync round at most); GOTCHA: the child goes through the same helper's client path so
// PDEATHSIG tracks the shell (crash-orphan safety), exactly like the backend's spawn.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "NightLightModel.js" as NightLightModel

QtObject {
    id: root

    readonly property string helper: Quickshell.shellPath("scripts/idle_control.py")

    property var section: ({enabled: false, active: false, running: false, available: true,
                            temperature: 0, mode: "manual", start: "", end: "", error: ""})
    property string signature: ""
    property string error: ""
    property string tail: ""           // the last 2048 characters of the child's stderr
    property bool stopping: false
    property bool probeSettled: false
    property bool probeAvailable: true

    property var lastPreferences: ({})
    property var lastPlace: null

    property CommandRunner tools: CommandRunner { id: runner }

    property Process client: Process {
        id: wlsunset
        command: []
        stdinEnabled: false
        stderr: SplitParser { onRead: line => root.childStderr(line) }
        onExited: code => root.childExited()
        onRunningChanged: if (!running && !root.stopping && wlsunset.command.length)
            root.childExited()
    }

    Component.onCompleted: probe()

    readonly property var handledActions: ["nightLightRefresh"]
    function handles(action) { return handledActions.includes(action); }
    function canRoute(action, payload, context) { return true; }

    function perform(action, request, done, context) {
        if (request && "retry" in request && typeof request.retry !== "boolean")
            return done(false, "Night Light retry must be boolean");
        // night_light_actions.py::live — invalidate so the next sync restarts the child,
        // then resync immediately (the backend waited for its 2 s poll).
        signature = "";
        sync(context && context.preferences ? context.preferences : lastPreferences, lastPlace);
        done(true, "Night Light refreshed");
    }

    // The snapshot hook's entry point: NightLightState.sync(preferences, place).
    function sync(preferences, place) {
        lastPreferences = preferences || {};
        lastPlace = place || null;
        let active = false, start = "", end = "", scheduleError = "";
        try {
            const result = NightLightModel.desiredState(lastPreferences, place || null, new Date());
            active = result[0]; start = result[1]; end = result[2];
        } catch (schedule) {
            if (lastPreferences.nightLightEnabled === true) scheduleError = String(schedule);
        }
        const temperature = lastPreferences.nightLightTemperature;
        const signature = active + "\u0000" + temperature;
        if (signature !== root.signature && !(active && !probeSettled)) {
            // The enable decision holds one sync round while the probe settles; the
            // signature only commits once the spawn decision is final.
            close();
            root.signature = signature;
            error = "";
            if (active) {
                if (!probeAvailable) {
                    error = "Install wlsunset, then restart the shell to enable Night Light.";
                } else {
                    wlsunset.command = ["python3", helper, "--parent", String(Quickshell.processId), "client",
                                         "wlsunset", "-T", String(temperature + 1), "-t", String(temperature),
                                         "-S", "06:00", "-s", "18:00"];
                    stopping = false;
                    wlsunset.running = true;
                }
            }
        }
        publish(scheduleError, start, end);
    }

    // The availability probe through the session helper — cached, like the backend's
    // runner which re-checked only a missing command.
    function probe() {
        runner.dispatch("python3", ["python3", helper, "probe", "wlsunset"], 3000, 8388608, (ok, text, error) => {
            probeSettled = true;
            probeAvailable = ok && String(text || "").trim() === "";
            publish("", section.start, section.end);
        });
    }

    function childStderr(line) {
        tail = (tail + line + "\n").slice(-2048);
        if (/fail|not supported|not available|no gamma/i.test(line)) {
            error = "Gamma control failed. Check compositor/driver support and stop any other gamma controller. "
                + tail.slice(-240).trim();
            publish("", section.start, section.end);
        }
    }

    function childExited() {
        if (wlsunset.command.length) {
            wlsunset.command = [];
            if (!stopping)
                error = "wlsunset stopped. Gamma control may be unavailable or owned by another app.";
        }
        stopping = false;
        publish("", section.start, section.end);
    }

    function close() {
        if (wlsunset.running) { stopping = true; wlsunset.running = false; }
        wlsunset.command = [];
        tail = "";
    }

    function publish(scheduleError, start, end) {
        section = {enabled: lastPreferences.nightLightEnabled === true,
                   active: wlsunset.running && !error, running: wlsunset.running,
                   available: probeSettled ? probeAvailable : true,
                   temperature: lastPreferences.nightLightTemperature,
                   mode: lastPreferences.nightLightMode, start: start, end: end,
                   error: scheduleError || error};
    }
}
