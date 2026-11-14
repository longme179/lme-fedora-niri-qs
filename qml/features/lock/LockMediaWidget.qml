// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockMediaWidget.qml (lock layer, fan-in 1 — LockSurface's media card).
// Ported from iNiR's LockMediaWidget.qml @ edca6cc (GPL-3.0; design reference
// re-read at 2836543), Material path only — the owner's L3 decision after the
// walkthrough: the card leaves liquid glass for a Material scheme adapted to
// the cover art's dominant colour, a 110px art thumb, and grows to 130px to
// balance the clock. Reshaped onto this shell's stack: the dominant colour is
// the 1×1 image average (iNiR's ColorQuantizer at depth 0 / rescale 1, done
// with sourceSize + an offscreen grab), LiquidButton glyphs stand in for
// MaterialSymbol, and the cava visualizer and seek stay out (no cava here; the
// bar keeps the read-only MediaProgress lesson).
// REL: services (FocusTimer time formatting), components (ShellText/LiquidButton), theme.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
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

    // The dominant colour of the cover: the 1×1 average, grabbed offscreen once
    // per artwork (iNiR quantizes the same way and leans the mix toward the
    // theme's primary container so the art never fully owns the card).
    property color artDominantColor: Theme.mix(Theme.purple, Theme.primaryContainer, 0.7)
    Image {
        id: quantizer
        visible: false
        source: root.artUrl
        sourceSize: Qt.size(1, 1)
        asynchronous: true
        cache: false // do not pin lock-screen art in QPixmapCache (iNiR #163/#164)
        onStatusChanged: if (status === Image.Ready)
            grabToImage(result => root.artDominantColor = Theme.mix(
                result.image.pixelColor(0, 0), Theme.primaryContainer, 0.7))
    }

    // Material scheme adapted to the dominant colour (iNiR AdaptedMaterialScheme):
    // the art lends its hue while every role keeps its tone, so the text/track
    // pairs keep their contrast instead of washing to the art's mid grey.
    readonly property QtObject scheme: QtObject {
        function adapted(base: color, amount: real): color {
            const mixed = Theme.mix(base, root.artDominantColor, amount)
            return Qt.hsla(mixed.hslHue, mixed.hslSaturation, base.hslLightness, 1)
        }
        readonly property color layer0: adapted(Theme.panel, 0.5)
        readonly property color layer1: adapted(Theme.surfaceContainer, 0.5)
        readonly property color onLayer0: adapted(Theme.text, 0.5)
        readonly property color subtext: adapted(Theme.muted, 0.5)
        readonly property color primary: Qt.hsla(root.artDominantColor.hslHue, Theme.accent.hslSaturation, Theme.accent.hslLightness, 1)
        readonly property color secondaryContainer: adapted(Theme.secondaryContainer, 0.3)
    }
    readonly property color cardColor: root.scheme.layer0

    visible: hasPlayer
    implicitWidth: 460
    implicitHeight: 130
    radius: 18
    color: root.scheme.layer0
    border.width: 1
    border.color: Theme.border
    clip: true

    // The blurred cover behind everything, dimmed by a horizontal gradient of
    // the adapted layer so the controls keep their ink (iNiR art backdrop).
    Image {
        anchors.fill: parent
        source: root.artUrl
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        visible: root.artUrl !== "" && status === Image.Ready
        opacity: 0.6
        layer.enabled: visible
        layer.effect: MultiEffect {
            blurEnabled: true
            blur: 0.4
            blurMax: 32
            saturation: 0.4
        }
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Theme.alpha(root.scheme.layer0, 0.7) }
            GradientStop { position: 0.3; color: Theme.alpha(root.scheme.layer0, 0.4) }
            GradientStop { position: 1.0; color: Theme.alpha(root.scheme.layer0, 0.2) }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        // Cover art thumbnail (110px, masked corners) with the note-glyph fallback.
        Rectangle {
            Layout.preferredWidth: 110
            Layout.preferredHeight: 110
            Layout.alignment: Qt.AlignVCenter
            radius: 12
            color: root.scheme.layer1
            clip: true

            Image {
                id: art
                anchors.fill: parent
                source: root.artUrl
                visible: root.artUrl !== "" && status === Image.Ready
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: false
            }
            ShellText {
                anchors.centerIn: parent
                visible: !(root.artUrl !== "" && art.status === Image.Ready)
                text: "♫"; color: root.scheme.subtext
                font.family: Theme.fontFamily; font.pixelSize: 32
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 2

            ShellText {
                Layout.fillWidth: true
                text: root.title
                elide: Text.ElideRight
                color: root.scheme.onLayer0
                font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.Medium
            }
            ShellText {
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.artist
                elide: Text.ElideRight
                color: root.scheme.subtext
                font.family: Theme.fontFamily; font.pixelSize: 12
            }

            Item { Layout.fillHeight: true }

            // Compact read-only progress bar (MediaProgress lesson: no polling).
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 4
                radius: 2
                color: root.scheme.secondaryContainer
                Rectangle {
                    width: parent.width * (root.duration > 0 ? Math.min(1, root.position / root.duration) : 0)
                    height: parent.height
                    radius: 2
                    color: root.scheme.primary
                    visible: root.progressAvailable
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                ShellText {
                    text: root.progressAvailable ? FocusTimer.format(Math.floor(root.position)) : ""
                    color: root.scheme.onLayer0; font.family: Theme.monoFamily; font.pixelSize: 11
                }
                Item { Layout.fillWidth: true }

                LiquidButton {
                    text: "⏮"; leftPadding: 10; rightPadding: 10
                    enabled: !!(root.player && root.player.canGoPrevious)
                    onClicked: if (root.player) root.player.previous()
                    palette.button: Theme.alpha(root.scheme.layer1, 0.5)
                    palette.buttonText: root.scheme.onLayer0
                    Accessible.name: "Previous track"
                }
                LiquidButton {
                    text: root.player && root.player.isPlaying ? "⏸" : "▶"
                    leftPadding: 12; rightPadding: 12
                    enabled: !!(root.player && root.player.canTogglePlaying)
                    onClicked: if (root.player) root.player.togglePlaying()
                    palette.button: root.scheme.primary
                    palette.buttonText: Theme.background
                    Accessible.name: root.player && root.player.isPlaying ? "Pause" : "Play"
                }
                LiquidButton {
                    text: "⏭"; leftPadding: 10; rightPadding: 10
                    enabled: !!(root.player && root.player.canGoNext)
                    onClicked: if (root.player) root.player.next()
                    palette.button: Theme.alpha(root.scheme.layer1, 0.5)
                    palette.buttonText: root.scheme.onLayer0
                    Accessible.name: "Next track"
                }

                Item { Layout.fillWidth: true }
                ShellText {
                    text: root.progressAvailable ? FocusTimer.format(Math.floor(root.duration)) : "—"
                    color: root.scheme.onLayer0; font.family: Theme.monoFamily; font.pixelSize: 11
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
