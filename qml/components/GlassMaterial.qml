// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import QtQml
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
    // True when the compositor already frosts the app pixels behind this
    // surface (true-backdrop preset applied, niri >= 26.04, and this
    // surface's blur region active). The bar overrides this with the bar
    // flag; every other host keeps the popup flag. False keeps the
    // wallpaper-lens behavior (frosted preset / older niri / no blur).
    property bool compositorBlur: Theme.compositorPopupBlur
    readonly property bool software: GraphicsInfo.api === GraphicsInfo.Software
    readonly property var hostWindow: Window.window
    readonly property bool active: Theme.liquidGlass && visible && width > 0 && height > 0 && !!hostWindow && hostWindow.visible
    readonly property bool lightEnabled: active && enabled && !software && Theme.animations
    property var backdrop: null
    // Glass-on-glass nesting (Liquid Glass 2.0, gap G1): every ancestor stratum
    // carrying a glass surface below this one attenuates its rim, bevel, veil
    // and grain instead of compounding them. Upstream mapping: nest = min(1, level * 0.5).
    readonly property bool isGlassFill: true
    property bool allowed: true
    property int nestLevel: 0
    readonly property real nest: Math.min(1, nestLevel * 0.5)
    property var nestWatched: []
    property int nestWalks: 0
    readonly property real baseRim: .45 * (Theme.glass.rim ?? 1)
    readonly property real baseFrost: 2.2 * (Theme.glass.blur ?? 1)
    property bool hasPointer: false
    readonly property point pointerScenePosition: pointer.point.scenePosition
    readonly property point lightPosition: hasPointer ? Qt.point(lightX.value, lightY.value) : Qt.point(width / 2, height / 2)
    property real hoverAmount: lightEnabled && (hovered || pointer.hovered) ? 1 : 0
    property real pressAmount: active && Theme.animations && pressed ? 1 : 0
    objectName: "glassMaterial"
    Behavior on hoverAmount { enabled: root.active && Theme.animations; NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic } }
    Behavior on pressAmount { enabled: root.active && Theme.animations; NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic } }
    onHoverAmountChanged: { if (hoverAmount === 0) hasPointer = false; dirty = true }
    onLightEnabledChanged: if (!lightEnabled && hoverAmount === 0) hasPointer = false
    onPointerScenePositionChanged: { if (lightEnabled && pointer.hovered) { dirty = true; if (renderWindow) renderWindow.update(); } }
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
    function updateBackdrop() {
        if (backdrop && (!active || software || backdrop.hostWindow !== hostWindow)) { GlassState.release(backdrop); backdrop = null; }
        if (active && !software && !backdrop) backdrop = GlassState.acquire(hostWindow);
    }
    // The walk stops below the stratum that hosts the shared backdrop; without
    // one (software rendering) the window content root bounds the domain instead.
    function nestingStop() {
        return backdrop && backdrop.parent ? backdrop.parent : (hostWindow ? hostWindow.contentItem : null);
    }
    function updateNest() {
        nestWalks++;
        const stop = nestingStop();
        nestLevel = GlassNesting.nestLevel(root, stop, false);
        const domain = [];
        let a = root.parent, depth = 0;
        while (a && a !== stop && depth < 48) { domain.push(a); a = a.parent; depth++; }
        let same = domain.length === nestWatched.length;
        for (let i = 0; same && i < domain.length; i++) same = domain[i] === nestWatched[i];
        if (!same) nestWatched = domain;
    }
    // A 0 ms child timer rather than Qt.callLater: a callLater closure outlives a
    // destroyed material and fires in an invalid context ("Property 'nestingStop'
    // ... is not a function" TypeErrors, caught by test_navigation's log scan),
    // while the timer dies with its parent and restart() still coalesces a burst
    // of tree events into exactly one walk per event-loop batch.
    function scheduleNestUpdate() { nestTimer.restart() }
    Timer { id: nestTimer; interval: 0; onTriggered: root.updateNest() }
    onActiveChanged: { dirty = true; updateBackdrop() }
    onSoftwareChanged: updateBackdrop()
    onBackdropChanged: { dirty = true; scheduleNestUpdate() }
    onParentChanged: { dirty = true; invalidateSample(); Qt.callLater(updateBackdrop); scheduleNestUpdate(); }
    onHostWindowChanged: { hasPointer = false; dirty = true; invalidateSample(); updateBackdrop(); scheduleNestUpdate(); }
    Component.onCompleted: { updateBackdrop(); updateNest(); }
    Component.onDestruction: if (backdrop) GlassState.release(backdrop)
    readonly property var sampleInputs: backdrop ? [backdrop.windowOrigin, backdrop.cropRect, backdrop.outputWidth, backdrop.outputHeight] : null
    property rect sampleRect: Qt.rect(0, 0, 1, 1)
    readonly property var renderWindow: Window.window
    function invalidateSample() {
        if (!backdrop) sampleRect = Qt.rect(0, 0, 1, 1);
        else if (renderWindow) renderWindow.update();
    }
    onSampleInputsChanged: { dirty = true; invalidateSample() }
    onRenderWindowChanged: { dirty = true; invalidateSample() }
    property bool dirty: true
    property int sampleCalls: 0
    onHoveredChanged: dirty = true
    onWidthChanged: dirty = true
    onHeightChanged: dirty = true
    onXChanged: dirty = true
    onYChanged: dirty = true
    onShadowChanged: dirty = true
    onVisibleChanged: dirty = true
    function updateSample() {
        if (!active || !backdrop) return;
        sampleCalls++;
        const a = root.mapToItem(null, -root.pad, -root.pad);
        const b = root.mapToItem(null, width + root.pad, height + root.pad);
        const origin = backdrop.windowOrigin;
        const crop = backdrop.cropRect;
        sampleRect = Qt.rect(crop.x + (origin.x + a.x) / backdrop.outputWidth * crop.width, crop.y + (origin.y + a.y) / backdrop.outputHeight * crop.height,
            (b.x - a.x) / backdrop.outputWidth * crop.width, (b.y - a.y) / backdrop.outputHeight * crop.height);
    }
    Connections {
        target: root.active ? root.renderWindow : null
        // Map glass and pointer coordinates once per rendered frame, without ancestor bindings.
        function onAfterAnimating() { if (FrameLogger.enabled) FrameLogger.sample(Date.now(), root.compositorBlur ? "true" : "lens"); if (!root.dirty) return; root.dirty = false; if (pointer.hovered || root.hoverAmount > 0) root.updateLight(); root.updateSample(); }
    }
    HoverHandler { id: pointer; enabled: root.lightEnabled }
    // Watched ancestors re-walk on tree events only; animation frames never
    // touch the level (docs/NEXT_OPTIMIZATION_PLAN.md upstream-walk warning).
    Instantiator {
        model: root.nestWatched
        delegate: Connections {
            required property var modelData
            target: modelData
            function onChildrenChanged() { root.scheduleNestUpdate() }
            function onXChanged() { root.dirty = true }
            function onYChanged() { root.dirty = true }
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
            // Software fallback has no shadow; keep the pill at panel size
            // inside the inflated frame.
            anchors.centerIn: parent
            width: root.width
            height: root.height
            radius: root.radius
            // Software fallback: the panel fill underneath already paints the
            // body; this only keeps the hairline visible (no brightness knob).
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
            src: root.backdrop
            sourceAvailable: root.backdrop && root.backdrop.status === Image.Ready ? 1 : 0
            compositorBlur: root.compositorBlur ? 1 : 0
            yieldOpacity: Theme.panelOpacity
            adaptiveContrast: Theme.adaptiveContrast ? 1 : 0
            grain: Theme.glass.grain ?? 0.004
            sourceRect: root.sampleRect
            topLeftRadius: root.topLeftRadius < 0 ? root.radius : root.topLeftRadius
            topRightRadius: root.topRightRadius < 0 ? root.radius : root.topRightRadius
            bottomLeftRadius: root.bottomLeftRadius < 0 ? root.radius : root.bottomLeftRadius
            bottomRightRadius: root.bottomRightRadius < 0 ? root.radius : root.bottomRightRadius
            glassPad: root.pad
            shadowAmt: root.shadow * (1 - 0.6 * root.nest)
            cursorPos: root.pad > 0 ? Qt.point(root.lightPosition.x + root.pad, root.lightPosition.y + root.pad) : root.lightPosition
            hover: root.hoverAmount; energy: root.pressAmount
            tintColor: Theme.panel; tintAmount: 0.35 * 0.5 * (1 - 0.5 * root.nest)
            clear: root.nestLevel >= 1 ? 1 : 0
            frost: root.nestLevel >= 1 ? Math.min(root.baseFrost, 1) : root.baseFrost
            dispersion: .02; saturation: 1.0; rim: root.baseRim * (1 - .35 * root.nest); nest: root.nest
            bezel: Math.max(3, Math.min(14, Math.min(root.width, root.height) * .28)) * (Theme.glass.edgeWidth ?? 1)
            thickness: bezel * 0.8
        }
    }
}
