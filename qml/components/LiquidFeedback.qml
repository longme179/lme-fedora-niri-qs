// SPDX-License-Identifier: GPL-3.0-only
// Press/hold/release sequencing adapted from Caelestia StateLayer.qml (GPL-3.0).
// See THIRD_PARTY.md for revisions and the compatible upstream license notices.
import QtQuick
import "../theme"

Item {
    id: root
    required property bool hovered
    required property bool pressed
    property real radius: height / 2
    property color ink: Theme.accent
    property real hoverAmount: hovered && Theme.animations ? 1 : 0
    property real rippleProgress: 0
    property real rippleOpacity: 0
    readonly property bool animating: expand.running || release.running
    anchors.fill: parent
    Behavior on hoverAmount { MotionAnimation { duration: Theme.animationDuration } }
    Rectangle { anchors.fill: parent; radius: root.radius; color: "transparent"; border.width: 1; border.color: Theme.alpha(root.ink, root.hoverAmount * .28) }
    Rectangle {
        anchors.centerIn: parent
        // shortcut: centered pill wave avoids shader clipping, use pointer-origin masked ripples if larger surfaces need them.
        width: root.width * root.rippleProgress; height: root.height * Math.min(1, root.rippleProgress * 2)
        radius: Math.min(root.radius, height / 2)
        color: root.ink; opacity: root.rippleOpacity
    }
    onPressedChanged: {
        if (!Theme.animations) return;
        if (pressed) {
            release.stop(); expand.stop(); rippleProgress = 0; rippleOpacity = .14; expand.start();
        } else if (!expand.running) release.start();
    }
    NumberAnimation {
        id: expand; target: root; property: "rippleProgress"; to: 1
        duration: Theme.animationDuration * 2; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.effectsCurve
        onFinished: if (!root.pressed) release.start()
    }
    NumberAnimation { id: release; target: root; property: "rippleOpacity"; to: 0; duration: Theme.animationDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.effectsCurve }
    Connections { target: Theme; function onAnimationsChanged() { if (!Theme.animations) { expand.stop(); release.stop(); root.rippleOpacity = 0; } } }
}
