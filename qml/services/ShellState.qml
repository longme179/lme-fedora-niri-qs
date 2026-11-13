pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "ActionPending.js" as Pending
import "SnapshotIdentity.js" as Identity

QtObject {
    id: root
    readonly property bool demo: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
    readonly property bool settingsApp: Quickshell.env("LME_SHELL_SETTINGS") === "1"
    // Development fixtures can simulate hardware while testing native services
    // on a private bus. The public demo/preview modes isolate both pathways.
    readonly property bool backendDemo: demo || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1"
    property var snapshot: ({apps: [], niri: {available: false, windows: [], workspaces: []}, system: {}, preferences: {language: "en", animations: true, opacity: 0.90, accent: "#9580ff"}})
    readonly property var apps: NativeState.apps(snapshot.apps) // Q2: native app list in real sessions (qml/services/LauncherState.qml)
    readonly property var launcherUsage: NativeState.usage(snapshot.launcherUsage, preferences.launcherRanking !== false) // Q2: native history store
    readonly property var audioDevices: NativeState.audioDevices(snapshot.audioDevices) // Q3: native audio device inventory (AudioDeviceState.qml)
    readonly property var networkConnections: NativeState.networkConnections(snapshot.networkConnections) // Q3: native saved connections (NetworkInventoryState.qml)
    readonly property var keybinds: NativeState.keybinds(snapshot.keybinds) // Q4: native keybinding viewer (KeybindsState.qml)
    readonly property var niri: NativeState.niri(snapshot.niri, draggingWindow) // Q4: native niri event-stream section (NiriState.qml)
    readonly property var displays: NativeState.displays(snapshot.displays) // Q4: native display refresh (DisplayState.qml)
    readonly property var mirror: NativeState.mirror(snapshot.mirror) // Q4: native mirroring (MirrorState.qml)
    readonly property var nightLight: NativeState.nightLight(snapshot.nightLight) // Q4: native Night Light (NightLightState.qml)
    readonly property var idle: NativeState.idle(snapshot.idle) // Q4: native idle profiles (IdleState.qml)
    readonly property var system: NativeState.merge(snapshot.system || {}) // Q1: native sections merged over the backend's (qml/services/NativeState.qml)
    readonly property var weather: NativeState.weather(snapshot.weather) // Q5: native weather (WeatherState.qml); backend section stays the A/B window
    readonly property var fileSearch: NativeState.fileSearch(snapshot.fileSearch) // Q5 leg 3: native search results (FileSearchState.qml); backend section stays the A/B window
    readonly property var preferences: snapshot.preferences || {}
    readonly property bool batterySaverActive: (snapshot.batterySaver || {}).active === true; readonly property bool reducedTransparency: preferences.reducedTransparency === true
    readonly property string shellName: preferences.shellName || "LME Shell"
    readonly property bool popupBlurEnabled: !demo && !batterySaverActive && !reducedTransparency && preferences.surfaceStyle !== "liquid" && preferences.popupBlur !== false && (snapshot.platform || {}).popupBlurSupported === true
    readonly property bool liquidBlurEnabled: !demo && !batterySaverActive && !reducedTransparency && preferences.surfaceStyle === "liquid" && (snapshot.platform || {}).popupBlurSupported === true
    readonly property bool barBlurEnabled: !demo && !batterySaverActive && !reducedTransparency && preferences.barBlur !== false && (snapshot.platform || {}).popupBlurSupported === true
    readonly property var legacyPanels: ["launchpad", "launcher", "control", "power", "settings", "tray", "overview", "activity", "wifi"]
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
    property var pendingActions: ({}) // INVARIANT: action ownership/pending state tracks JSON-lines requests/results.
    property var pendingState: Pending.initial()
    property real trayAnchorX: -1
    readonly property bool panelOpen: catalogPanelOpen || launchpadOpen || launcherOpen || controlOpen || notificationsOpen || powerOpen || settingsOpen || trayOpen || overviewOpen || activityOpen || wifiOpen
    // Bumped whenever an open panel is replaced by a different one; the shell
    // retires the outgoing surface immediately (atomic swap).
    property int panelSwap: 0
    property var panelScreen: null
    property string statusMessage: ""
    property bool statusError: false
    property bool backendReady: false
    property var wifiConsumers: []
    function watchWifi(consumer, enabled) {
        const wasWatching = wifiConsumers.length > 0;
        if (enabled && !wifiConsumers.includes(consumer)) wifiConsumers = [...wifiConsumers, consumer];
        else if (!enabled) wifiConsumers = wifiConsumers.filter(item => item !== consumer);
        const watching = wifiConsumers.length > 0;
        if (!backendDemo && !settingsApp) NetworkState.watching = watching; // Q3: native scanner + list gating (A6)
        if (backendReady && wasWatching !== watching) run("wifiWatch", {enabled: watching}); // backend keeps its A/B copy
    }
    onBackendReadyChanged: if (backendReady && wifiConsumers.length) run("wifiWatch", {enabled: true})
    property int restartDelay: 2000
    property var lastResult: null
    property var wifiResult: null
    property string osdLabel: ""; property real osdValue: 0
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
            const replacing = panelOpen && !wasOpen;
            closePanels();
            if (replacing) panelSwap++;
            if (screen) panelScreen = screen;
            panelKind = name; catalogPanelOpen = !wasOpen;
            if (name === "notifications") { notificationsOpen = !wasOpen; if (notificationsOpen) Notifications.markRead(); }
            return;
        }
        const key = name + "Open";
        if (!legacyPanels.includes(name)) return;
        const wasOpen = root[key];
        const replacing = panelOpen && !wasOpen;
        closePanels();
        if (replacing) panelSwap++;
        if (screen) panelScreen = screen;
        if (name !== "activity") panelKind = name;
        root[key] = !wasOpen;
        if (notificationsOpen) Notifications.markRead();
    }
    function settingsPageAvailable(page) {
        return ["appearance", "elements", "topbar", "controlLayout", "display", "behavior"].includes(page)
                || (FeatureCatalog.data.settingsPage || []).some(entry => entry.key === page);
    }
    function featureEnabled(id) { return FeatureCatalog.featureEnabled(id); }
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
    property bool overlayVisible: false; property real captureDeadline: 0
    property real recordDeadline: 0
    property var recordingRequest: ({}); property bool snapshotWarning: false
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
    // Q3 native router — the write families (plan §5 Q3). Real sessions route a family's
    // action names to the owning service's native calls (Pending sequencing unchanged so
    // busy/status UX is identical); fixture modes always keep the backend round-trip (the
    // demo registry owns its state), and real sessions a service cannot serve natively fall
    // back to the backend registry for its canonical errors while the A/B window is open.
    readonly property var nativeMutationActions: ["wifiConnect", "wifiSaved", "wifiDisconnect", "wifiForget", "wifiToggle", "networkConnect", "networkDisconnect", "networkHotspotStart", "networkEdit"]
    function nativeOwner(action) {
        if (NetworkState.handles(action)) return NetworkState;
        if (AudioState.handles(action)) return AudioState;
        if (BluetoothState.handles(action)) return BluetoothState;
        if (PowerState.handles(action)) return PowerState;
        if (NetworkInventoryState.handles(action)) return NetworkInventoryState;
        if (AudioDeviceState.handles(action)) return AudioDeviceState;
        if (WindowState.handles(action)) return WindowState; // Q4: compositor window/workspace actions
        if (KeybindsState.handles(action)) return KeybindsState; // Q4: keybinding viewer
        if (ImeState.handles(action)) return ImeState; // Q4: input-method name
        if (DisplayState.handles(action)) return DisplayState; // Q4: display refresh
        if (MirrorState.handles(action)) return MirrorState; // Q4: display mirroring
        if (NightLightState.handles(action)) return NightLightState; // Q4: Night Light retry
        if (IdleState.handles(action)) return IdleState; // Q4: idle refresh + inhibit
        if (WeatherState.handles(action)) return WeatherState; // Q5: search/detect/refresh; Q6 leg 1: select writes preferences through StorageState
        if (WallpaperState.handles(action)) return WallpaperState; // Q5 leg 2: daemon status/ensure + the playlist advance (user saves stay backend)
        if (FileSearchState.handles(action)) return FileSearchState; // Q5 leg 3: the search worker + fileOpen entry validation
        if (EqualizerState.handles(action)) return EqualizerState; // Q5 leg 3b: the eq staging machine + daemon runner + test tone
        return null;
    }
    // The inventory families' pending gates (scripts/audio_device_actions.py::prepare and
    // scripts/wifi_actions.py::provide_connections::prepare): one audio operation at a time
    // (bluetoothDevice included — a route may target its card), and the connection actions
    // block each other including refresh/plan (mutations also block wifi work below).
    function inventoryBusy(action) {
        const audioFamily = ["audioDevicesRefresh", "audioPort", "audioProfile", "audioRoute", "bluetoothDevice"];
        const connections = ["networkRefresh", "networkConnect", "networkDisconnect", "networkHotspotPlan", "networkHotspotStart", "networkEdit"];
        if (audioFamily.indexOf(action) >= 0 && audioFamily.some(name => pendingActions[name]))
            return "An audio device operation is already running";
        if (connections.indexOf(action) >= 0 && connections.some(name => pendingActions[name]))
            return "This operation is already running";
        return "";
    }
    function run(action, payload) {
        // Release the layer-shell keyboard grab before any external agent opens.
        // The built-in Polkit agent also closes panels for requests from apps.
        if ((action === "imageAnnotate" || action === "chargeMode") && !demo || ["networkConnect", "networkDisconnect", "networkHotspotStart", "networkEdit"].includes(action)) closePanels();
        if (!backendDemo && !settingsApp) {
            const owner = nativeOwner(action);
            if (owner) {
                // The context carries the merged system (backend-fed transitional keys like
                // the charging section and rfkill flags), the merged niri lists and the
                // preferences (the session family's paths), and an interim-status emitter, so
                // the services stay free of ShellState references (composition stays acyclic).
                const context = {system: system, niri: niri, preferences: preferences, status: message => { statusMessage = message; statusError = false; statusTimer.restart(); }};
                if (owner.canRoute(action, payload || {}, context)) {
                    // The backend's busy() contract: only a pending MUTATION blocks another
                    // mutation — routine reads and the rapid window/workspace actions stay
                    // dispatchable while one runs (Q4 scoped the Q3 approximation to the
                    // incoming action).
                    const busy = inventoryBusy(action) || (nativeMutationActions.includes(action) && nativeMutationActions.some(name => pendingActions[name]) ? "This operation is already running" : "");
                    if (busy) { statusMessage = busy; statusError = true; statusTimer.restart(); return; }
                    let sent;
                    try { sent = Pending.sent(pendingState, action); }
                    catch (error) { statusMessage = String(error); statusError = true; statusTimer.restart(); return; }
                    pendingState = sent;
                    pendingActions = sent.pending;
                    owner.perform(action, payload || {}, (ok, message) => nativeDone(action, ok, message), context);
                    return;
                }
            }
        }
        send(action, payload);
    }
    // Settle a natively-served action: the backend never sees the request, so its metadata
    // must not be waited for (ActionPending.settled) and the result surfaces like a backend
    // result — routine actions stay toast-silent exactly like accept()'s result path.
    readonly property var routineActions: ["calculate", "notificationSave", "displayRefresh", "monitor", "wifiWatch", "controlsRefresh", "audioDevicesRefresh", "networkRefresh", "networkHotspotPlan", "keybindRefresh", "idleRefresh", "idleInhibit", "platformRefresh", "nightLightRefresh", "mirrorRefresh", "captureLanguages", "captureClose", "ready", "volume", "mute", "micVolume", "micMute", "brightness", "bluetoothDevice", "focusWindow", "workspace", "moveWindow", "nativeOverview", "weatherSearch", "weatherDetect", "weatherRefresh", "fileSearch", "notesInit", "recordStart", "inputMethod", "eqGet"]
    function nativeDone(action, ok, message) {
        pendingState = Pending.settled(pendingState, action);
        pendingActions = pendingState.pending;
        const result = {action: action, ok: ok, message: message, pending: false};
        lastResult = result;
        if (String(action).startsWith("wifi") && action !== "wifiWatch") wifiResult = result;
        if (message && (!ok || !routineActions.includes(action))) { statusMessage = message; statusError = !ok; statusTimer.restart(); }
    }
    function send(action, payload) { // REL: scripts/desktop_backend.py::handle – sends {action,...} over stdin.
        if (!backend.running || !backendReady) {
            statusMessage = "Desktop backend is unavailable. Check the shell log.";
            statusError = true; statusTimer.restart(); return;
        }
        let sent;
        try { sent = Pending.sent(pendingState, action); }
        catch (error) { statusMessage = String(error); statusError = true; statusTimer.restart(); return; }
        const request = Object.assign({}, payload || {}, {action: action, clientSerial: sent.serial});
        pendingState = sent;
        backend.write(JSON.stringify(request) + "\n"); // Protocol: JSON-lines request; result carries ok/action/message/sequence/pending.
        // Write before notifying consumers, which can synchronously submit again.
        pendingActions = sent.pending;
    }
    function accept(data) {
        try {
            const next = JSON.parse(data);
            if (!next.apps || !next.system || !next.niri) {
                if (!snapshotWarning) { snapshotWarning = true; console.warn("Incomplete desktop backend snapshot; keeping the previous state."); statusMessage = "Desktop backend sent an incomplete snapshot. Check the shell log."; statusError = true; statusTimer.restart(); } return;
            }
            snapshotWarning = false; const resultChanged = next.lastResult && JSON.stringify(next.lastResult) !== JSON.stringify(lastResult);
            const ownership = Pending.received(pendingState, next.actionPending, resultChanged ? next.lastResult : null);
            if (ownership.invalid) console.warn("Invalid desktop backend message: actionPending ownership");
            pendingState = ownership.state;
            pendingActions = ownership.state.pending;
            const oldBrightness = system.brightness;
            // Keep delegate identities stable between polls, especially during a drag.
            if (Identity.keep(next, snapshot, "niri", niri, draggingWindow)) next.niri = niri;
            if (Identity.keep(next, snapshot, "apps", apps)) next.apps = apps;
            if (Identity.keep(next, snapshot, "launcherUsage", launcherUsage)) next.launcherUsage = launcherUsage;
            if (Identity.keep(next, snapshot, "preferences", preferences)) next.preferences = preferences;
            // Stable references keep bindings from re-evaluating every poll; the merged system caches in SystemMerge.js.
            if (Identity.keep(next, snapshot, "displays", snapshot.displays)) next.displays = snapshot.displays;
            snapshot = next;
            if (!demo && !settingsApp && !backendDemo) NativeState.compareSections(next, system, apps, niri, draggingWindow); // Q1/Q2/Q4 A/B window
            // Q4 session-daemon sync at the backend's 2 s poll cadence (desktop_backend.py's
            // state_snapshot loop owned wlsunset/swayidle and re-checked the mirror there —
            // the native services now own them, driven from the snapshot hook with the
            // resolved weather place and the merged AC state).
            if (!demo && !settingsApp && !backendDemo) {
                WeatherState.sync(preferences); // Q5: resolves the native weather place (ipwho.is detect) at the poll cadence
            // Q5 leg 2: the native playlist scheduler (daemon ownership + deadline machine). The
            // write/run closures keep WallpaperState ShellState-free; the backend stays the A/B
            // window (spawned with --no-wallpaper) and still owns user-initiated saves.
            WallpaperState.sync(preferences,
                Array.from(new Set((next.niri.workspaces || []).map(item => item.output).filter(name => name))),
                ((next.batterySaver || {}).active === true),
                (key, value, token) => send("setting", {key: key, value: value, token: token}),
                (action, payload) => run(action, payload));
            NightLightState.sync(preferences, ((WeatherState.section || {}).location) || ((next.weather || {}).location) || null);
                IdleState.sync(preferences, (system.battery || {}).acOnline === true);
                MirrorState.recheck(preferences);
            }
            FeatureCatalog.validate(next.catalogValidation);
            const wasReady = backendReady;
            backendReady = true; restartDelay = 2000;
            if (statusError && statusMessage.indexOf("Desktop backend stopped") === 0) { statusMessage = ""; statusError = false; }
            if (!demo && !settingsApp) {
                const low = PeripheralBatteries.check(system.peripheralBatteries || [], preferences.peripheralBatteryAlerts !== false,
                    preferences.peripheralBatteryThreshold);
                if (low.length) Notifications.local("Device battery low", low.map(device => device.name + " · " + Math.round(device.percentage) + "%").join("\n"));
            }
            if (!wasReady && stayAwake && !settingsApp) run("idleInhibit", {value: true});
            if (oldBrightness && next.system.brightness && oldBrightness.available && next.system.brightness.available
                    && oldBrightness.percent !== next.system.brightness.percent) {
                osdLabel = "Brightness"; osdValue = next.system.brightness.percent;
                osdOpen = true; osdTimer.restart(); OSDManager.show(osdLabel,osdValue);
            }
            if (resultChanged) {
                lastResult = next.lastResult;
                if (String(next.lastResult.action).startsWith("wifi") && next.lastResult.action !== "wifiWatch") wifiResult = next.lastResult;
                if (next.lastResult.action === "nativeOverview" && !next.lastResult.ok) togglePanel("overview");
                const routine = routineActions.includes(next.lastResult.action);
                if (next.lastResult.message && (!next.lastResult.ok || !routine && (!settingsApp || next.lastResult.action !== "setting"))) {
                    statusMessage = next.lastResult.message;
                    statusError = !next.lastResult.ok; statusTimer.restart();
                }
            }
        } catch (error) { console.warn("Invalid desktop backend message:", error); }
    }
    property Connections audioOsd: Connections { // Q1: volume/mute OSD follows native audio; brightness still tracks the backend poll.
        target: AudioState
        function onOsd(volume, muted) {
            osdLabel = muted ? "Muted" : "Volume"; osdValue = muted ? 0 : volume;
            osdOpen = true; osdTimer.restart(); OSDManager.show(osdLabel, osdValue);
        }
    }
    property Process backend: Process { // REL: scripts/desktop_backend.py – long-lived Python backend (see Phase 3 map).
        command: ["python3", "-u", Quickshell.shellPath("scripts/desktop_backend.py")]
            .concat(root.backendDemo ? ["--demo"] : []).concat(root.settingsApp ? ["--settings"] : [])
            .concat(!root.backendDemo && !root.settingsApp ? ["--no-session-daemons"] : []) // Q4: the native services own wlsunset/swayidle
            .concat(!root.backendDemo && !root.settingsApp ? ["--no-weather"] : []) // Q5: WeatherState.qml owns weather; the backend section stays fetch-idle (A/B window)
            .concat(!root.backendDemo && !root.settingsApp ? ["--no-wallpaper"] : []) // Q5 leg 2: WallpaperState.qml owns the scheduler; the backend keeps user saves (A/B window)
        stdinEnabled: true
        running: true
        stdout: SplitParser { onRead: data => root.accept(data) }
        stderr: SplitParser { onRead: data => console.warn("Desktop backend:", data) }
        onExited: exitCode => {
            root.pendingState = Pending.initial();
            root.pendingActions = ({});
            root.backendReady = false;
            if (root.wifiResult && root.wifiResult.pending) root.wifiResult = {ok: false, message: "Desktop backend stopped during the Wi-Fi operation. Retry after it reconnects."};
            root.statusMessage = "Desktop backend stopped (" + exitCode + ").";
            root.statusError = true; root.statusTimer.restart();
            root.restartTimer.interval = root.restartDelay; root.restartTimer.restart(); root.restartDelay = Math.min(60000, root.restartDelay * 2);
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
