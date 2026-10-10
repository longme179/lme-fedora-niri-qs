import QtQuick
import QtQuick.Controls
import "../theme"

TextField {
    id: root
    implicitHeight: 48
    leftPadding: 16; rightPadding: 16
    color: Theme.text
    placeholderTextColor: Theme.muted
    selectionColor: Theme.accent
    selectedTextColor: Theme.onPrimary
    font.family: Theme.fontFamily
    font.pixelSize: Theme.bodySize
    selectByMouse: true
    background: Rectangle {
        radius: Theme.smallRadius
        color: Theme.surfaceContainerHigh
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? Theme.accent : Theme.outlineVariant
    }
}
