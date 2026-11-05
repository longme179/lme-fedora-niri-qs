pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

// Serpantinum equalizer panel port: staged band editing with the lightning
// sweep, preset chips, a dimming Dynamic EQ overlay, and the audio view with
// balance, channel flags, dynamic range and the channel test tone.
GlassPanel {
    id: root
    implicitWidth: 620
    implicitHeight: 440
    focus: true
    Keys.onEscapePressed: ShellState.closePanels()

    property int pageIndex: 0
    property real introHeader: 1
    property real introSliders: 1
    property real introPresets: 1
    property real introBalance: 1
    property real introFlags: 1
    property real introDynamics: 1

    readonly property var eqData: EqualizerState.eqData
    readonly property bool dynamicOn: eqData ? eqData.dyneq === true : false
    property real dynamicDim: dynamicOn ? 1.0 : 0.0
    Behavior on dynamicDim { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }

    onVisibleChanged: {
        if (!visible)
            return;
        EqualizerState.refresh();
        playIntro();
    }
    Component.onCompleted: {
        if (visible) {
            EqualizerState.refresh();
            playIntro();
        }
    }

    function playIntro() {
        if (!Theme.animations) {
            introHeader = 1; introSliders = 1; introPresets = 1;
            introBalance = 1; introFlags = 1; introDynamics = 1;
            return;
        }
        introHeader = 0; introSliders = 0; introPresets = 0;
        introBalance = 0; introFlags = 0; introDynamics = 0;
        introAnim.restart();
    }

    function playAudioIntro() {
        if (!Theme.animations) {
            introBalance = 1; introFlags = 1; introDynamics = 1;
            return;
        }
        audioIntroAnim.restart();
    }

    ParallelAnimation {
        id: introAnim
        running: false
        SequentialAnimation {
            PauseAnimation { duration: 60 }
            NumberAnimation { target: root; property: "introHeader"; from: 0; to: 1.0; duration: 710; easing.type: Easing.OutQuart }
        }
        SequentialAnimation {
            PauseAnimation { duration: 180 }
            NumberAnimation { target: root; property: "introSliders"; from: 0; to: 1.0; duration: 860; easing.type: Easing.OutExpo }
        }
        SequentialAnimation {
            PauseAnimation { duration: 300 }
            NumberAnimation { target: root; property: "introPresets"; from: 0; to: 1.0; duration: 810; easing.type: Easing.OutBack; easing.overshoot: 0.8 }
        }
    }

    SequentialAnimation {
        id: audioIntroAnim
        running: false
        NumberAnimation { target: root; property: "introBalance"; from: 0; to: 1.0; duration: 560; easing.type: Easing.OutQuart }
        PauseAnimation { duration: 60 }
        NumberAnimation { target: root; property: "introFlags"; from: 0; to: 1.0; duration: 560; easing.type: Easing.OutQuart }
        PauseAnimation { duration: 60 }
        NumberAnimation { target: root; property: "introDynamics"; from: 0; to: 1.0; duration: 560; easing.type: Easing.OutQuart }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            LabelText { text: qsTr("Equalizer"); font.pixelSize: 22; font.weight: Font.Bold; Layout.fillWidth: true }
            IconButton { glyph: "×"; tooltip: qsTr("Close equalizer"); onClicked: ShellState.closePanels() }
        }

        // Toolbar (MusicBottomHeader port): tabs, test, dynamic and apply.
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            opacity: root.introHeader
            transform: Translate { y: 12 * (1 - root.introHeader) }

            SegmentSwitch {
                options: [qsTr("Equalizer"), qsTr("Audio")]
                currentIndex: root.pageIndex
                onActivated: index => {
                    if (index === root.pageIndex)
                        return;
                    // Switching views abandons staged band edits (upstream parity).
                    EqualizerState.revertPending();
                    root.pageIndex = index;
                    if (index === 1)
                        root.playAudioIntro();
                }
            }
            Item { Layout.fillWidth: true }

            LiquidButton {
                visible: root.pageIndex === 1
                Layout.preferredHeight: 34
                text: EqualizerState.audioTestRunning ? qsTr("Stop") : qsTr("Test")
                selected: EqualizerState.audioTestRunning
                selectionColor: Theme.accent
                onClicked: EqualizerState.toggleTest()
            }

            // The Dynamic EQ control stays outside the view it dims, so it can
            // always be switched off (the old popup locked itself here).
            RowLayout {
                spacing: 6
                LabelText {
                    text: qsTr("Dynamic")
                    color: root.dynamicOn ? Theme.accent : Theme.muted
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    Behavior on color { ColorMotion {} }
                }
                ExpressiveSwitch {
                    checked: root.dynamicOn
                    onToggled: {
                        const requested = checked;
                        checked = Qt.binding(() => root.dynamicOn);
                        EqualizerState.setFlag("dyneq", requested);
                    }
                }
            }

            LiquidButton {
                Layout.preferredHeight: 34
                readonly property bool dirty: root.eqData && (Math.abs(root.eqData.balance || 0) >= 0.005
                    || root.eqData.mono === true || root.eqData.swap === true
                    || String(root.eqData.dynamics || "off") !== "off")
                enabled: root.pageIndex === 0
                    ? (root.eqData && root.eqData.pending === true && !root.dynamicOn)
                    : dirty
                text: root.pageIndex === 0
                    ? (root.eqData && root.eqData.pending ? qsTr("Apply") : qsTr("Saved"))
                    : qsTr("Reset")
                selected: root.pageIndex === 0 && root.eqData && root.eqData.pending === true
                selectionColor: Theme.accent
                onClicked: root.pageIndex === 0 ? EqualizerState.commit() : EqualizerState.resetAudio()
            }

            LabelText {
                visible: root.pageIndex === 0
                text: root.eqData && root.eqData.preset ? root.eqData.preset : "Flat"
                color: Theme.muted
                font.pixelSize: 13
                font.bold: true
            }
        }

        LabelText {
            Layout.fillWidth: true
            visible: EqualizerState.loadStatus.length > 0
            text: EqualizerState.loadStatus
            color: Theme.muted
            wrapMode: Text.Wrap
        }

        // Sliding pages (MusicEqView/MusicAudioView crossfade port).
        Item {
            id: pager
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Item {
                id: eqView
                anchors.top: parent.top
                anchors.left: parent.left
                width: pager.width
                height: eqColumn.implicitHeight
                x: root.pageIndex === 0 ? 0 : -pager.width - 24
                opacity: root.pageIndex === 0 ? 1.0 : 0.0
                visible: opacity > 0.0
                Behavior on x { NumberAnimation { duration: 400; easing.type: Easing.OutQuart } }
                Behavior on opacity { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }

                ColumnLayout {
                    id: eqColumn
                    width: eqView.width
                    spacing: 14
                    enabled: !root.dynamicOn
                    opacity: 1.0 - 0.7 * root.dynamicDim

                    EqualizerBands {
                        id: bands
                        Layout.fillWidth: true
                        eqData: root.eqData
                        intro: root.introSliders
                        onBandMoved: (band, value) => EqualizerState.setBand(band, value)
                    }

                    EqualizerPresets {
                        id: presets
                        Layout.fillWidth: true
                        eqData: root.eqData
                        opacity: root.introPresets
                        transform: Translate { y: 18 * (1 - root.introPresets) }
                        onPresetSelected: name => EqualizerState.applyPreset(name)
                    }
                }

                // Dynamic EQ veil: input-blocked, with the upstream message.
                Item {
                    anchors.fill: parent
                    z: 10
                    opacity: root.dynamicDim
                    visible: opacity > 0.01

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.AllButtons
                        onWheel: wheel => wheel.accepted = true
                    }
                    LabelText {
                        anchors.centerIn: parent
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: qsTr("Adapting to your sound")
                        font.pixelSize: 18
                        font.bold: true
                    }
                }
            }

            Item {
                id: audioView
                anchors.top: parent.top
                anchors.left: parent.left
                width: pager.width
                height: audioColumn.implicitHeight
                x: root.pageIndex === 1 ? 0 : pager.width + 24
                opacity: root.pageIndex === 1 ? 1.0 : 0.0
                visible: opacity > 0.0
                Behavior on x { NumberAnimation { duration: 400; easing.type: Easing.OutQuart } }
                Behavior on opacity { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }

                ColumnLayout {
                    id: audioColumn
                    width: audioView.width
                    spacing: 8

                    EqualizerAudioControls {
                        Layout.fillWidth: true
                        eqData: root.eqData
                        introBalance: root.introBalance
                        introFlags: root.introFlags
                        introDynamics: root.introDynamics
                    }
                }
            }
        }
    }
}
