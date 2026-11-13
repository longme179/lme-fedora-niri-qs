// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockSurface.qml (lock layer, fan-in 1 — instantiated per screen inside
// LockState's WlSessionLockSurface).
// Ported from the interaction half of iNiR's LockSurface.qml @ edca6cc (GPL-3.0):
// the clock→login view machine, any-key capture into the password field, Esc
// semantics, Ctrl+Enter (unlock + keep awake) and the niri focus machinery
// (focusEnsureTimer 100ms×30; the 2s heartbeat lives in LockState).
// REL: LockContext (context), LockWallpaper/LockLoginView (own dir), Theme only.
pragma ComponentBehavior: Bound
import QtQuick
import "../../services"
import "../../theme"
import "../../components"

MouseArea {
    id: root
    required property var context

    // Views: "clock" (initial) or "login" (password entry).
    property string currentView: "clock"
    readonly property bool showLoginView: currentView === "login"
    property bool ctrlHeld: false

    anchors.fill: parent
    hoverEnabled: false
    focus: true

    function switchToLogin(): void {
        root.currentView = "login";
        Qt.callLater(() => loginView.focusPassword());
    }

    function forceFieldFocus(): void {
        if (root.showLoginView && loginView.visible)
            loginView.focusPassword();
        else if (root.visible)
            root.forceActiveFocus();
    }

    LockWallpaper { anchors.fill: parent }

    // ---- clock view (Phase 3 adds weather/battery/status) --------------------
    Column {
        anchors.centerIn: parent
        visible: !root.showLoginView
        spacing: 6

        ShellText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatDateTime(clock.now, "HH:mm")
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Math.min(root.width, root.height) * 0.16
            font.weight: Font.Light
        }
        ShellText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatDateTime(clock.now, "dddd, MMMM d")
            color: Theme.muted
            font.family: Theme.fontFamily
            font.pixelSize: 18
        }
        ShellText {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Press any key to unlock"
            color: Theme.muted
            font.family: Theme.fontFamily
            font.pixelSize: 12
            opacity: 0.7
        }
    }

    // ---- login view ----------------------------------------------------------
    LockLoginView {
        id: loginView
        anchors.centerIn: parent
        visible: root.showLoginView
        context: root.context
    }

    // ---- input handling (iNiR semantics) -------------------------------------
    Keys.onPressed: event => {
        root.context.resetClearTimer();

        if (event.key === Qt.Key_Control) {
            root.ctrlHeld = true;
            return;
        }

        if (event.key === Qt.Key_Escape) {
            if (root.context.currentText.length > 0)
                root.context.currentText = "";
            else if (root.showLoginView)
                root.currentView = "clock";
            event.accepted = true;
            return;
        }

        // Any key switches to the login view and captures the character.
        if (!root.showLoginView) {
            root.currentView = "login";
            const inputChar = event.text;
            Qt.callLater(() => {
                loginView.focusPassword();
                if (inputChar.length === 1 && inputChar.charCodeAt(0) >= 32)
                    root.context.currentText += inputChar;
            });
            event.accepted = true;
            return;
        }

        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (root.context.currentText.length > 0) {
                loginView.hasAttemptedUnlock = true;
                root.context.tryUnlock(root.ctrlHeld);
            }
            event.accepted = true;
            return;
        }

        if (!loginView.passwordActiveFocus)
            loginView.focusPassword();
    }

    Keys.onReleased: event => {
        if (event.key === Qt.Key_Control)
            root.ctrlHeld = false;
        forceFieldFocus();
    }

    onClicked: forceFieldFocus()

    Component.onCompleted: {
        root.currentView = "clock";
        Qt.callLater(() => root.forceActiveFocus());
    }

    // Reset whenever the lock engages.
    Connections {
        target: root.context
        function onLockedChanged() {
            if (root.context.locked) {
                root.currentView = "clock";
                Qt.callLater(() => root.forceActiveFocus());
            }
        }
        function onShouldReFocus() {
            forceFieldFocus();
        }
    }

    // Ensure focus on first show (Loader focus workaround, iNiR): 100ms × 30.
    Timer {
        id: focusEnsureTimer
        interval: 100
        running: root.context.locked && root.visible
        repeat: true
        property int attempts: 0
        onTriggered: {
            attempts++;
            if (attempts > 30) {
                repeat = false;
                return;
            }
            if (!loginView.passwordActiveFocus && root.showLoginView)
                loginView.focusPassword();
            else if (!root.activeFocus && !root.showLoginView)
                root.forceActiveFocus();
        }
    }

    // A live clock for the clock view (re-evaluates every 5s; cheap and battery-kind).
    property var clock: QtObject {
        property date now: new Date()
    }
    Timer {
        interval: 5000
        running: root.visible
        repeat: true
        triggeredOnStart: true
        onTriggered: root.clock.now = new Date()
    }
}
