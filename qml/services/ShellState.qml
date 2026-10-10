pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    readonly property bool demo: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
    // Development fixtures can simulate hardware while testing native services
    // on a private bus. The public demo/preview modes isolate both pathways.
    readonly property bool backendDemo: demo || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1"
    property var snapshot: ({apps: [], niri: {available: false, windows: [], workspaces: []}, system: {}, preferences: {language: "en", animations: true, opacity: 0.90, dockAutoHide: true, accent: "#9580ff"}})
    readonly property var apps: snapshot.apps || []
    readonly property var niri: snapshot.niri || {available: false, windows: [], workspaces: []}
    readonly property var system: snapshot.system || {}
    readonly property var preferences: snapshot.preferences || {}
    property bool launcherOpen: false
    property bool controlOpen: false
    property bool notificationsOpen: false
    property bool powerOpen: false
    property bool settingsOpen: false
    readonly property bool panelOpen: launcherOpen || controlOpen || notificationsOpen || powerOpen || settingsOpen
    property var panelScreen: null
    property string statusMessage: ""
    property bool statusError: false
    property bool backendReady: false
    property int restartAttempts: 0
    property var lastResult: null
    property string osdLabel: ""
    property real osdValue: 0
    property bool osdOpen: false
    readonly property string focusedTitle: {
        const windows = niri.windows || [];
        const focused = windows.find(w => w.is_focused);
        return focused ? focused.title : "LME / Liquid Desktop";
    }

    function closePanels() {
        launcherOpen = false; controlOpen = false; notificationsOpen = false;
        powerOpen = false; settingsOpen = false;
    }
    function togglePanel(name, screen) {
        const key = name + "Open";
        if (!["launcher", "control", "notifications", "power", "settings"].includes(name)) return;
        const wasOpen = root[key];
        closePanels();
        if (screen) panelScreen = screen;
        root[key] = !wasOpen;
        if (notificationsOpen) Notifications.markRead();
    }
    function appIcon(icon) {
        if (!icon) return "";
        if (icon.startsWith("/")) return "file://" + icon;
        return Quickshell.iconPath(icon, true);
    }
    function run(action, payload) {
        if (!backend.running || !backendReady) {
            statusMessage = "Desktop backend is unavailable. Check the shell log.";
            statusError = true; statusTimer.restart(); return;
        }
        const request = Object.assign({}, payload || {}, {action: action});
        backend.write(JSON.stringify(request) + "\n");
    }
    function accept(data) {
        try {
            const next = JSON.parse(data);
            if (!next.apps || !next.system || !next.niri) return;
            const oldAudio = system.audio;
            const oldBrightness = system.brightness;
            snapshot = next;
            backendReady = true; restartAttempts = 0;
            if (oldAudio && next.system.audio && oldAudio.available && next.system.audio.available
                    && (oldAudio.volume !== next.system.audio.volume || oldAudio.muted !== next.system.audio.muted)) {
                osdLabel = next.system.audio.muted ? "Muted" : "Volume";
                osdValue = next.system.audio.muted ? 0 : next.system.audio.volume;
                osdOpen = true; osdTimer.restart();
            } else if (oldBrightness && next.system.brightness && oldBrightness.available
                    && oldBrightness.percent !== next.system.brightness.percent) {
                osdLabel = "Brightness"; osdValue = next.system.brightness.percent;
                osdOpen = true; osdTimer.restart();
            }
            if (next.lastResult && JSON.stringify(next.lastResult) !== JSON.stringify(lastResult)) {
                lastResult = next.lastResult;
                if (next.lastResult.message && (!next.lastResult.ok || !["ready", "volume", "mute", "brightness", "focusWindow", "workspace"].includes(next.lastResult.action))) {
                    statusMessage = next.lastResult.message;
                    statusError = !next.lastResult.ok; statusTimer.restart();
                }
            }
        } catch (error) { console.warn("Invalid desktop backend message:", error); }
    }
    property Process backend: Process {
        command: root.backendDemo ? ["python3", "-u", Quickshell.shellPath("scripts/desktop_backend.py"), "--demo"]
                           : ["python3", "-u", Quickshell.shellPath("scripts/desktop_backend.py")]
        stdinEnabled: true
        running: true
        stdout: SplitParser { onRead: data => root.accept(data) }
        stderr: SplitParser { onRead: data => console.warn("Desktop backend:", data) }
        onExited: exitCode => {
            root.backendReady = false;
            root.statusMessage = "Desktop backend stopped (" + exitCode + ").";
            root.statusError = true;
            if (root.restartAttempts < 3) { root.restartAttempts++; root.restartTimer.restart(); }
        }
    }
    property Timer restartTimer: Timer { interval: 2000; onTriggered: root.backend.running = true }
    property Timer statusTimer: Timer { interval: 4500; onTriggered: root.statusMessage = "" }
    property Timer osdTimer: Timer { interval: 1600; onTriggered: root.osdOpen = false }
}
