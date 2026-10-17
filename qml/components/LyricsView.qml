// SPDX-License-Identifier: GPL-3.0-or-later
// Lifecycle/follow behavior references DMS LyricsController/LyricsOverlay (8e690022, MIT).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.Mpris
import "../services"
import "../theme"

ColumnLayout {
    id: root
    property MprisPlayer player
    property bool expanded: false
    property bool following: true
    readonly property bool followDefault: ShellState.preferences.lyricsFollow !== false
    readonly property bool singleLine: ShellState.preferences.lyricsMode === "line" && !!player && player.positionSupported
    readonly property bool active: expanded && visible && (Window.window?.visible ?? false) && ShellState.preferences.lyricsEnabled !== false
    readonly property LyricsSession session: player && player === ActivityState.player ? ActivityState.lyrics : localSession
    property LyricsSession subscribed: null
    readonly property var lyricData: session.lyricData
    readonly property var lines: session.lines
    readonly property string songKey: session.songKey
    readonly property int currentLine: session.currentLine
    spacing: 8
    visible: ShellState.preferences.lyricsEnabled !== false
    LyricsSession { id: localSession; player: root.player === ActivityState.player ? null : root.player }
    function sync() {
        const next = active ? session : null;
        if (subscribed === next) return;
        if (subscribed) subscribed.readers--;
        subscribed = next;
        if (next) next.readers++;
    }
    function centerCurrent() {
        if (active && !singleLine && following && currentLine >= 0)
            Qt.callLater(() => transcript.positionViewAtIndex(currentLine, ListView.Center));
    }
    function load() { session.load(); }
    onActiveChanged: { sync(); if (active) { following = followDefault; centerCurrent(); } }
    onSessionChanged: sync()
    onSongKeyChanged: following = followDefault
    onFollowDefaultChanged: { following = followDefault; centerCurrent(); }
    onSingleLineChanged: centerCurrent()
    onCurrentLineChanged: centerCurrent()
    Component.onCompleted: { sync(); following = followDefault; }
    Component.onDestruction: if (subscribed) subscribed.readers--
    RowLayout {
        Layout.fillWidth: true
        LiquidButton { objectName: "lyricsToggle"; text: root.expanded ? "Hide lyrics" : "Lyrics"; selected: root.expanded; enabled: root.player !== null || ShellState.demo; onClicked: root.expanded = !root.expanded }
        Item { Layout.fillWidth: true }
        LiquidButton { visible: root.expanded && !root.singleLine && root.lyricData.synced === true && !root.following; text: "Follow"; onClicked: { root.following = true; transcript.positionViewAtIndex(Math.max(0, root.currentLine), ListView.Center); } }
    }
    LabelText {
        visible: root.expanded && !["ready", "idle"].includes(root.lyricData.status)
        Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
        text: root.lyricData.status === "loading" ? "Finding lyrics…" : root.lyricData.status === "instrumental" ? "Instrumental"
            : root.lyricData.status === "offline" ? "No local or cached lyrics. Enable online lookup to search LRCLIB."
            : root.lyricData.status === "metadata" ? "Track title and artist are needed to find lyrics."
            : root.lyricData.status === "error" ? root.lyricData.error || "Lyrics unavailable" : "No lyrics found for this track."
    }
    LabelText {
        objectName: "lyricsCurrentLine"
        visible: root.expanded && root.singleLine && root.lyricData.status === "ready" && root.lyricData.synced === true
        Layout.fillWidth: true; Layout.minimumHeight: 64
        text: root.session.currentText || "♪"
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        wrapMode: Text.Wrap; color: Theme.accent; font.weight: Font.Bold
        Accessible.name: root.session.currentText || "Instrumental break"
    }
    ListView {
        id: transcript; objectName: "lyricsTranscript"
        visible: root.expanded && !root.singleLine && root.lyricData.status === "ready" && root.lyricData.synced === true
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
        objectName: "lyricsPlain"
        visible: root.expanded && root.lyricData.status === "ready" && !root.lyricData.synced
        Layout.fillWidth: true; Layout.preferredHeight: 220; clip: true; contentWidth: availableWidth
        LabelText { width: parent.width; text: root.lyricData.plain || ""; wrapMode: Text.Wrap }
    }
    LabelText { visible: root.expanded && root.lyricData.synced === true && root.player && !root.player.positionSupported; text: "This player does not expose playback timing."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    RowLayout {
        visible: root.expanded && root.lyricData.status !== "loading"; Layout.fillWidth: true
        LabelText { text: root.lyricData.source || ""; color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
        LiquidButton { visible: root.lyricData.status === "offline"; text: "Enable LRCLIB"; onClicked: ShellState.run("setting", {key: "lyricsOnline", value: true}) }
        LiquidButton { text: "Retry"; enabled: !!root.session.song; onClicked: root.load() }
    }
}
