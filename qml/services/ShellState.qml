pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    readonly property bool demo: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
    readonly property bool settingsApp: Quickshell.env("LME_SHELL_SETTINGS") === "1"
    // Development fixtures can simulate hardware while testing native services
    // on a private bus. The public demo/preview modes isolate both pathways.
    readonly property bool backendDemo: demo || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1"
    property var snapshot: ({apps: [], niri: {available: false, windows: [], workspaces: []}, system: {}, preferences: {language: "en", animations: true, opacity: 0.90, accent: "#9580ff"}})
    readonly property var apps: snapshot.apps || []
    readonly property var niri: snapshot.niri || {available: false, windows: [], workspaces: []}
    readonly property var system: snapshot.system || {}
    readonly property var weather: snapshot.weather || {}
    readonly property var preferences: snapshot.preferences || {}
    property bool launcherOpen: false
    property bool controlOpen: false
    property bool notificationsOpen: false
    property bool powerOpen: false
    property bool settingsOpen: false
    property string settingsPage: "appearance"
    property bool trayOpen: false
    property bool overviewOpen: false
    property bool clipboardOpen: false
    property bool activityOpen: false
    property bool wifiOpen: false
    property real activityAnchorX: -1
    property real activityAnchorWidth: 180
    property bool stayAwake: false
    property bool draggingWindow: false
    property bool authenticationActive: false
    property var pendingActions: ({})
    property real trayAnchorX: -1
    readonly property bool panelOpen: launcherOpen || controlOpen || notificationsOpen || powerOpen || settingsOpen || trayOpen || overviewOpen || clipboardOpen || activityOpen || wifiOpen
    property var panelScreen: null
    property string statusMessage: ""
    property bool statusError: false
    property bool backendReady: false
    property int restartAttempts: 0
    property var lastResult: null
    property var wifiResult: null
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
        powerOpen = false; settingsOpen = false; trayOpen = false; overviewOpen = false; clipboardOpen = false; activityOpen = false; wifiOpen = false;
    }
    function togglePanel(name, screen) {
        if (authenticationActive) return;
        if (name === "settings" && !demo && !settingsApp) {
            openSettingsPage("appearance");
            return;
        }
        const key = name + "Open";
        if (!["launcher", "control", "notifications", "power", "settings", "tray", "overview", "clipboard", "activity", "wifi"].includes(name)) return;
        const wasOpen = root[key];
        closePanels();
        if (screen) panelScreen = screen;
        root[key] = !wasOpen;
        if (notificationsOpen) Notifications.markRead();
    }
    function openSettingsPage(page) {
        if (!["appearance", "topbar", "controlLayout", "display", "wallpaper", "weather", "clipboard", "behavior", "about"].includes(page)) return;
        closePanels(); settingsPage = page;
        if (demo) settingsOpen = true;
        else if (!settingsProcess.running) settingsProcess.running = true;
    }
    function appIcon(icon) {
        if (!icon) return "";
        if (icon.startsWith("/")) return "file://" + icon;
        return Quickshell.iconPath(icon, true);
    }
    function workspacesFor(screen) {
        return (niri.workspaces || []).filter(w => !screen || !w.output || w.output === screen.name)
            .slice().sort((a, b) => String(a.output || "").localeCompare(String(b.output || "")) || Number(a.idx) - Number(b.idx) || Number(a.id) - Number(b.id));
    }
    function windowIcon(window) {
        const appId = String(window.app_id || "").toLowerCase();
        const app = apps.find(item => item.id.replace(/\.desktop$/, "").toLowerCase() === appId)
                 || apps.find(item => item.id.toLowerCase().includes(appId) && appId.length > 0);
        return appIcon(app ? app.icon : window.app_id);
    }
    function nativeOverview() {
        if (demo) { togglePanel("overview"); return; }
        closePanels();
        nativeOverviewDelay.restart();
    }
    function run(action, payload) {
        if (!backend.running || !backendReady) {
            statusMessage = "Desktop backend is unavailable. Check the shell log.";
            statusError = true; statusTimer.restart(); return;
        }
        const request = Object.assign({}, payload || {}, {action: action});
        // Release the layer-shell keyboard grab before any external agent opens.
        // The built-in Polkit agent also closes panels for requests from apps.
        if (action === "chargeMode" && !demo) closePanels();
        pendingActions = Object.assign({}, pendingActions, {[action]: true});
        backend.write(JSON.stringify(request) + "\n");
    }
    function accept(data) {
        try {
            const next = JSON.parse(data);
            if (!next.apps || !next.system || !next.niri) return;
            const oldAudio = system.audio;
            const oldBrightness = system.brightness;
            // Keep delegate identities stable between polls, especially during a drag.
            if (draggingWindow || JSON.stringify(next.niri) === JSON.stringify(niri)) next.niri = niri;
            if (JSON.stringify(next.apps) === JSON.stringify(apps)) next.apps = apps;
            if (JSON.stringify(next.preferences) === JSON.stringify(preferences)) next.preferences = preferences;
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
                if (String(next.lastResult.action).startsWith("wifi")) wifiResult = next.lastResult;
                const pending = Object.assign({}, pendingActions);
                if (!next.lastResult.pending) delete pending[next.lastResult.action];
                pendingActions = pending;
                if (next.lastResult.action === "nativeOverview" && !next.lastResult.ok) togglePanel("overview");
                if (next.lastResult.message && !["calculate", "notificationSave", "displayRefresh"].includes(next.lastResult.action) && (!next.lastResult.ok || (!settingsApp || next.lastResult.action !== "setting") && !["ready", "volume", "mute", "micVolume", "micMute", "brightness", "focusWindow", "workspace", "moveWindow", "nativeOverview", "weatherSearch", "weatherDetect", "weatherRefresh"].includes(next.lastResult.action))) {
                    statusMessage = next.lastResult.message;
                    statusError = !next.lastResult.ok; statusTimer.restart();
                }
            }
        } catch (error) { console.warn("Invalid desktop backend message:", error); }
    }
    property Process backend: Process {
        command: ["python3", "-u", Quickshell.shellPath("scripts/desktop_backend.py")]
            .concat(root.backendDemo ? ["--demo"] : []).concat(root.settingsApp ? ["--settings"] : [])
        stdinEnabled: true
        running: true
        stdout: SplitParser { onRead: data => root.accept(data) }
        stderr: SplitParser { onRead: data => console.warn("Desktop backend:", data) }
        onExited: exitCode => {
            root.backendReady = false;
            if (root.wifiResult && root.wifiResult.pending) root.wifiResult = {ok: false, message: "Desktop backend stopped during the Wi-Fi operation. Retry after it reconnects."};
            root.pendingActions = ({});
            root.statusMessage = "Desktop backend stopped (" + exitCode + ").";
            root.statusError = true;
            if (root.restartAttempts < 3) { root.restartAttempts++; root.restartTimer.restart(); }
        }
    }
    property Timer restartTimer: Timer { interval: 2000; onTriggered: root.backend.running = true }
    property Process settingsProcess: Process {
        command: ["bash", Quickshell.shellPath("scripts/settings.sh"), "--daemonize", "--page", root.settingsPage]
        stderr: SplitParser { onRead: data => console.warn("Settings:", data) }
        onExited: exitCode => {
            if (exitCode !== 0) {
                root.statusMessage = "Settings could not be opened. Check the shell log.";
                root.statusError = true; root.statusTimer.restart();
            }
        }
    }
    property Timer statusTimer: Timer { interval: 4500; onTriggered: root.statusMessage = "" }
    property Timer osdTimer: Timer { interval: 1600; onTriggered: root.osdOpen = false }
    property Timer nativeOverviewDelay: Timer { interval: 80; onTriggered: root.run("nativeOverview") }
}
