// SPDX-License-Identifier: MIT
// Copyright (c) 2025-2026 Avenge Media LLC
// Adapted from DTabBar.qml at bd90e4b; local controls, vertical/grid support.
// Glass lens treatment inspired by Serpantinum; timing (leading fast / trailing slow,
// lifted magnify) derived from Serpantinum GlassLens.qml (AGPL-3.0-or-later,
// Illia Miroshnichenko); see third_party/Serpantinum-NOTICE.
import QtQuick
import "../theme"
Rectangle {
    id: root
    property LiquidButton targetItem
    property bool vertical: false
    // Lens-local opt-out to the legacy symmetric springs. Default is the new
    // OutExpo timing (Lens 2.0); the global Theme.springMotion pref is shared
    // by sliders/switches/popups and must keep its true default, so it cannot
    // gate the lens without hiding the new motion from most users.
    property bool legacyMotion: false
    property bool initialized: false
    property bool placed: false
    property bool settling: false
    property bool forward: true
    property color fill: Theme.primaryContainer
    Timer { id: settleTimer; interval: 300; onTriggered: root.settling = false }
    Connections { target: Theme; function onLiquidGlassChanged() { root.settling = true; settleTimer.restart(); } }
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
    MotionValue { id: leftMotion; enabled: root.initialized && root.legacyMotion; target: root.geometry.x; response: root.vertical ? 1 : root.forward ? .82 : 1.12 }
    MotionValue { id: rightMotion; enabled: root.initialized && root.legacyMotion; target: root.geometry.x + root.geometry.width; response: root.vertical ? 1 : root.forward ? 1.12 : .82 }
    MotionValue { id: topMotion; enabled: root.initialized && root.legacyMotion; target: root.geometry.y; response: !root.vertical ? 1 : root.forward ? .82 : 1.12 }
    MotionValue { id: bottomMotion; enabled: root.initialized && root.legacyMotion; target: root.geometry.y + root.geometry.height; response: !root.vertical ? 1 : root.forward ? 1.12 : .82 }
    property real leftEdge: root.legacyMotion ? leftMotion.value : geometry.x
    property real rightEdge: root.legacyMotion ? rightMotion.value : geometry.x + geometry.width
    property real topEdge: root.legacyMotion ? topMotion.value : geometry.y
    property real bottomEdge: root.legacyMotion ? bottomMotion.value : geometry.y + geometry.height
    onGeometryChanged: { forward = vertical ? geometry.y >= y : geometry.x >= x; Qt.callLater(() => initialized=true); Qt.callLater(() => placed = !!targetItem || placed); }
    visible: !!targetItem && Theme.animatedTabs && placed
    opacity: placed && targetItem ? 1 : 0
    Behavior on opacity { enabled: Theme.animations; NumberAnimation { easing.type: Easing.OutExpo } }
    x: Math.max(0, leftEdge); y: Math.max(0, topEdge)
    width: Math.max(0, Math.min(rightEdge - leftEdge, parent ? parent.width - x : rightEdge - leftEdge))
    height: Math.max(0, Math.min(bottomEdge - topEdge, parent ? parent.height - y : bottomEdge - topEdge))
    // Lift while moving: bounded magnify <= 0.16 plus the hover-channel glint in GlassMaterial.
    property real liftMagnify: root.moving && !root.legacyMotion ? 1.16 : 1
    scale: (targetItem ? targetItem.scale : 1) * liftMagnify
    Behavior on liftMagnify { enabled: Theme.animations; NumberAnimation { duration: 200; easing.type: Easing.OutExpo } }
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
    Behavior on leftEdge { enabled: root.initialized && Theme.animations && !root.legacyMotion; NumberAnimation { duration: root.vertical ? 200 : root.forward ? 350 : 200; easing.type: Easing.OutExpo } }
    Behavior on rightEdge { enabled: root.initialized && Theme.animations && !root.legacyMotion; NumberAnimation { duration: root.vertical ? 200 : root.forward ? 200 : 350; easing.type: Easing.OutExpo } }
    Behavior on topEdge { enabled: root.initialized && Theme.animations && !root.legacyMotion; NumberAnimation { duration: !root.vertical ? 200 : root.forward ? 350 : 200; easing.type: Easing.OutExpo } }
    Behavior on bottomEdge { enabled: root.initialized && Theme.animations && !root.legacyMotion; NumberAnimation { duration: !root.vertical ? 200 : root.forward ? 200 : 350; easing.type: Easing.OutExpo } }
}
