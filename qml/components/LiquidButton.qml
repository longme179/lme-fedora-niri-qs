import QtQuick
import QtQuick.Controls
import "../theme"

Button {
    id: root
    implicitWidth: Math.max(36, contentItem.implicitWidth + leftPadding + rightPadding)
    implicitHeight: 36
    leftPadding: 12
    rightPadding: 12
    topPadding: 7
    bottomPadding: 7
    hoverEnabled: true
    opacity: enabled ? 1 : 0.35
    palette.button: Theme.surface
    palette.buttonText: Theme.text
    font.family: Theme.fontFamily
    font.pixelSize: 12
    Accessible.name: text
    background: Rectangle {
        radius: Theme.smallRadius
        color: root.checked ? Theme.alpha(Theme.accent, 0.23) : root.down ? Qt.lighter(root.palette.button, 1.18) : root.hovered ? Qt.lighter(root.palette.button, 1.12) : root.palette.button
        border.width: root.visualFocus ? 2 : root.checked ? 1 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
    }
    contentItem: Text {
        text: root.text
        textFormat: Text.PlainText
        color: root.palette.buttonText
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
