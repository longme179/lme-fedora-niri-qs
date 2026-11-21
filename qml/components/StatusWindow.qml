// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: StatusWindow.qml (shared layer, fan-in 1).
// Shared component/helper; keep API stable for wide QML reuse.
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../services"
import "../theme"

PanelWindow {
    id: root
    property bool preview: false
    property string message: ""
    property bool error: false
    // Status popups follow statusToastPosition; "bar" tracks the bar side and
    // the default keeps the historical bottom-center placement.
    readonly property string position: {
        const value = ShellState.preferences.statusToastPosition
        return !value || value === "bar" ? (Theme.barBottom ? "bottom-center" : "top-center") : value
    }
    readonly property real edgeMargin: 24
    readonly property real barMargin: Theme.panelTopMargin + Math.max(0, edgeMargin - 14)
    readonly property bool statusToasts: ShellState.preferences.statusToasts !== false
    readonly property bool shown: !preview && statusToasts && !ShellState.authenticationActive && !!ShellState.statusMessage
    screen: ShellState.panelScreen || Quickshell.screens[0]
    visible: transition.mounted
    anchors { top: position.startsWith("top"); bottom: position.startsWith("bottom"); left: position.endsWith("left"); right: position.endsWith("right") }
    margins { top: Theme.barBottom ? edgeMargin : barMargin; bottom: Theme.barBottom ? barMargin : edgeMargin; left: edgeMargin; right: edgeMargin }
    implicitWidth: Math.min(Theme.notificationWidth, Math.max(160, (screen?.width || 1920) - 28))
    implicitHeight: transition.item ? (transition.item as Item).implicitHeight : 0
    color: "transparent"; exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay; WlrLayershell.namespace: "lme-osd"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    BackgroundEffect.blurRegion: visible && ShellState.liquidBlurEnabled ? glassBlur : null
    SurfaceBlurRegion { id: glassBlur; surface: transition.item as Item }
    mask: Region { item: root.shown ? root.contentItem : null }
    function retain() { if (ShellState.statusMessage) { message = ShellState.statusMessage; error = ShellState.statusError; } }
    Component.onCompleted: retain()
    Connections {
        target: ShellState
        function onStatusMessageChanged() { root.retain(); }
        function onStatusErrorChanged() { root.retain(); }
    }
    Item {
        width: root.implicitWidth; height: root.implicitHeight
        SlideLoader {
                id: transition; anchors.fill: parent; shown: root.shown
                exitToEdge: true; exitEdge: root.position.endsWith("left") ? "left" : root.position.endsWith("right") ? "right" : root.position.startsWith("top") ? "top" : "bottom"
                content: NotificationCard {
                    entry: ({appName: root.error ? "Action failed" : ShellState.shellName, summary: root.message, body: "", urgency: root.error ? 2 : 1, actions: []})
                    maximumHeight: Math.max(160, (root.screen?.height || 1080) * .6)
                    animateIdle: root.shown
                    onDismissRequested: ShellState.statusMessage = ""
                }
        }
    }
}
