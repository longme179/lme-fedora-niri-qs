import QtQuick
import Quickshell
import "../bar"
import "../services"
import "../theme"

Item {
    id: root
    property var screenInfo: null
    property var windowInfo: null
    readonly property var layout: ShellState.preferences.barLayout || BarRegistry.defaults
    readonly property bool islands: ShellState.preferences.barStyle === "islands"
    // The islands surface is invisible, so a pill-only region union leaves the
    // gaps between pills unblurred (sharp app chrome pierces through). Keep a
    // full-strip region over the whole bar so app pixels in the gaps are
    // frosted even when only the pills are visible.
    readonly property Region fullStrip: Region { item: root.visible && root.width > 0 ? root : null }
    readonly property Region blurRegion: Region { regions: [root.fullStrip, surface.blurRegion, leftGroup.blurRegion, centerGroup.blurRegion, rightGroup.blurRegion] }
    implicitHeight: Theme.barHeight
    BarSurface { id: surface; anchors.fill: parent; visible: !root.islands }
    BarGroup {
        id: leftGroup; zone: "left"
        anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
        width: implicitWidth; height: parent.height
        modules: root.layout.left; screenInfo: root.screenInfo; windowInfo: root.windowInfo
        budget: root.width * 0.39; compact: root.width < 1200; island: root.islands
    }
    BarGroup {
        id: rightGroup; zone: "right"
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        width: implicitWidth; height: parent.height
        modules: root.layout.right; screenInfo: root.screenInfo; windowInfo: root.windowInfo
        budget: root.width * 0.58; compact: root.width < 1200; island: root.islands
    }
    BarGroup {
        id: centerGroup
        zone: "center"
        readonly property real freeWidth: Math.max(0, root.width - leftGroup.width - rightGroup.width - 24)
        width: implicitWidth; height: parent.height
        x: Math.max(leftGroup.width + 12, Math.min((root.width - width) / 2, rightGroup.x - width - 12))
        modules: root.layout.center; screenInfo: root.screenInfo; windowInfo: root.windowInfo
        budget: freeWidth; compact: root.width < 1200; island: root.islands
    }
}
