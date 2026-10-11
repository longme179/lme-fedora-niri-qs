import QtQuick
import "../theme"

NumberAnimation {
    property bool large: false
    duration: large ? Theme.slideDuration : Theme.animationDuration
    easing.type: Easing.BezierSpline
    easing.bezierCurve: large ? Theme.spatialCurve : Theme.fastSpatialCurve
}
