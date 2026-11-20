// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: Motion.qml (theme layer, shared singleton) — the motion factory:
// duration tokens that collapse when the shell's animations gate is off and
// scale with the user's motionSpeed, plus the shared curve set and the
// role→curve/duration mapping animation components are born from.
// REL: Theme.qml (animations gate, motionSpeed, spatial/effects curves ported
// from DMS Anims.qml, MIT); iNiR modules/common/pill/PillMotion.qml @ edca6cc
// (GNU GPL version 3) for the pill token set — independent rewrite, see
// THIRD_PARTY.md.
pragma Singleton
import QtQuick

QtObject {
    readonly property real mult: Theme.animations ? 1 : 0

    function scaled(ms) { return Math.round(ms * mult / Theme.motionSpeed) }

    // Pill-family duration tokens (iNiR lineage).
    readonly property int fast: scaled(140)
    readonly property int standard: scaled(300)
    readonly property int morph: scaled(420)
    readonly property int shapeshift: scaled(820)
    readonly property int glide: scaled(260)
    readonly property int heat: scaled(1100)
    readonly property int pulse: scaled(420)

    // Factory duration tokens for fade-family animations.
    readonly property int fade: scaled(180)
    readonly property int fadeExit: scaled(150)
    readonly property int pop: scaled(220)

    readonly property int easeStandard: Easing.OutCubic
    readonly property int easeMorph: Easing.BezierSpline
    readonly property var morphCurve: [0.16, 1, 0.3, 1, 1, 1]

    // Curve roles: spatial curves may overshoot; effects/exit curves stay
    // monotonic so colors, opacity and progress never invert mid-flight.
    readonly property var curveSpatial: Theme.spatialCurve
    readonly property var curveSpatialFast: Theme.fastSpatialCurve
    readonly property var curveEffects: Theme.effectsCurve
    readonly property var curveExit: Theme.exitCurve
    function curveFor(role) {
        return role === "effects" ? curveEffects : role === "exit" ? curveExit
            : role === "spatialFast" ? curveSpatialFast : curveSpatial;
    }
    function durationFor(role, large, ms) {
        if (ms > 0) return scaled(ms);
        if (role === "exit") return fadeExit;
        if (role === "effects") return Theme.animationDuration;
        return large ? Theme.slideDuration : Theme.animationDuration;
    }

    readonly property real rSmall: 7
    readonly property real rTile: 13
}
