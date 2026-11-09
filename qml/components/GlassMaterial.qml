// SPDX-License-Identifier: GPL-3.0-or-later
// Glass material/shader binding for shell surfaces; selects blur/optics paths from settings/capabilities.
// REL: qml/components/GlassOptics.qml, qml/components/shaders/liquid-glass.frag(.qsb) – uniforms/effects.
// GOTCHA: Shader/material changes affect many surfaces; keep fallbacks for unsupported/backdrop cases.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import "../theme"
import "../services"
import "GlassNesting.js" as GlassNesting

Item {
    id: root
    property real radius: 20
    property real topLeftRadius: radius
    property real topRightRadius: radius
    property real bottomLeftRadius: radius
    property real bottomRightRadius: radius
    property real shadow: 0
    readonly property real pad: shadow > 0 ? Theme.glassShadowPad : 0
    property bool hovered: false
    property bool pressed: false
    readonly property bool software: GraphicsInfo.api === GraphicsInfo.Software
    readonly property var hostWindow: Window.window
    readonly property bool active: Theme.liquidGlass && visible && width > 0 && height > 0 && !!hostWindow && hostWindow.visible
    readonly property bool lightEnabled: active && enabled && !software && Theme.animations
    // Glass-on-glass nesting (Liquid Glass 2.0, gap G1): every ancestor stratum
    // carrying a glass surface below this one attenuates its rim and grain
    // instead of compounding them.
    readonly property bool isGlassFill: true
    property bool allowed: true
    property int nestLevel: 0
    readonly property real nest: Math.min(1, nestLevel * 0.5)
    property var nestWatched: []
    property int nestWalks: 0
    readonly property real baseRim: .45 * (Theme.glass.rim ?? 1)
    property bool hasPointer: false
    readonly property point pointerScenePosition: pointer.point.scenePosition
    readonly property point lightPosition: hasPointer ? Qt.point(lightX.value, lightY.value) : Qt.point(width / 2, height / 2)
    property real hoverAmount: lightEnabled && (hovered || pointer.hovered) ? 1 : 0
    property real pressAmount: active && Theme.animations && pressed ? 1 : 0
    objectName: "glassMaterial"
    Behavior on hoverAmount { enabled: root.active && Theme.animations; NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic } }
    Behavior on pressAmount { enabled: root.active && Theme.animations; NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic } }
    onHoverAmountChanged: if (hoverAmount === 0) hasPointer = false
    onLightEnabledChanged: if (!lightEnabled && hoverAmount === 0) hasPointer = false
    SpringMotion {
        id: lightX; objectName: "glassLightX"
        enabled: root.lightEnabled && Theme.springMotion && root.hoverAmount > 0
        stiffness: Theme.springStiffness(false) * 2
        damping: 2 * Math.sqrt(stiffness)
        positionEpsilon: .12; velocityEpsilon: 1
    }
    SpringMotion {
        id: lightY; objectName: "glassLightY"
        enabled: lightX.enabled; stiffness: lightX.stiffness; damping: lightX.damping
        positionEpsilon: lightX.positionEpsilon; velocityEpsilon: lightX.velocityEpsilon
    }
    function updateLight() {
        if (!lightEnabled || !pointer.hovered) return;
        const point = root.mapFromItem(null, pointerScenePosition.x, pointerScenePosition.y);
        const x = Math.max(0, Math.min(width, point.x)), y = Math.max(0, Math.min(height, point.y));
        if (!hasPointer) { lightX.snapTo(x); lightY.snapTo(y); hasPointer = true; }
        else { lightX.retarget(x); lightY.retarget(y); }
    }
    function nestingStop() {
        return hostWindow ? hostWindow.contentItem : null;
    }
    function updateNest() {
        nestWalks++;
        const stop = root.hostWindow ? root.hostWindow.contentItem : null;
        nestLevel = GlassNesting.nestLevel(root, stop);
        const domain = [];
        let a = root.parent, depth = 0;
        while (a && a !== stop && depth < 48) { domain.push(a); a = a.parent; depth++; }
        let same = domain.length === nestWatched.length;
        for (let i = 0; same && i < domain.length; i++) same = domain[i] === nestWatched[i];
        if (!same) nestWatched = domain;
    }
    function scheduleNestUpdate() { nestTimer.restart() }
    Timer { id: nestTimer; interval: 0; onTriggered: root.updateNest() }
    onActiveChanged: scheduleNestUpdate()
    onParentChanged: { Qt.callLater(updateNest); scheduleNestUpdate(); }
    onHostWindowChanged: { hasPointer = false; scheduleNestUpdate(); }
    Component.onCompleted: updateNest()
    readonly property var renderWindow: Window.window
    Connections {
        target: root.active && root.lightEnabled ? root.renderWindow : null
        function onAfterAnimating() {
            if (FrameLogger.enabled) FrameLogger.sample(Date.now(), "glass");
            if (pointer.hovered || root.hoverAmount > 0) root.updateLight();
        }
    }
    HoverHandler { id: pointer; enabled: root.lightEnabled }
    Instantiator {
        model: root.nestWatched
        delegate: Connections {
            required property var modelData
            target: modelData
            function onChildrenChanged() { root.scheduleNestUpdate() }
        }
    }
    Item {
        id: glassFrame
        anchors.centerIn: parent
        width: root.width + root.pad * 2
        height: root.height + root.pad * 2
        visible: root.active
        Loader {
            anchors.fill: parent
            active: root.active
            sourceComponent: root.software ? fallback : optical
        }
    }
    Component {
        id: fallback
        Rectangle {
            anchors.centerIn: parent
            width: root.width
            height: root.height
            radius: root.radius
            color: Qt.rgba(0, 0, 0, 0); border.width: 1; border.color: "#60ffffff"
            topLeftRadius: root.topLeftRadius < 0 ? root.radius : root.topLeftRadius
            topRightRadius: root.topRightRadius < 0 ? root.radius : root.topRightRadius
            bottomLeftRadius: root.bottomLeftRadius < 0 ? root.radius : root.bottomLeftRadius
            bottomRightRadius: root.bottomRightRadius < 0 ? root.radius : root.bottomRightRadius
        }
    }
    Component {
        id: optical
        GlassOptics {
            anchors.fill: parent
            panelOpacity: Theme.panelOpacity
            grain: Theme.glass.grain ?? 0.004
            topLeftRadius: root.topLeftRadius < 0 ? root.radius : root.topLeftRadius
            topRightRadius: root.topRightRadius < 0 ? root.radius : root.topRightRadius
            bottomLeftRadius: root.bottomLeftRadius < 0 ? root.radius : root.bottomLeftRadius
            bottomRightRadius: root.bottomRightRadius < 0 ? root.radius : root.bottomRightRadius
            glassPad: root.pad
            shadowAmt: root.shadow * (1 - 0.6 * root.nest)
            tintColor: Theme.panel; tintAmount: 0.35 * 0.5 * (1 - 0.5 * root.nest)
            rim: root.baseRim * (1 - .35 * root.nest); nest: root.nest
            bezel: Math.max(3, Math.min(14, Math.min(root.width, root.height) * .28)) * (Theme.glass.edgeWidth ?? 1)
        }
    }
}
