import QtQuick
import QtQuick.Controls
import "../theme"

Button {
    id: root
    property bool selected: checked
    implicitWidth: Math.max(36, contentItem.implicitWidth + leftPadding + rightPadding)
    implicitHeight: 40
    leftPadding: 16
    rightPadding: 16
    topPadding: 7
    bottomPadding: 7
    hoverEnabled: true
    opacity: enabled ? 1 : 0.35
    palette.button: Theme.surfaceContainerHigh
    palette.buttonText: Theme.text
    font.family: Theme.fontFamily
    font.pixelSize: 13
    font.weight: Font.Medium
    Accessible.name: text
    background: Rectangle {
        radius: root.down ? 12 : height / 2
        color: root.selected ? Theme.primaryContainer : root.down ? Theme.mix(root.palette.button, Theme.text, 0.14) : root.hovered ? Theme.mix(root.palette.button, Theme.text, 0.08) : root.palette.button
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
        Behavior on radius { NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic } }
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
