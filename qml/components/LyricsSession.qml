// SPDX-License-Identifier: GPL-3.0-only
// Cue-boundary scheduling adapted from pctrade/end4-pC LyricsService (8fbb6716).
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Mpris
import "../services"

QtObject {
    id: root
    property MprisPlayer player
    property bool active: false
    property int readers: 0
    readonly property bool wanted: (active || readers > 0) && ShellState.preferences.lyricsEnabled !== false && !ShellState.settingsApp
    property var lyricData: ({status: "idle", lines: []})
    property string pending: ""
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
        delay.stop(); lookup.active = false;
        if (!wanted || !song) return;
        lyricData = {status: "loading", lines: []}; requestedKey = songKey;
        if (ShellState.demo) { lyricData = {status: "none", lines: []}; return; }
        pending = JSON.stringify(song); lookup.active = true;
    }
    function invalidate() {
        lookup.active = false; lyricData = {status: "idle", lines: []}; requestedKey = "";
        if (wanted && song) delay.restart();
    }
    onSongKeyChanged: invalidate()
    onWantedChanged: {
        if (wanted && requestedKey !== songKey) delay.restart();
        else if (!wanted) {
            delay.stop(); lookup.active = false;
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
    property Loader lookup: Loader {
        active: false
        sourceComponent: Process {
            id: worker
            property string requestKey: ""
            property string requestBody: ""
            Component.onCompleted: { requestKey = root.requestedKey; requestBody = root.pending; running = true; }
            command: ["python3", "-u", Quickshell.shellPath("scripts/lyrics.py")]; stdinEnabled: true
            onStarted: write(requestBody + "\n")
            stdout: SplitParser { onRead: value => {
                if (!root.wanted || worker.requestKey !== root.songKey) return;
                try { root.lyricData = JSON.parse(value); }
                catch (error) { root.lyricData = {status: "error", error: "Invalid lyrics response", lines: []}; }
            } }
            // qmllint disable signal-handler-parameters
            onExited: if (root.wanted && root.lyricData.status === "loading" && requestKey === root.songKey)
                root.lyricData = {status: "error", error: "Lyrics lookup stopped. Retry to reconnect.", lines: []}
        }
    }
}
