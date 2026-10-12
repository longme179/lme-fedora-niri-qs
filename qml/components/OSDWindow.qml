pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../services"
import "../theme"
PanelWindow {
    id: root
    required property var screenInfo
    readonly property var entry: OSDManager.entries[screenInfo.name] || null
    readonly property string position: ShellState.preferences.osdPosition || "bottom-center"
    readonly property bool vertical: ShellState.preferences.osdLayout === "vertical"
    property bool open: false
    screen: screenInfo
    visible: transition.mounted && !ShellState.authenticationActive && ShellState.preferences.osdEnabled !== false
    onEntryChanged: if(entry) { open=true; timeout.restart(); }
    anchors.top: position.startsWith("top")
    anchors.bottom: position.startsWith("bottom")
    anchors.left: position.endsWith("left")
    anchors.right: position.endsWith("right")
    margins { top: (ShellState.preferences.osdMargin ?? 24); bottom: (ShellState.preferences.osdMargin ?? 24); left: (ShellState.preferences.osdMargin ?? 24); right: (ShellState.preferences.osdMargin ?? 24) }
    implicitWidth: vertical ? 90 : 280; implicitHeight: vertical ? 240 : 86
    color: "transparent"; exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay; WlrLayershell.namespace: "lme-osd"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    Timer { id: timeout; interval: 1600; onTriggered: root.open=false }
    SlideLoader {
        id: transition; anchors.fill: parent; shown: root.open; direction: root.position.endsWith("right") ? "right" : root.position.startsWith("top") ? "down" : "up"
        exitToEdge: true
        exitEdge: root.position.endsWith("left") ? "left" : root.position.endsWith("right") ? "right" : root.position.startsWith("top") ? "top" : "bottom"
        content: GlassPanel {
            anchors.fill: parent; radius: 28
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 16; spacing: 10
                LabelText { text: root.entry ? root.entry.label : ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; font.weight: Font.Bold; font.pixelSize: 13 }
                Item {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    Rectangle {
                        anchors.centerIn: parent; width: root.vertical ? 8 : parent.width; height: root.vertical ? parent.height : 8
                        color: Theme.sliderTrack; radius: 4
                        Rectangle {
                            readonly property real level: Math.max(0,Math.min(100,root.entry ? root.entry.value : 0))/100
                            width: root.vertical ? parent.width : parent.width*level; height: root.vertical ? parent.height*level : parent.height
                            anchors.bottom: parent.bottom; radius: 4; color: Theme.sliderFill
                            Behavior on width { MotionAnimation {} } Behavior on height { MotionAnimation {} }
                        }
                    }
                }
                LabelText { visible: root.vertical; text: root.entry ? Math.round(root.entry.value)+"%" : ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; color: Theme.accent }
            }
            HoverHandler { onHoveredChanged: { if(hovered) timeout.stop(); else if(root.open) timeout.restart(); } }
        }
    }
}
