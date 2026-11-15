// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: Motion.qml (theme layer, shared singleton) — the pill family's motion
// tokens: durations that collapse when the shell's animations gate is off and
// scale with the user's motionSpeed.
// REL: Theme.qml (animations gate, motionSpeed); iNiR modules/common/pill/
// PillMotion.qml @ edca6cc (GNU GPL version 3) for the token set — independent
// rewrite, see THIRD_PARTY.md.
pragma Singleton
import QtQuick

QtObject {
    readonly property real mult: Theme.animations ? 1 : 0

    function scaled(ms) { return Math.round(ms * mult / Theme.motionSpeed) }

    readonly property int fast: scaled(140)
    readonly property int standard: scaled(300)
    readonly property int morph: scaled(420)
    readonly property int shapeshift: scaled(820)
    readonly property int glide: scaled(260)
    readonly property int heat: scaled(1100)
    readonly property int pulse: scaled(420)

    readonly property int easeStandard: Easing.OutCubic
    readonly property int easeMorph: Easing.BezierSpline
    readonly property var morphCurve: [0.16, 1, 0.3, 1, 1, 1]

    readonly property real rSmall: 7
    readonly property real rTile: 13
}
