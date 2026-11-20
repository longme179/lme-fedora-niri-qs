// Role: MotionAnimation.qml (shared layer, fan-in 14).
// Shared component/helper; keep API stable for wide QML reuse.
// The number-animation factory: role picks the curve family (spatial,
// spatialFast, effects, exit); ms overrides the token duration (still scaled
// and gated). Empty role plus large keeps the legacy slide/spatial pairing.
import QtQuick
import "../theme"

NumberAnimation {
    property bool large: false
    property string role: ""
    property int ms: 0
    duration: Motion.durationFor(role, large, ms)
    easing.type: Easing.BezierSpline
    easing.bezierCurve: role === "" ? (large ? Theme.spatialCurve : Theme.fastSpatialCurve) : Motion.curveFor(role)
}
