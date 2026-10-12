pragma Singleton
import QtQuick
import Quickshell
Singleton {
    id: root
    property var entries: ({})
    property int sequence: 0
    function show(label,value) {
        if (ShellState.preferences.osdEnabled === false || ShellState.settingsApp) return;
        const selected=ShellState.preferences.osdOutput || "focused";
        const focused=(ShellState.niri.workspaces || []).find(w => w.is_focused);
        const name=selected === "focused" ? (focused && focused.output || ShellState.panelScreen && ShellState.panelScreen.name || (Quickshell.screens[0] || {}).name) : selected;
        const next=Object.assign({},entries);
        for (const screen of Quickshell.screens) if (name === "all" || screen.name===name) next[screen.name]={label,value,sequence:++sequence};
        entries=next;
    }
    Connections {
        target: Quickshell
        function onScreensChanged() { const next={}; for (const screen of Quickshell.screens) if(root.entries[screen.name]) next[screen.name]=root.entries[screen.name]; root.entries=next; }
    }
}
