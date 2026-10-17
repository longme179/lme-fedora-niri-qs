// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Avenge Media LLC
// Loop/shuffle controls adapted from DMS MediaPlayerTab (8e690022); LME layout and capability guards.
import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Mpris
import "../services"

ColumnLayout {
    id: root
    property MprisPlayer player
    property string prefix: "media"
    readonly property bool canShuffle: !ShellState.demo && !!(player && player.canControl && player.shuffleSupported)
    readonly property bool canRepeat: !ShellState.demo && !!(player && player.canControl && player.loopSupported)
    readonly property bool shuffled: canShuffle && player.shuffle
    readonly property int loop: canRepeat ? player.loopState : MprisLoopState.None
    function toggleShuffle() { if (canShuffle) player.shuffle = !player.shuffle; }
    function cycleRepeat() {
        if (!canRepeat) return;
        player.loopState = loop === MprisLoopState.None ? MprisLoopState.Playlist : loop === MprisLoopState.Playlist ? MprisLoopState.Track : MprisLoopState.None;
    }
    spacing: 4
    GridLayout {
        Layout.alignment: Qt.AlignHCenter; columnSpacing: 8; rowSpacing: 6
        columns: previousButton.implicitWidth + playButton.implicitWidth + nextButton.implicitWidth + 16 <= root.width ? 3 : 1
        LiquidButton {
            id: previousButton; objectName: root.prefix + "Previous"; text: "Previous"; leftPadding: 8; rightPadding: 8
            enabled: ShellState.demo || !!(root.player && root.player.canGoPrevious)
            onClicked: if (root.player) root.player.previous()
        }
        LiquidButton {
            id: playButton; objectName: root.prefix + "Play"; text: (ShellState.demo ? ActivityState.demoPlaying : root.player?.isPlaying) ? "Pause" : "Play"
            selected: true; leftPadding: 12; rightPadding: 12
            enabled: ShellState.demo || !!(root.player && root.player.canTogglePlaying)
            onClicked: if (ShellState.demo) ActivityState.demoPlaying = !ActivityState.demoPlaying; else if (root.player) root.player.togglePlaying()
        }
        LiquidButton {
            id: nextButton; objectName: root.prefix + "Next"; text: "Next"; leftPadding: 8; rightPadding: 8
            enabled: ShellState.demo || !!(root.player && root.player.canGoNext)
            onClicked: if (root.player) root.player.next()
        }
    }
    GridLayout {
        visible: ShellState.preferences.mediaControls !== false
        Layout.alignment: Qt.AlignHCenter; columnSpacing: 8; rowSpacing: 6
        columns: shuffleButton.implicitWidth + repeatButton.implicitWidth + 8 <= root.width ? 2 : 1
        LiquidButton {
            id: shuffleButton; objectName: root.prefix + "Shuffle"; text: "Shuffle"; selected: root.shuffled; enabled: root.canShuffle
            Accessible.checkable: true; Accessible.checked: selected
            onClicked: root.toggleShuffle()
        }
        LiquidButton {
            id: repeatButton; objectName: root.prefix + "Repeat"
            text: root.loop === MprisLoopState.Playlist ? "Repeat all" : root.loop === MprisLoopState.Track ? "Repeat one" : "Repeat off"
            selected: root.loop !== MprisLoopState.None; enabled: root.canRepeat
            onClicked: root.cycleRepeat()
        }
    }
}
