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
    readonly property var launcherUsage: snapshot.launcherUsage || ({})
    readonly property var niri: snapshot.niri || {available: false, windows: [], workspaces: []}
    readonly property var system: snapshot.system || {}
    readonly property var weather: snapshot.weather || {}
    readonly property var preferences: snapshot.preferences || {}
    readonly property bool batterySaverActive: (snapshot.batterySaver || {}).active === true
    readonly property string shellName: preferences.shellName || "LME Shell"
    readonly property bool popupBlurEnabled: !demo && !batterySaverActive && preferences.surfaceStyle !== "liquid" && preferences.popupBlur !== false && (snapshot.platform || {}).popupBlurSupported === true
    readonly property bool liquidBlurEnabled: !demo && !batterySaverActive && preferences.surfaceStyle === "liquid" && (snapshot.platform || {}).popupBlurSupported === true
    readonly property bool barBlurEnabled: !demo && !batterySaverActive && preferences.barBlur !== false && (snapshot.platform || {}).popupBlurSupported === true
    readonly property var legacyPanels: ["launchpad", "launcher", "control", "notifications", "power", "settings", "tray", "overview", "activity", "wifi"]
    property string panelKind: "control"
    property bool launchpadOpen: false
    property bool launcherOpen: false
    property bool controlOpen: false
    property bool notificationsOpen: false
    property bool powerOpen: false
    property bool settingsOpen: false
    property string settingsPage: "appearance"
    property bool trayOpen: false
    property bool overviewOpen: false
    property bool catalogPanelOpen: false
    property bool activityOpen: false
    property bool wifiOpen: false
    property real activityAnchorX: -1
    property real activityAnchorWidth: 180
    property int controlTab: 0
    readonly property string controlTabId: ControlRegistry.tabForIndex(controlTab).id || ""
    function selectControlTab(id) { controlTab = ControlRegistry.indexForId(id); }
    property bool stayAwake: false
    onStayAwakeChanged: if (backendReady && !settingsApp) run("idleInhibit", {value: stayAwake})
    property bool draggingWindow: false
    property bool authenticationActive: false
    property var pendingActions: ({})
    property real trayAnchorX: -1
    readonly property bool panelOpen: catalogPanelOpen || launchpadOpen || launcherOpen || controlOpen || notificationsOpen || powerOpen || settingsOpen || trayOpen || overviewOpen || activityOpen || wifiOpen
    property var panelScreen: null
    property string statusMessage: ""
    property bool statusError: false
    property bool backendReady: false
    property var wifiConsumers: []
    function watchWifi(consumer, enabled) {
        const wasWatching = wifiConsumers.length > 0;
        if (enabled && !wifiConsumers.includes(consumer)) wifiConsumers = [...wifiConsumers, consumer];
        else if (!enabled) wifiConsumers = wifiConsumers.filter(item => item !== consumer);
        if (backendReady && wasWatching !== (wifiConsumers.length > 0)) run("wifiWatch", {enabled: wifiConsumers.length > 0});
    }
    onBackendReadyChanged: if (backendReady && wifiConsumers.length) run("wifiWatch", {enabled: true})
    property int restartAttempts: 0
    property var lastResult: null
    property var wifiResult: null
    property string osdLabel: ""
    property real osdValue: 0
    property bool osdOpen: false
    readonly property string focusedTitle: {
        const windows = niri.windows || [];
        const focused = windows.find(w => w.is_focused);
        return focused && focused.title ? focused.title : root.shellName;
    }

    function isPanelOpen(name) { return FeatureCatalog.panel(name) ? catalogPanelOpen && panelKind === name : root[name + "Open"] === true; }
    function closePanels() {
        catalogPanelOpen = false;
        launchpadOpen = false; launcherOpen = false; controlOpen = false; notificationsOpen = false;
        powerOpen = false; settingsOpen = false; trayOpen = false; overviewOpen = false; activityOpen = false; wifiOpen = false;
    }
    function togglePanel(name, screen) {
        if (authenticationActive) return;
        if (name === "settings" && !demo && !settingsApp) {
            openSettingsPage("appearance");
            return;
        }
        if (FeatureCatalog.panel(name)) {
            const wasOpen = isPanelOpen(name);
            closePanels();
            if (screen) panelScreen = screen;
            panelKind = name; catalogPanelOpen = !wasOpen;
            return;
        }
        const key = name + "Open";
        if (!legacyPanels.includes(name)) return;
        const wasOpen = root[key];
        closePanels();
        if (screen) panelScreen = screen;
        if (name !== "activity") panelKind = name;
        root[key] = !wasOpen;
        if (notificationsOpen) Notifications.markRead();
    }
    function settingsPageAvailable(page) {
        return ["desktop", "appearance", "elements", "topbar", "controlLayout", "display", "notifications", "behavior", "about"].includes(page)
                || (FeatureCatalog.data.settingsPage || []).some(entry => entry.key === page);
    }
    function openSettingsPage(page) {
        if (!settingsPageAvailable(page)) return;
        closePanels(); settingsPage = page;
        if (demo) { panelKind = "settings"; settingsOpen = true; }
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
    property bool overlayVisible: false
    property real captureDeadline: 0
    property real recordDeadline: 0
    property var recordingRequest: ({})
    function startRecording(request) { if(demo || authenticationActive) return; closePanels(); captureDelay.stop(); statusMessage=""; recordingRequest=request; recordDeadline=Date.now()+3000; recordDelay.restart(); }
    property Timer recordDelay: Timer { interval: 80; onTriggered: { if(root.authenticationActive) return; if(root.panelOpen) return; if(root.overlayVisible) { if(Date.now()<root.recordDeadline) restart(); else { root.statusMessage="Recording cancelled: the overlay did not close"; root.statusTimer.restart(); } return; } root.run("recordStart",root.recordingRequest); } }
    property string captureMode: "screen"
    function takeScreenshot(mode) {
        if (!['screen', 'area', 'window'].includes(mode) || demo || authenticationActive) return;
        closePanels(); recordDelay.stop(); statusMessage=""; captureMode = mode; captureDeadline=Date.now()+3000; captureDelay.restart();
    }
    property Timer captureDelay: Timer {
        interval: 250
        onTriggered: { if(root.authenticationActive) return; if(root.panelOpen) return; if(root.overlayVisible) { if(Date.now()<root.captureDeadline) restart(); else { root.statusMessage="Capture cancelled: the overlay did not close"; root.statusTimer.restart(); } return; } root.run(({screen: 'screenshot', area: 'screenshotArea', window: 'screenshotWindow'})[root.captureMode]); }
    }
    function run(action, payload) {
        if (!backend.running || !backendReady) {
            statusMessage = "Desktop backend is unavailable. Check the shell log.";
            statusError = true; statusTimer.restart(); return;
        }
        const request = Object.assign({}, payload || {}, {action: action});
        // Release the layer-shell keyboard grab before any external agent opens.
        // The built-in Polkit agent also closes panels for requests from apps.
        if (action === "imageAnnotate" || action === "chargeMode" && !demo) closePanels();
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
            if (JSON.stringify(next.launcherUsage || {}) === JSON.stringify(launcherUsage)) next.launcherUsage = launcherUsage;
            if (JSON.stringify(next.preferences) === JSON.stringify(preferences)) next.preferences = preferences;
            snapshot = next;
            FeatureCatalog.validate(next.catalogValidation);
            const wasReady = backendReady;
            backendReady = true; restartAttempts = 0;
            if (!demo && !settingsApp) {
                const low = PeripheralBatteries.check(system.peripheralBatteries || [], preferences.peripheralBatteryAlerts !== false,
                    preferences.peripheralBatteryThreshold);
                if (low.length) Notifications.local("Device battery low", low.map(device => device.name + " · " + Math.round(device.percentage) + "%").join("\n"));
            }
            if (!wasReady && stayAwake && !settingsApp) run("idleInhibit", {value: true});
            if (oldAudio && next.system.audio && oldAudio.available && next.system.audio.available
                    && (oldAudio.volume !== next.system.audio.volume || oldAudio.muted !== next.system.audio.muted)) {
                osdLabel = next.system.audio.muted ? "Muted" : "Volume";
                osdValue = next.system.audio.muted ? 0 : next.system.audio.volume;
                osdOpen = true; osdTimer.restart(); OSDManager.show(osdLabel,osdValue);
            } else if (oldBrightness && next.system.brightness && oldBrightness.available
                    && oldBrightness.percent !== next.system.brightness.percent) {
                osdLabel = "Brightness"; osdValue = next.system.brightness.percent;
                osdOpen = true; osdTimer.restart(); OSDManager.show(osdLabel,osdValue);
            }
            if (next.lastResult && JSON.stringify(next.lastResult) !== JSON.stringify(lastResult)) {
                lastResult = next.lastResult;
                if (String(next.lastResult.action).startsWith("wifi") && next.lastResult.action !== "wifiWatch") wifiResult = next.lastResult;
                const pending = Object.assign({}, pendingActions);
                if (!next.lastResult.pending) delete pending[next.lastResult.action];
                pendingActions = pending;
                if (next.lastResult.action === "nativeOverview" && !next.lastResult.ok) togglePanel("overview");
                if (next.lastResult.message && !["calculate", "notificationSave", "displayRefresh", "monitor", "wifiWatch", "controlsRefresh", "keybindRefresh", "idleRefresh", "idleInhibit", "platformRefresh", "nightLightRefresh", "mirrorRefresh", "captureLanguages", "captureClose"].includes(next.lastResult.action) && (!next.lastResult.ok || (!settingsApp || next.lastResult.action !== "setting") && !["ready", "volume", "mute", "micVolume", "micMute", "brightness", "bluetoothDevice", "focusWindow", "workspace", "moveWindow", "nativeOverview", "weatherSearch", "weatherDetect", "weatherRefresh", "fileSearch", "notesInit", "recordStart"].includes(next.lastResult.action))) {
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
        command: ["env", "LME_SHELL_ENTRY=" + Quickshell.shellPath("shell.qml"),
                  "bash", Quickshell.shellPath("scripts/settings.sh"), "--daemonize", "--page", root.settingsPage]
        stdout: SplitParser { onRead: data => console.log("Settings:", data) }
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
