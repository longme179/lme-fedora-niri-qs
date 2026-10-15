// SPDX-License-Identifier: GPL-3.0-or-later
// Rotation lifecycle inspired by iNiR's MaterialLoadingIndicator; see THIRD_PARTY.md.
import QtQuick
import QtQuick.Window
import "../theme"

Item {
    id: root
    property bool animate: true
    property color accent: Theme.notificationAccent
    readonly property bool animating: animate && Theme.animations && visible && (Window.window?.visible ?? false)
    implicitWidth: 36; implicitHeight: 36
    MorphShape {
        anchors.fill: parent
        shape: "flower"
        color: Theme.alpha(root.accent, .12)
        strokeColor: Theme.alpha(root.accent, .55); strokeWidth: 1
        RotationAnimator on rotation {
            running: root.animating
            from: 0; to: 360; loops: Animation.Infinite
            duration: Theme.notificationIdleSpeed * 1000
        }
    }
    ShellIcon { anchors.centerIn: parent; width: 18; height: 18; name: "bell"; color: root.accent }
}
