// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockState.qml (lock family skeleton, Phase 0; owner: the lock IPC surface, Phase 1).
// Vendored mechanism from snowarch/iNiR v3.1.0 modules/shared/lock/Lock.qml @ edca6cc
// (GPL-3.0; see THIRD_PARTY.md) — the session-lock + PAM port per
// ~/agent-collab/plans/2026-11-13-lockscreen-port-plan.md.
// Phase 0: gated skeleton only, no behavior change. INVARIANT: demo/preview sessions and
// LME_SHELL_LOCK_ENABLED=0 keep every entry point inert, and nothing here creates a
// session-lock surface or an auth context before Phase 1 lands them.
pragma Singleton

import QtQuick
import Quickshell

QtObject {
    id: root

    // Engine fixtures and preview/demo launches must never engage a session lock;
    // LME_SHELL_LOCK_ENABLED=0 is the hard override for live sessions too.
    readonly property bool enabled:
        Quickshell.env("LME_SHELL_DEMO") !== "1"
        && Quickshell.env("LME_SHELL_LOCK_ENABLED") !== "0"

    // Phase 1 wires locked to the lock object's state and secure to the compositor ack.
    readonly property bool locked: false
    readonly property bool secure: false
    readonly property string status: enabled ? (locked ? "locked" : "unlocked") : "disabled"

    // Phase 1 contract stubs (IPC target "lock", mirroring iNiR): activate debounces
    // 150ms then locks; prepareSleep locks immediately and reports "locking" until the
    // compositor confirms; focus re-focuses the lock surface after resume; deactivate
    // releases only after PAM accepts. Until then: report, never engage.
    function activate(): string { return root.status; }
    function prepareSleep(): string { return root.status; }
    function deactivate(): void { }
    function focus(): void { }
}
