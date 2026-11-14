// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockSurface.qml (lock layer, fan-in 1 — instantiated per screen inside
// LockState's WlSessionLockSurface).
// Ported from the interaction half of iNiR's LockSurface.qml @ edca6cc (GPL-3.0):
// the clock→login view machine (Theme-curve transitions + the login smoke overlay),
// any-key capture into the password field, Esc semantics, Ctrl+Enter (unlock + keep
// awake), the unlock recede overlay and the niri focus machinery (focusEnsureTimer
// 100ms×30; the 2s heartbeat lives in LockState). Phase 3 adds the composed views:
// LockClockView (status row/weather/hint) and LockMediaWidget below the clock.
// REL: LockContext (context), LockWallpaper/LockClockView/LockMediaWidget/
// LockLoginView (own dir), ActivityState (player), Theme only.
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
    // How long the surfaces recede on unlock before LockState releases the lock
    // (iNiR recede); the unlock overlay's fade duration matches it.
    readonly property int recedeDuration: 250
    // Media only while a track is actually up (iNiR: a title is present) and the
    // widget preference (Phase 3 PR2, config/lock.json) allows the card.
    readonly property bool mediaActive: ShellState.preferences.lockMediaWidget !== false
        && ActivityState.player !== null
        && !!(ActivityState.display && ActivityState.display.title)

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

    // ---- clock view (status row / weather / hint live in LockClockView) -------
    Item {
        id: clockView
        anchors.fill: parent
        visible: opacity > 0
        opacity: root.showLoginView ? 0 : 1
        scale: root.showLoginView ? 0.94 : 1

        Behavior on opacity {
            enabled: Theme.animations
            NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic }
        }
        Behavior on scale {
            enabled: Theme.animations
            NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.spatialCurve }
        }

        LockClockView { anchors.fill: parent }
    }

    // ---- media card (below the raised clock; iNiR position) --------------------
    LockMediaWidget {
        id: mediaWidget
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.verticalCenter
        anchors.topMargin: 64
        visible: root.mediaActive && !root.showLoginView
        player: ActivityState.player
        title: ActivityState.display ? ActivityState.display.title : ""
        artist: ActivityState.display ? (ActivityState.display.artist || "") : ""
        artUrl: ActivityState.artwork
    }

    // The login view dims everything behind it (iNiR smoke overlay).
    Rectangle {
        id: smokeOverlay
        anchors.fill: parent
        color: "#59000000"
        visible: opacity > 0
        opacity: root.showLoginView ? 1 : 0
        Behavior on opacity {
            enabled: Theme.animations
            NumberAnimation { duration: 350; easing.type: Easing.OutCubic }
        }
    }

    // ---- login view ----------------------------------------------------------
    LockLoginView {
        id: loginView
        anchors.centerIn: parent
        visible: root.showLoginView
        opacity: root.showLoginView ? 1 : 0
        scale: root.showLoginView ? 1 : 0.98
        context: root.context

        Behavior on opacity {
            enabled: Theme.animations
            NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.OutCubic }
        }
        Behavior on scale {
            enabled: Theme.animations
            NumberAnimation { duration: Theme.animationDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.spatialCurve }
        }
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

    // ---- unlock success overlay (fades in while the lock recedes) --------------
    Rectangle {
        id: unlockOverlay
        anchors.fill: parent
        color: Theme.background
        opacity: 0
        z: 100

        NumberAnimation {
            id: unlockFadeAnim
            target: unlockOverlay
            property: "opacity"
            from: 0; to: 1
            duration: 300
            easing.type: Easing.InQuad
        }
    }
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
        function onUnlocked(action) {
            unlockFadeAnim.restart();
        }
    }
}
