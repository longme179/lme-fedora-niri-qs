// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Quickshell
import "../theme"

Popup {
    id: root
    property bool mounted: false
    property bool positioned: false
    property bool opening: false
    property real requested: 0
    property real curveProgress: 0
    property real travelX: 0
    property real travelY: 0
    readonly property real progress: Theme.springMotion ? spring.value : curveProgress
    readonly property Item surface: background ? background.parent : contentItem ? contentItem.parent : null
    readonly property Region glassBlurRegion: SurfaceBlurRegion { surface: root.positioned ? root.background : null; popup: true }
    opacity: positioned ? 1 : 0
    popupType: Popup.Item
    MotionValue {
        id: spring; large: true; target: root.requested; enabled: root.mounted; positionEpsilon: .001
        damping: root.requested ? Math.max(Theme.springDamping(true), 1.6 * Math.sqrt(stiffness)) : 2 * Math.sqrt(stiffness)
        driver.running: spring.enabled && Theme.springMotion && spring.running && !spring.effectiveReducedMotion
    }
    property Translate shift: Translate {
        x: root.travelX * (1 - root.progress)
        y: root.travelY * (1 - root.progress)
    }
    function attach() { if (surface && shift && !surface.transform.includes(shift)) surface.transform.push(shift); }
    onSurfaceChanged: attach()
    Component.onCompleted: attach()
    PopupElasticity {
        objectName: "popupElasticity"
        parent: root.surface
        surface: root.surface; mounted: root.mounted
        horizontal: root.travelX !== 0
        velocity: -(horizontal ? root.travelX : root.travelY) * spring.velocity
    }
    function move(to) {
        curve.stop(); requested = to;
        if (!Theme.animations) { spring.snapTo(to); curveProgress = to; }
        else if (!Theme.springMotion) { curve.to = to; curve.start(); }
    }
    onAboutToShow: {
        opening = true;
        if (!mounted) {
            spring.snapTo(0); curveProgress = 0; mounted = true; positioned = false;
            // Qt resolves popup placement after aboutToShow; hide until its entry is seeded.
            Qt.callLater(() => {
                if (!root.mounted || !root.visible || !root.opening) return;
                const origin = root.parent ? root.parent.mapToItem(null, root.x, root.y) : Qt.point(root.x, root.y);
                const viewport = root.parent ? root.parent.Window.window : null;
                const gaps = [origin.x, (viewport ? viewport.width : root.width) - origin.x - root.width,
                    origin.y, (viewport ? viewport.height : root.height) - origin.y - root.height];
                const edge = gaps.indexOf(Math.min(...gaps));
                root.travelX = edge === 0 ? -(origin.x + root.width + 16) * 1.3 : edge === 1 ? (root.width + gaps[1] + 16) * 1.3 : 0;
                root.travelY = edge === 2 ? -(origin.y + root.height + 16) * 1.3 : edge === 3 ? (root.height + gaps[3] + 16) * 1.3 : 0;
                root.positioned = true;
                root.move(1);
            });
        } else move(1);
    }
    onAboutToHide: { opening = false; move(0); }
    onClosed: { mounted = false; positioned = false; curve.stop(); spring.snapTo(0); curveProgress = 0; }
    enter: Transition { PauseAnimation { duration: Theme.animations ? Math.round(160 / Theme.motionSpeed) : 0 } }
    exit: Transition { PauseAnimation { duration: Theme.animations && root.positioned ? Math.round(200 / Theme.motionSpeed) : 0 } }
    NumberAnimation {
        id: curve; target: root; property: "curveProgress"
        duration: root.requested ? Theme.slideDuration : Math.round(200 / Theme.motionSpeed)
        easing.type: Easing.BezierSpline; easing.bezierCurve: root.requested ? Theme.effectsCurve : Theme.exitCurve
    }
    Connections {
        target: Theme
        function onSpringMotionChanged() {
            if (!root.mounted || !root.positioned) return;
            if (Theme.springMotion) { spring.value = root.curveProgress; spring.velocity = 0; spring.retarget(root.requested); }
            else { root.curveProgress = spring.value; root.move(root.requested); }
        }
        function onAnimationsChanged() { if (!Theme.animations) { curve.stop(); spring.snapTo(root.requested); root.curveProgress = root.requested; } }
    }
}
