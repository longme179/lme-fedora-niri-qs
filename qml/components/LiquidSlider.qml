import QtQuick
import QtQuick.Controls
import "../theme"

Slider {
    id: root
    implicitHeight: 36
    implicitWidth: 180
    leftPadding: 7
    rightPadding: 7
    hoverEnabled: true
    opacity: enabled ? 1 : 0.35
    palette.highlight: Theme.sliderFill
    background: Rectangle {
        x: root.leftPadding
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth
        height: 10
        radius: 5
        color: Theme.sliderTrack
        Rectangle {
            width: root.visualPosition * parent.width
            height: parent.height
            radius: 5
            color: root.palette.highlight
        }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.pressed ? 4 : 6
        height: root.hovered && Theme.animations ? 32 : 28
        radius: 3
        color: root.palette.highlight
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.text
        Behavior on width { MotionAnimation {} }
        Behavior on height { MotionAnimation {} }
    }
}
