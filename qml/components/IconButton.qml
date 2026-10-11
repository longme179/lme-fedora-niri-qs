import QtQuick
import QtQuick.Controls
import "../theme"

AbstractButton {
    id: root
    property string glyph: ""
    property string iconName: ""
    property int iconSize: 18
    property int glyphSize: 17
    property real cornerRadius: height / 2
    property string tooltip: text
    property bool active: false
    property color accentColor: Theme.accent
    implicitWidth: 36
    implicitHeight: 36
    padding: 0
    hoverEnabled: true
    Accessible.name: tooltip || text || glyph
    Accessible.role: Accessible.Button
    scale: down ? 1 - Theme.deformation : 1
    Behavior on scale { MotionAnimation {} }
    opacity: enabled ? 1 : 0.4
    background: Rectangle {
        radius: root.cornerRadius
        color: root.active ? Theme.primaryContainer
                           : root.hovered ? Theme.alpha(Theme.text, 0.09) : "transparent"
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
    }
    contentItem: Item {
        ShellIcon {
            anchors.centerIn: parent
            width: root.iconSize; height: root.iconSize
            visible: root.iconName.length > 0
            name: root.iconName
            color: root.active ? root.accentColor : Theme.text
        }
        LabelText {
            anchors.fill: parent
            visible: root.iconName.length === 0
            text: root.glyph || root.text
            color: root.active ? root.accentColor : Theme.text
            font.pixelSize: root.glyphSize
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }
    ToolTip.visible: hovered && tooltip.length > 0
    ToolTip.text: tooltip
    ToolTip.delay: 550
}
