// SPDX-License-Identifier: GPL-3.0-or-later
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
    readonly property bool shown: !preview && !ShellState.authenticationActive && !!ShellState.statusMessage
    screen: ShellState.panelScreen || Quickshell.screens[0]
    visible: transition.mounted
    anchors.bottom: true; margins.bottom: 24
    implicitWidth: Math.min(Theme.notificationWidth, Math.max(160, (screen?.width || 1920) - 28))
    implicitHeight: transition.item ? (transition.item as Item).implicitHeight : 0
    color: "transparent"; exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay; WlrLayershell.namespace: "lme-osd"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
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
                exitToEdge: true; exitEdge: "bottom"
                content: NotificationCard {
                    entry: ({appName: root.error ? "Action failed" : "LME Shell", summary: root.message, body: "", urgency: root.error ? 2 : 1, actions: []})
                    maximumHeight: Math.max(160, (root.screen?.height || 1080) * .6)
                    animateIdle: root.shown
                    onDismissRequested: ShellState.statusMessage = ""
                }
        }
    }
}
