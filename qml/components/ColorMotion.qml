// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: ColorMotion.qml (shared layer, fan-in 10).
// Shared component/helper; keep API stable for wide QML reuse.
import QtQuick
import "../theme"

ColorAnimation {
    duration: Theme.animationDuration
    easing.type: Easing.BezierSpline
    easing.bezierCurve: Theme.effectsCurve
}
