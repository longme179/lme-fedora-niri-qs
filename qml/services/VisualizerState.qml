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
    Process {
        id: bridge
        command: ["python3","-u",Quickshell.shellPath("scripts/audio_visualizer.py")]
        stdout: SplitParser { onRead: line => { try { const value=JSON.parse(line); if(value.error) { root.error=value.error; root.failed=true; } else if(value.bars && value.bars.length===16) root.bars=value.bars; } catch(error) { console.warn("Invalid visualizer frame"); } } }
        onExited: {
            const expected = root.stopping;
            root.stopping = false;
            if (expected) Qt.callLater(root.sync);
            else if (root.wanted) { root.error = "Audio visualizer stopped"; root.failed = true; }
        }
    }
}
