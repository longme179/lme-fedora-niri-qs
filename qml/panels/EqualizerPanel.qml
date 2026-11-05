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
    property bool adjusting: false
    property string loadStatus: ""

    function parseEqualizerLine(message) {
        const tokens = String(message || "").trim().split(/\s+/);
        if (tokens.length !== 17 || tokens[0] !== "set")
            return null;
        const gains = tokens.slice(1, 11).map(value => Number(value));
        if (gains.some(value => !Number.isFinite(value) || value < -12 || value > 12))
            return null;
        const balance = Number(tokens[11]);
        if (!Number.isFinite(balance) || balance < -1 || balance > 1)
            return null;
        if (!["1", "0", "true", "false"].includes(tokens[12]) || !["1", "0", "true", "false"].includes(tokens[13]))
            return null;
        if (tokens[14] !== "off" && tokens[14] !== "balanced" && tokens[14] !== "night")
            return null;
        if (!["1", "0", "true", "false"].includes(tokens[15]) || !["1", "0", "true", "false"].includes(tokens[16]))
            return null;
        return { gains: gains, balance: balance, mono: tokens[12] === "1" || tokens[12] === "true",
                 swap: tokens[13] === "1" || tokens[13] === "true", dynamics: tokens[14],
                 bypass: tokens[15] === "1" || tokens[15] === "true",
                 dyneq: tokens[16] === "1" || tokens[16] === "true" };
    }

    Connections {
        target: ShellState
        function onLastResultChanged() {
            if (!ShellState.lastResult || ShellState.lastResult.action !== "eqGet")
                return;
            if (!ShellState.lastResult.ok) {
                root.loadStatus = String(ShellState.lastResult.message || "Equalizer is unavailable");
                return;
            }
            const payload = root.parseEqualizerLine(ShellState.lastResult.message);
            if (!payload || root.adjusting)
                return;
            root.gains = payload.gains.slice();
            root.balance = payload.balance;
            root.mono = payload.mono;
            root.swap = payload.swap;
            root.dynamics = payload.dynamics;
            root.bypass = payload.bypass;
            root.dyneq = payload.dyneq;
            root.loadStatus = "";
        }
        function onBackendReadyChanged() {
            if (ShellState.backendReady)
                ShellState.run("eqGet");
        }
    }

    Component.onCompleted: {
        if (ShellState.backendReady)
            ShellState.run("eqGet");
    }

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
        LabelText { visible: !!root.loadStatus; text: root.loadStatus; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
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
                        onPressedChanged: {
                        if (pressed) { root.adjusting = true; return; }
                        const next = root.gains.slice();
                        next[index] = value;
                        root.gains = next;
                        Qt.callLater(() => { root.adjusting = false; });
                    }
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
                LiquidSlider { Layout.fillWidth: true; from: -1; to: 1; stepSize: 0.05; value: root.balance; onMoved: if (!pressed) root.balance = value; onPressedChanged: if (pressed) { root.adjusting = true; return; } root.balance = value; Qt.callLater(() => { root.adjusting = false; }) }
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