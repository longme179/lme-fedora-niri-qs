// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockMechanism.qml (lock layer, fan-in 1 — instantiated by shell.qml).
// Ported from the WlSessionLock half of iNiR's Lock.qml @ edca6cc (GPL-3.0):
// owns the session-lock object and its per-screen surfaces, releases to the
// idle_control fallback when the surface fails to load, and mirrors the
// compositor's `secure` ack back into LockState.
// Lives on the feature side so qml/services never imports a feature folder
// (the shared layer must stay acyclic); everything stateful stays in LockState.
// REL: qml/services/LockState.qml (state, fallback, context), LockSurface.qml.
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../../services"

QtObject {
    id: root

    // The keyring opt-out preference (Phase 3 PR2) flows in here: this feature
    // side may read ShellState, LockState itself may not.
    property Binding keyringPolicy: Binding {
        target: LockState
        property: "keyringEnabled"
        value: ShellState.preferences.lockKeyringUnlock !== false
    }

    // ext-session-lock exists only under a compositor; engine fixtures blank
    // WAYLAND_DISPLAY so this loader stays inert in every test environment.
    property Loader lockLoader: Loader {
        active: LockState.enabled && LockState.wayland
        sourceComponent: lockComponent
    }

    property Component lockComponent: Component {
        id: lockComponent
        WlSessionLock {
            id: lock
            locked: LockState.screenLocked
            onSecureChanged: LockState.secure = lock.secure

            WlSessionLockSurface {
                id: lockSurface
                color: "#22212c"

                Loader {
                    id: surfaceLoader
                    anchors.fill: parent
                    active: LockState.screenLocked
                    sourceComponent: lockSurfaceComponent
                    onStatusChanged: {
                        if (status === Loader.Error) {
                            console.error("[LockMechanism] lock surface failed to load");
                            LockState.useFallbackLock();
                        }
                    }
                    onLoaded: {
                        if (item) {
                            item.forceActiveFocus();
                            fallbackTimer.stop();
                        }
                    }
                }

                Component {
                    id: lockSurfaceComponent
                    LockSurface { context: LockState.lockContext }
                }

                // Not loaded after 2s → the shell lock is broken; get to a tested one.
                Timer {
                    id: fallbackTimer
                    interval: 2000
                    running: LockState.screenLocked && !surfaceLoader.item
                    onTriggered: {
                        console.warn("[LockMechanism] lock surface never loaded; falling back");
                        LockState.useFallbackLock();
                    }
                }

                Connections {
                    target: LockState
                    function onScreenLockedChanged() {
                        if (LockState.screenLocked && surfaceLoader.item)
                            Qt.callLater(() => surfaceLoader.item.forceActiveFocus());
                    }
                }
            }
        }
    }

    // When the lock object goes away (gate off, session end), the compositor
    // ack must not linger from a previous engagement.
    property Connections loaderWatch: Connections {
        target: lockLoader
        function onItemChanged() { if (!lockLoader.item) LockState.secure = false; }
        function onActiveChanged() { if (!lockLoader.active) LockState.secure = false; }
    }

    // Poweroff/Reboot after a locked authentication ride the regular backend
    // actions (this side may reference ShellState; LockState itself may not).
    property Connections powerWatch: Connections {
        target: LockState
        function onPowerActionRequested(action) { ShellState.run(action); }
    }
}
