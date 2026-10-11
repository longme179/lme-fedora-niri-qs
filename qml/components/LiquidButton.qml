import QtQuick
import QtQuick.Controls
import "../theme"

Button {
    id: root
    property bool selected: checked
    readonly property Rectangle plate: background as Rectangle
    readonly property bool semanticFill: !Qt.colorEqual(palette.button, Theme.buttonFill)
    implicitWidth: Math.max(36, contentItem.implicitWidth + leftPadding + rightPadding)
    implicitHeight: 40
    leftPadding: 16
    rightPadding: 16
    topPadding: 7
    bottomPadding: 7
    hoverEnabled: true
    opacity: enabled ? 1 : 0.35
    palette.button: Theme.buttonFill
    palette.buttonText: Theme.buttonText
    font.family: Theme.buttonFamily
    font.pixelSize: Theme.bodySize - 1
    font.weight: Font.Medium
    Accessible.name: text
    scale: !Theme.animations ? 1 : down ? .98 - Theme.deformation * .3 : hovered ? 1.012 + Theme.deformation * .2 : 1
    Behavior on scale { MotionAnimation {} }
    background: Rectangle {
        radius: root.down ? 12 : root.hovered && Theme.animations ? Math.max(14, height / 2 - 4) : height / 2
        color: root.selected ? Theme.buttonSelected
            : root.down ? root.semanticFill ? Qt.lighter(root.palette.button, 1.14) : Theme.buttonPressed
            : root.hovered ? root.semanticFill ? Qt.lighter(root.palette.button, 1.08) : Theme.buttonHover
            : root.palette.button
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
        Behavior on radius { MotionAnimation {} }
    }
    LiquidFeedback { objectName: "liquidFeedback"; z: -.5; hovered: root.hovered; pressed: root.down; radius: root.plate ? root.plate.radius : root.height / 2 }
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
