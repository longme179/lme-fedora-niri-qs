// SPDX-License-Identifier: GPL-3.0-only
// Press/hold/release sequencing adapted from Caelestia StateLayer.qml (GPL-3.0).
// Pointer-origin clip shader adapted from DCommon DRipple (MIT, Avenge Media 2025-2026).
// See THIRD_PARTY.md for revisions and the compatible upstream license notices.
import QtQuick
import "../theme"

Item {
    id: root
    required property bool hovered
    required property bool pressed
    property real radius: height / 2
    property real originX: width / 2
    property real originY: height / 2
    property real clickX: width / 2
    property real clickY: height / 2
    readonly property real maxRadius: Math.hypot(Math.max(clickX,width-clickX),Math.max(clickY,height-clickY))
    readonly property bool software: GraphicsInfo.api === GraphicsInfo.Software
    property color ink: Theme.accent
    property real hoverAmount: hovered && Theme.animations ? 1 : 0
    property real rippleProgress: 0
    property real rippleOpacity: 0
    readonly property bool animating: expand.running || release.running
    anchors.fill: parent
    Behavior on hoverAmount { NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.effectsCurve } }
    Rectangle { anchors.fill: parent; radius: root.radius; color: "transparent"; border.width: 1; border.color: Theme.alpha(root.ink, root.hoverAmount * .28) }
    ShaderEffect {
        visible: !root.software && root.rippleOpacity > 0
        x: Math.max(0,root.clickX-rippleRadius); y: Math.max(0,root.clickY-rippleRadius)
        width: Math.max(0,Math.min(root.width,root.clickX+rippleRadius)-x)
        height: Math.max(0,Math.min(root.height,root.clickY+rippleRadius)-y)
        property real widthPx: width
        property real heightPx: height
        property real rippleCenterX: root.clickX
        property real rippleCenterY: root.clickY
        property real rippleRadius: root.maxRadius * root.rippleProgress
        property real rippleOpacity: root.rippleOpacity
        property real offsetX: x
        property real offsetY: y
        property real parentWidth: root.width
        property real parentHeight: root.height
        property vector4d rippleCol: Qt.vector4d(root.ink.r,root.ink.g,root.ink.b,root.ink.a)
        property vector4d cornerRadiiPx: Qt.vector4d(root.radius,root.radius,root.radius,root.radius)
        fragmentShader: Qt.resolvedUrl("shaders/ripple.frag.qsb")
    }
    Canvas {
        id: fallback; anchors.fill: parent; visible: root.software
        onPaint: {
            const c=getContext("2d"); c.reset(); c.clearRect(0,0,width,height);
            if (root.rippleOpacity<=0) return;
            const r=Math.min(root.radius,width/2,height/2);
            c.beginPath(); c.moveTo(r,0); c.lineTo(width-r,0); c.quadraticCurveTo(width,0,width,r);
            c.lineTo(width,height-r); c.quadraticCurveTo(width,height,width-r,height);
            c.lineTo(r,height); c.quadraticCurveTo(0,height,0,height-r); c.lineTo(0,r); c.quadraticCurveTo(0,0,r,0); c.closePath(); c.clip();
            c.globalAlpha=root.rippleOpacity; c.fillStyle=root.ink;
            c.beginPath(); c.arc(root.clickX,root.clickY,root.maxRadius*root.rippleProgress,0,Math.PI*2); c.fill();
        }
        Connections { target: root; function onRippleProgressChanged() { if(root.software) fallback.requestPaint(); } function onRippleOpacityChanged() { if(root.software) fallback.requestPaint(); } function onRadiusChanged() { if(root.software) fallback.requestPaint(); } }
    }
    onPressedChanged: {
        if (!Theme.animations) return;
        if (pressed) {
            clickX = Theme.pointerRipple ? Math.max(0,Math.min(width,originX)) : width/2;
            clickY = Theme.pointerRipple ? Math.max(0,Math.min(height,originY)) : height/2;
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
