import QtQuick
import Quickshell
import Quickshell.Wayland
import "../services"

Scope {
    id: root
    required property var screenInfo
    property bool revealed: false
    readonly property bool shown: ShellState.preferences.dockAutoHide === false || revealed || ShellState.panelOpen
    Timer { id: hideTimer; interval: 600; onTriggered: root.revealed = false }
    PanelWindow {
        screen: root.screenInfo
        anchors.bottom: true
        implicitWidth: dock.implicitWidth + 20
        implicitHeight: 6
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "lme-dock-reveal"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onEntered: { hideTimer.stop(); root.revealed = true; }
            onExited: hideTimer.restart()
        }
    }
    PanelWindow {
        id: window
        screen: root.screenInfo
        anchors.bottom: true
        margins.bottom: 10
        implicitWidth: dock.implicitWidth
        implicitHeight: dock.implicitHeight
        visible: root.shown
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "lme-dock"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        Dock { id: dock; anchors.fill: parent }
        HoverHandler {
            onHoveredChanged: {
                if (hovered) { hideTimer.stop(); root.revealed = true; }
                else hideTimer.restart();
            }
        }
    }
}
