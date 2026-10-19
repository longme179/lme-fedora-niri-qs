// SPDX-License-Identifier: MIT
// Copyright (c) 2025-2026 Avenge Media LLC
// Adapted from DTabBar.qml at bd90e4b; local controls, vertical/grid support.
// Glass lens treatment inspired by Serpantinum; see third_party/Serpantinum-NOTICE.
import QtQuick
import "../theme"
Rectangle {
    id: root
    property LiquidButton targetItem
    property bool vertical: false
    property bool initialized: false
    property bool forward: true
    property color fill: Theme.primaryContainer
    readonly property bool moving: visible && Theme.animations && (Math.abs(x - geometry.x) > .5 || Math.abs(y - geometry.y) > .5
        || Math.abs(width - geometry.width) > .5 || Math.abs(height - geometry.height) > .5)
    readonly property var geometry: {
        if (!targetItem) return {x:0,y:0,width:0,height:0};
        // shortcut: ancestors are untransformed layouts; use layout mapping if a caller adds transforms.
        let x = targetItem.x, y = targetItem.y;
        for (let container = targetItem.parent; container && container !== parent; container = container.parent) {
            x += container.x; y += container.y;
        }
        return {x,y,width:targetItem.width,height:targetItem.height};
    }
    MotionValue { id: leftMotion; enabled: root.initialized && Theme.springMotion; target: root.geometry.x; response: root.vertical ? 1 : root.forward ? .82 : 1.12 }
    MotionValue { id: rightMotion; enabled: root.initialized && Theme.springMotion; target: root.geometry.x + root.geometry.width; response: root.vertical ? 1 : root.forward ? 1.12 : .82 }
    MotionValue { id: topMotion; enabled: root.initialized && Theme.springMotion; target: root.geometry.y; response: !root.vertical ? 1 : root.forward ? .82 : 1.12 }
    MotionValue { id: bottomMotion; enabled: root.initialized && Theme.springMotion; target: root.geometry.y + root.geometry.height; response: !root.vertical ? 1 : root.forward ? 1.12 : .82 }
    property real leftEdge: Theme.springMotion ? leftMotion.value : geometry.x
    property real rightEdge: Theme.springMotion ? rightMotion.value : geometry.x + geometry.width
    property real topEdge: Theme.springMotion ? topMotion.value : geometry.y
    property real bottomEdge: Theme.springMotion ? bottomMotion.value : geometry.y + geometry.height
    onGeometryChanged: { forward = vertical ? geometry.y >= y : geometry.x >= x; Qt.callLater(() => initialized=true); }
    visible: !!targetItem && Theme.animatedTabs
    x: Math.max(0, leftEdge); y: Math.max(0, topEdge)
    width: Math.max(0, Math.min(rightEdge - leftEdge, parent ? parent.width - x : rightEdge - leftEdge))
    height: Math.max(0, Math.min(bottomEdge - topEdge, parent ? parent.height - y : bottomEdge - topEdge))
    scale: targetItem ? targetItem.scale : 1
    transformOrigin: targetItem ? targetItem.transformOrigin : Item.Center
    color: fill; radius: targetItem && targetItem.plate ? targetItem.plate.radius : Math.min(width,height)/2
    GlassMaterial {
        anchors.fill: parent; radius: root.radius
        visible: Theme.glassSelection
        enabled: !!root.targetItem && root.targetItem.enabled
        hovered: !!root.targetItem && root.targetItem.hovered
        pressed: !!root.targetItem && root.targetItem.down
        // Lift the optics during travel without adding a second geometric animation.
        pressAmount: active && Theme.animations ? Math.max(pressed ? 1 : 0, root.moving ? .25 : 0) : 0
    }
    Behavior on leftEdge { enabled: root.initialized && Theme.animations && !Theme.springMotion; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 2 : 1) } }
    Behavior on rightEdge { enabled: root.initialized && Theme.animations && !Theme.springMotion; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 1 : 2) } }
    Behavior on topEdge { enabled: root.initialized && Theme.animations && !Theme.springMotion; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 2 : 1) } }
    Behavior on bottomEdge { enabled: root.initialized && Theme.animations && !Theme.springMotion; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 1 : 2) } }
}
