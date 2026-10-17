import QtQuick
import "../theme"

Loader {
    id: root
    property bool shown: true
    property Component content
    property Component retainedContent
    property string direction: "right"
    property bool exitToEdge: false
    property bool animateResize: true
    property string exitEdge: "nearest"
    property int travelEdge: -1
    property real exitX: 0
    property real exitY: 0
    property real progress: Theme.springMotion ? spring.value : 0
    property bool mounted: false
    property bool initialized: false
    readonly property bool transitioning: mounted && (motion.running || spring.running || exitSpringX.running || exitSpringY.running || exitMotionX.running || exitMotionY.running)
    readonly property real slideOffset: exitToEdge ? 0 : (1 - progress) * (direction === "right" ? 92 : direction === "down" ? -32 : 64)
    readonly property real offsetX: (direction === "right" ? slideOffset : 0) + (Theme.springMotion ? exitSpringX.value : exitX)
    readonly property real offsetY: (direction === "right" ? 0 : slideOffset) + (Theme.springMotion ? exitSpringY.value : exitY)
    readonly property bool fillsTravelAxis: parent && (travelEdge < 2 ? width >= parent.width - 1 : height >= parent.height - 1)
    // Scale also deforms the translation; include travel before declaring a popup off-screen.
    readonly property real overdraw: Math.max(width, height, Math.abs(offsetX), Math.abs(offsetY)) * Math.abs(Theme.deformation * (1 - progress)) + 2
    readonly property bool outsideViewport: parent && (x + offsetX + width + overdraw < 0 || x + offsetX - overdraw > parent.width || y + offsetY + height + overdraw < 0 || y + offsetY - overdraw > parent.height)
    active: mounted
    enabled: shown
    sourceComponent: retainedContent
    Behavior on width { enabled: root.animateResize && root.shown && root.mounted && root.progress >= .99 && Theme.animations; MotionAnimation { large: true; easing.bezierCurve: Theme.effectsCurve } }
    Behavior on height { enabled: root.animateResize && root.shown && root.mounted && root.progress >= .99 && Theme.animations; MotionAnimation { large: true; easing.bezierCurve: Theme.effectsCurve } }
    transform: [
        Translate { x: root.offsetX; y: root.offsetY },
        Scale {
            origin.x: root.direction === "right" ? root.width : root.width / 2
            origin.y: root.direction === "down" ? 0 : root.height / 2
            xScale: 1 - (1 - root.progress) * Theme.deformation
            yScale: 1 + (1 - root.progress) * Theme.deformation
        }
    ]
    function finishClose() {
        if (shown || !mounted) return;
        // Off-screen content need not wait for the spring's sub-pixel settling tail.
        if (exitToEdge ? !outsideViewport && transitioning : transitioning) return;
        mounted = false;
        motion.stop(); exitMotionX.stop(); exitMotionY.stop();
        spring.snapTo(0); exitSpringX.snapTo(0); exitSpringY.snapTo(0);
        if (!Theme.springMotion) progress = 0;
        exitX = 0; exitY = 0;
        travelEdge = -1;
    }
    function edgeOffset() {
        let dx = 0, dy = 0;
        if (exitToEdge && parent) {
            const gaps = [x, parent.width - x - width, y, parent.height - y - height];
            const forced = ["left", "right", "top", "bottom"].indexOf(exitEdge);
            if (travelEdge < 0) travelEdge = forced >= 0 ? forced : gaps.indexOf(Math.min(...gaps));
            const cushion = Math.max(width, height) * Theme.deformation + 16;
            // Use one edge for the entire lifecycle, including size changes and reversals.
            if (travelEdge === 0) dx = -(x + width + cushion) * 1.3;
            else if (travelEdge === 1) dx = (parent.width - x + cushion) * 1.3;
            else if (travelEdge === 2) dy = -(y + height + cushion) * 1.3;
            else dy = (parent.height - y + cushion) * 1.3;
        }
        return {x: dx, y: dy};
    }
    function moveExit(open) {
        const offset = open ? {x: 0, y: 0} : edgeOffset();
        exitMotionX.stop(); exitMotionY.stop();
        if (Theme.springMotion) { exitSpringX.retarget(offset.x); exitSpringY.retarget(offset.y); }
        else if (Theme.animations) { exitMotionX.to = offset.x; exitMotionY.to = offset.y; exitMotionX.start(); exitMotionY.start(); }
        else { exitX = offset.x; exitY = offset.y; }
    }
    function move(to) {
        if (to === 0 && !mounted) return;
        if (to === 1 && !mounted) {
            travelEdge = -1;
            mounted = true;
            const offset = Theme.animations ? edgeOffset() : {x: 0, y: 0};
            exitSpringX.snapTo(offset.x); exitSpringY.snapTo(offset.y);
            exitX = offset.x; exitY = offset.y;
        }
        motion.stop();
        moveExit(to === 1);
        if (Theme.springMotion) { spring.retarget(to); finishClose(); return; }
        spring.snapTo(to);
        if (!Theme.animations) { progress = to; if (to === 0) mounted = false; return; }
        motion.to = to; motion.start();
    }
    onOutsideViewportChanged: if (outsideViewport) Qt.callLater(finishClose)
    function replay() {
        if (Theme.springMotion) spring.snapTo(0); else progress = 0;
        if (exitToEdge && shown) {
            const offset = edgeOffset();
            exitSpringX.snapTo(offset.x); exitSpringY.snapTo(offset.y);
            exitX = offset.x; exitY = offset.y;
        }
        move(shown ? 1 : 0);
    }
    onShownChanged: if (initialized) { if (shown) retainedContent = content; if (shown || mounted) move(shown ? 1 : 0); }
    onContentChanged: if (initialized && shown) { retainedContent = content; if (!mounted) move(1); }
    Component.onCompleted: { initialized = true; if (shown) { retainedContent = content; move(1); } }
    onLoaded: {
        const panel = item as Item;
        if (panel && shown) panel.forceActiveFocus();
    }
    SpringMotion {
        id: spring; enabled: Theme.springMotion
        stiffness: Theme.springStiffness(true)
        damping: Theme.springDamping(true)
        positionEpsilon: .001; velocityEpsilon: .001
        onRunningChanged: if (!running) Qt.callLater(root.finishClose)
    }
    // Long-distance travel needs bounded bounce; tight native surfaces must not overshoot their clip.
    SpringMotion { id: exitSpringX; enabled: Theme.springMotion; stiffness: spring.stiffness; damping: root.shown && !root.fillsTravelAxis ? Math.max(spring.damping, 1.6 * Math.sqrt(stiffness)) : 2 * Math.sqrt(stiffness); onRunningChanged: if (!running) Qt.callLater(root.finishClose) }
    SpringMotion { id: exitSpringY; enabled: Theme.springMotion; stiffness: spring.stiffness; damping: exitSpringX.damping; onRunningChanged: if (!running) Qt.callLater(root.finishClose) }
    MotionAnimation { id: exitMotionX; target: root; property: "exitX"; duration: root.shown ? Theme.slideDuration : Math.round(200 / Theme.motionSpeed); easing.bezierCurve: root.shown ? Theme.effectsCurve : Theme.exitCurve; onFinished: root.finishClose() }
    MotionAnimation { id: exitMotionY; target: root; property: "exitY"; duration: exitMotionX.duration; easing.bezierCurve: exitMotionX.easing.bezierCurve; onFinished: root.finishClose() }
    MotionAnimation {
        id: motion; target: root; property: "progress"; large: true
        duration: to === 0 ? (Theme.animations ? Math.round(200 / Theme.motionSpeed) : 0) : Theme.slideDuration
        easing.bezierCurve: to === 0 ? Theme.exitCurve : Theme.spatialCurve
        onFinished: root.finishClose()
    }
    Connections {
        target: Theme
        function onSpringMotionChanged() {
            if (Theme.springMotion) { exitSpringX.snapTo(root.exitX); exitSpringY.snapTo(root.exitY); }
            else { root.exitX = exitSpringX.value; root.exitY = exitSpringY.value; }
            root.progress = Qt.binding(() => Theme.springMotion ? spring.value : (root.shown ? 1 : 0));
            root.move(root.shown ? 1 : 0);
        }
        function onAnimationsChanged() {
            if (!Theme.animations) {
                motion.stop(); exitMotionX.stop(); exitMotionY.stop();
                exitSpringX.snapTo(0); exitSpringY.snapTo(0); root.exitX = 0; root.exitY = 0;
                if (Theme.springMotion) spring.snapTo(root.shown ? 1 : 0);
                else root.progress = root.shown ? 1 : 0;
                root.mounted = root.shown;
            }
        }
    }
}
