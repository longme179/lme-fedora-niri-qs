pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
Singleton {
    id: root
    property bool retryAllowed: true
    readonly property bool watching: !ShellState.demo && !ShellState.settingsApp && !!ShellState.niri.available && (ShellState.preferences.privacyIndicators !== false || ShellState.preferences.dndWhileSharing !== false)
    property var casts: []
    readonly property var captures: (ShellState.system.privacy || {}).captures || []
    readonly property bool sharing: !!(ShellState.snapshot.mirror || {}).active || casts.some(c => c.is_active) || captures.some(c => c.kind === "screen") || !!(ShellState.system.recording || {}).owned
    readonly property var indicators: [
        {icon:"microphone", title:"Microphone in use", active:captures.some(c => c.kind === "microphone"), kind:"microphone"},
        {icon:"camera", title:"Camera in use", active:captures.some(c => c.kind === "camera"), kind:"camera"},
        {icon:"screen-share", title:"Screen sharing", active:sharing, kind:"screen"}
    ].filter(i => i.active)
    function event(value) {
        if (value.CastsChanged) casts=value.CastsChanged.casts || [];
        else if (value.CastStartedOrChanged && value.CastStartedOrChanged.cast) {
            const cast=value.CastStartedOrChanged.cast;
            casts=[...casts.filter(c => c.stream_id !== cast.stream_id),cast];
        } else if (value.CastStopped) casts=casts.filter(c => c.stream_id !== value.CastStopped.stream_id);
    }
    Process {
        id: events; command: ["niri","msg","--json","event-stream"]
        running: root.watching && root.retryAllowed
        stdout: SplitParser { onRead: line => { try { root.event(JSON.parse(line)); } catch(error) { console.warn("Privacy event could not be read"); } } }
        onExited: { root.casts=[]; if (root.watching) { root.retryAllowed=false; retry.restart(); } }
    }
    Timer { id: retry; interval: 5000; onTriggered: root.retryAllowed=true }
}
