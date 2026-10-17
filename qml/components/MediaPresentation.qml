// SPDX-License-Identifier: MIT
// Copyright (c) 2025-2026 Avenge Media LLC
// Adapted from DMS MediaPresentation (8e690022); LME retains cosmetic metadata only.
import QtQuick

QtObject {
    id: root
    required property var player
    property bool enabled: true
    property var current: null
    readonly property bool settling: settle.running
    readonly property var incoming: player ? ({key: player.dbusName, identity: player.identity,
        title: player.trackTitle || "", artist: player.trackArtist || "", artUrl: String(player.trackArtUrl || "")}) : null
    onIncomingChanged: sync()
    onEnabledChanged: sync()
    Component.onCompleted: sync()

    function sync() {
        if (!enabled || !current || incoming && current.key !== incoming.key) {
            settle.stop(); current = incoming; return;
        }
        const incomplete = !incoming || ["title", "artist", "artUrl"].some(key => current[key] && !incoming[key]);
        if (!incomplete) { settle.stop(); current = incoming; return; }
        // Keep one coherent card; never extend the grace period with repeated partial updates.
        if (!settle.running) { settle.interval = incoming ? 500 : 250; settle.start(); }
    }
    property Timer settle: Timer { onTriggered: root.current = root.incoming }
}
