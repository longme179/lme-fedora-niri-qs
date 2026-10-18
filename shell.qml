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
    Component.onCompleted: ClipboardState.start()
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
    LazyLoader { active: !root.preview; component: DesktopCanvas {} }
    PanelWindow {
        id: overlay
        screen: ShellState.panelScreen || Quickshell.screens[0]
        visible: !root.preview && (ShellState.panelOpen || activityIsland.visible || panelLoader.active) && !ShellState.authenticationActive
        anchors { top: true; bottom: true; left: true; right: true }
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
        PopupBackdrop { anchors.fill: parent; shown: ShellState.panelOpen || ShellState.activityOpen; strength: ["launcher", "power", "overview", "clipboard"].includes(ShellState.panelKind) ? .40 : ShellState.panelKind === "tray" ? 0 : .13 }
        MouseArea { anchors.fill: parent; onClicked: ShellState.closePanels() }
        Item {
            width: overlay.screen ? overlay.screen.width : overlay.width
            height: overlay.screen ? overlay.screen.height : overlay.height
            focus: true
            Keys.onEscapePressed: ShellState.closePanels()
            ActivityIsland { id: activityIsland; z: 2 }
            SlideLoader {
                id: panelLoader
                exitToEdge: true
                readonly property bool centered: ["launcher", "power", "overview", "clipboard"].includes(ShellState.panelKind)
                direction: centered ? "up" : ShellState.panelKind === "tray" ? Theme.barBottom ? "up" : "down" : "right"
                shown: ShellState.panelOpen && !ShellState.activityOpen
                content: ShellState.panelKind === "launcher" ? launcherComponent : ShellState.panelKind === "control" ? controlComponent
                               : ShellState.panelKind === "notifications" ? notificationsComponent : ShellState.panelKind === "wifi" ? wifiComponent : ShellState.panelKind === "settings" ? settingsComponent : ShellState.panelKind === "tray" ? trayComponent : ShellState.panelKind === "overview" ? overviewComponent : ShellState.panelKind === "clipboard" ? clipboardComponent : powerComponent
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
    Component { id: launcherComponent; Launcher {} }
    Component { id: controlComponent; ControlCenter {} }
    Component { id: notificationsComponent; NotificationCenter {} }
    Component { id: settingsComponent; SettingsPanel {} }
    Component { id: powerComponent; PowerMenu {} }
    Component { id: trayComponent; TrayMenu { windowInfo: overlay } }
    Component { id: overviewComponent; Overview {} }
    Component { id: clipboardComponent; ClipboardPanel {} }
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
    NotificationToasts { preview: root.preview }
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
