import QtQuick
import QtQuick.Controls
import "../theme"

AbstractButton {
    id: root
    property string glyph: ""
    property string tooltip: text
    property bool active: false
    property color accentColor: Theme.accent
    implicitWidth: 36
    implicitHeight: 36
    hoverEnabled: true
    Accessible.name: tooltip || text || glyph
    Accessible.role: Accessible.Button
    opacity: enabled ? 1 : 0.4
    background: Rectangle {
        radius: Theme.smallRadius
        color: root.active ? Theme.alpha(root.accentColor, 0.20)
                           : root.hovered ? Theme.alpha(Theme.text, 0.09) : "transparent"
        border.width: root.visualFocus ? 2 : root.active ? 1 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
    }
    contentItem: LabelText {
        text: root.glyph || root.text
        color: root.active ? root.accentColor : Theme.text
        font.pixelSize: 17
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    ToolTip.visible: hovered && tooltip.length > 0
    ToolTip.text: tooltip
    ToolTip.delay: 550
}
