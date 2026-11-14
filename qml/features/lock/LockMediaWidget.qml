// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockMediaWidget.qml (lock layer, fan-in 1 — LockSurface's media card).
// Ported from iNiR's LockMediaWidget.qml @ edca6cc (GPL-3.0; design reference
// re-read at 2836543), Material path only — the owner's L3 decision after the
// walkthrough: the card leaves liquid glass for a Material scheme adapted to
// the cover art's dominant colour (LockArtQuantizer, own file), a 110px art
// thumb, and the final 520×150 the owner approved. The card and the thumb
// composite through Qt5Compat OpacityMask corner masks — clip cuts bounding
// boxes, not radii (#158), and MultiEffect's mask blanked the whole layer on
// the live lock surface (#160's silent regression; OpacityMask is iNiR's own
// mask for this card, proven on session-lock surfaces). The final ground is
// the blurred cover itself — flat 25% darken + a two-ring feather rim +
// 1px border per the owner's 2026-11-15 design (the soft-ring dimming
// mirrors how iNiR grounds its lock media backdrop). Reshaped on this stack:
// LiquidButton glyphs for MaterialSymbol; cava and seek stay out (no cava
// here; the bar keeps the read-only MediaProgress lesson).
// REL: LockArtQuantizer (dominant colour), services (FocusTimer time
// formatting), components (ShellText/LiquidButton), theme.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Qt5Compat.GraphicalEffects as GE
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

    // The dominant colour of the cover (the pipeline and its lessons live in
    // LockArtQuantizer); no art means the theme fallback. Declared after the
    // quantizer: bindings evaluate in document order, before later ids exist.
    LockArtQuantizer { id: quantizer; artUrl: root.artUrl }
    readonly property color artDominantColor: quantizer.dominant

    // Material scheme adapted to the dominant colour (iNiR AdaptedMaterialScheme):
    // the art lends its hue while every role keeps its tone, so the text/track
    // pairs keep their contrast instead of washing to the art's mid grey.
    // The text ink is `ink`, NOT `onLayer0`: a property whose name is on+Cap
    // on an object owning a `layer0` property is swallowed as layer0's change
    // handler — the binding never ran, the ink stayed invalid (black) since
    // #158, hidden by the bright-wash ground. #163's dark ground (and the
    // render-PNG review it feeds) exposed it.
    readonly property QtObject scheme: QtObject {
        function adapted(base: color, amount: real): color {
            const mixed = Theme.mix(base, root.artDominantColor, amount)
            return Qt.hsla(mixed.hslHue, mixed.hslSaturation, base.hslLightness, 1)
        }
        readonly property color layer0: adapted(Theme.panel, 0.5)
        readonly property color layer1: adapted(Theme.surfaceContainer, 0.5)
        readonly property color ink: adapted(Theme.text, 0.5)
        readonly property color subtext: adapted(Theme.muted, 0.5)
        readonly property color primary: Qt.hsla(root.artDominantColor.hslHue, Theme.accent.hslSaturation, Theme.accent.hslLightness, 1)
        readonly property color secondaryContainer: adapted(Theme.secondaryContainer, 0.3)
    }
    readonly property color cardColor: root.scheme.layer0

    visible: hasPlayer
    implicitWidth: 520
    implicitHeight: 150
    radius: 18
    // With art, the base steps aside: the blurred cover + the flat darken are
    // the ground (owner: no bright wash over the art).
    color: "transparent"
    border.width: 1
    border.color: Theme.border
    clip: true
    // Real rounded corners: clip only cuts the bounding box, and MultiEffect's
    // mask blanked the whole layer on the live lock surface — the #160 silent
    // render regression, not one log line. iNiR's own mask for this card is
    // Qt5Compat's OpacityMask, proven on session-lock surfaces; the card keeps
    // MultiEffect only for the backdrop blur (which renders fine).
    layer.enabled: true
    layer.effect: GE.OpacityMask {
        maskSource: Rectangle { width: root.width; height: root.height; radius: root.radius }
    }

    // No-art fallback: the adapted base only when there is no cover to blur.
    Rectangle {
        anchors.fill: parent
        visible: root.artUrl === ""
        color: root.scheme.layer0
    }

    // The blurred cover behind everything (iNiR art backdrop), kept at 0.6 so
    // the art reads through the flat darken layered above it.
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
    // Flat 25% darken over the blurred cover — the owner's dark ground.
    Rectangle {
        anchors.fill: parent
        color: Theme.alpha("#000000", 0.25)
    }
    // Feather rim: two soft rings instead of a hard edge, fading the darken
    // toward the 1px border (owner: "feather viền").
    Rectangle {
        anchors.fill: parent; radius: root.radius; color: "transparent"
        border.width: 18; border.color: Theme.alpha("#000000", 0.05)
    }
    Rectangle {
        anchors.fill: parent; radius: root.radius; color: "transparent"
        border.width: 8; border.color: Theme.alpha("#000000", 0.10)
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 14

        // Cover art thumbnail (110px) with the note-glyph fallback.
        Rectangle {
            id: artThumb
            Layout.preferredWidth: 110
            Layout.preferredHeight: 110
            Layout.alignment: Qt.AlignVCenter
            radius: 12
            color: root.scheme.layer1
            clip: true
            layer.enabled: true
            layer.effect: GE.OpacityMask {
                maskSource: Rectangle { width: artThumb.width; height: artThumb.height; radius: artThumb.radius }
            }

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
            spacing: 3

            ShellText {
                Layout.fillWidth: true
                text: root.title
                elide: Text.ElideRight
                color: root.scheme.ink
                font.family: Theme.fontFamily; font.pixelSize: 15; font.weight: Font.Medium
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
                implicitHeight: 6
                radius: 3
                color: root.scheme.secondaryContainer
                Rectangle {
                    width: parent.width * (root.duration > 0 ? Math.min(1, root.position / root.duration) : 0)
                    height: parent.height
                    radius: 3
                    color: root.scheme.primary
                    visible: root.progressAvailable
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                ShellText {
                    text: root.progressAvailable ? FocusTimer.format(Math.floor(root.position)) : ""
                    color: root.scheme.ink; font.family: Theme.monoFamily; font.pixelSize: 11
                }
                Item { Layout.fillWidth: true }

                // Media pills (owner tweak 2026-11-15): wider horizontal pads so the
                // LiquidButton pill shape reads, and a flat, translucent thumbnail
                // tint instead of a bright overlay washing the card.
                LiquidButton {
                    text: "⏮"; leftPadding: 20; rightPadding: 20
                    enabled: !!(root.player && root.player.canGoPrevious)
                    onClicked: if (root.player) root.player.previous()
                    palette.button: Theme.alpha(root.scheme.layer1, 0.3)
                    palette.buttonText: root.scheme.ink
                    Accessible.name: "Previous track"
                }
                LiquidButton {
                    text: root.player && root.player.isPlaying ? "⏸" : "▶"
                    leftPadding: 24; rightPadding: 24
                    enabled: !!(root.player && root.player.canTogglePlaying)
                    onClicked: if (root.player) root.player.togglePlaying()
                    palette.button: Theme.alpha(root.scheme.layer1, 0.3)
                    palette.buttonText: root.scheme.primary
                    Accessible.name: root.player && root.player.isPlaying ? "Pause" : "Play"
                }
                LiquidButton {
                    text: "⏭"; leftPadding: 20; rightPadding: 20
                    enabled: !!(root.player && root.player.canGoNext)
                    onClicked: if (root.player) root.player.next()
                    palette.button: Theme.alpha(root.scheme.layer1, 0.3)
                    palette.buttonText: root.scheme.ink
                    Accessible.name: "Next track"
                }

                Item { Layout.fillWidth: true }
                ShellText {
                    text: root.progressAvailable ? FocusTimer.format(Math.floor(root.duration)) : "—"
                    color: root.scheme.ink; font.family: Theme.monoFamily; font.pixelSize: 11
                }
            }
        }
    }

    // Engine seam: both corner masks must actually be armed. Reached through
    // the layer property chains — ids declared inside layer.effect values do
    // not join the file scope other bindings can see.
    readonly property bool maskArmed: root.layer.enabled && root.layer.effect !== null
        && artThumb.layer.enabled && artThumb.layer.effect !== null

    // The 1s position tick: Quickshell's getter advances its local clock; this
    // does not poll D-Bus (the MediaProgress lesson).
    Timer {
        interval: 1000
        repeat: true
        running: root.visible && root.player !== null && root.player.isPlaying
        onTriggered: if (root.player) root.player.positionChanged()
    }
}
