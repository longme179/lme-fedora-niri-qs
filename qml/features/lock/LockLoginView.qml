// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockLoginView.qml (lock layer, fan-in 1 — LockSurface's login view).
// Ported from the login half of iNiR's LockSurface.qml @ edca6cc (GPL-3.0): the
// password card (shake on failure), the authenticating indicator, and the power
// buttons. Poweroff/Reboot arm a targetAction and ride the password attempt
// (requirePasswordToPower); Suspend acts immediately — the lock stays engaged.
// REL: LockContext (context) — no direct service access beyond Theme/ShellState.run.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../theme"
import "../../components"

ColumnLayout {
    id: root
    required property var context
    property bool hasAttemptedUnlock: false
    readonly property alias passwordActiveFocus: passwordField.activeFocus
    // Test seam for the failure-state caret policy below.
    readonly property alias caretVisible: passwordField.cursorVisible

    spacing: 12

    function focusPassword(): void {
        passwordField.forceActiveFocus();
    }

    function submit(): void {
        if (root.context.currentText.length === 0 || root.context.unlockInProgress)
            return;
        root.hasAttemptedUnlock = true;
        root.context.tryUnlock(false); // Ctrl+Enter goes through the surface's key handler
    }

    function requestTarget(action): void {
        root.context.targetAction = action;
        passwordField.forceActiveFocus();
    }

    // ---- password card ------------------------------------------------------
    Rectangle {
        id: passwordCard
        property real shakeOffset: 0
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: 380
        Layout.preferredHeight: 64
        radius: 18
        color: Theme.panel
        border.width: 1
        border.color: root.context.showFailure ? Theme.red : Theme.border
        x: shakeOffset

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 10
            spacing: 10

            ShellText {
                text: root.context.targetAction === LockContext.ActionEnum.Poweroff ? "Password to shut down"
                    : root.context.targetAction === LockContext.ActionEnum.Reboot ? "Password to restart"
                    : root.context.showFailure ? "Incorrect password"
                    : "Enter password"
                color: root.context.showFailure ? Theme.red : Theme.muted
                font.family: Theme.fontFamily
                font.pixelSize: 12
                Layout.fillWidth: true
            }

            TextInput {
                id: passwordField
                Layout.preferredWidth: 200
                font.family: Theme.fontFamily
                font.pixelSize: 16
                color: Theme.text
                echoMode: TextInput.Password
                passwordCharacter: "●"
                clip: true
                activeFocusOnPress: true
                text: root.context.currentText
                onTextEdited: root.context.currentText = text
                onAccepted: root.submit()
                onActiveFocusChanged: if (activeFocus) cursorPosition = length
                // A failed attempt clears the field but keeps focus, so the blinking
                // caret sat at position 0 right beside "Incorrect password" and read
                // as part of the message (owner L1 walkthrough nit). Hide it while
                // the failure is up; the first keystroke clears showFailure
                // (LockContext) and this binding restores the caret.
                cursorVisible: !root.context.showFailure
            }

            LiquidButton {
                text: root.context.unlockInProgress ? "•••"
                    : root.context.targetAction === LockContext.ActionEnum.Poweroff ? "⏻"
                    : root.context.targetAction === LockContext.ActionEnum.Reboot ? "↻"
                    : "→"
                enabled: !root.context.unlockInProgress
                onClicked: root.submit()
                palette.button: Theme.surface
                palette.buttonText: Theme.text
            }
        }

        // The wrong-password shake (iNiR): the context clears the text and raises
        // showFailure; only an attempt we started shakes the card.
        SequentialAnimation {
            id: wrongPasswordShake
            NumberAnimation { target: passwordCard; property: "shakeOffset"; to: -18; duration: 50 }
            NumberAnimation { target: passwordCard; property: "shakeOffset"; to: 18; duration: 50 }
            NumberAnimation { target: passwordCard; property: "shakeOffset"; to: -10; duration: 40 }
            NumberAnimation { target: passwordCard; property: "shakeOffset"; to: 10; duration: 40 }
            NumberAnimation { target: passwordCard; property: "shakeOffset"; to: 0; duration: 30 }
        }
        Connections {
            target: root.context
            function onShowFailureChanged() {
                if (root.context.showFailure && root.hasAttemptedUnlock)
                    wrongPasswordShake.restart();
            }
        }
    }

    ShellText {
        Layout.alignment: Qt.AlignHCenter
        text: root.context.unlockInProgress ? "Checking…" : ""
        color: Theme.muted
        font.family: Theme.fontFamily
        font.pixelSize: 11
    }

    // ---- power buttons ------------------------------------------------------
    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        spacing: 10

        LiquidButton {
            text: "Suspend"
            onClicked: ShellState.run("suspend")
            palette.button: Theme.surface
            palette.buttonText: Theme.text
        }
        LiquidButton {
            text: "Restart"
            onClicked: root.requestTarget(LockContext.ActionEnum.Reboot)
            palette.button: Theme.surface
            palette.buttonText: Theme.text
        }
        LiquidButton {
            text: "Shut down"
            onClicked: root.requestTarget(LockContext.ActionEnum.Poweroff)
            palette.button: Theme.surface
            palette.buttonText: Theme.text
        }
    }

    ShellText {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 4
        text: "Ctrl+Enter unlocks and keeps the session awake · Esc clears"
        color: Theme.muted
        font.family: Theme.fontFamily
        font.pixelSize: 10
        opacity: 0.7
    }
}
