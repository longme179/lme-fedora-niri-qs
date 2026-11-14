// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockCaptureNotice.qml (lock layer, fan-in 1 — LockSurface's capture
// policy notice). Not an iNiR port: iNiR ships no lock-capture feedback and its
// niri config has the same locked-session refusal. This answers the owner's L3
// walkthrough finding that Print on the lock was perfectly silent: niri refuses
// all screencopy while the session is locked (compositor security, like
// Android/iOS), and the capture toasts live on layers below the
// WlSessionLockSurface. The notice rides the ShellState attempt deadlines that
// takeScreenshot/startRecording bump — instant, and independent of the error
// path the backend takes afterwards.
// REL: LockContext (context.locked), ShellState (attempt deadlines), Theme,
// ShellText (components).
pragma ComponentBehavior: Bound
import QtQuick
import "../../services"
import "../../theme"
import "../../components"

Rectangle {
    id: root
    required property var context

    property bool notice: false
    property string noticeText: ""
    property int noticeMs: 2500

    z: 50
    visible: opacity > 0
    opacity: root.notice ? 1 : 0
    radius: 16
    color: Theme.panel
    border.width: 1
    border.color: Theme.border
    implicitWidth: noticeLabel.implicitWidth + 32
    implicitHeight: noticeLabel.implicitHeight + 18

    Behavior on opacity {
        enabled: Theme.animations
        NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic }
    }

    Connections {
        target: ShellState
        function onCaptureDeadlineChanged() {
            if (root.context.locked) {
                root.noticeText = "Screenshots are disabled while locked";
                root.notice = true;
                noticeTimer.restart();
            }
        }
        function onRecordDeadlineChanged() {
            if (root.context.locked) {
                root.noticeText = "Screen recording is disabled while locked";
                root.notice = true;
                noticeTimer.restart();
            }
        }
    }

    Timer {
        id: noticeTimer
        interval: root.noticeMs
        onTriggered: root.notice = false
    }

    ShellText {
        id: noticeLabel
        anchors.centerIn: parent
        text: root.noticeText
        color: Theme.muted
        font.family: Theme.fontFamily
        font.pixelSize: 12
    }
}
