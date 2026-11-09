// Role: MotionAnimation.qml (shared layer, fan-in 14).
// Shared component/helper; keep API stable for wide QML reuse.
import QtQuick
import "../theme"

NumberAnimation {
    property bool large: false
    duration: large ? Theme.slideDuration : Theme.animationDuration
    easing.type: Easing.BezierSpline
    easing.bezierCurve: large ? Theme.spatialCurve : Theme.fastSpatialCurve
}
