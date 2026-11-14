// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LockArtQuantizer.qml (lock layer, fan-in 1 — LockMediaWidget's
// dominant-colour source). The cover averaged into an 8×8 canvas — iNiR's
// ColorQuantizer at depth 0 / rescale 1 without a C++ plugin — leaned toward
// the theme's primary container so the art never fully owns the card.
// The canvas lessons from #158 live here: paint on request (Immediate), park
// the canvas where nothing shows it but the paint pass still runs, and never
// average a paint that arrived before the cover decoded.
// REL: Theme (purple/primaryContainer mix) — the caller feeds artUrl and binds
// dominant.
pragma ComponentBehavior: Bound
import QtQuick
import "../../theme"

Item {
    id: root
    required property url artUrl
    // No art yet (or a failed decode): the theme fallback, like iNiR.
    property color dominant: Theme.mix(Theme.purple, Theme.primaryContainer, 0.7)

    Canvas {
        id: quantizer
        // Painted but never shown: an offscreen corner inside the caller's
        // clipped card. A visible:false canvas never gets its paint pass.
        x: -width; y: -height
        width: 8; height: 8
        renderStrategy: Canvas.Immediate
        property bool artReady: false
        onPaint: {
            if (!artReady)
                return
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.drawImage(root.artUrl, 0, 0, width, height)
            const data = ctx.getImageData(0, 0, width, height).data
            let r = 0, g = 0, b = 0
            const samples = width * height
            for (let i = 0; i < samples; i++) {
                r += data[i * 4]; g += data[i * 4 + 1]; b += data[i * 4 + 2]
            }
            root.dominant = Theme.mix(
                Qt.rgba(r / samples / 255, g / samples / 255, b / samples / 255, 1),
                Theme.primaryContainer, 0.7)
            // Do not pin lock-screen art in memory either (iNiR #163/#164 lesson).
            unloadImage(root.artUrl)
            artReady = false
        }
        Component.onCompleted: if (root.artUrl !== "") loadImage(root.artUrl)
        onImageLoaded: { artReady = true; requestPaint() }
        Connections {
            target: root
            function onArtUrlChanged() {
                artReady = false
                if (root.artUrl !== "")
                    quantizer.loadImage(root.artUrl)
            }
        }
    }
}
