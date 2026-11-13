// Role: VisualizerState.qml (audio layer, fan-in 3).
// Shared component/helper; keep API stable for wide QML reuse.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
Singleton {
    id: root
    property int refs: 0
    property var bars: Array(16).fill(0)
    property string error: ""
    property bool failed: false
    property bool stopping: false
    readonly property bool wanted: refs > 0 && !failed && !ShellState.demo && !ShellState.settingsApp
        && !ShellState.batterySaverActive && ShellState.preferences.audioVisualizer === true
    function addRef() { if (!refs) { failed=false; error=""; } refs++; }
    function removeRef() { refs=Math.max(0,refs-1); if(!refs) bars=Array(16).fill(0); }
    function sync() {
        if (!bridge) return;
        if (!wanted && bridge.running) { stopping = true; bridge.running = false; }
        else if (wanted && !bridge.running && !stopping) bridge.running = true;
    }
    onWantedChanged: sync()
    Component.onCompleted: sync()
    // The frame() port of scripts/audio_visualizer.py: 16 semicolon-separated values,
    // clamped to [0,1]; anything else is dropped like the bridge dropped it.
    function frame(line) {
        const parts = String(line).trim().replace(/^;+|;+$/g, "").split(";");
        if (parts.length !== 16) return null;
        const values = [];
        for (let i = 0; i < 16; i++) {
            const value = Number(parts[i]);
            if (!isFinite(value)) return null;
            values.push(Math.max(0, Math.min(100, value)) / 100);
        }
        return values;
    }
    // Q5: cava runs directly with the in-repo config (the python bridge is retired); the
    // raw ascii frames parse in JS. A binary that never started is the 'install cava' case
    // the bridge used to report.
    Process {
        id: bridge
        command: ["cava", "-p", Quickshell.shellPath("config/cava-visualizer.config")]
        property bool everStarted: false
        onStarted: everStarted = true
        stdout: SplitParser { onRead: line => { const values = root.frame(line); if (values) root.bars = values; } }
        onExited: {
            const expected = root.stopping;
            root.stopping = false;
            if (!everStarted) { root.error = "Install cava to enable the audio visualizer"; root.failed = true; }
            else if (expected) Qt.callLater(root.sync);
            else if (root.wanted) { root.error = "Audio visualizer stopped"; root.failed = true; }
        }
    }
}
