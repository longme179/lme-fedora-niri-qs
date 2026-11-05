pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    implicitWidth: 620
    implicitHeight: 730
    focus: true
    Keys.onEscapePressed: ShellState.closePanels()

    property var gains: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    property real balance: 0
    property bool mono: false
    property bool swap: false
    property string dynamics: "off"
    property bool bypass: false
    property bool dyneq: false

    function apply() {
        if (ShellState.backendReady)
            ShellState.run("eqApply", {gains: root.gains, balance: root.balance, mono: root.mono, swap: root.swap, dynamics: root.dynamics, bypass: root.bypass, dyneq: root.dyneq});
    }

    background: Rectangle {
        radius: Theme.radius
        color: Theme.surface
        border.width: 1
        border.color: Theme.border
        GlassMaterial { anchors.fill: parent; radius: parent.radius }
    }

    contentItem: ColumnLayout {
        objectName: "equalizerPopupBody"
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Equalizer"; font.pixelSize: 22; font.weight: Font.Bold; Layout.fillWidth: true }
            IconButton { glyph: "×"; tooltip: "Close equalizer"; onClicked: ShellState.closePanels() }
        }
        LabelText {
            Layout.fillWidth: true
            text: "Optional Serpantinum audio daemon. Install and start serpantinum-audio before applying."
            color: Theme.muted; wrapMode: Text.Wrap
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                LabelText { text: "Enable"; font.weight: Font.Medium }
                LabelText { text: "Start or stop the optional audio daemon"; color: Theme.muted; font.pixelSize: 12 }
            }
            ExpressiveSwitch {
                checked: ShellState.preferences.equalizerEnabled !== false
                onToggled: {
                    ShellState.run("setting", {key: "equalizerEnabled", value: checked});
                    if (checked) ShellState.run("eqStart"); else ShellState.run("eqStop");
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            LiquidButton { text: "Apply"; enabled: ShellState.backendReady; onClicked: root.apply() }
            LiquidButton { text: "Status"; enabled: ShellState.backendReady; onClicked: ShellState.run("eqStatus") }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 8
            LabelText { text: "10-band gains"; font.weight: Font.Medium }
            Repeater {
                model: root.gains.length
                delegate: RowLayout {
                    required property int index
                    Layout.fillWidth: true
                    LabelText { text: "Band " + (index + 1); Layout.preferredWidth: 60 }
                    LiquidSlider {
                        Layout.fillWidth: true; from: -12; to: 12; stepSize: 0.5
                        value: root.gains[index] || 0
                        onMoved: if (!pressed) { const next = root.gains.slice(); next[index] = value; root.gains = next; }
                        onPressedChanged: if (!pressed) { const next = root.gains.slice(); next[index] = value; root.gains = next; }
                    }
                    LabelText { text: (root.gains[index] || 0).toFixed(1) + " dB"; Layout.preferredWidth: 55 }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 6
            LabelText { text: "Output and dynamics"; font.weight: Font.Medium }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Balance"; Layout.fillWidth: true }
                LiquidSlider { Layout.fillWidth: true; from: -1; to: 1; stepSize: 0.05; value: root.balance; onMoved: if (!pressed) root.balance = value; onPressedChanged: if (!pressed) root.balance = value }
                LabelText { text: root.balance.toFixed(2); Layout.preferredWidth: 45 }
            }
            RowLayout { Layout.fillWidth: true; LabelText { text: "Mono"; Layout.fillWidth: true }; ExpressiveSwitch { checked: root.mono; onToggled: root.mono = checked } }
            RowLayout { Layout.fillWidth: true; LabelText { text: "Swap"; Layout.fillWidth: true }; ExpressiveSwitch { checked: root.swap; onToggled: root.swap = checked } }
            RowLayout { Layout.fillWidth: true; LabelText { text: "Dynamics"; Layout.fillWidth: true }; LiquidComboBox { model: ["off", "balanced", "night"]; currentIndex: Math.max(0, model.indexOf(root.dynamics)); onActivated: root.dynamics = currentText } }
            RowLayout { Layout.fillWidth: true; LabelText { text: "Bypass"; Layout.fillWidth: true }; ExpressiveSwitch { checked: root.bypass; onToggled: root.bypass = checked } }
            RowLayout { Layout.fillWidth: true; LabelText { text: "Dynamic EQ"; Layout.fillWidth: true }; ExpressiveSwitch { checked: root.dyneq; onToggled: root.dyneq = checked } }
        }
    }
}