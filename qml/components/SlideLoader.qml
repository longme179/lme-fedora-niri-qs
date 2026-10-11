import QtQuick
import "../theme"

Loader {
    id: root
    property bool shown: true
    property Component content
    property Component retainedContent
    property string direction: "right"
    property real progress: 0
    property bool mounted: false
    readonly property bool transitioning: motion.running
    readonly property real slideOffset: (1 - progress) * (direction === "right" ? 92 : direction === "down" ? -32 : 64)
    active: mounted
    enabled: shown
    sourceComponent: retainedContent
    transform: [
        Translate { x: root.direction === "right" ? root.slideOffset : 0; y: root.direction === "right" ? 0 : root.slideOffset },
        Scale {
            origin.x: root.direction === "right" ? root.width : root.width / 2
            origin.y: root.direction === "down" ? 0 : root.height / 2
            xScale: 1 - (1 - root.progress) * Theme.deformation
            yScale: 1 + (1 - root.progress) * Theme.deformation
        }
    ]
    function move(to) {
        if (to === 1) mounted = true;
        motion.stop();
        if (!Theme.animations) { progress = to; if (to === 0) mounted = false; return; }
        motion.to = to; motion.start();
    }
    function replay() { progress = 0; move(shown ? 1 : 0); }
    onShownChanged: { if (shown) retainedContent = content; if (shown || mounted) move(shown ? 1 : 0); }
    onContentChanged: if (shown) { retainedContent = content; replay(); }
    Component.onCompleted: if (shown) { retainedContent = content; move(1); }
    onLoaded: {
        const panel = item as Item;
        if (panel && shown) panel.forceActiveFocus();
        if (shown) replay();
    }
    MotionAnimation {
        id: motion; target: root; property: "progress"; large: true
        duration: to === 0 ? (Theme.animations ? Math.round(200 / Theme.motionSpeed) : 0) : Theme.slideDuration
        easing.bezierCurve: to === 0 ? Theme.exitCurve : Theme.spatialCurve
        onFinished: if (!root.shown) root.mounted = false
    }
    Connections { target: Theme; function onAnimationsChanged() { if (!Theme.animations) { motion.stop(); root.progress = root.shown ? 1 : 0; root.mounted = root.shown; } } }
}
