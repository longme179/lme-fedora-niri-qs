// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import "../theme"
import "../services"

Item {
    id: root
    property real radius: 20
    property real topLeftRadius: radius
    property real topRightRadius: radius
    property real bottomLeftRadius: radius
    property real bottomRightRadius: radius
    property bool hovered: false
    property bool pressed: false
    readonly property bool software: GraphicsInfo.api === GraphicsInfo.Software
    readonly property var hostWindow: Window.window
    readonly property bool active: Theme.liquidGlass && visible && width > 0 && height > 0 && !!hostWindow && hostWindow.visible
    property var backdrop: null
    property var geometryItems: []
    property real hoverAmount: active && Theme.animations && (hovered || pointer.hovered) ? 1 : 0
    property real pressAmount: active && Theme.animations && pressed ? 1 : 0
    objectName: "glassMaterial"
    Behavior on hoverAmount { enabled: root.active && Theme.animations; NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic } }
    Behavior on pressAmount { enabled: root.active && Theme.animations; NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic } }
    function updateBackdrop() {
        if (backdrop && (!active || software || backdrop.hostWindow !== hostWindow)) { GlassState.release(backdrop); backdrop = null; }
        if (active && !software) { trackGeometry(); if (!backdrop) backdrop = GlassState.acquire(hostWindow); }
        else geometryItems = [];
    }
    onActiveChanged: updateBackdrop()
    onSoftwareChanged: updateBackdrop()
    function trackGeometry() {
        const items = [];
        for (let item = root; item; item = item.parent) {
            items.push(item);
            for (const transform of item.transform) items.push(transform);
        }
        geometryItems = items;
    }
    onParentChanged: Qt.callLater(updateBackdrop)
    onHostWindowChanged: updateBackdrop()
    Component.onCompleted: updateBackdrop()
    Component.onDestruction: if (backdrop) GlassState.release(backdrop)
    readonly property rect sampleRect: {
        if (!backdrop) return Qt.rect(0, 0, 1, 1);
        // Track ancestor transforms without a per-button timer or frame loop.
        for (const item of geometryItems) {
            if (!item) continue;
            if (item.x !== undefined) void item.x;
            if (item.y !== undefined) void item.y;
            if (item.width !== undefined) void item.width;
            if (item.height !== undefined) void item.height;
            if (item.scale !== undefined) void item.scale;
            if (item.rotation !== undefined) void item.rotation;
            if (item.xScale !== undefined) void item.xScale;
            if (item.yScale !== undefined) void item.yScale;
        }
        const a = root.mapToItem(null, 0, 0);
        const b = root.mapToItem(null, width, height);
        const origin = backdrop.windowOrigin;
        const crop = backdrop.cropRect;
        return Qt.rect(crop.x + (origin.x + a.x) / backdrop.outputWidth * crop.width, crop.y + (origin.y + a.y) / backdrop.outputHeight * crop.height,
            (b.x - a.x) / backdrop.outputWidth * crop.width, (b.y - a.y) / backdrop.outputHeight * crop.height);
    }
    HoverHandler { id: pointer; enabled: root.active && Theme.animations }
    Loader {
        anchors.fill: parent
        active: root.active
        sourceComponent: root.software ? fallback : optical
    }
    Component {
        id: fallback
        Rectangle {
            radius: root.radius
            color: "transparent"; border.width: 1; border.color: "#60ffffff"
            topLeftRadius: root.topLeftRadius < 0 ? root.radius : root.topLeftRadius
            topRightRadius: root.topRightRadius < 0 ? root.radius : root.topRightRadius
            bottomLeftRadius: root.bottomLeftRadius < 0 ? root.radius : root.bottomLeftRadius
            bottomRightRadius: root.bottomRightRadius < 0 ? root.radius : root.bottomRightRadius
        }
    }
    Component {
        id: optical
        GlassOptics {
            src: root.backdrop
            sourceAvailable: root.backdrop && root.backdrop.status === Image.Ready ? 1 : 0
            sourceRect: root.sampleRect
            topLeftRadius: root.topLeftRadius < 0 ? root.radius : root.topLeftRadius
            topRightRadius: root.topRightRadius < 0 ? root.radius : root.topRightRadius
            bottomLeftRadius: root.bottomLeftRadius < 0 ? root.radius : root.bottomLeftRadius
            bottomRightRadius: root.bottomRightRadius < 0 ? root.radius : root.bottomRightRadius
            cursorPos: pointer.hovered ? pointer.point.position : Qt.point(width / 2, height / 2)
            hover: root.hoverAmount; energy: root.pressAmount
            tintAmount: 0; clear: 1; frost: .35; dispersion: .025; rim: .3
            bezel: Math.max(2, Math.min(8, Math.min(width, height) * .14))
        }
    }
}
