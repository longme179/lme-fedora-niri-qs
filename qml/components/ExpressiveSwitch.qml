import QtQuick
import QtQuick.Controls
import "../theme"

Switch {
    id: root
    implicitWidth: 58
    implicitHeight: 40
    padding: 2
    hoverEnabled: true
    indicator: Rectangle {
        x: root.leftPadding; y: (root.height - height) / 2
        width: 54; height: 32; radius: 16
        color: root.checked ? Theme.switchTrack : Theme.surfaceContainerHigh
        border.width: root.checked ? 0 : 2
        border.color: root.visualFocus ? Theme.text : Theme.muted
        opacity: root.enabled ? 1 : 0.4
        LiquidFeedback { hovered: root.hovered; pressed: root.down; radius: 16 }
        Rectangle {
            width: root.checked || root.down ? 24 : 16; height: width; radius: width / 2
            x: root.checked ? parent.width - width - 4 : 8
            y: (parent.height - height) / 2
            color: root.checked ? Theme.switchThumb : Theme.muted
            Text { anchors.centerIn: parent; text: "✓"; visible: root.checked; color: Theme.accent; font.pixelSize: 15; font.family: Theme.fontFamily; font.bold: true }
            Behavior on x { MotionAnimation {} }
            Behavior on width { MotionAnimation {} }
        }
        Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
    }
}
