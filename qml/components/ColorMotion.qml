// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import "../theme"

ColorAnimation {
    duration: Theme.animationDuration
    easing.type: Easing.BezierSpline
    easing.bezierCurve: Theme.effectsCurve
}
