// SPDX-License-Identifier: GPL-3.0-or-later
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
