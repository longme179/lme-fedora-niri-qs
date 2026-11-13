// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockContext.qml (lock layer, fan-in 2 — LockState owns the one instance).
// Ported from snowarch/iNiR v3.1.0 modules/shared/lock/LockContext.qml @ edca6cc
// (GPL-3.0; see THIRD_PARTY.md): the state shared by every lock surface plus the two
// PAM conversations (password via the system `login` stack; fingerprints via the
// vendored config/pam/fprintd.conf, dormant while no reader is enrolled).
// Shared service type (like CommandRunner, non-singleton) so both LockState and
// the lock surfaces in qml/features/lock/ can see it without a services→feature edge.
// REL: qml/services/LockState.qml (owner) — surfaces receive this as their `context`.
// The fprintd-list detection and the 10s/750ms timers follow iNiR; the pamConfig/
// pamConfigDirectory overrides exist only so engine cases can point the password
// conversation at disposable test configs (defaults reproduce iNiR exactly).
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pam

QtObject {
    id: root

    enum ActionEnum { Unlock, Poweroff, Reboot }

    signal shouldReFocus()
    signal unlocked(var targetAction)
    signal failed()

    // State shared by all lock surfaces (one context, one conversation at a time).
    property string currentText: ""
    property bool unlockInProgress: false
    property bool showFailure: false
    property bool fingerprintsConfigured: false
    property var targetAction: ActionEnum.Unlock
    property bool alsoInhibitIdle: false
    property bool locked: false // kept in sync by LockState; drives the finger retry

    // Test seams: defaults match iNiR (system `login` stack, default directory).
    property string pamConfig: "login"
    property string pamConfigDirectory: ""

    function resetTargetAction(): void {
        root.targetAction = ActionEnum.Unlock;
    }

    function clearText(): void {
        root.currentText = "";
    }

    function resetClearTimer(): void {
        passwordClearTimer.restart();
    }

    function reset(): void {
        root.resetTargetAction();
        root.clearText();
        root.unlockInProgress = false;
        root.showFailure = false;
        stopFingerPam();
        if (root.locked)
            Qt.callLater(root.tryFingerUnlock);
    }

    // Clear the entry after 10s of inactivity so a half-typed password never lingers.
    Timer {
        id: passwordClearTimer
        interval: 10000
        onTriggered: root.reset()
    }

    onCurrentTextChanged: {
        if (currentText.length > 0)
            showFailure = false;
        // Typing a password takes over from the finger conversation.
        if (currentText.length > 0 && fingerPam.active)
            stopFingerPam();
        passwordClearTimer.restart();
    }

    function tryUnlock(alsoInhibitIdle = false): void {
        root.alsoInhibitIdle = alsoInhibitIdle;
        root.unlockInProgress = true;
        pamTimeoutTimer.restart();
        pam.start();
    }

    // Safety timeout: if PAM never answers, surface the failure and re-arm input.
    Timer {
        id: pamTimeoutTimer
        interval: 10000
        onTriggered: {
            if (root.unlockInProgress) {
                console.warn("[LockContext] PAM timeout - resetting state");
                root.unlockInProgress = false;
                root.showFailure = true;
                root.failed();
            }
        }
    }

    function tryFingerUnlock(): void {
        if (!root.locked || !root.fingerprintsConfigured || fingerPam.active)
            return;
        fingerprintRetryTimer.stop();
        if (!fingerPam.start())
            fingerprintRetryTimer.restart();
    }

    function stopFingerPam(): void {
        fingerprintRetryTimer.stop();
        if (fingerPam.active)
            fingerPam.abort();
    }

    Timer {
        id: fingerprintRetryTimer
        interval: 750
        repeat: false
        onTriggered: root.tryFingerUnlock()
    }

    // Fingerprint enrollment probe: fprintd-list's enrolled-print rows are stable
    // machine-readable identifiers, independent of localized headings (iNiR lesson).
    Process {
        id: fingerprintCheckProc
        running: true
        command: ["bash", "-c", "command -v fprintd-list >/dev/null && fprintd-list $(whoami) 2>/dev/null || exit 1"]
        stdout: StdioCollector {
            id: fingerprintOutputCollector
            onStreamFinished: {
                root.fingerprintsConfigured = /(^|\n)\s*-\s*#\d+:/.test(fingerprintOutputCollector.text);
                if (root.fingerprintsConfigured && root.locked)
                    Qt.callLater(root.tryFingerUnlock);
            }
        }
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                root.fingerprintsConfigured = false; // fprintd absent or no reader: dormant
        }
    }

    // The password conversation (system `login` stack; test overrides above).
    PamContext {
        id: pam

        config: root.pamConfig
        Component.onCompleted: {
            if (root.pamConfigDirectory.length > 0)
                pam.configDirectory = root.pamConfigDirectory;
        }

        // pam_unix asks for the password through the conversation.
        onPamMessage: if (pam.responseRequired) pam.respond(root.currentText)

        // A completion replaces the state; Error and MaxTries are failures too.
        onCompleted: result => {
            pamTimeoutTimer.stop();
            if (result == PamResult.Success) {
                root.unlockInProgress = false;
                root.unlocked(root.targetAction);
                stopFingerPam();
            } else {
                root.clearText();
                root.unlockInProgress = false;
                root.showFailure = true;
                root.failed();
            }
        }
    }

    // The fingerprint conversation; dormant unless prints are enrolled.
    PamContext {
        id: fingerPam

        configDirectory: Quickshell.shellPath("config/pam")
        config: "fprintd.conf"

        onCompleted: result => {
            if (result == PamResult.Success) {
                fingerprintRetryTimer.stop();
                root.unlocked(root.targetAction);
            } else if (root.locked && root.fingerprintsConfigured) {
                // Failed scans, PAM errors and max-tries completions are recoverable
                // while the lock stays active; retry through a timer so a broken
                // device/PAM stack cannot create a tight loop (iNiR lesson).
                fingerprintRetryTimer.restart();
            }
        }
    }
}
