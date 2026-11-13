// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockWallpaper.qml (lock layer, fan-in 1 — LockSurface's backdrop).
// Ported from the wallpaper half of iNiR's LockSurface.qml @ edca6cc (GPL-3.0):
// the current session wallpaper, blurred and dimmed behind the lock UI.
// Phase 1 policy (plan decision D2): static image + MultiEffect blur only — the
// shell has no gif/video wallpapers, so iNiR's second pipeline is unnecessary.
// GOTCHA (iNiR #163/#164): cache stays false; a cached lock wallpaper pins the
// source image in QPixmapCache for the whole session.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects
import "../../services"
import "../../theme"

Item {
    id: root
    anchors.fill: parent

    // WallpaperState.current() is the live wallpaper path; the bundled Dracula
    // asset is the same fallback the desktop preview uses when none is set.
    readonly property string source: WallpaperState.current("") || "../../../assets/wallpapers/liquid-dracula.png"
    readonly property color tint: Theme.background

    Image {
        id: wallpaper
        anchors.fill: parent
        source: root.source
        fillMode: Image.PreserveAspectCrop
        cache: false
        visible: false
        asynchronous: true
    }

    MultiEffect {
        id: blur
        anchors.fill: wallpaper
        source: wallpaper
        blurEnabled: true
        blur: 0.8
        blurMax: 64
        blurMultiplier: 1.0
        // Slight zoom hides the blurred edge sampling at the screen border.
        scale: 1.1
    }

    // A dark tint plus a flat dim keep text readable over any wallpaper.
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.35)
    }
    Rectangle {
        anchors.fill: parent
        color: "#59000000"
    }
}
