// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockMediaWidget.qml (lock layer, fan-in 1 — LockSurface's media card).
// Ported from iNiR's LockMediaWidget.qml @ edca6cc (GPL-3.0), reshaped onto the
// shell's own stack: the caller feeds ActivityState's stable presentation
// (title/artist/artUrl) and the live MprisPlayer; the cava visualizer and seek
// are dropped (plan §3.1 — the shared MediaProgress is too tall for the card,
// so the bar is a compact read-only one).
// REL: services (FocusTimer time formatting), components (ShellText/LiquidButton), theme.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../../services"
import "../../theme"
import "../../components"

Rectangle {
    id: root

    required property var player // MprisPlayer; null in engine fixtures
    required property string title
    required property string artist
    required property string artUrl

    readonly property bool hasPlayer: root.title.length > 0
    readonly property real duration: root.player && root.player.lengthSupported && Number.isFinite(root.player.length) ? Math.max(0, root.player.length) : 0
    readonly property bool progressAvailable: !!(root.player && root.player.positionSupported && root.duration > 0)
    readonly property real position: root.progressAvailable && Number.isFinite(root.player.position)
        ? Math.max(0, Math.min(root.duration, root.player.position)) : 0

    visible: hasPlayer
    implicitWidth: 340
    implicitHeight: 108
    radius: 18
    color: Theme.panel
    border.width: 1
    border.color: Theme.border

    RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        // Cover art (rounded) with the note-glyph placeholder.
        Rectangle {
            Layout.preferredWidth: 76
            Layout.preferredHeight: 76
            Layout.alignment: Qt.AlignVCenter
            radius: 12
            color: Theme.surfaceContainer
            clip: true

            Image {
                id: art
                anchors.fill: parent
                source: root.artUrl
                visible: root.artUrl !== "" && status === Image.Ready
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                // Do not pin lock-screen art in QPixmapCache (iNiR #163/#164 lesson).
                cache: false
            }
            ShellText {
                anchors.centerIn: parent
                visible: !(root.artUrl !== "" && art.status === Image.Ready)
                text: "♫"; color: Theme.pink
                font.family: Theme.fontFamily; font.pixelSize: 24
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 3

            ShellText {
                Layout.fillWidth: true
                text: root.title
                elide: Text.ElideRight
                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14
            }
            ShellText {
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.artist
                elide: Text.ElideRight
                color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12
            }

            // Compact read-only progress bar.
            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: 2
                implicitHeight: 4
                radius: 2
                color: Theme.sliderTrack
                Rectangle {
                    width: parent.width * (root.duration > 0 ? Math.min(1, root.position / root.duration) : 0)
                    height: parent.height
                    radius: 2
                    color: Theme.accent
                    visible: root.progressAvailable
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                ShellText {
                    text: root.progressAvailable ? FocusTimer.format(Math.floor(root.position)) : ""
                    color: Theme.muted; font.family: Theme.monoFamily; font.pixelSize: 11
                }
                Item { Layout.fillWidth: true }

                LiquidButton {
                    text: "⏮"; leftPadding: 10; rightPadding: 10
                    enabled: !!(root.player && root.player.canGoPrevious)
                    onClicked: if (root.player) root.player.previous()
                    palette.button: Theme.surface
                    palette.buttonText: Theme.text
                    Accessible.name: "Previous track"
                }
                LiquidButton {
                    text: root.player && root.player.isPlaying ? "⏸" : "▶"
                    leftPadding: 12; rightPadding: 12
                    enabled: !!(root.player && root.player.canTogglePlaying)
                    onClicked: if (root.player) root.player.togglePlaying()
                    palette.button: Theme.surface
                    palette.buttonText: Theme.text
                    Accessible.name: root.player && root.player.isPlaying ? "Pause" : "Play"
                }
                LiquidButton {
                    text: "⏭"; leftPadding: 10; rightPadding: 10
                    enabled: !!(root.player && root.player.canGoNext)
                    onClicked: if (root.player) root.player.next()
                    palette.button: Theme.surface
                    palette.buttonText: Theme.text
                    Accessible.name: "Next track"
                }

                Item { Layout.fillWidth: true }
                ShellText {
                    text: root.progressAvailable ? FocusTimer.format(Math.floor(root.duration)) : "—"
                    color: Theme.muted; font.family: Theme.monoFamily; font.pixelSize: 11
                }
            }
        }
    }

    // The 1s position tick: Quickshell's getter advances its local clock; this
    // does not poll D-Bus (the MediaProgress lesson).
    Timer {
        interval: 1000
        repeat: true
        running: root.visible && root.player !== null && root.player.isPlaying
        onTriggered: if (root.player) root.player.positionChanged()
    }
}
