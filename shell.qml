//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env QS_NO_RELOAD_POPUP=1
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "qml/services"
import "qml/theme"
import "qml/components"
import "qml/panels"
import "qml/auth"

ShellRoot {
    id: root
    readonly property string screenshotPath: Quickshell.env("LME_SHELL_SCREENSHOT") || ""
    readonly property bool preview: Quickshell.env("LME_SHELL_PREVIEW") === "1"
    FeatureBootstrap {}
    LazyLoader {
        id: authentication
        active: !ShellState.demo
        component: AuthenticationAgent {}
    }
    IpcHandler {
        target: "shell"
        function toggle(panel: string): void { ShellState.togglePanel(panel); }
        function desktopEdit(): bool { if (!DesktopState.enabled) return false; DesktopState.editing = !DesktopState.editing; return true; }
        function close(): void { ShellState.closePanels(); }
        function mirrorStatus(): string { return JSON.stringify(ShellState.snapshot.mirror || {}); }
        function mirrorStart(source: string, target: string): bool {
            if (!ShellState.backendReady) return false;
            ShellState.run("mirrorStart", {source: source, target: target});
            return true;
        }
        function mirrorStop(): bool {
            if (!ShellState.backendReady) return false;
            ShellState.run("mirrorStop");
            return true;
        }
        function idleStatus(): string { return JSON.stringify(ShellState.snapshot.idle || {}); }
        function mediaStatus(): string {
            const player = ActivityState.player;
            return JSON.stringify({demo: ShellState.demo, player: player?.dbusName || "", playing: ActivityState.playing,
                positionSupported: player?.positionSupported ?? false, lengthSupported: player?.lengthSupported ?? false,
                position: player?.position ?? 0, duration: player?.lengthSupported ? player.length : 0,
                mediaWave: Theme.mediaWave, animations: Theme.animations});
        }
        function nightLightStatus(): string { return JSON.stringify(ShellState.snapshot.nightLight || {}); }
        function retryNightLight(): void { ShellState.run("nightLightRefresh"); }
        function capture(mode: string): void { ShellState.takeScreenshot(mode); }
        function refresh(): void { ShellState.run("refresh"); }
        function authenticationStatus(): string {
            return ShellState.demo ? "disabled in demo" : authentication.item && authentication.item.registered ? "registered" : "not registered; check the shell log and other session agents";
        }
    }
    Binding { target: ShellState; property: "overlayVisible"; value: overlay.visible }
    Variants {
        model: root.preview ? [] : Quickshell.screens
        delegate: Scope {
            id: screenScope
            required property var modelData
            PanelWindow {
                id: barWindow
                screen: screenScope.modelData
                anchors { top: !Theme.barBottom; bottom: Theme.barBottom; left: true; right: true }
                margins { left: Theme.barSideMargin; right: Theme.barSideMargin; top: Theme.barBottom ? 0 : Theme.barTopMargin; bottom: Theme.barBottom ? Theme.barTopMargin : 0 }
                implicitHeight: Theme.barHeight
                exclusiveZone: implicitHeight
                color: "transparent"
                WlrLayershell.namespace: "lme-bar"
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                BackgroundEffect.blurRegion: visible && ShellState.barBlurEnabled ? bar.blurRegion : null
                Bar { id: bar; anchors.fill: parent; screenInfo: screenScope.modelData; windowInfo: barWindow }
                IdleInhibitor { window: barWindow; enabled: ShellState.stayAwake && !ShellState.demo }
            }
        }
    }
    PanelWindow {
        id: liquidScrim
        screen: overlay.screen
        visible: overlay.visible && ShellState.liquidBlurEnabled
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.namespace: "lme-overlay"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        mask: Region { item: ShellState.panelOpen ? liquidScrim.contentItem : null }
        MouseArea { anchors.fill: parent; onClicked: ShellState.closePanels() }
    }
    PanelWindow {
        id: overlay
        screen: ShellState.panelScreen || Quickshell.screens[0]
        visible: !root.preview && (ShellState.panelOpen || activityIsland.visible || panelLoader.active) && !ShellState.authenticationActive
        // Non-xray blur captures the native surface; reserve the flight envelope, not the whole output.
        readonly property rect viewport: {
            const w = screen ? screen.width : 1920, h = screen ? screen.height : 1080;
            if (!ShellState.liquidBlurEnabled) return Qt.rect(0, 0, w, h);
            const frames = [];
            function reserve(x, y, width, height, edge) {
                const px = (edge < 2 ? width * .25 : 0) + 32;
                const py = (edge >= 2 ? height * .25 : 0) + 32;
                frames.push({left: edge === 0 ? 0 : x - px, right: edge === 1 ? w : x + width + px,
                    top: edge === 2 ? 0 : y - py, bottom: edge === 3 ? h : y + height + py});
            }
            if (activityIsland.mounted) {
                const width = activityIsland.expandedWidth, height = activityIsland.expandedHeight;
                const anchor = ShellState.activityAnchorX >= 0 ? ShellState.activityAnchorX : w / 2;
                const x = Math.max(activityIsland.sideInset, Math.min(w - width - activityIsland.sideInset, anchor - width / 2));
                reserve(x, Theme.barBottom ? h - activityIsland.edgeInset - height : activityIsland.edgeInset,
                    width, height, Theme.barBottom ? 3 : 2);
            }
            if (panelLoader.mounted) reserve(panelLoader.x, panelLoader.y, panelLoader.width, panelLoader.height, panelLoader.travelEdge);
            if (!frames.length) return Qt.rect(0, 0, w, h);
            const left = Math.max(0, Math.floor(Math.min(...frames.map(r => r.left))));
            const top = Math.max(0, Math.floor(Math.min(...frames.map(r => r.top))));
            return Qt.rect(left, top, Math.max(1, Math.min(w, Math.ceil(Math.max(...frames.map(r => r.right)))) - left),
                Math.max(1, Math.min(h, Math.ceil(Math.max(...frames.map(r => r.bottom)))) - top));
        }
        anchors { top: true; left: true }
        margins { top: viewport.y; left: viewport.x }
        implicitWidth: viewport.width
        implicitHeight: viewport.height
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "lme-overlay"
        BackgroundEffect.blurRegion: !visible ? null : ShellState.liquidBlurEnabled ? glassPopupBlur : ShellState.popupBlurEnabled ? popupBlurRegion : null
        Region { id: popupBlurRegion; item: overlay.contentItem }
        Region { id: glassPopupBlur; regions: [islandBlur, panelBlur, ...GlassState.popupsFor(overlay)] }
        SurfaceBlurRegion { id: islandBlur; surface: activityIsland.panel }
        SurfaceBlurRegion { id: panelBlur; surface: panelLoader.item as Item }
        // Closing visuals must not block another bar click or the application beneath.
        mask: Region { item: ShellState.panelOpen ? overlay.contentItem : null }
        WlrLayershell.keyboardFocus: ShellState.panelOpen ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
        PopupBackdrop { parent: ShellState.liquidBlurEnabled ? liquidScrim.contentItem : overlay.contentItem; anchors.fill: parent; shown: ShellState.panelOpen || ShellState.activityOpen; strength: FeatureCatalog.panel(ShellState.panelKind)?.scrim ?? (["launchpad", "launcher", "power", "overview"].includes(ShellState.panelKind) ? .40 : ShellState.panelKind === "tray" ? 0 : .13) }
        MouseArea { anchors.fill: parent; onClicked: ShellState.closePanels() }
        Item {
            x: -overlay.viewport.x
            y: -overlay.viewport.y
            width: overlay.screen ? overlay.screen.width : overlay.width
            height: overlay.screen ? overlay.screen.height : overlay.height
            focus: true
            Keys.onEscapePressed: ShellState.closePanels()
            ActivityIsland { id: activityIsland; z: 2 }
            SlideLoader {
                id: panelLoader
                exitToEdge: true
                readonly property bool centered: FeatureCatalog.panel(ShellState.panelKind)?.centered === true || ["launchpad", "launcher", "power", "overview"].includes(ShellState.panelKind)
                direction: centered ? "up" : ShellState.panelKind === "tray" ? Theme.barBottom ? "up" : "down" : "right"
                shown: ShellState.panelOpen && !ShellState.activityOpen
                content: FeatureCatalog.panel(ShellState.panelKind) ? FeatureCatalog.component(FeatureCatalog.panel(ShellState.panelKind).entry) : ShellState.panelKind === "launchpad" ? launchpadComponent : ShellState.panelKind === "launcher" ? launcherComponent : ShellState.panelKind === "control" ? controlComponent
                               : ShellState.panelKind === "wifi" ? wifiComponent : ShellState.panelKind === "settings" ? settingsComponent : ShellState.panelKind === "tray" ? trayComponent : ShellState.panelKind === "overview" ? overviewComponent : powerComponent
                width: item ? Math.min(item.implicitWidth, parent.width - 32) : 400
                height: item ? Math.min(item.implicitHeight, parent.height - Theme.panelTopMargin - 16) : 500
                x: centered ? (parent.width - width) / 2
                   : ShellState.panelKind === "tray" && ShellState.trayAnchorX >= 0 ? Math.max(14, Math.min(parent.width - width - 14, ShellState.trayAnchorX - width))
                   : parent.width - width - 14
                y: centered ? (parent.height - height) / 2 : Theme.barBottom ? parent.height - height - Theme.panelTopMargin : Theme.panelTopMargin
                MouseArea { anchors.fill: parent; z: -1; onClicked: mouse => mouse.accepted = true }
            }
        }
    }
    Component { id: launchpadComponent; LaunchpadPanel {} }
    Component { id: launcherComponent; Launcher {} }
    Component { id: controlComponent; ControlCenter {} }
    Component { id: settingsComponent; SettingsPanel {} }
    Component { id: powerComponent; PowerMenu {} }
    Component { id: trayComponent; TrayMenu { windowInfo: overlay } }
    Component { id: overviewComponent; Overview {} }
    Component { id: wifiComponent; WifiPanel {} }
    LazyLoader {
        active: !ShellState.demo && (ShellState.snapshot.capture || {}).status === "ready"
        component: FloatingWindow {
            id: captureWindow
            title: "LME Screenshot"; implicitWidth: 1180; implicitHeight: 860; minimumSize: Qt.size(850, 700)
            color: Theme.background
            onClosed: ShellState.run("captureClose")
            ScreenshotEditor {
                anchors.fill: parent
                session: ShellState.snapshot.capture || {}
                onCloseRequested: if (!busy) ShellState.run("captureClose")
            }
        }
    }
    Variants { model: root.preview ? [] : Quickshell.screens; delegate: OSDWindow { required property var modelData; screenInfo: modelData } }
    StatusWindow { preview: root.preview }
    LazyLoader {
        active: root.preview
        component: FloatingWindow {
            id: previewWindow
            implicitWidth: 1920; implicitHeight: 1080
            title: ShellState.shellName + " · Demo"
            fullscreen: root.screenshotPath !== ""
            color: Theme.background
            DesktopPreview { id: previewContent; anchors.fill: parent }
            Timer {
                interval: 1200; repeat: true; running: root.screenshotPath !== ""
                onTriggered: {
                    if (!ShellState.backendReady) return;
                    stop();
                    previewContent.grabToImage(result => {
                        if (!result.saveToFile(root.screenshotPath)) console.error("Screenshot could not be saved");
                        else console.log("Preview screenshot saved");
                        Qt.quit();
                    });
                }
            }
        }
    }
}
