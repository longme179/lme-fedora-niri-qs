import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts
import Quickshell.Services.Mpris
import "../services"
import "../theme"

ColumnLayout {
    id: root
    property MprisPlayer player
    property bool playing: ShellState.demo ? ActivityState.demoPlaying : !!(player && player.isPlaying)
    readonly property bool hasMedia: ShellState.demo || player !== null
    readonly property real duration: ShellState.demo ? 240 : player && player.lengthSupported && Number.isFinite(player.length) ? Math.max(0, player.length) : 0
    readonly property bool progressAvailable: ShellState.demo || !!(player && player.positionSupported && duration > 0)
    readonly property real position: ShellState.demo ? 64 : progressAvailable && Number.isFinite(player.position) ? Math.max(0, Math.min(duration, player.position)) : 0
    readonly property bool canSeek: ShellState.preferences.mediaControls !== false && !ShellState.demo && !!(player && player.canControl && player.canSeek && progressAvailable)
    function trackKey(source: MprisPlayer): string { return source ? String(source.metadata["mpris:trackid"] || source.trackTitle || "") : ""; }
    function seek(seconds) {
        if (!canSeek || !Number.isFinite(seconds)) return;
        player.position = Math.max(0, Math.min(duration, seconds));
    }
    visible: hasMedia
    spacing: 2

    Item {
        Layout.fillWidth: true; implicitHeight: 32
        WaveProgress {
            objectName: "mediaProgressWave"
            anchors.fill: parent
            value: root.duration > 0 ? (scrub.pressed ? scrub.value : root.position) / root.duration : 0
            indeterminate: !root.progressAvailable
            isPlaying: root.playing
            // Quickshell's getter advances its local clock; this does not poll D-Bus.
            onFrameTicked: if (root.progressAvailable && root.player) root.player.positionChanged()
        }
        Slider {
            id: scrub; objectName: "mediaSeek"
            anchors.fill: parent
            enabled: root.canSeek
            from: 0; to: Math.max(1, root.duration); stepSize: 5; live: true
            leftPadding: 4; rightPadding: 4; hoverEnabled: true
            Accessible.name: "Seek playback"
            property MprisPlayer dragPlayer: null
            property string dragTrack: ""
            onPressedChanged: {
                if (pressed) { dragPlayer = root.player; dragTrack = root.trackKey(root.player); }
                else {
                    if (enabled && root.visible && (root.Window.window?.visible ?? false) && root.player === dragPlayer && root.trackKey(root.player) === dragTrack) root.seek(value);
                    dragPlayer = null;
                }
            }
            Keys.onPressed: event => {
                if (!enabled) return;
                let target = root.position;
                if ([Qt.Key_Right, Qt.Key_Up].includes(event.key)) target += 5;
                else if ([Qt.Key_Left, Qt.Key_Down].includes(event.key)) target -= 5;
                else if (event.key === Qt.Key_Home) target = 0;
                else if (event.key === Qt.Key_End) target = root.duration;
                else return;
                event.accepted = true; root.seek(target);
            }
            background: Item {}
            handle: Rectangle {
                x: scrub.leftPadding + scrub.visualPosition * scrub.availableWidth - width / 2
                y: (scrub.height - height) / 2
                width: scrub.pressed ? 12 : 8; height: 16; radius: 4
                visible: scrub.enabled && (scrub.hovered || scrub.pressed || scrub.visualFocus)
                color: Theme.sliderFill; border.width: scrub.visualFocus ? 2 : 0; border.color: Theme.text
            }
            Binding { target: scrub; property: "value"; value: root.position; when: !scrub.pressed; restoreMode: Binding.RestoreNone }
        }
    }
    RowLayout {
        visible: root.progressAvailable
        Layout.fillWidth: true
        LabelText { objectName: "mediaElapsed"; text: FocusTimer.format(Math.floor(scrub.pressed ? scrub.value : root.position)); font.pixelSize: 11; color: Theme.muted }
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
