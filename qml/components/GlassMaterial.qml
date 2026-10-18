// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import "../theme"
import "../services"

Item {
    id: root
    property real radius: 20
    property real topLeftRadius: radius
    property real topRightRadius: radius
    property real bottomLeftRadius: radius
    property real bottomRightRadius: radius
    property bool hovered: false
    property bool pressed: false
    readonly property bool software: GraphicsInfo.api === GraphicsInfo.Software
    readonly property var hostWindow: Window.window
    readonly property bool active: Theme.liquidGlass && visible && width > 0 && height > 0 && !!hostWindow && hostWindow.visible
    readonly property bool lightEnabled: active && enabled && !software && Theme.animations
    property var backdrop: null
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
    onPointerScenePositionChanged: if (lightEnabled && pointer.hovered && renderWindow) renderWindow.update()
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
    onActiveChanged: updateBackdrop()
    onSoftwareChanged: updateBackdrop()
    onParentChanged: Qt.callLater(updateBackdrop)
    onHostWindowChanged: { hasPointer = false; updateBackdrop(); }
    Component.onCompleted: updateBackdrop()
    Component.onDestruction: if (backdrop) GlassState.release(backdrop)
    readonly property var sampleInputs: backdrop ? [backdrop.windowOrigin, backdrop.cropRect, backdrop.outputWidth, backdrop.outputHeight] : null
    property rect sampleRect: Qt.rect(0, 0, 1, 1)
    readonly property var renderWindow: Window.window
    function invalidateSample() {
        if (!backdrop) sampleRect = Qt.rect(0, 0, 1, 1);
        else if (renderWindow) renderWindow.update();
    }
    onSampleInputsChanged: invalidateSample()
    onRenderWindowChanged: invalidateSample()
    function updateSample() {
        if (!active || !backdrop) return;
        const a = root.mapToItem(null, 0, 0);
        const b = root.mapToItem(null, width, height);
        const origin = backdrop.windowOrigin;
        const crop = backdrop.cropRect;
        sampleRect = Qt.rect(crop.x + (origin.x + a.x) / backdrop.outputWidth * crop.width, crop.y + (origin.y + a.y) / backdrop.outputHeight * crop.height,
            (b.x - a.x) / backdrop.outputWidth * crop.width, (b.y - a.y) / backdrop.outputHeight * crop.height);
    }
    Connections {
        target: root.active ? root.renderWindow : null
        // Map glass and pointer coordinates once per rendered frame, without ancestor bindings.
        function onAfterAnimating() { root.updateLight(); root.updateSample(); }
    }
    HoverHandler { id: pointer; enabled: root.lightEnabled }
    Loader {
        anchors.fill: parent
        active: root.active
        sourceComponent: root.software ? fallback : optical
    }
    Component {
        id: fallback
        Rectangle {
            radius: root.radius
            color: Qt.rgba(0, 0, 0, 1 - (Theme.glass.brightness ?? 1)); border.width: 1; border.color: "#60ffffff"
            topLeftRadius: root.topLeftRadius < 0 ? root.radius : root.topLeftRadius
            topRightRadius: root.topRightRadius < 0 ? root.radius : root.topRightRadius
            bottomLeftRadius: root.bottomLeftRadius < 0 ? root.radius : root.bottomLeftRadius
            bottomRightRadius: root.bottomRightRadius < 0 ? root.radius : root.bottomRightRadius
        }
    }
    Component {
        id: optical
        GlassOptics {
            src: root.backdrop
            sourceAvailable: root.backdrop && root.backdrop.status === Image.Ready ? 1 : 0
            sourceRect: root.sampleRect
            topLeftRadius: root.topLeftRadius < 0 ? root.radius : root.topLeftRadius
            topRightRadius: root.topRightRadius < 0 ? root.radius : root.topRightRadius
            bottomLeftRadius: root.bottomLeftRadius < 0 ? root.radius : root.bottomLeftRadius
            bottomRightRadius: root.bottomRightRadius < 0 ? root.radius : root.bottomRightRadius
            cursorPos: root.lightPosition
            hover: root.hoverAmount; energy: root.pressAmount
            tintAmount: 0; clear: 1; frost: .9 * (Theme.glass.blur ?? 1); dispersion: .025; rim: .38 * (Theme.glass.rim ?? 1)
            brightness: Theme.glass.brightness ?? 1
            feather: Theme.glass.feather ?? 1
            smearing: Theme.glass.smearing ?? 1
            bezel: Math.max(2, Math.min(8, Math.min(width, height) * .14)) * (Theme.glass.edgeWidth ?? 1)
        }
    }
}
