import QtQuick
import QtQuick.Controls
import "../theme"

Slider {
    id: root
    implicitHeight: 28
    implicitWidth: 180
    leftPadding: 7
    rightPadding: 7
    hoverEnabled: true
    opacity: enabled ? 1 : 0.35
    palette.highlight: Theme.accent
    background: Rectangle {
        x: root.leftPadding
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth
        height: 4
        radius: 2
        color: Theme.alpha(Theme.border, 0.7)
        Rectangle {
            width: root.visualPosition * parent.width
            height: parent.height
            radius: 2
            color: root.palette.highlight
        }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.pressed ? 17 : 14
        height: width
        radius: width / 2
        color: root.palette.highlight
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.text
        Behavior on width { NumberAnimation { duration: Theme.animationDuration } }
    }
}
