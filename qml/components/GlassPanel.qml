import QtQuick
import "../theme"

Rectangle {
    id: root
    property bool connectedSurface: false
    property string role: "panelFill"
    radius: Theme.radius
    color: connectedSurface ? "transparent" : Theme.alpha(Theme.tokenColor(role), Theme.panelOpacity)
    border.width: connectedSurface ? 0 : 1
    border.color: Theme.outlineVariant
    Rectangle {
        visible: !root.connectedSurface
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(0, parent.width - parent.radius * 2)
        height: 1
        color: Theme.alpha(Theme.text, 0.14)
    }
}
