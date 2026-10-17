import QtQuick
import "../theme"

Rectangle {
    id: root
    property string role: "panelFill"
    radius: Theme.radius
    color: Theme.alpha(Theme.tokenColor(role), Theme.panelOpacity)
    border.width: 1
    border.color: Theme.outlineVariant
    Rectangle {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(0, parent.width - parent.radius * 2)
        height: 1
        color: Theme.alpha(Theme.text, 0.14)
    }
}
