// Role: CommandRunner.qml (shared layer) — queued one-shot allowlisted CLI runner (Q3 inventory
// families; the plan §4 Q4 Process machinery, scoped to what these families need).
// REL: scripts/command_runner.py – the argv/error contract this ports (no shell evaluation,
// LC_ALL=C, timeouts, bounded output, TERM→KILL stop, FailedToStart detection). Instantiated
// per service (AudioDeviceState/NetworkInventoryState) so one family never queues behind the
// other; argv arrays are caller-built constants, which is the allowlist by construction.
// INVARIANT: every dispatched request settles exactly once through done(ok, text, error) with
// command_runner.py's exact error strings; requests queue (a second dispatch waits) so no
// pending slot can leak. GOTCHA: onExited also fires after running=false (terminate), so a
// cancellation resolves through the settled flag before the failure path composes; the
// StdioCollector replaces its text per run (waitForEnd), so no manual clearing is needed.
import QtQuick
import Quickshell.Io

Process {
    id: tool

    property var queue: []            // [{name, argv, timeout, cap, done}]
    property var current: null
    property bool settled: false
    property bool timedOut: false
    property var cancelled: null      // handler(request) set by the owning service before stopping
    environment: ({LC_ALL: "C"})
    stdinEnabled: false
    stdout: StdioCollector { id: collector }
    stderr: StdioCollector { id: failures }

    property Timer watchdog: Timer {
        onTriggered: { tool.timedOut = true; tool.running = false; tool.killer.restart(); }
    }
    // The backend's stop ladder: SIGTERM, 100 ms, SIGKILL.
    property Timer killer: Timer {
        interval: 100
        onTriggered: if (tool.current && !tool.settled) tool.signal(9)
    }

    onExited: code => {
        tool.settled = true; tool.watchdog.stop(); tool.killer.stop();
        const request = tool.current;
        if (!request) return;
        if (tool.cancelled) return finishWith(tool.cancelled, request);
        if (tool.timedOut) return settle(request, false, "", request.name + " timed out");
        if (code === 0) {
            const text = String(collector.text || "");
            if (request.cap && text.length > request.cap)
                return settle(request, false, "", request.name + " output exceeds " + request.cap + " bytes");
            return settle(request, true, text, "");
        }
        const detail = String(failures.text || collector.text || "").trim()
            .replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, "").trim().slice(0, 350);
        settle(request, false, "", request.name + " failed (" + code + ")" + (detail ? ": " + detail : ""));
    }
    onRunningChanged: if (!running && !settled && current) {  // FailedToStart
        tool.settled = true; tool.watchdog.stop(); tool.killer.stop();
        const request = tool.current;
        if (tool.cancelled) finishWith(tool.cancelled, request);
        else settle(request, false, "", "Required command is unavailable: " + request.name);
    }

    // done(ok, stdout, error); timeout in milliseconds, cap in characters (the backend's byte
    // caps govern ASCII CLI output; document the approximation in the owning service).
    function dispatch(name, argv, timeout, cap, done) {
        if (current) { queue.push({name: name, argv: argv, timeout: timeout, cap: cap, done: done}); return; }
        start({name: name, argv: argv, timeout: timeout, cap: cap, done: done});
    }

    function start(request) {
        current = request; settled = false; timedOut = false; cancelled = null;
        command = request.argv; watchdog.interval = request.timeout; watchdog.restart();
        running = true;
    }

    // Stop the in-flight command and hand it to handler(request) instead of its done callback
    // (the network activation cancel path).
    function stopCurrent(handler) {
        if (!current || settled) return false;
        cancelled = handler;
        running = false;
        killer.restart();
        return true;
    }

    function spawnDetached(argv) {
        command = argv;
        startDetached();
    }

    function settle(request, ok, text, error) {
        current = null; timedOut = false; cancelled = null;
        watchdog.stop(); killer.stop();
        if (request) request.done(ok, text, error);
        if (queue.length) start(queue.shift());
    }
    function finishWith(handler, request) {
        current = null; timedOut = false; cancelled = null;
        watchdog.stop(); killer.stop();
        handler(request);
        if (queue.length) start(queue.shift());
    }
}
