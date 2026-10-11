import QtQuick
import QtQuick.Controls
import "../theme"

TextField {
    id: root
    implicitHeight: 48
    leftPadding: 16; rightPadding: 16
    color: Theme.fieldText
    placeholderTextColor: Theme.muted
    selectionColor: Theme.accent
    selectedTextColor: Theme.onPrimary
    font.family: Theme.buttonFamily
    font.pixelSize: Theme.bodySize
    selectByMouse: true
    background: Rectangle {
        radius: root.activeFocus && Theme.animations ? 12 : Theme.smallRadius
        color: Theme.fieldFill
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? Theme.accent : Theme.outlineVariant
        Behavior on radius { MotionAnimation {} }
        Behavior on border.color { ColorAnimation { duration: Theme.animationDuration } }
    }
}
