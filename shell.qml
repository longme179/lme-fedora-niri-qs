//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env QS_NO_RELOAD_POPUP=1
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
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
        function close(): void { ShellState.closePanels(); }
        function idleStatus(): string { return JSON.stringify(ShellState.snapshot.idle || {}); }
        function nightLightStatus(): string { return JSON.stringify(ShellState.snapshot.nightLight || {}); }
        function retryNightLight(): void { ShellState.run("nightLightRefresh"); }
        function capture(mode: string): void { ShellState.takeScreenshot(mode); }
        function refresh(): void { ShellState.run("refresh"); }
        function authenticationStatus(): string {
            return ShellState.demo ? "disabled in demo" : authentication.item && authentication.item.registered ? "registered" : "not registered; check the shell log and other session agents";
        }
    }
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
                Bar { anchors.fill: parent; screenInfo: screenScope.modelData; windowInfo: barWindow }
                IdleInhibitor { window: barWindow; enabled: ShellState.stayAwake && !ShellState.demo }
            }
        }
    }
    PanelWindow {
        id: overlay
        screen: ShellState.panelScreen || Quickshell.screens[0]
        visible: !root.preview && (ShellState.panelOpen || activityIsland.visible || panelLoader.active) && !ShellState.authenticationActive
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "lme-overlay"
        BackgroundEffect.blurRegion: visible && ShellState.popupBlurEnabled ? popupBlurRegion : null
        Region { id: popupBlurRegion; item: overlay.contentItem }
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
        Rectangle { anchors.fill: parent; color: Theme.alpha(Theme.background, ShellState.trayOpen ? 0 : ShellState.launcherOpen || ShellState.powerOpen || ShellState.overviewOpen || ShellState.clipboardOpen ? 0.40 : 0.13) }
        MouseArea { anchors.fill: parent; onClicked: ShellState.closePanels() }
        Item {
            anchors.fill: parent
            focus: true
            Keys.onEscapePressed: ShellState.closePanels()
            ActivityIsland { id: activityIsland; z: 2 }
            SlideLoader {
                id: panelLoader
                readonly property bool centered: ["launcher", "power", "overview", "clipboard"].includes(ShellState.panelKind)
                direction: centered ? "up" : ShellState.panelKind === "tray" ? Theme.barBottom ? "up" : "down" : "right"
                shown: ShellState.panelOpen && !ShellState.activityOpen
                content: ShellState.panelKind === "launcher" ? launcherComponent : ShellState.panelKind === "control" ? controlComponent
                               : ShellState.panelKind === "notifications" ? notificationsComponent : ShellState.panelKind === "wifi" ? wifiComponent : ShellState.panelKind === "settings" ? settingsComponent : ShellState.panelKind === "tray" ? trayComponent : ShellState.panelKind === "overview" ? overviewComponent : ShellState.panelKind === "clipboard" ? clipboardComponent : powerComponent
                width: item ? Math.min(item.implicitWidth, overlay.width - 32) : 400
                height: item ? Math.min(item.implicitHeight, overlay.height - Theme.panelTopMargin - 16) : 500
                x: centered ? (overlay.width - width) / 2
                   : ShellState.panelKind === "tray" && ShellState.trayAnchorX >= 0 ? Math.max(14, Math.min(overlay.width - width - 14, ShellState.trayAnchorX - width))
                   : overlay.width - width - 14
                y: centered ? (overlay.height - height) / 2 : Theme.barBottom ? overlay.height - height - Theme.panelTopMargin : Theme.panelTopMargin
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
    PanelWindow {
        screen: ShellState.panelScreen || Quickshell.screens[0]
        visible: !root.preview && Notifications.popups.length > 0 && !ShellState.notificationsOpen && !ShellState.authenticationActive
        anchors { top: !Theme.barBottom; bottom: Theme.barBottom; right: true }
        margins { top: Theme.barBottom ? 0 : Theme.panelTopMargin; bottom: Theme.barBottom ? Theme.panelTopMargin : 0; right: 14 }
        implicitWidth: 360
        implicitHeight: toastColumn.implicitHeight
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "lme-notifications"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        Column {
            id: toastColumn
            width: parent.width; spacing: 10
            Repeater {
                model: Notifications.popups
                delegate: GlassPanel {
                    id: toastCard
                    role: "notificationFill"
                    required property var modelData
                    width: toastColumn.width
                    height: toastContent.implicitHeight + 32
                    ColumnLayout {
                        id: toastContent
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
                        spacing: 8
                        RowLayout {
                            LabelText { text: toastCard.modelData.appName; color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                            IconButton { glyph: "×"; tooltip: "Dismiss notification"; implicitWidth: 24; implicitHeight: 24; onClicked: Notifications.dismiss(toastCard.modelData.id) }
                        }
                        LabelText { text: toastCard.modelData.summary; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        LabelText { text: toastCard.modelData.body; visible: text.length > 0; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight }
                        RowLayout {
                            Repeater {
                                model: toastCard.modelData.actions || []
                                delegate: IconButton { required property var modelData; text: modelData.text; implicitWidth: Math.min(145, Math.max(80, text.length * 8)); onClicked: Notifications.invokeAction(toastCard.modelData.id, modelData.identifier) }
                            }
                        }
                    }
                }
            }
        }
    }
    PanelWindow {
        screen: ShellState.panelScreen || Quickshell.screens[0]
        visible: !root.preview && !ShellState.authenticationActive && (ShellState.osdOpen || ShellState.statusMessage.length > 0)
        anchors.bottom: true
        margins.bottom: 24
        implicitWidth: ShellState.statusMessage.length > 0 ? 460 : 240
        implicitHeight: ShellState.statusMessage.length > 0 ? 76 : 64
        color: "transparent"; exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "lme-osd"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        GlassPanel {
            anchors.fill: parent
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 16; spacing: 9
                LabelText {
                    text: ShellState.statusMessage || ShellState.osdLabel + "  " + Math.round(ShellState.osdValue) + "%"
                    color: ShellState.statusError && ShellState.statusMessage ? Theme.red : Theme.text
                    Layout.fillWidth: true; wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                }
                Rectangle {
                    visible: !ShellState.statusMessage
                    Layout.fillWidth: true; Layout.preferredHeight: 4; radius: 2; color: Theme.surface
                    Rectangle { width: parent.width * Math.max(0, Math.min(100, ShellState.osdValue)) / 100; height: parent.height; radius: 2; color: Theme.accent }
                }
            }
        }
    }
    LazyLoader {
        active: root.preview
        component: FloatingWindow {
            id: previewWindow
            implicitWidth: 1920; implicitHeight: 1080
            title: "LME Shell · Demo"
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
