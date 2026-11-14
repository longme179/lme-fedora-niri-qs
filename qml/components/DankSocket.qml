// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2025-2026 snowarch; reconnect wrapper from iNiR's services/DankSocket.qml,
// vendored near-verbatim for LME at iNiR commit edca6cc. See third_party/iNiR-NOTICE.
// Modified for LME (probed live on quickshell 0.3.2, 2026-11-14): a REFUSED connect
// attempt fires onError but no connectionStateChanged, which dead-ends the retry chain
// exactly when the server is down — the reason this wrapper exists. The chain now also
// starts from onError, deduped by a pending flag so a live drop (both signals) still
// schedules one retry. Everything else is upstream unchanged.
import QtQuick
import Quickshell.Io

Item {
    id: root

    property alias path: socket.path
    property alias parser: socket.parser
    property bool connected: false
    // Whether the socket is open now (`connected` is only what was asked for).
    property bool socketConnected: false

    property int reconnectBaseMs: 400
    property int reconnectMaxMs: 15000

    property int _reconnectAttempt: 0
    property bool _reconnectPending: false

    signal connectionStateChanged()

    onConnectedChanged: {
        socket.connected = connected
    }

    Socket {
        id: socket

        onConnectionStateChanged: {
            // Set before the signal: a handler reading it sees the state that fired it.
            root.socketConnected = connected
            root.connectionStateChanged()
            if (connected) {
                root._reconnectAttempt = 0
                return
            }
            if (root.connected) {
                root._reconnectSoon()
            }
        }

        // quickshell 0.3.2 fires no connectionStateChanged when a connect attempt
        // is refused — without this arm the chain would die on the first dead server.
        onError: if (root.connected && !socket.connected) root._reconnectSoon()
    }

    Timer {
        id: reconnectTimer
        interval: 0
        repeat: false
        onTriggered: {
            root._reconnectPending = false
            socket.connected = false
            Qt.callLater(() => socket.connected = true)
        }
    }

    function send(data) {
        const json = typeof data === "string" ? data : JSON.stringify(data)
        const message = json.endsWith("\n") ? json : json + "\n"
        socket.write(message)
        socket.flush()
    }

    // One schedule per event cascade: a live drop fires both onError and
    // connectionStateChanged; a refused attempt fires only onError.
    function _reconnectSoon() {
        if (_reconnectPending) return
        _reconnectPending = true
        _scheduleReconnect()
    }

    function _scheduleReconnect() {
        const pow = Math.min(_reconnectAttempt, 10)
        const base = Math.min(reconnectBaseMs * Math.pow(2, pow), reconnectMaxMs)
        const jitter = Math.floor(Math.random() * Math.floor(base / 4))
        reconnectTimer.interval = base + jitter
        reconnectTimer.restart()
        _reconnectAttempt++
    }
}
