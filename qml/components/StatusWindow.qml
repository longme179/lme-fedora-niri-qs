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
    implicitWidth: 460; implicitHeight: 76
    color: "transparent"; exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay; WlrLayershell.namespace: "lme-osd"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region {}
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
                content: GlassPanel {
                    anchors.fill: parent
                    LabelText {
                        anchors.fill: parent; anchors.margins: 16
                        text: root.message; color: root.error ? Theme.red : Theme.text
                        wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    }
                }
        }
    }
}
