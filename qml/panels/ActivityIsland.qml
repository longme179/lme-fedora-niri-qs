import QtQuick
import QtQuick.Controls
import "../components"
import "../services"
import "../theme"

Item {
    id: root
    property bool expanded: ShellState.activityOpen && !ShellState.authenticationActive
    property real expansion: expanded ? 1 : 0
    readonly property bool transitioning: morph.running
    readonly property real compactWidth: Math.max(54, ShellState.activityAnchorWidth)
    readonly property real expandedWidth: Math.min(460, parent ? parent.width - 28 : 460)
    readonly property real expandedHeight: Math.min(card.implicitHeight + 76, parent ? parent.height - 36 : 680)
    visible: expanded || expansion > 0
    width: compactWidth + (expandedWidth - compactWidth) * expansion
    height: 30 + (expandedHeight - 30) * expansion
    x: Math.max(14, Math.min((parent ? parent.width : width) - width - 14, (ShellState.activityAnchorX >= 0 ? ShellState.activityAnchorX : (parent ? parent.width / 2 : width / 2)) - width / 2))
    y: Theme.barBottom && parent ? parent.height - Theme.barTopMargin - 6 - height : Theme.barTopMargin + 6
    focus: expanded
    Keys.onEscapePressed: ShellState.closePanels()
    onExpandedChanged: if (expanded) Qt.callLater(() => closeButton.forceActiveFocus());
    Behavior on expansion { MotionAnimation { id: morph; large: true; easing.bezierCurve: root.expanded ? Theme.spatialCurve : [.3, 0, .8, 1, 1, 1] } }
    GlassPanel { role: "islandFill";
        anchors.fill: parent; radius: 15 + 13 * root.expansion; clip: true
        MouseArea { anchors.fill: parent }
        Row {
            x: 16; y: 8; spacing: 8
            ShellIcon { name: ActivityState.icon; width: 18; height: 18; color: ActivityState.kind === "recording" ? Theme.red : Theme.accent; anchors.verticalCenter: parent.verticalCenter }
            LabelText { text: ActivityState.title; width: Math.max(0, root.width - 94); elide: Text.ElideRight; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight; anchors.verticalCenter: parent.verticalCenter }
        }
        IconButton { id: closeButton; objectName: "activityClose"; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8; implicitWidth: 30; implicitHeight: 30; glyph: "×"; Accessible.name: "Close activity"; onClicked: ShellState.closePanels() }
        ScrollView {
            id: activityScroll
            x: 16; y: 52; width: Math.max(0, parent.width - 32); height: Math.max(0, parent.height - 68); clip: true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ActivityCard { id: card; width: Math.max(0, root.expandedWidth - 32) }
        }
    }
}
