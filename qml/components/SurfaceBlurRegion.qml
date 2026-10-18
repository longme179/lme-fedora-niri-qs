// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import "../theme"
import "../services"

Region {
    id: root
    property Item surface: null
    readonly property Rectangle plate: surface as Rectangle
    property bool popup: false
    readonly property var hostWindow: surface ? surface.QsWindow.window : null
    readonly property var geometryItems: {
        const items = [];
        for (let item = surface; item; item = item.parent) items.push(item);
        return items;
    }
    property var transforms: []
    function trackTransforms() {
        const list = [];
        for (const item of geometryItems) for (const transform of item.transform) list.push(transform);
        transforms = list;
    }
    onGeometryItemsChanged: trackTransforms()
    readonly property rect bounds: {
        if (!Theme.liquidGlass || !surface || !hostWindow || !hostWindow.visible) return Qt.rect(0, 0, 0, 0);
        // Region.item does not watch ancestor transforms; follow the existing springs without a timer.
        for (const item of geometryItems) {
            if (!item.visible || item.opacity <= 0) return Qt.rect(0, 0, 0, 0);
            void item.x; void item.y; void item.width; void item.height;
            void item.scale; void item.rotation; void item.transformOrigin;
        }
        for (const transform of transforms) {
            if (transform.x !== undefined) void transform.x;
            if (transform.y !== undefined) void transform.y;
            if (transform.xScale !== undefined) void transform.xScale;
            if (transform.yScale !== undefined) void transform.yScale;
            if (transform.angle !== undefined) void transform.angle;
            if (transform.origin !== undefined) void transform.origin;
        }
        return surface.mapToItem(hostWindow.contentItem, 0, 0, surface.width, surface.height);
    }
    readonly property bool active: bounds.width > 0 && bounds.height > 0
    readonly property real radiusScale: surface && active ? Math.min(bounds.width / Math.max(1, surface.width), bounds.height / Math.max(1, surface.height)) : 1
    x: Math.floor(bounds.x); y: Math.floor(bounds.y)
    width: active ? Math.ceil(bounds.x + bounds.width) - x : 0
    height: active ? Math.ceil(bounds.y + bounds.height) - y : 0
    radius: Math.round((plate ? plate.radius : Theme.radius) * radiusScale)
    function corner(name) {
        return plate && plate[name] >= 0 ? Math.round(plate[name] * radiusScale) : radius;
    }
    topLeftRadius: corner("topLeftRadius"); topRightRadius: corner("topRightRadius")
    bottomLeftRadius: corner("bottomLeftRadius"); bottomRightRadius: corner("bottomRightRadius")
    onActiveChanged: GlassState.watchPopup(root, popup && active)
    onPopupChanged: GlassState.watchPopup(root, popup && active)
    Component.onCompleted: { trackTransforms(); GlassState.watchPopup(root, popup && active); }
    Component.onDestruction: GlassState.watchPopup(root, false)
}
