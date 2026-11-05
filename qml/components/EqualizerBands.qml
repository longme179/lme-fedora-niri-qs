import QtQuick
import QtQuick.Controls
import "../services"
import "../theme"

// Serpantinum MusicEqView port: ten vertical band sliders, lightning sweep and
// per-band pulses. Band edits are staged through EqualizerState.setBand.
Item {
    id: root
    property var eqData: ({})
    property real intro: 1
    property color accentColor: Theme.accent
    readonly property var bandModel: [
        {idx: 1, lbl: "31"}, {idx: 2, lbl: "63"}, {idx: 3, lbl: "125"},
        {idx: 4, lbl: "250"}, {idx: 5, lbl: "500"}, {idx: 6, lbl: "1k"},
        {idx: 7, lbl: "2k"}, {idx: 8, lbl: "4k"}, {idx: 9, lbl: "8k"},
        {idx: 10, lbl: "16k"}
    ]
    implicitHeight: 168
    signal bandMoved(int band, real value)

    Row {
        id: bandRow
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottomMargin: 16
        z: 1

        Repeater {
            model: root.bandModel

            delegate: Item {
                id: bandDelegate
                required property var modelData
                width: bandRow.width / 10
                height: bandRow.height
                opacity: root.intro
                transform: Translate {
                    y: 25 * (1 - root.intro) + (index * 7 * (1 - root.intro))
                }

                property real dist: EqualizerState.eqLightningProgress - (modelData.idx - 1)
                property real hitPulse: dist >= 0 && dist < 1.0 ? Math.sin(dist * Math.PI) : 0.0
                property real trackPulse: 0.0
                property real ringPulse: 0.0
                property real flashFade: 0.0
                property bool hasFired: false

                onDistChanged: {
                    if (dist <= 0.05) {
                        hasFired = false;
                    } else if (dist > 0.4 && !hasFired) {
                        hasFired = true;
                        trackPulseAnim.restart();
                        ringPulseAnim.restart();
                        flashFadeAnim.restart();
                    }
                }

                SequentialAnimation {
                    id: trackPulseAnim
                    NumberAnimation { target: bandDelegate; property: "trackPulse"; from: 0.0; to: 1.0; duration: 1000; easing.type: Easing.OutQuart }
                }
                SequentialAnimation {
                    id: ringPulseAnim
                    NumberAnimation { target: bandDelegate; property: "ringPulse"; from: 1.0; to: 0.0; duration: 1500; easing.type: Easing.OutExpo }
                }
                SequentialAnimation {
                    id: flashFadeAnim
                    NumberAnimation { target: bandDelegate; property: "flashFade"; from: 1.0; to: 0.0; duration: 1500; easing.type: Easing.OutSine }
                }

                Slider {
                    id: bandSlider
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 24
                    orientation: Qt.Vertical
                    from: -12
                    to: 12
                    stepSize: 1
                    hoverEnabled: true
                    opacity: enabled ? 1 : 0.35

                    Component.onCompleted: {
                        const initial = Number(root.eqData["b" + modelData.idx]);
                        if (Number.isFinite(initial))
                            value = initial;
                    }
                    Connections {
                        target: root
                        function onEqDataChanged() {
                            if (bandSlider.pressed)
                                return;
                            const next = Number(root.eqData["b" + modelData.idx]);
                            if (Number.isFinite(next))
                                bandSlider.value = next;
                        }
                    }
                    Behavior on value {
                        enabled: !bandSlider.pressed && Theme.animations
                        NumberAnimation { duration: 400; easing.type: Easing.OutQuart }
                    }
                    onPressedChanged: {
                        if (!pressed)
                            root.bandMoved(modelData.idx, Math.round(value));
                    }

                    background: Rectangle {
                        id: track
                        x: bandSlider.leftPadding + (bandSlider.availableWidth - width) / 2
                        y: bandSlider.topPadding
                        width: 12
                        height: bandSlider.availableHeight
                        radius: 6
                        color: Theme.sliderTrack

                        // Glow ring around the struck track (MusicEqView ring pulse).
                        Rectangle {
                            z: -1
                            anchors.centerIn: parent
                            width: parent.width + 17 + bandDelegate.ringPulse * 34
                            height: parent.height + 17 + bandDelegate.ringPulse * 51
                            radius: parent.radius + 8 + bandDelegate.ringPulse * 17
                            color: "transparent"
                            border.color: root.accentColor
                            border.width: 2 + bandDelegate.ringPulse * 4
                            opacity: bandDelegate.ringPulse * 0.8 * (1.0 - EqualizerState.eqLightningFade)
                        }

                        // Filled range from the bottom up to the handle.
                        Item {
                            width: parent.width
                            height: (1 - bandSlider.visualPosition) * parent.height
                            y: bandSlider.visualPosition * parent.height
                            clip: true

                            Rectangle {
                                anchors.fill: parent
                                radius: track.radius
                                color: root.accentColor
                            }

                            // Fill flash riding the lightning strike.
                            Rectangle {
                                anchors.fill: parent
                                radius: track.radius
                                opacity: bandDelegate.flashFade
                                gradient: Gradient {
                                    orientation: Gradient.Vertical
                                    GradientStop { position: 0.0; color: Qt.lighter(root.accentColor, 1.3) }
                                    GradientStop { position: 0.5; color: root.accentColor }
                                    GradientStop { position: 1.0; color: "transparent" }
                                }
                            }

                            // Rising pulse bar under the struck band.
                            Rectangle {
                                width: parent.width
                                height: 70
                                y: (bandDelegate.trackPulse * (parent.height + height)) - height
                                radius: width / 2
                                opacity: Math.sin(bandDelegate.trackPulse * Math.PI) * 2.0 * (1.0 - EqualizerState.eqLightningFade)
                                gradient: Gradient {
                                    orientation: Gradient.Vertical
                                    GradientStop { position: 0.0; color: "transparent" }
                                    GradientStop { position: 0.2; color: root.accentColor }
                                    GradientStop { position: 0.5; color: Theme.text }
                                    GradientStop { position: 0.8; color: Qt.lighter(root.accentColor, 1.2) }
                                    GradientStop { position: 1.0; color: "transparent" }
                                }
                            }
                        }
                    }

                    handle: Rectangle {
                        id: handle
                        x: bandSlider.leftPadding + (bandSlider.availableWidth - width) / 2
                        y: bandSlider.topPadding + bandSlider.visualPosition * (bandSlider.availableHeight - height)
                        width: 16
                        height: 16
                        radius: 8
                        color: bandSlider.pressed ? Qt.lighter(root.accentColor, 1.30)
                            : bandSlider.hovered ? Qt.lighter(root.accentColor, 1.15)
                            : Theme.text
                        Behavior on color { ColorAnimation { duration: 150 } }

                        property real targetScale: bandSlider.pressed ? 1.25 : bandSlider.hovered ? 1.08 : 1.0
                        Behavior on targetScale { NumberAnimation { duration: 150; easing.type: Easing.OutBack } }

                        property real popScale: 1.0
                        property real flashOpacity: 0.0

                        SequentialAnimation {
                            id: handlePop
                            NumberAnimation { target: handle; property: "popScale"; to: 1.12; duration: 100; easing.type: Easing.OutQuad }
                            NumberAnimation { target: handle; property: "popScale"; to: 1.0; duration: 250; easing.type: Easing.OutCubic }
                        }
                        NumberAnimation {
                            id: handleFlash
                            target: handle
                            property: "flashOpacity"
                            from: 0.35
                            to: 0
                            duration: 250
                            easing.type: Easing.OutCubic
                        }
                        Connections {
                            target: bandSlider
                            function onMoved() { handlePop.restart(); }
                            function onPressedChanged() {
                                if (!bandSlider.pressed)
                                    handleFlash.restart();
                            }
                        }

                        // White release flash over the handle.
                        Rectangle {
                            anchors.fill: parent
                            radius: parent.radius
                            color: "#ffffff"
                            opacity: handle.flashOpacity
                        }

                        // Halo burst when the lightning passes this band.
                        Rectangle {
                            anchors.centerIn: parent
                            width: parent.width + 31 * bandDelegate.hitPulse
                            height: width
                            radius: width / 2
                            color: root.accentColor
                            opacity: bandDelegate.hitPulse * 0.45 * (1.0 - EqualizerState.eqLightningFade)
                        }

                        scale: (targetScale * popScale) + (bandDelegate.hitPulse * 0.4 * (1.0 - EqualizerState.eqLightningFade))
                    }
                }

                LabelText {
                    anchors.top: bandSlider.bottom
                    anchors.topMargin: 2
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: modelData.lbl
                    color: Theme.muted
                    font.pixelSize: 10
                    font.bold: true
                }
            }
        }
    }

    // Lightning strand across the band positions (eq_lightning.frag port).
    ShaderEffect {
        id: lightning
        anchors.fill: parent
        z: 0
        opacity: 1.0 - EqualizerState.eqLightningFade
        visible: opacity > 0.001

        property real animTime: 0.0
        NumberAnimation on animTime {
            running: lightning.visible && Theme.animations
            loops: Animation.Infinite
            from: 0
            to: 1000
            duration: 1000000
        }

        property vector2d itemSize: Qt.vector2d(width, height)
        property real time: animTime
        property real progress: EqualizerState.eqLightningProgress
        property real fade: EqualizerState.eqLightningFade
        property real scale: 1.0
        property color accentColor: root.accentColor

        property vector4d bands0: Qt.vector4d(
            Number(root.eqData.b1) || 0, Number(root.eqData.b2) || 0,
            Number(root.eqData.b3) || 0, Number(root.eqData.b4) || 0)
        property vector4d bands1: Qt.vector4d(
            Number(root.eqData.b5) || 0, Number(root.eqData.b6) || 0,
            Number(root.eqData.b7) || 0, Number(root.eqData.b8) || 0)
        property vector4d bands2: Qt.vector4d(
            Number(root.eqData.b9) || 0, Number(root.eqData.b10) || 0, 0, 16)

        fragmentShader: Qt.resolvedUrl("shaders/eq-lightning.frag.qsb")
    }
}
