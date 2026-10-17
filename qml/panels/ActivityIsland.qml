pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "../components"
import "../services"
import "../theme"

SlideLoader {
    id: root
    property bool expanded: ShellState.activityOpen && !ShellState.authenticationActive
    readonly property real expansion: progress
    readonly property real sideInset: parent ? Math.min(14, Math.max(0, parent.width / 2 - 1)) : 14
    readonly property real edgeInset: parent ? Math.min(Theme.barTopMargin + 6, Math.max(0, parent.height / 2 - 1)) : Theme.barTopMargin + 6
    readonly property real compactWidth: Math.min(expandedWidth, Math.max(54, ShellState.activityAnchorWidth))
    readonly property real expandedWidth: Math.max(1, Math.min(Theme.activityPopupMaxWidth, parent ? parent.width - 2 * sideInset : Theme.activityPopupMaxWidth))
    readonly property Item panel: item as Item
    readonly property real expandedHeight: Math.max(1, Math.min(panel ? panel.implicitHeight : 680, Theme.activityPopupMaxHeight || Infinity, parent ? parent.height - edgeInset - 14 : 680))
    shown: expanded
    exitToEdge: true
    exitEdge: Theme.barBottom ? "bottom" : "top"
    animateResize: false
    direction: Theme.barBottom ? "up" : "down"
    visible: mounted
    width: Math.max(1, Math.min(expandedWidth, Theme.springMotion ? widthSpring.value : compactWidth + (expandedWidth - compactWidth) * expansion))
    height: Math.max(1, Math.min(expandedHeight, Theme.springMotion ? heightSpring.value : 30 + (expandedHeight - 30) * expansion))
    x: Math.max(sideInset, Math.min((parent ? parent.width : width) - width - sideInset, (ShellState.activityAnchorX >= 0 ? ShellState.activityAnchorX : (parent ? parent.width / 2 : width / 2)) - width / 2))
    y: Theme.barBottom && parent ? parent.height - edgeInset - height : edgeInset
    focus: expanded
    Keys.onEscapePressed: ShellState.closePanels()
    MotionValue { id: widthSpring; large: true; value: root.compactWidth; target: root.mounted ? root.expandedWidth : root.compactWidth; enabled: Theme.springMotion && root.mounted }
    MotionValue { id: heightSpring; large: true; value: 30; target: root.mounted ? root.expandedHeight : 30; enabled: Theme.springMotion && root.mounted }
    content: GlassPanel { role: "islandFill";
        implicitHeight: card.implicitHeight + 76
        anchors.fill: parent; radius: 15 + 13 * root.expansion; clip: true
        MouseArea { anchors.fill: parent }
        Row {
            x: 16; y: 8; spacing: 8
            ShellIcon { name: ActivityState.icon; width: 18; height: 18; color: ActivityState.kind === "recording" ? Theme.red : Theme.accent; anchors.verticalCenter: parent.verticalCenter }
            LabelText { objectName: "activityPanelTitle"; text: "Activity Island"; width: Math.max(0, root.width - 94); elide: Text.ElideRight; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight; anchors.verticalCenter: parent.verticalCenter }
        }
        IconButton { objectName: "activityClose"; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8; implicitWidth: 30; implicitHeight: 30; glyph: "×"; Accessible.name: "Close activity"; onClicked: ShellState.closePanels(); Component.onCompleted: Qt.callLater(() => forceActiveFocus()) }
        ScrollView {
            id: activityScroll
            x: 16; y: 52; width: Math.max(0, parent.width - 32); height: Math.max(0, parent.height - 68); clip: true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ActivityCard { id: card; width: Math.max(0, root.expandedWidth - 32) }
        }
    }
}
