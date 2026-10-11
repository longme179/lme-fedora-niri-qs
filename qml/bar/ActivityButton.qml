import QtQuick
import "../components"
import "../services"
import "../theme"

LiquidButton {
    id: root
    property var screenInfo: null
    property var windowInfo: null
    property real budget: 360
    implicitHeight: 30
    implicitWidth: Math.min(Math.ceil(measure.implicitWidth) + 54, Math.max(0, Math.min(300, budget)))
    leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0; hoverEnabled: true
    visible: !(ShellState.activityOpen && (!ShellState.panelScreen || ShellState.panelScreen === screenInfo))
    Accessible.name: "Activity: " + ActivityState.title + ". Expand media and timers."
    Behavior on implicitWidth { MotionAnimation { large: true } }
    background: Rectangle { radius: height / 2; color: root.hovered || ShellState.activityOpen ? Theme.barHover : "transparent"; border.width: root.visualFocus ? 2 : 0; border.color: Theme.accent }
    LabelText { id: measure; visible: false; text: ActivityState.title; font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight }
    contentItem: Item {
        Row {
            anchors.centerIn: parent; spacing: 8
            ShellIcon { name: ActivityState.icon; width: 18; height: 18; color: ActivityState.kind === "recording" ? Theme.red : Theme.accent; anchors.verticalCenter: parent.verticalCenter }
            LabelText { text: ActivityState.title; width: Math.max(0, root.width - 54); elide: Text.ElideRight; font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight; anchors.verticalCenter: parent.verticalCenter }
        }
    }
    onClicked: {
        const point = root.mapToItem(null, root.width / 2, 0);
        ShellState.activityAnchorX = point.x + (windowInfo ? Theme.barSideMargin : 0);
        ShellState.activityAnchorWidth = width;
        ShellState.togglePanel("activity", screenInfo);
    }
}
