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
    function addRef() { if (!refs) { failed=false; error=""; } refs++; }
    function removeRef() { refs=Math.max(0,refs-1); if(!refs) bars=Array(16).fill(0); }
    Process {
        command: ["python3","-u",Quickshell.shellPath("scripts/audio_visualizer.py")]
        running: root.refs>0 && !root.failed && !ShellState.demo && !ShellState.settingsApp && ShellState.preferences.audioVisualizer === true
        stdout: SplitParser { onRead: line => { try { const value=JSON.parse(line); if(value.error) { root.error=value.error; root.failed=true; } else if(value.bars && value.bars.length===16) root.bars=value.bars; } catch(error) { console.warn("Invalid visualizer frame"); } } }
        onExited: code => { if(root.refs && !root.failed && ShellState.preferences.audioVisualizer === true) { root.error="Audio visualizer stopped"; root.failed=true; } }
    }
}
