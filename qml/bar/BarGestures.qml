pragma Singleton
import QtQuick
import "../services"

QtObject {
    id: root
    // Gesture defaults follow Noctalia; execution uses LME's existing actions.
    readonly property var gestures: ["left", "right", "middle", "scrollUp", "scrollDown"]
    readonly property var labels: ["Left click", "Right click", "Middle click", "Scroll up", "Scroll down"]
    readonly property var actions: [
        {id: "default", title: "Default"}, {id: "none", title: "Do nothing"},
        {id: "control", title: "Control center"}, {id: "audio", title: "Audio controls"},
        {id: "devices", title: "Devices"}, {id: "agenda", title: "Agenda"}, {id: "system", title: "System monitor"},
        {id: "wifi", title: "Wi-Fi"}, {id: "notifications", title: "Notifications"},
        {id: "activity", title: "Activity Island"}, {id: "launcher", title: "Applications"},
        {id: "launchpad", title: "Launchpad"},
        {id: "clipboard", title: "Clipboard"}, {id: "settings", title: "Settings"}, {id: "power", title: "Power menu"},
        {id: "overview", title: "niri overview"}, {id: "workspaceBoard", title: "Workspace board"},
        {id: "mute", title: "Toggle mute"}, {id: "dnd", title: "Toggle Do Not Disturb"},
        {id: "volumeUp", title: "Volume +5%"}, {id: "volumeDown", title: "Volume −5%"},
        {id: "mediaToggle", title: "Play / pause"}, {id: "mediaNext", title: "Next track"}, {id: "mediaPrevious", title: "Previous track"},
        {id: "workspaceNext", title: "Next workspace"}, {id: "workspacePrevious", title: "Previous workspace"}
    ]
    function action(module, gesture) {
        const configured = (ShellState.preferences.barGestures || {})[module]?.[gesture] || "default";
        if (configured !== "default") return configured;
        if (gesture === "left") return "default";
        if (gesture === "middle") return "settings";
        if (gesture === "right") return ({audio: "mute", notifications: "dnd", overview: "workspaceBoard", media: "mediaToggle"})[module] || "none";
        if (module === "audio") return gesture === "scrollUp" ? "volumeUp" : "volumeDown";
        if (module === "media") return gesture === "scrollUp" ? "mediaNext" : "mediaPrevious";
        if (module === "workspaces") return gesture === "scrollUp" ? "workspacePrevious" : "workspaceNext";
        return "none";
    }
    function perform(module, gesture, screen, count) {
        const name = action(module, gesture);
        if (name === "default") return false;
        if (name === "none") return true;
        if (name === "mute") ShellState.run("mute");
        else if (name === "dnd") Notifications.setDnd(Notifications.dnd ? 0 : -1);
        else if (name === "volumeUp" || name === "volumeDown") {
            ShellState.run("volume", {delta: (name === "volumeUp" ? 5 : -5) * Math.min(10, count || 1)});
        } else if (name === "mediaToggle") ActivityState.togglePlaying();
        else if (name === "mediaNext") ActivityState.next();
        else if (name === "mediaPrevious") ActivityState.previous();
        else if (name === "overview") ShellState.nativeOverview();
        else if (name === "workspaceNext" || name === "workspacePrevious") {
            const workspaces = ShellState.workspacesFor(screen);
            const current = workspaces.findIndex(w => w.is_active || w.is_focused);
            const next = current + (name === "workspaceNext" ? 1 : -1);
            if (current >= 0 && next >= 0 && next < workspaces.length) ShellState.run("workspace", {id: workspaces[next].id});
        } else if (["audio", "devices", "agenda", "system"].includes(name)) {
            ShellState.controlTab = ({audio: 1, devices: 2, agenda: 3, system: 5})[name];
            ShellState.togglePanel("control", screen);
        } else ShellState.togglePanel(name === "workspaceBoard" ? "overview" : name, screen);
        return true;
    }
}
