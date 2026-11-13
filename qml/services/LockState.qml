// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockState.qml (lock family, Phase 1 mechanism; owner: the lock IPC surface).
// Ported from snowarch/iNiR v3.1.0 modules/shared/lock/Lock.qml @ edca6cc (GPL-3.0,
// THIRD_PARTY.md): the gated state machine with a 150ms activate debounce, the v2
// recovery file (a lock survives shell restarts inside one compositor session),
// the idle_control fallback hand-off, the 2s focus heartbeat (niri drops focus
// after resume), keyring unlock (engine fixtures set LME_SHELL_LOCK_KEYRING=0 so
// a driven unlock never touches the real session keyring), the 250ms unlock
// recede, the `lock` IPC target and the native-router
// hooks for the PowerMenu "lock" action. The WlSessionLock object itself lives in
// qml/features/lock/LockMechanism.qml (shell.qml host) so this shared service
// never imports a feature folder.
// INVARIANT: LME_SHELL_DEMO=1 or LME_SHELL_LOCK_ENABLED=0 keeps every entry point
// inert — IPC answers "unlocked" so swayidle/idle_control keep their swaylock path.
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root

    // Demo/preview sessions, engine fixtures and the hard env override stay inert.
    readonly property bool enabled:
        Quickshell.env("LME_SHELL_DEMO") !== "1"
        && Quickshell.env("LME_SHELL_LOCK_ENABLED") !== "0"
    // ext-session-lock exists only under a compositor; fixtures blank WAYLAND_DISPLAY.
    readonly property bool wayland: Quickshell.env("WAYLAND_DISPLAY").length > 0

    property bool screenLocked: false
    readonly property bool locked: screenLocked
    property bool secure: false // mirrored from the mechanism's WlSessionLock
    readonly property string status: {
        if (!enabled) return "unlocked";
        if (secure) return "secure";
        if (screenLocked) return "locked";
        if (activateDelay.running) return "activating";
        return "unlocked";
    }

    function activate(): void {
        if (!enabled || screenLocked || activateDelay.running)
            return;
        activateDelay.restart();
    }

    function deactivate(): void {
        if (!enabled)
            return;
        activateDelay.stop();
        recedeRelease.stop();
        screenLocked = false;
    }

    // Suspend handshake: lock immediately (skip the debounce) and report whether
    // the compositor has confirmed the lock ("secure") or is still engaging.
    function prepareSleep(): string {
        if (!enabled)
            return "unlocked";
        activateDelay.stop();
        if (!screenLocked)
            screenLocked = true;
        return secure ? "secure" : "locking";
    }

    function focus(): void {
        if (enabled)
            lockContext.shouldReFocus();
    }

    // Fallback chain: release the QS lock, then hand over to the already-tested
    // secure_lock() in idle_control.py (swaylock + ready-fd + its own state file).
    function useFallbackLock(): void {
        if (!screenLocked && !activateDelay.running)
            return;
        recedeRelease.stop();
        screenLocked = false;
        Quickshell.execDetached(["python3", Quickshell.shellPath("scripts/idle_control.py"), "lock"]);
    }

    // ---- shared context + unlock flow ---------------------------------------
    property LockContext lockContext: LockContext {
        locked: root.screenLocked
        onUnlocked: targetAction => root.handleUnlocked(targetAction)
    }

    // Power actions run through the mechanism (features/lock), which may talk to
    // ShellState; a shared service must not (acyclic layering). The lock stays
    // engaged while the machine powers down — no keyring, no release (iNiR).
    signal powerActionRequested(string action)
    function handleUnlocked(targetAction): void {
        if (targetAction === LockContext.ActionEnum.Poweroff) {
            root.powerActionRequested("poweroff");
            return;
        }
        if (targetAction === LockContext.ActionEnum.Reboot) {
            root.powerActionRequested("reboot");
            return;
        }
        // Unlock the keyring with the accepted password before the text clears,
        // then let the surfaces recede (250ms) before the lock releases (iNiR).
        unlockKeyring();
        recedeRelease.restart();
    }

    function finishUnlock(): void {
        // Release before anything else, or the compositor keeps its own fallback
        // lock surface that cannot be interacted with (iNiR lesson).
        screenLocked = false;
        lockContext.reset();
    }

    // The recede window: the unlock overlay fades while the session stays locked
    // (iNiR recede; the +40ms grace matches the overlay's 300ms fade).
    readonly property int recedeDuration: 250
    property Timer recedeRelease: Timer {
        interval: root.recedeDuration + 40
        onTriggered: root.finishUnlock()
    }

    property Process keyringProc: Process {
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0)
                console.warn("[LockState] keyring unlock exited with", exitCode);
        }
    }
    function unlockKeyring(): void {
        // Engine fixtures drive handleUnlocked end-to-end; they must not run the
        // real keyring script (it restarts the session's gnome-keyring-daemon).
        if (Quickshell.env("LME_SHELL_LOCK_KEYRING") === "0")
            return;
        keyringProc.exec({
            environment: ({UNLOCK_PASSWORD: lockContext.currentText}),
            command: ["bash", Quickshell.shellPath("scripts/keyring_unlock.sh")]
        });
    }

    // ---- the 150ms activate debounce ------------------------------------------
    property Timer activateDelay: Timer {
        interval: 150
        onTriggered: root.screenLocked = true
    }

    // ---- focus keepalive (niri drops lock-surface focus after resume) --------
    property Timer focusHeartbeat: Timer {
        interval: 2000
        repeat: true
        running: root.screenLocked
        onTriggered: lockContext.shouldReFocus()
    }
    property Connections screensWatch: Connections {
        target: Quickshell
        function onScreensChanged() {
            if (root.screenLocked)
                Qt.callLater(() => lockContext.shouldReFocus());
        }
    }

    // ---- recovery across shell restarts --------------------------------------
    readonly property string sessionSocket: Quickshell.env("NIRI_SOCKET")
    readonly property string recoveryPath: {
        const runtime = Quickshell.env("XDG_RUNTIME_DIR");
        return runtime.length > 0 ? runtime + "/lme-shell/session-lock-v2.state" : "";
    }
    property bool recoveryLoaded: false

    function writeRecoveryState(lockedValue): void {
        if (sessionSocket.length === 0 || !recoveryLoaded || recoveryPath.length === 0)
            return;
        recoveryFile.setText((lockedValue ? "locked" : "unlocked") + "\n" + sessionSocket + "\n");
    }

    function loadRecoveryState(): void {
        if (recoveryLoaded)
            return;
        const lines = recoveryFile.text().split("\n");
        const wasLocked = lines[0] === "locked";
        const previousSocket = lines[1] ?? "";
        recoveryLoaded = true;
        if (sessionSocket.length === 0)
            return;
        if (wasLocked && previousSocket === sessionSocket) {
            console.warn("[LockState] recovering an interrupted compositor session lock");
            screenLocked = true;
            return;
        }
        writeRecoveryState(screenLocked);
    }

    property FileView recoveryFile: FileView {
        path: root.recoveryPath
        blockLoading: true
        atomicWrites: true
        printErrors: false
        onLoaded: root.loadRecoveryState()
        onLoadFailed: {
            root.recoveryLoaded = true;
            // stock Quickshell forgets a write started inside its own load signal
            Qt.callLater(() => root.writeRecoveryState(root.screenLocked));
        }
    }

    onScreenLockedChanged: writeRecoveryState(screenLocked)

    // ---- native router (PowerMenu "lock"; the backend stays the A/B fallback) --
    readonly property var handledActions: ["lock"]
    function handles(action) { return handledActions.includes(action); }
    function canRoute(action, payload, context) { return root.enabled; }
    function perform(action, payload, done, context) {
        activate();
        done(true, "");
    }

    // ---- IPC surface (swayidle, keybinds, idle_control) ----------------------
    property IpcHandler lockIpc: IpcHandler {
        target: "lock"

        /// Lock the screen (debounced 150ms).
        function activate(): void {
            root.activate();
        }

        /// Suspend handshake: lock immediately; "secure" once the compositor confirms.
        function prepareSleep(): string {
            return root.prepareSleep();
        }

        /// Cancel the lock and mark the session unlocked.
        function deactivate(): void {
            root.deactivate();
        }

        /// Return the lock state ("secure", "locked", "activating" or "unlocked").
        function status(): string {
            return root.status;
        }

        /// Refocus the lock surface input (called after logind resume).
        function focus(): void {
            root.focus();
        }
    }
}
