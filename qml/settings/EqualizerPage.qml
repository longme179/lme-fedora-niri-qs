import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    spacing: 20
    property var gains: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    property real balance: 0
    property bool mono: false
    property bool swap: false
    property string dynamics: "off"
    property bool bypass: false
    property bool dyneq: false

    SettingsCard {
        title: "Serpantinum equalizer"
        description: "Optional external PipeWire daemon. Installing and starting serpantinum-audio is required; disabling stops the daemon and routes audio directly again."
        RowLayout {
            Layout.fillWidth: true; spacing: 20
            ColumnLayout {
                Layout.fillWidth: true; spacing: 5
                LabelText { text: "Enable equalizer"; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.Wrap }
                LabelText { text: "Start or stop the optional daemon"; color: Theme.muted; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
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
        LabelText { text: "Availability: " + (ShellState.backendReady ? "checked by backend actions" : "waiting"); color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
        RowLayout {
            Layout.fillWidth: true
            LiquidButton { text: "Apply"; enabled: ShellState.backendReady; onClicked: ShellState.run("eqApply", {gains: gains, balance: balance, mono: mono, swap: swap, dynamics: dynamics, bypass: bypass, dyneq: dyneq}) }
            LiquidButton { text: "Status"; enabled: ShellState.backendReady; onClicked: ShellState.run("eqStatus") }
        }
    }

    SettingsCard {
        title: "Band gains"
        description: "Ten peaking bands from 32 Hz to 16 kHz, -12 to +12 dB."
        Repeater {
            model: gains.length
            delegate: RowLayout {
                required property int index
                Layout.fillWidth: true
                LabelText { text: "Band " + (index + 1); Layout.preferredWidth: 70 }
                LiquidSlider {
                    Layout.fillWidth: true; from: -12; to: 12; stepSize: 0.5
                    value: gains[index] || 0
                    onMoved: if (!pressed) { const next = gains.slice(); next[index] = value; gains = next; }
                    onPressedChanged: if (!pressed) { const next = gains.slice(); next[index] = value; gains = next; }
                }
                LabelText { text: (gains[index] || 0).toFixed(1) + " dB"; Layout.preferredWidth: 60 }
            }
        }
    }

    SettingsCard {
        title: "Output and dynamics"
        description: "Balance, mono, channel swap, dynamics and bypass."
        RowLayout {
            LabelText { text: "Balance"; Layout.fillWidth: true }
            LiquidSlider { Layout.fillWidth: true; from: -1; to: 1; stepSize: 0.05; value: balance
                onMoved: if (!pressed) balance = value
                onPressedChanged: if (!pressed) balance = value
            }
            LabelText { text: balance.toFixed(2); Layout.preferredWidth: 50 }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Mono"; Layout.fillWidth: true }
            ExpressiveSwitch { checked: mono; onToggled: mono = checked }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Channel swap"; Layout.fillWidth: true }
            ExpressiveSwitch { checked: swap; onToggled: swap = checked }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Dynamics"; Layout.fillWidth: true }
            LiquidComboBox {
                model: ["off", "balanced", "night"]
                currentIndex: Math.max(0, model.indexOf(dynamics))
                onActivated: dynamics = currentText
            }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Bypass"; Layout.fillWidth: true }
            ExpressiveSwitch { checked: bypass; onToggled: bypass = checked }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Dynamic EQ"; Layout.fillWidth: true }
            ExpressiveSwitch { checked: dyneq; onToggled: dyneq = checked }
        }
    }
}
