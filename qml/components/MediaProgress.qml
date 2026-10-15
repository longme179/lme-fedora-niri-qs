import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import Quickshell.Services.Mpris
import "../services"
import "../theme"

ColumnLayout {
    id: root
    property MprisPlayer player
    property bool playing: ShellState.demo || !!(player && player.isPlaying)
    readonly property bool hasMedia: ShellState.demo || player !== null
    readonly property real duration: ShellState.demo ? 240 : player && player.lengthSupported && Number.isFinite(player.length) ? Math.max(0, player.length) : 0
    readonly property bool progressAvailable: ShellState.demo || !!(player && player.positionSupported && duration > 0)
    readonly property real position: ShellState.demo ? 64 : progressAvailable && Number.isFinite(player.position) ? Math.max(0, Math.min(duration, player.position)) : 0
    visible: hasMedia
    spacing: 2

    WaveProgress {
        objectName: "mediaProgressWave"
        Layout.fillWidth: true
        value: root.duration > 0 ? root.position / root.duration : 0
        indeterminate: !root.progressAvailable
        isPlaying: root.playing
        // Quickshell's getter advances its local clock; this does not poll D-Bus.
        onFrameTicked: if (root.progressAvailable && root.player) root.player.positionChanged()
    }
    RowLayout {
        visible: root.progressAvailable
        Layout.fillWidth: true
        LabelText { objectName: "mediaElapsed"; text: FocusTimer.format(Math.floor(root.position)); font.pixelSize: 11; color: Theme.muted }
        Item { Layout.fillWidth: true }
        LabelText { text: FocusTimer.format(Math.floor(root.duration)); font.pixelSize: 11; color: Theme.muted }
    }
    LabelText {
        objectName: "mediaTimingUnavailable"
        visible: !root.progressAvailable
        text: "Playback timing unavailable"
        font.pixelSize: 11; color: Theme.muted
    }
    Timer {
        interval: 1000; repeat: true; triggeredOnStart: true
        running: root.visible && root.progressAvailable && (root.Window.window?.visible ?? false) && root.playing && (!Theme.mediaWave || !Theme.animations)
        onTriggered: if (root.player) root.player.positionChanged()
    }
}
