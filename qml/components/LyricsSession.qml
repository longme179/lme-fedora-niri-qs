// SPDX-License-Identifier: GPL-3.0-only
// Role: LyricsSession.qml (shared layer, fan-in 2).
// Shared component/helper; keep API stable for wide QML reuse.
// Cue-boundary scheduling adapted from pctrade/end4-pC LyricsService (8fbb6716).
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Services.Mpris
import "../services"

QtObject {
    id: root
    property MprisPlayer player
    property bool active: false
    property int readers: 0
    readonly property bool wanted: (active || readers > 0) && ShellState.preferences.lyricsEnabled !== false && !ShellState.settingsApp
    property var lyricData: ({status: "idle", lines: []})
    property string requestedKey: ""
    property real boundaryAt: 0
    readonly property var song: player ? ({title: player.trackTitle || "", artist: player.trackArtist || "", album: player.trackAlbum || "",
        duration: player.lengthSupported ? Math.max(0, player.length) : 0, url: String(player.metadata["xesam:url"] || ""),
        embedded: String(player.metadata["xesam:asText"] || ""), online: ShellState.preferences.lyricsOnline === true}) : null
    readonly property string songKey: song ? JSON.stringify([player.dbusName, player.metadata["mpris:trackid"], song]) : ""
    readonly property var lines: lyricData.lines || []
    readonly property real position: player && player.positionSupported ? player.position : 0
    readonly property real playbackRate: player && Number.isFinite(player.rate) && player.rate > 0 ? player.rate : 1
    readonly property int currentLine: lyricData.synced && player && player.positionSupported ? indexAt(position) : -1
    readonly property string currentText: currentLine >= 0 ? lines[currentLine].text : ""
    readonly property bool ticking: wanted && lyricData.synced === true && !!player && player.positionSupported && player.isPlaying

    function indexAt(pos) {
        let low = 0, high = lines.length - 1, found = -1;
        while (low <= high) {
            const mid = (low + high) >> 1;
            if (lines[mid].time <= pos) { found = mid; low = mid + 1; }
            else high = mid - 1;
        }
        return found;
    }
    function schedule() {
        const source = player;
        if (!ticking || !source || !source.positionSupported || !source.isPlaying) { boundary.stop(); return; }
        const pos = source.position, next = lines[indexAt(pos) + 1];
        if (!next) { boundary.stop(); return; }
        const remaining = (next.time - pos) * 1000 / playbackRate;
        const deadline = Date.now() + remaining;
        // Visible media controls also emit position every frame; keep an accurate timer.
        if (boundary.running && Math.abs(boundaryAt - deadline) < 80) return;
        boundary.stop(); boundaryAt = deadline;
        boundary.interval = Math.max(10, Math.ceil(remaining));
        boundary.start();
    }
    function refresh() {
        // Quickshell advances its local playback clock; emitting this does not poll D-Bus.
        if (wanted && player) player.positionChanged();
        schedule();
    }
    function load() {
        delay.stop();
        if (!wanted || !song) return;
        lyricData = {status: "loading", lines: []}; requestedKey = songKey;
        if (ShellState.demo) { lyricData = {status: "none", lines: []}; return; }
        LyricsState.lookup(song, value => {  // Q5: the native lookup chain (LyricsState.qml); the lyrics.py worker protocol is retired
            if (!root.wanted || root.requestedKey !== root.songKey) return;
            root.lyricData = value && value.lines ? value : {status: "error", error: "Invalid lyrics response", lines: []};
        });
    }
    function invalidate() {
        lyricData = {status: "idle", lines: []}; requestedKey = "";
        if (wanted && song) delay.restart();
    }
    onSongKeyChanged: invalidate()
    onWantedChanged: {
        if (wanted && requestedKey !== songKey) delay.restart();
        else if (!wanted) {
            delay.stop();
            if (lyricData.status === "loading") requestedKey = "";
        }
        refresh();
    }
    onPositionChanged: schedule()
    onPlaybackRateChanged: refresh()
    onTickingChanged: refresh()
    onLyricDataChanged: refresh()
    Component.onCompleted: if (wanted && song) delay.restart()
    property Timer delay: Timer { interval: 300; onTriggered: root.load() }
    property Timer boundary: Timer { onTriggered: root.refresh() }
    property Timer drift: Timer { interval: 4000; repeat: true; running: root.ticking; onTriggered: root.refresh() }
}
