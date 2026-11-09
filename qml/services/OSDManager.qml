// Role: OSDManager.qml (shared layer, fan-in 4).
// Shared component/helper; keep API stable for wide QML reuse.
pragma Singleton
import QtQuick
import Quickshell
Singleton {
    id: root
    property var entries: ({})
    property int sequence: 0
    function outputName(selected, screens, focused, panel) {
        const fallback=[focused && focused.output, panel && panel.name, screens.length ? screens[0].name : ""].find(name => name && screens.some(screen => screen.name === name)) || "";
        if (selected === "focused") return fallback;
        if (selected === "all") return screens.length ? "all" : fallback;
        return screens.some(screen => screen.name === selected) ? selected : fallback;
    }
    function show(label,value,text) {
        if (ShellState.preferences.osdEnabled === false || ShellState.settingsApp) return;
        const selected=ShellState.preferences.osdOutput || "focused";
        const focused=(ShellState.niri.workspaces || []).find(w => w.is_focused);
        const name=outputName(selected, Quickshell.screens, focused, ShellState.panelScreen);
        const next=Object.assign({},entries);
        for (const screen of Quickshell.screens) if (name === "all" || screen.name===name) next[screen.name]={label,value,text: (text === undefined ? "" : text),sequence:++sequence};
        entries=next;
    }
    Connections {
        target: Quickshell
        function onScreensChanged() { const next={}; for (const screen of Quickshell.screens) if(root.entries[screen.name]) next[screen.name]=root.entries[screen.name]; root.entries=next; }
    }
}
