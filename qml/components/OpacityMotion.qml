// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: OpacityMotion.qml (shared layer) — the fade factory: monotonic
// effects curve for opacity/amount changes; exit flips to the exit curve.
// REL: qml/theme/Motion.qml (fade tokens, curve set); sibling of
// MotionAnimation/ColorMotion — new fades are born from here.
import QtQuick
import "../theme"

NumberAnimation {
    property bool exit: false
    property int ms: 0
    duration: ms > 0 ? Motion.scaled(ms) : (exit ? Motion.fadeExit : Motion.fade)
    easing.type: Easing.BezierSpline
    easing.bezierCurve: exit ? Motion.curveExit : Motion.curveEffects
}
