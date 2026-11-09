// Role: AudioState.qml (audio layer, fan-in 2) — native default sink/source state and the
// audio/backlight control writes (QML-first plan Q1/Q3).
// REL: Quickshell.Services.Pipewire::Pipewire – defaultAudioSink/defaultAudioSource;
// PwNode.audio.muted/.volume (setAverageVolume writes the same scale wpctl prints — the Q1
// A/B window validated the read side). Quickshell.Io::Process – brightnessctl with the
// backend argv: quickshell 0.3.2 has no backlight service, so the write is a CLI call and
// the read stays backend-fed (DEPRECATED(Q2->Q6) transitional key).
// INVARIANT: section shapes mirror scripts/desktop_backend.py::audio() exactly (tests/
// test_native_state.py); the Q3 write port mirrors scripts/audio_actions.py's controls —
// messages, percentage bounds and the wpctl --limit 1.0 clamp included (tests/
// test_native_controls.py). Demo fixtures live in NativeState.qml; this singleton is pure
// native state + writes. Known native edge: an unbound default node cannot be served here
// and falls back to the backend registry for its canonical errors.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire

QtObject {
    id: root

    // Bind the default nodes: PwNode.audio volume/muted are invalid on unbound nodes.
    property PwObjectTracker tracker: PwObjectTracker {
        objects: [Pipewire.defaultAudioSink, Pipewire.defaultAudioSource]
    }

    readonly property var state: section(Pipewire.defaultAudioSink)
    readonly property var microphone: section(Pipewire.defaultAudioSource)

    // Fired on real volume/mute changes (native, event-driven) so the shell OSD no
    // longer waits for the backend poll; ShellState connects to this signal.
    signal osd(int volume, bool muted)
    property var previous: null
    onStateChanged: {
        if (previous && previous.available && state.available
                && (previous.volume !== state.volume || previous.muted !== state.muted))
            osd(state.volume, state.muted);
        previous = state;
    }

    function section(node) {
        if (!node || !node.audio || !node.ready) return {available: false, volume: null, muted: false};
        return {available: true, volume: Math.round(node.audio.volume * 100), muted: node.audio.muted};
    }

    // ---- Q3 write path: the router's audio leg (scripts/audio_actions.py's controls). ----

    readonly property var handledActions: ["volume", "mute", "micVolume", "micMute", "brightness"]
    function handles(action) { return handledActions.includes(action); }

    // Port of scripts/desktop_backend.py::percentage(): bounds + round, or the exact error.
    // round() is Python's ties-to-even (50.5 -> 50), not Math.round's half-up.
    function percent(value, minimum) {
        if (typeof value !== "number" || !isFinite(value) || value < minimum || value > 100)
            return "Value must be between " + minimum + " and 100";
        return round(value);
    }

    function round(value) {
        const floor = Math.floor(value);
        const diff = value - floor;
        if (diff > 0.5) return floor + 1;
        if (diff < 0.5) return floor;
        return floor % 2 === 0 ? floor : floor + 1;
    }

    // Route natively when the target node is bound (the harness/private-bus case falls back
    // to the backend registry for its canonical errors); brightness always routes.
    function canRoute(action, payload, context) {
        if (action === "brightness") return true;
        const node = action.indexOf("mic") === 0 ? Pipewire.defaultAudioSource : Pipewire.defaultAudioSink;
        return !!node && node.ready && !!node.audio;
    }

    function perform(action, request, done, context) {
        if (action === "brightness") {
            const value = percent(request.value, 1);
            if (typeof value !== "number") return done(false, value);
            brightnessTool.dispatch(["brightnessctl", "--class=backlight", "set", value + "%"], value, done);
            return;
        }
        const microphone = action.indexOf("mic") === 0;
        const node = microphone ? Pipewire.defaultAudioSource : Pipewire.defaultAudioSink;
        if (!node || !node.audio) return done(false, "No audio device is available");
        if (action === "mute" || action === "micMute") {
            node.audio.muted = !node.audio.muted;
            return done(true, microphone ? "Microphone mute toggled" : "Mute toggled");
        }
        if ("delta" in request) {  // volume only — audio_actions.py has no microphone delta
            const delta = percent(request.delta, -100);
            if (typeof delta !== "number") return done(false, delta);
            node.audio.volume = clampVolume(node.audio.volume + delta / 100);
            return done(true, "Volume adjusted");
        }
        const value = percent(request.value, 0);
        if (typeof value !== "number") return done(false, value);
        node.audio.volume = clampVolume(value / 100);
        done(true, (microphone ? "Microphone " : "Volume ") + value + "%");
    }

    // wpctl's --limit 1.0: writes clamp at 100%.
    function clampVolume(volume) { return Math.min(1, Math.max(0, volume)); }

    // brightnessctl one-shot with the backend's argv and timeout. Requests queue (a rapid
    // second change waits for the first) so every pending slot settles; a missing binary
    // (FailedToStart never emits exited) surfaces the runner's unavailable-tool message.
    property Process brightnessTool: Process {
        id: tool
        property var current: null           // [argv, value, done]
        property var queue: []
        property bool settled: false
        property bool timedOut: false
        property Timer watchdog: Timer {
            interval: 3000
            onTriggered: { tool.timedOut = true; tool.running = false; }
        }
        stdinEnabled: false
        stdout: StdioCollector {}
        stderr: StdioCollector {}
        onExited: code => {
            tool.settled = true; tool.watchdog.stop();
            if (timedOut) finish(false, "brightnessctl timed out");
            else if (code === 0) finish(true, "Brightness " + current[1] + "%");
            else {
                const detail = String(stderr.text || stdout.text || "").trim().slice(0, 350);
                finish(false, "brightnessctl failed (" + code + ")" + (detail ? ": " + detail : ""));
            }
        }
        onRunningChanged: if (!running && !settled && current) {  // FailedToStart
            tool.settled = true; tool.watchdog.stop();
            finish(false, "Required command is unavailable: brightnessctl");
        }
        function dispatch(argv, value, done) {
            if (current) { queue.push([argv, value, done]); return; }
            start(argv, value, done);
        }
        function start(argv, value, done) {
            current = [argv, value, done]; settled = false; timedOut = false;
            command = argv; running = true; watchdog.restart();
        }
        function finish(ok, message) {
            const request = current; current = null; timedOut = false;
            watchdog.stop();  // a queued next restarts it in start()
            if (request) request[2](ok, message);
            if (queue.length) { const next = queue.shift(); start(next[0], next[1], next[2]); }
        }
    }
}
