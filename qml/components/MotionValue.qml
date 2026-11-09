// SPDX-License-Identifier: GPL-3.0-or-later
// Role: MotionValue.qml (shared layer, fan-in 8).
// Shared component/helper; keep API stable for wide QML reuse.
import QtQuick
import "../theme"

SpringMotion {
    property bool large: false
    property real response: 1
    enabled: Theme.springMotion
    stiffness: Theme.springStiffness(large) * response * response
    damping: Theme.springDamping(large) * response
    positionEpsilon: .02
    velocityEpsilon: .02
    onTargetChanged: retarget(target)
    Component.onCompleted: snapTo(target)
}
