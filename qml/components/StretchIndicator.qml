// SPDX-License-Identifier: MIT
// Copyright (c) 2025-2026 Avenge Media LLC
// Adapted from DTabBar.qml at bd90e4b; local controls, vertical/grid support.
import QtQuick
import "../theme"
Rectangle {
    id: root
    property LiquidButton targetItem
    property bool vertical: false
    property bool initialized: false
    property bool forward: true
    property color fill: Theme.primaryContainer
    readonly property var geometry: {
        if (!targetItem) return {x:0,y:0,width:0,height:0};
        // shortcut: ancestors are untransformed layouts; use layout mapping if a caller adds transforms.
        let x = targetItem.x, y = targetItem.y;
        for (let container = targetItem.parent; container && container !== parent; container = container.parent) {
            x += container.x; y += container.y;
        }
        return {x,y,width:targetItem.width,height:targetItem.height};
    }
    property real leftEdge: geometry.x
    property real rightEdge: geometry.x + geometry.width
    property real topEdge: geometry.y
    property real bottomEdge: geometry.y + geometry.height
    onGeometryChanged: { forward = vertical ? geometry.y >= y : geometry.x >= x; Qt.callLater(() => initialized=true); }
    visible: !!targetItem && Theme.animatedTabs
    x: leftEdge; y: topEdge; width: Math.max(0,rightEdge-leftEdge); height: Math.max(0,bottomEdge-topEdge)
    scale: targetItem ? targetItem.scale : 1
    transformOrigin: targetItem ? targetItem.transformOrigin : Item.Center
    color: fill; radius: targetItem && targetItem.plate ? targetItem.plate.radius : Math.min(width,height)/2
    Behavior on leftEdge { enabled: root.initialized && Theme.animations; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 2 : 1) } }
    Behavior on rightEdge { enabled: root.initialized && Theme.animations; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 1 : 2) } }
    Behavior on topEdge { enabled: root.initialized && Theme.animations; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 2 : 1) } }
    Behavior on bottomEdge { enabled: root.initialized && Theme.animations; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 1 : 2) } }
}
