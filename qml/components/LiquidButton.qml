import QtQuick
import QtQuick.Controls
import "../theme"

Button {
    id: root
    property bool selected: checked
    property bool selectionFill: true
    property real cornerRadius: height / 2
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
    // Keep wide rows inside their scroll gutters; animate above neighbouring plates.
    z: hovered || down ? 1 : 0
    readonly property real scaleTarget: !Theme.animations || flat ? 1 : down ? .98 - Theme.deformation * .3 : hovered ? 1 + Math.min(.012 + Theme.deformation * .2, 4 / Math.max(1, width, height)) : 1
    readonly property real radiusTarget: flat ? cornerRadius : down ? Math.min(cornerRadius, 12) : hovered && Theme.animations ? Math.min(cornerRadius, Math.max(14, height / 2 - 4)) : cornerRadius
    MotionValue { id: scaleMotion; target: root.scaleTarget; positionEpsilon: .0002; velocityEpsilon: .005 }
    MotionValue { id: radiusMotion; target: root.radiusTarget }
    scale: Theme.springMotion ? scaleMotion.value : scaleTarget
    Behavior on scale { enabled: !Theme.springMotion && Theme.animations; MotionAnimation {} }
    background: Rectangle {
        radius: Theme.springMotion ? radiusMotion.value : root.radiusTarget
        color: root.selected ? (root.selectionFill ? Theme.buttonSelected : "transparent")
            : root.down ? root.semanticFill ? Qt.lighter(root.palette.button, 1.14) : Theme.buttonPressed
            : root.hovered ? root.semanticFill ? Qt.lighter(root.palette.button, 1.08) : Theme.buttonHover
            : root.palette.button
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
        Behavior on color { ColorMotion {} }
        Behavior on radius { enabled: !Theme.springMotion && Theme.animations; MotionAnimation {} }
        GlassMaterial { anchors.fill: parent; radius: parent.radius; hovered: root.hovered; pressed: root.down; visible: !root.flat }
    }
    LiquidFeedback { objectName: "liquidFeedback"; z: -.5; hovered: root.hovered; pressed: root.down; originX: root.pressX; originY: root.pressY; radius: root.plate ? root.plate.radius : root.cornerRadius }
    contentItem: ShellText {
        text: root.text
        textFormat: Text.PlainText
        color: root.palette.buttonText
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
