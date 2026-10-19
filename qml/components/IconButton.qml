import QtQuick
import QtQuick.Controls
import "../theme"

AbstractButton {
    id: root
    property string glyph: ""
    property string iconName: ""
    property int iconSize: 18
    property int glyphSize: 17
    property real cornerRadius: height / 2
    property string tooltip: text
    property bool active: false
    readonly property Rectangle plate: background as Rectangle
    property color accentColor: Theme.accent
    readonly property color foreground: active ? Theme.contrastingText(Theme.primaryContainer, accentColor) : Theme.iconColor
    implicitWidth: 36
    implicitHeight: 36
    padding: 0
    hoverEnabled: true
    Accessible.name: tooltip || text || glyph
    Accessible.role: Accessible.Button
    z: hovered || down ? 1 : 0
    readonly property real scaleTarget: !Theme.animations ? 1 : down ? .96 - Theme.deformation * .3 : hovered ? 1.045 + Theme.deformation * .2 : 1
    readonly property real radiusTarget: down ? Math.max(8, cornerRadius - 6) : hovered && Theme.animations ? Math.max(10, cornerRadius - 3) : cornerRadius
    MotionValue { id: scaleMotion; target: root.scaleTarget; positionEpsilon: .0002; velocityEpsilon: .005 }
    MotionValue { id: radiusMotion; target: root.radiusTarget }
    scale: Theme.springMotion ? scaleMotion.value : scaleTarget
    Behavior on scale { enabled: !Theme.springMotion && Theme.animations; MotionAnimation {} }
    opacity: enabled ? 1 : 0.4
    background: Rectangle {
        radius: Theme.springMotion ? radiusMotion.value : root.radiusTarget
        property color stateFill: root.active ? Theme.primaryContainer
                           : root.hovered ? Theme.iconHover : Theme.alpha(Theme.iconHover, 0)
        Behavior on stateFill { enabled: !Theme.shapeMorph; ColorMotion {} }
        color: Theme.shapeMorph ? "transparent" : stateFill
        MorphShape { anchors.fill: parent; visible: Theme.shapeMorph; shape: root.down && Theme.animations ? "flower" : root.hovered && Theme.animations ? "square" : "circle"; color: parent.stateFill; strokeColor: root.visualFocus ? Theme.accent : "transparent"; strokeWidth: root.visualFocus ? 2 : 0 }
        border.width: root.visualFocus && !Theme.shapeMorph ? 2 : 0
        border.color: Theme.accent
        Behavior on radius { enabled: !Theme.springMotion && Theme.animations; MotionAnimation {} }
    }
    LiquidFeedback { z: -.5; hovered: root.hovered; pressed: root.down; originX: root.pressX; originY: root.pressY; radius: root.plate ? root.plate.radius : root.cornerRadius }
    contentItem: Item {
        ShellIcon {
            anchors.centerIn: parent
            width: root.iconSize; height: root.iconSize
            visible: root.iconName.length > 0
            name: root.iconName
            color: root.foreground
            Behavior on color { ColorMotion {} }
        }
        LabelText {
            anchors.fill: parent
            visible: root.iconName.length === 0
            text: root.glyph || root.text
            glassText: !root.active
            color: root.foreground
            Behavior on color { ColorMotion {} }
            font.pixelSize: root.glyphSize
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }
    ToolTip.visible: hovered && tooltip.length > 0
    ToolTip.text: tooltip
    ToolTip.delay: 550
}
