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
    implicitWidth: 36
    implicitHeight: 36
    padding: 0
    hoverEnabled: true
    Accessible.name: tooltip || text || glyph
    Accessible.role: Accessible.Button
    z: hovered || down ? 1 : 0
    scale: !Theme.animations ? 1 : down ? .96 - Theme.deformation * .3 : hovered ? 1.045 + Theme.deformation * .2 : 1
    Behavior on scale { MotionAnimation {} }
    opacity: enabled ? 1 : 0.4
    background: Rectangle {
        radius: root.down ? Math.max(8, root.cornerRadius - 6) : root.hovered && Theme.animations ? Math.max(10, root.cornerRadius - 3) : root.cornerRadius
        property color stateFill: root.active ? Theme.primaryContainer
                           : root.hovered ? Theme.iconHover : Theme.alpha(Theme.iconHover, 0)
        color: Theme.shapeMorph ? "transparent" : stateFill
        MorphShape { anchors.fill: parent; visible: Theme.shapeMorph; shape: root.down && Theme.animations ? "flower" : root.hovered && Theme.animations ? "square" : "circle"; color: parent.stateFill; strokeColor: root.visualFocus ? Theme.accent : "transparent"; strokeWidth: root.visualFocus ? 2 : 0 }
        border.width: root.visualFocus && !Theme.shapeMorph ? 2 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
        Behavior on radius { MotionAnimation {} }
    }
    LiquidFeedback { z: -.5; hovered: root.hovered; pressed: root.down; originX: root.pressX || root.width/2; originY: root.pressY || root.height/2; radius: root.plate ? root.plate.radius : root.cornerRadius }
    contentItem: Item {
        ShellIcon {
            anchors.centerIn: parent
            width: root.iconSize; height: root.iconSize
            visible: root.iconName.length > 0
            name: root.iconName
            property color stateFill: root.active ? root.accentColor : Theme.iconColor
        }
        LabelText {
            anchors.fill: parent
            visible: root.iconName.length === 0
            text: root.glyph || root.text
            property color stateFill: root.active ? root.accentColor : Theme.iconColor
            font.pixelSize: root.glyphSize
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }
    ToolTip.visible: hovered && tooltip.length > 0
    ToolTip.text: tooltip
    ToolTip.delay: 550
}
