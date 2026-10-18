// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import "../theme"
import "../services"
import "JellyGeometry.js" as Jelly

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
    property var elasticities: []
    function trackTransforms() {
        const list = [], effects = [];
        for (const item of geometryItems) {
            for (const transform of item.transform) list.push(transform);
            for (const child of item.children) {
                const effect = child as PopupElasticity;
                if (effect && effect.surface === item) effects.push(effect);
            }
        }
        transforms = list;
        elasticities = effects;
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
    readonly property var warps: elasticities.filter(effect => effect && effect.rendering && !effect.software)
    readonly property var strips: {
        if (!active || !warps.length) return [];
        void bounds;
        const radii = ["topRightRadius", "bottomRightRadius", "bottomLeftRadius", "topLeftRadius"].map(name => plate && plate[name] >= 0 ? plate[name] : plate ? plate.radius : Theme.radius);
        return Jelly.strips(Jelly.outline(surface.width, surface.height, radii).map(point => {
            let owner = surface;
            for (const effect of warps) {
                point = owner.mapToItem(effect.surface, point.x, point.y);
                point = Jelly.warp(point, effect.surface.width, effect.surface.height, effect.strain, effect.horizontal, effect.bounded);
                owner = effect.surface;
            }
            return owner.mapToItem(hostWindow.contentItem, point.x, point.y);
        }), hostWindow.width, hostWindow.height);
    }
    property int bandCapacity: 0
    onStripsChanged: {
        if (!active || !warps.length) bandCapacity = 0;
        else if (strips.length > bandCapacity) bandCapacity = Math.ceil(strips.length / 32) * 32;
    }
    readonly property Instantiator bands: Instantiator {
        active: root.active && root.warps.length > 0
        // Numeric model changes rebuild delegates; reuse a bounded pool during flight.
        model: root.bandCapacity
        delegate: Region {
            required property int index
            readonly property var band: root.strips[index]
            x: band ? band.x : 0; y: band ? band.y : 0
            width: band ? band.width : 0; height: band ? band.height : 0
        }
        onObjectAdded: (index, object) => root.regions.push(object)
        onObjectRemoved: (index, object) => { root.regions = root.regions.filter(region => region !== object); }
    }
    readonly property real radiusScale: surface && active ? Math.min(bounds.width / Math.max(1, surface.width), bounds.height / Math.max(1, surface.height)) : 1
    x: Math.floor(bounds.x); y: Math.floor(bounds.y)
    width: active && !warps.length ? Math.ceil(bounds.x + bounds.width) - x : 0
    height: active && !warps.length ? Math.ceil(bounds.y + bounds.height) - y : 0
    radius: Math.round((plate ? plate.radius : Theme.radius) * radiusScale)
    function corner(name) {
        return plate && plate[name] >= 0 ? Math.round(plate[name] * radiusScale) : radius;
    }
    topLeftRadius: corner("topLeftRadius"); topRightRadius: corner("topRightRadius")
    bottomLeftRadius: corner("bottomLeftRadius"); bottomRightRadius: corner("bottomRightRadius")
    onActiveChanged: GlassState.watchPopup(root, popup && active)
    onPopupChanged: GlassState.watchPopup(root, popup && active)
    Component.onCompleted: { trackTransforms(); Qt.callLater(trackTransforms); GlassState.watchPopup(root, popup && active); }
    Component.onDestruction: GlassState.watchPopup(root, false)
}
