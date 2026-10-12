// SPDX-License-Identifier: MIT
// Copyright (c) 2025-2026 Avenge Media LLC
// Adapted from DTabBar.qml at bd90e4b; local controls, vertical/grid support.
import QtQuick
import "../theme"
Rectangle {
    id: root
    property Item targetItem
    property bool vertical: false
    property bool initialized: false
    property bool forward: true
    property color fill: Theme.primaryContainer
    readonly property var geometry: {
        if (!targetItem) return {x:0,y:0,width:0,height:0};
        const watched=[targetItem.x,targetItem.y,targetItem.width,targetItem.height,parent.width,parent.height];
        const point=targetItem.mapToItem(parent,0,0);
        return {x:point.x,y:point.y,width:watched[2],height:watched[3]};
    }
    property real leftEdge: geometry.x
    property real rightEdge: geometry.x + geometry.width
    property real topEdge: geometry.y
    property real bottomEdge: geometry.y + geometry.height
    onGeometryChanged: { forward = vertical ? geometry.y >= y : geometry.x >= x; Qt.callLater(() => initialized=true); }
    visible: !!targetItem && Theme.animatedTabs
    x: leftEdge; y: topEdge; width: Math.max(0,rightEdge-leftEdge); height: Math.max(0,bottomEdge-topEdge)
    color: fill; radius: Math.min(width,height)/2
    Behavior on leftEdge { enabled: root.initialized && Theme.animations; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 2 : 1) } }
    Behavior on rightEdge { enabled: root.initialized && Theme.animations; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 1 : 2) } }
    Behavior on topEdge { enabled: root.initialized && Theme.animations; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 2 : 1) } }
    Behavior on bottomEdge { enabled: root.initialized && Theme.animations; MotionAnimation { duration: Theme.animationDuration * (root.forward ? 1 : 2) } }
}
