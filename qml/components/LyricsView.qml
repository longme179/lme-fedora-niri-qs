// SPDX-License-Identifier: GPL-3.0-or-later
// Lifecycle/follow behavior references DMS LyricsController/LyricsOverlay (8e690022, MIT).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Services.Mpris
import "../services"
import "../theme"

ColumnLayout {
    id: root
    property MprisPlayer player
    property bool expanded: false
    property bool following: true
    property var lyricData: ({status: "idle", lines: []})
    property string pending: ""
    property string requestedKey: ""
    readonly property bool active: expanded && visible && (Window.window?.visible ?? false) && ShellState.preferences.lyricsEnabled !== false
    readonly property var song: player ? ({title: player.trackTitle || "", artist: player.trackArtist || "", album: player.trackAlbum || "",
        duration: player.lengthSupported ? Math.max(0, player.length) : 0, url: String(player.metadata["xesam:url"] || ""),
        embedded: String(player.metadata["xesam:asText"] || ""), online: ShellState.preferences.lyricsOnline === true}) : null
    readonly property string songKey: song ? JSON.stringify([player.dbusName, player.metadata["mpris:trackid"], song]) : ""
    readonly property var lines: lyricData.lines || []
    readonly property real position: player && player.positionSupported ? player.position : 0
    readonly property int currentLine: {
        let low = 0, high = lines.length - 1, found = -1;
        while (low <= high) { const mid = (low + high) >> 1; if (lines[mid].time <= position) { found = mid; low = mid + 1; } else high = mid - 1; }
        return found;
    }
    spacing: 8
    visible: ShellState.preferences.lyricsEnabled !== false
    function load() {
        delay.stop(); lookup.active = false;
        if (!active || !song) return;
        following = true; lyricData = {status: "loading", lines: []}; requestedKey = songKey;
        if (ShellState.demo) { lyricData = {status: "none", lines: []}; return; }
        pending = JSON.stringify(song); lookup.active = true;
    }
    function invalidate() {
        lookup.active = false; lyricData = {status: "idle", lines: []}; requestedKey = ""; following = true;
        if (active && song) delay.restart();
    }
    onSongKeyChanged: invalidate()
    onActiveChanged: { if (active && requestedKey !== songKey) delay.restart(); else if (!active) { delay.stop(); lookup.active = false; if (lyricData.status === "loading") requestedKey = ""; } }
    onCurrentLineChanged: if (following && currentLine >= 0) Qt.callLater(() => transcript.positionViewAtIndex(currentLine, ListView.Center))
    Component.onCompleted: if (active && song) delay.restart()
    RowLayout {
        Layout.fillWidth: true
        LiquidButton { objectName: "lyricsToggle"; text: root.expanded ? "Hide lyrics" : "Lyrics"; selected: root.expanded; enabled: root.player !== null || ShellState.demo; onClicked: root.expanded = !root.expanded }
        Item { Layout.fillWidth: true }
        LiquidButton { visible: root.expanded && root.lyricData.synced && !root.following; text: "Follow"; onClicked: { root.following = true; transcript.positionViewAtIndex(Math.max(0, root.currentLine), ListView.Center); } }
    }
    LabelText {
        visible: root.expanded && !["ready", "idle"].includes(root.lyricData.status)
        Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
        text: root.lyricData.status === "loading" ? "Finding lyrics…" : root.lyricData.status === "instrumental" ? "Instrumental"
            : root.lyricData.status === "offline" ? "No local or cached lyrics. Enable online lookup to search LRCLIB."
            : root.lyricData.status === "metadata" ? "Track title and artist are needed to find lyrics."
            : root.lyricData.status === "error" ? root.lyricData.error || "Lyrics unavailable" : "No lyrics found for this track."
    }
    ListView {
        id: transcript; objectName: "lyricsTranscript"
        visible: root.expanded && root.lyricData.status === "ready" && root.lyricData.synced
        Layout.fillWidth: true; Layout.preferredHeight: 220
        clip: true; model: root.lines; spacing: 8; boundsBehavior: Flickable.StopAtBounds
        onMovementStarted: root.following = false
        ScrollBar.vertical: ScrollBar {}
        delegate: LiquidButton {
            id: line; required property var modelData; required property int index
            objectName: "lyricLine-" + index; width: transcript.width - 12
            implicitHeight: lyricText.implicitHeight + 20
            selected: index === root.currentLine; flat: true
            Accessible.name: modelData.text || "Instrumental break"
            contentItem: LabelText { id: lyricText; text: line.modelData.text || "♪"; wrapMode: Text.Wrap; color: line.selected ? Theme.accent : Theme.muted; font.weight: line.selected ? Font.Bold : Font.Normal }
            onClicked: if (root.player && root.player.canControl && root.player.canSeek && root.player.positionSupported) root.player.position = modelData.time
        }
    }
    ScrollView {
        visible: root.expanded && root.lyricData.status === "ready" && !root.lyricData.synced
        Layout.fillWidth: true; Layout.preferredHeight: 220; clip: true; contentWidth: availableWidth
        LabelText { width: parent.width; text: root.lyricData.plain || ""; wrapMode: Text.Wrap }
    }
    LabelText { visible: root.expanded && root.lyricData.synced && root.player && !root.player.positionSupported; text: "This player does not expose playback timing."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    RowLayout {
        visible: root.expanded && root.lyricData.status !== "loading"; Layout.fillWidth: true
        LabelText { text: root.lyricData.source || ""; color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
        LiquidButton { visible: root.lyricData.status === "offline"; text: "Enable LRCLIB"; onClicked: ShellState.run("setting", {key: "lyricsOnline", value: true}) }
        LiquidButton { text: "Retry"; enabled: !!root.song; onClicked: root.load() }
    }
    Timer { id: delay; interval: 300; onTriggered: root.load() }
    Timer { interval: 250; repeat: true; running: root.active && root.lyricData.synced === true && root.player && root.player.positionSupported && root.player.isPlaying; onTriggered: root.player.positionChanged() }
    Loader {
        id: lookup; active: false; visible: false; Layout.preferredHeight: 0
        sourceComponent: Process {
        id: worker
        property string requestKey: ""
        property string requestBody: ""
        Component.onCompleted: { requestKey = root.requestedKey; requestBody = root.pending; running = true; }
        command: ["python3", "-u", Quickshell.shellPath("scripts/lyrics.py")]; stdinEnabled: true
        onStarted: write(requestBody + "\n")
        stdout: SplitParser { onRead: value => { if (!root.active || worker.requestKey !== root.songKey) return; try { root.lyricData = JSON.parse(value); } catch (error) { root.lyricData = {status: "error", error: "Invalid lyrics response"}; } } }
        // qmllint disable signal-handler-parameters
        onExited: { if (root.active && root.lyricData.status === "loading" && requestKey === root.songKey) root.lyricData = {status: "error", error: "Lyrics lookup stopped. Retry to reconnect."}; }
    }
    }
}
