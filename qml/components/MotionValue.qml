// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: MotionValue.qml (shared layer, fan-in 8).
// Shared component/helper; keep API stable for wide QML reuse.
import QtQuick
import "../theme"

SpringMotion {
    id: root
    property bool large: false
    property real response: 1
    // Opt-in pill-family size morph (A4b): morphMs > 0 replaces the physics
    // spring with a token-timed bezier flight along morphCurve. 0 keeps the
    // spring every other consumer rides, so the default changes nothing.
    property int morphMs: 0
    property var morphCurve: [0.16, 1, 0.3, 1, 1, 1]
    enabled: morphMs > 0 ? Theme.animations : Theme.springMotion
    stiffness: Theme.springStiffness(large) * response * response
    damping: Theme.springDamping(large) * response
    positionEpsilon: .02
    velocityEpsilon: .02
    // A standalone animation targets this object's own value; from/to are set
    // imperatively so a reversal restarts from wherever the flight is now.
    property NumberAnimation morphAnimator: NumberAnimation {
        target: root; property: "value"; duration: Math.max(0, root.morphMs)
        easing.type: Easing.BezierSpline
        easing.bezierCurve: root.morphCurve
    }
    onTargetChanged: morphMs > 0 ? morphRetarget(target) : retarget(target)
    function morphRetarget(v) {
        morphAnimator.stop()
        if (target !== v) target = v
        morphAnimator.from = value
        morphAnimator.to = v
        morphAnimator.restart()
    }
    // Shadows SpringMotion.snapTo: same three writes, plus retiring a morph
    // flight mid-air (warm-up passes and dormant parks snap on purpose).
    function snapTo(v) {
        morphAnimator.stop()
        value = v; velocity = 0; _running = false
    }
    Component.onCompleted: snapTo(target)
}
