// SPDX-License-Identifier: MIT
// Copyright (c) 2025-2026 Avenge Media LLC
// Adapted from DCommon M3WaveProgress at 50ca5ccb; LME theme and software fallback.
import QtQuick
import QtQuick.Window
import "../theme"

Item {
    id: root
    property real value: 0
    property bool isPlaying: false
    property real lineWidth: 2
    property real wavelength: 24
    property real amp: 3
    property real phase: 0
    property real currentAmp: isPlaying && Theme.mediaWave && Theme.animations ? amp : 0
    property color trackColor: Theme.colorFor("sliderTrack", Theme.alpha(Theme.muted, .35))
    property color fillColor: Theme.sliderFill
    readonly property bool software: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool animating: isPlaying && Theme.mediaWave && Theme.animations && visible && (Window.window?.visible ?? false)
    readonly property real ratio: Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0
    implicitHeight: 24
    signal frameTicked()

    Behavior on currentAmp {
        enabled: Theme.animations
        NumberAnimation { duration: Math.round(300 / Theme.motionSpeed); easing.type: Easing.OutCubic }
    }
    ShaderEffect {
        anchors.fill: parent; visible: !root.software
        readonly property real widthPx: width
        readonly property real heightPx: height
        readonly property real value: root.ratio
        readonly property real phase: root.phase
        readonly property real ampPx: root.currentAmp
        readonly property real wavelengthPx: root.wavelength
        readonly property real lineWidthPx: root.lineWidth
        readonly property vector4d fillColor: Qt.vector4d(root.fillColor.r, root.fillColor.g, root.fillColor.b, root.fillColor.a)
        readonly property vector4d trackColor: Qt.vector4d(root.trackColor.r, root.trackColor.g, root.trackColor.b, root.trackColor.a)
        fragmentShader: Qt.resolvedUrl("shaders/wave-progress.frag.qsb")
    }
    Canvas {
        id: fallback
        anchors.fill: parent; visible: root.software
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const c = getContext("2d"); c.reset(); c.clearRect(0, 0, width, height);
            const start = 4, end = Math.max(start, width - 4), head = start + root.ratio * (end - start), mid = height / 2;
            const waveY = x => mid + root.currentAmp * Math.sin(2 * Math.PI * x / root.wavelength + root.phase);
            c.lineCap = "round"; c.lineWidth = root.lineWidth;
            c.strokeStyle = root.trackColor; c.beginPath(); c.moveTo(head, mid); c.lineTo(end, mid); c.stroke();
            if (head > start) {
                c.strokeStyle = root.fillColor; c.beginPath(); c.moveTo(start, waveY(start));
                for (let x = start + 1.5; x < head; x += 1.5) c.lineTo(x, waveY(x));
                c.lineTo(head, waveY(head)); c.stroke();
            }
            c.strokeStyle = root.fillColor; c.lineWidth = 3.5;
            c.beginPath(); c.moveTo(head, mid - 6); c.lineTo(head, mid + 6); c.stroke();
        }
        Connections {
            target: root
            function onRatioChanged() { if (root.software) fallback.requestPaint(); }
            function onPhaseChanged() { if (root.software) fallback.requestPaint(); }
            function onCurrentAmpChanged() { if (root.software) fallback.requestPaint(); }
            function onFillColorChanged() { if (root.software) fallback.requestPaint(); }
            function onTrackColorChanged() { if (root.software) fallback.requestPaint(); }
        }
    }
    FrameAnimation {
        running: root.animating
        onTriggered: {
            root.phase = (root.phase + 1.8 * frameTime) % (2 * Math.PI);
            root.frameTicked();
        }
    }
}
