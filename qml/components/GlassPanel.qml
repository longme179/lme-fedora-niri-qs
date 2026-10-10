import QtQuick
import "../theme"

Rectangle {
    id: root
    radius: Theme.radius
    color: Theme.alpha(Theme.panel, Theme.panelOpacity)
    border.width: 1
    border.color: Theme.alpha(Theme.border, 0.65)
    gradient: Gradient {
        GradientStop { position: 0; color: Theme.alpha(Qt.lighter(Theme.panel, 1.28), Theme.panelOpacity) }
        GradientStop { position: 0.46; color: Theme.alpha(Theme.panel, Theme.panelOpacity) }
        GradientStop { position: 1; color: Theme.alpha(Qt.darker(Theme.panel, 1.13), Theme.panelOpacity) }
    }
    Rectangle {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.max(0, parent.width - parent.radius * 2)
        height: 1
        color: Theme.alpha(Theme.text, 0.14)
    }
}
