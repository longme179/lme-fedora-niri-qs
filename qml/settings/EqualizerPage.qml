import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

// Settings surface for the Serpantinum equalizer port: enable the optional
// daemon, stage band edits with presets, and tune the audio view.
ColumnLayout {
    id: root
    spacing: 20

    Component.onCompleted: EqualizerState.refresh()

    SettingsCard {
        title: qsTr("Serpantinum equalizer")
        description: qsTr("Optional external PipeWire daemon. Installing and starting serpantinum-audio is required; disabling stops the daemon and routes audio directly again.")

        RowLayout {
            Layout.fillWidth: true
            spacing: 20
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 5
                LabelText {
                    text: qsTr("Enable equalizer")
                    font.weight: Font.Medium
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
                LabelText {
                    text: qsTr("Start or stop the optional daemon")
                    color: Theme.muted
                    font.pixelSize: 13
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
            }
            ExpressiveSwitch {
                checked: ShellState.preferences.equalizerEnabled !== false
                enabled: ShellState.backendReady
                onToggled: {
                    const requested = checked;
                    checked = Qt.binding(() => ShellState.preferences.equalizerEnabled !== false);
                    ShellState.run("setting", {key: "equalizerEnabled", value: requested});
                    if (requested) ShellState.run("eqStart"); else ShellState.run("eqStop");
                }
            }
        }
        LabelText {
            Layout.fillWidth: true
            visible: EqualizerState.loadStatus.length > 0
            text: EqualizerState.loadStatus
            color: Theme.muted
            wrapMode: Text.Wrap
        }
        RowLayout {
            Layout.fillWidth: true
            LiquidButton {
                text: EqualizerState.eqData && EqualizerState.eqData.pending ? qsTr("Apply") : qsTr("Saved")
                enabled: ShellState.backendReady && EqualizerState.eqData && EqualizerState.eqData.pending === true
                selected: EqualizerState.eqData && EqualizerState.eqData.pending === true
                selectionColor: Theme.accent
                onClicked: EqualizerState.commit()
            }
            LiquidButton {
                text: qsTr("Status")
                enabled: ShellState.backendReady
                onClicked: ShellState.run("eqStatus")
            }
            Item { Layout.fillWidth: true }
            LabelText {
                text: EqualizerState.eqData && EqualizerState.eqData.preset ? EqualizerState.eqData.preset : "Flat"
                color: Theme.muted
                font.pixelSize: 13
                font.bold: true
            }
        }
    }

    SettingsCard {
        title: qsTr("Band gains")
        description: qsTr("Ten peaking bands from 31 Hz to 16 kHz, -12 to +12 dB. Drag a band to stage it, then Apply; presets apply immediately.")

        EqualizerBands {
            Layout.fillWidth: true
            Layout.leftMargin: 8
            Layout.rightMargin: 8
            eqData: EqualizerState.eqData
            onBandMoved: (band, value) => EqualizerState.setBand(band, value)
        }

        EqualizerPresets {
            Layout.fillWidth: true
            eqData: EqualizerState.eqData
            onPresetSelected: name => EqualizerState.applyPreset(name)
        }
    }

    SettingsCard {
        title: qsTr("Output and dynamics")
        description: qsTr("Balance, mono, channel swap and dynamic range; changes apply immediately. Test plays a channel tone through the equalizer sink.")

        EqualizerAudioControls {
            Layout.fillWidth: true
            eqData: EqualizerState.eqData
        }

        RowLayout {
            Layout.fillWidth: true
            LiquidButton {
                text: EqualizerState.audioTestRunning ? qsTr("Stop test") : qsTr("Test channels")
                selected: EqualizerState.audioTestRunning
                selectionColor: Theme.accent
                onClicked: EqualizerState.toggleTest()
            }
            LiquidButton {
                text: qsTr("Reset")
                enabled: EqualizerState.eqData && (Math.abs(EqualizerState.eqData.balance || 0) >= 0.005
                    || EqualizerState.eqData.mono === true || EqualizerState.eqData.swap === true
                    || String(EqualizerState.eqData.dynamics || "off") !== "off")
                onClicked: EqualizerState.resetAudio()
            }
            Item { Layout.fillWidth: true }
        }
    }
}
