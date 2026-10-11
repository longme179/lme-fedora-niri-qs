import QtQuick
import "../bar"
import "../components"
import "../services"
import "../theme"

Item {
    id: root
    property var screenInfo: null
    property var windowInfo: null
    readonly property var layout: ShellState.preferences.barLayout || BarRegistry.defaults
    readonly property bool islands: ShellState.preferences.barStyle === "islands"
    implicitHeight: Theme.barHeight
    GlassPanel { role: "barFill"; anchors.fill: parent; radius: height / 2; visible: !root.islands }
    BarGroup {
        id: leftGroup
        anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
        width: implicitWidth; height: parent.height
        modules: root.layout.left; screenInfo: root.screenInfo; windowInfo: root.windowInfo
        budget: root.width * 0.39; compact: root.width < 1200; island: root.islands
    }
    BarGroup {
        id: rightGroup
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        width: implicitWidth; height: parent.height
        modules: root.layout.right; screenInfo: root.screenInfo; windowInfo: root.windowInfo
        budget: root.width * 0.58; compact: root.width < 1200; island: root.islands
    }
    BarGroup {
        readonly property real freeWidth: Math.max(0, root.width - leftGroup.width - rightGroup.width - 24)
        width: implicitWidth; height: parent.height
        x: Math.max(leftGroup.width + 12, Math.min((root.width - width) / 2, rightGroup.x - width - 12))
        modules: root.layout.center; screenInfo: root.screenInfo; windowInfo: root.windowInfo
        budget: freeWidth; compact: root.width < 1200; island: root.islands
    }
}
