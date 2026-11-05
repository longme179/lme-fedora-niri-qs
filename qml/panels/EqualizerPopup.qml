pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

MotionPopup {
    id: root
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(920, parent ? parent.width - 32 : 920)
    height: Math.min(780, parent ? parent.height - 32 : 780)
    padding: 20
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    property var gains: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    property real balance: 0
    property bool mono: false
    property bool swap: false
    property string dynamics: "off"
    property bool bypass: false
    property bool dyneq: false
    property bool adjusting: false
    property string loadStatus: ""
    property int gainCount: 10

    readonly property bool daemonAvailable: ShellState.backendReady
    readonly property var presetMap: ({
        "Flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "Bass": [5, 7, 5, 2, 1, 0, 0, 0, 1, 2],
        "Treble": [-2, -1, 0, 1, 2, 3, 4, 5, 6, 6],
        "Vocal": [-2, -1, 1, 3, 5, 5, 4, 2, 1, 0],
        "Pop": [2, 4, 2, 0, 1, 2, 4, 2, 1, 2],
        "Rock": [5, 4, 2, -1, -2, -1, 2, 4, 5, 6],
        "Jazz": [3, 3, 1, 1, 1, 1, 2, 1, 2, 3],
        "Classic": [0, 1, 2, 2, 2, 2, 1, 2, 3, 4]
    })

    function applyPreset(name) {
        const values = presetMap[name];
        if (!Array.isArray(values) || values.length !== root.gainCount)
            return;
        root.gains = values.slice();
        root.balance = 0;
        root.mono = false;
        root.swap = false;
        root.dynamics = "off";
        root.bypass = false;
        root.dyneq = false;
        root.apply();
    }

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

    function apply() {
        if (!ShellState.backendReady)
            return;
        if (ShellState.preferences.equalizerEnabled !== true) {
            ShellState.run("setting", {key: "equalizerEnabled", value: true});
            ShellState.run("eqStart");
        }
        ShellState.run("eqApply", {gains: root.gains, balance: root.balance, mono: root.mono, swap: root.swap, dynamics: root.dynamics, bypass: root.bypass, dyneq: root.dyneq});
    }

    function refreshFromDaemon() {
        if (ShellState.backendReady)
            ShellState.run("eqGet");
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
                root.refreshFromDaemon();
        }
    }

    onAboutToShow: root.refreshFromDaemon()

    background: Rectangle {
        radius: Theme.radius
        color: Theme.surface
        border.width: 1
        border.color: Theme.border
        GlassMaterial { anchors.fill: parent; radius: parent.radius }
    }

    contentItem: ColumnLayout {
        spacing: 12
        anchors.fill: parent
        anchors.margins: 16
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Equalizer"; font.pixelSize: 22; font.weight: Font.Bold; Layout.fillWidth: true }
            IconButton { glyph: "×"; tooltip: "Close equalizer"; onClicked: root.close() }
        }
        LabelText {
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
            text: "Optional Serpantinum audio daemon. Applying values stores and applies them via the daemon."
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                LabelText { text: "Enable"; font.weight: Font.Medium } LabelText { text: "Start or stop the optional audio daemon"; color: Theme.muted; font.pixelSize: 12 }
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
            LiquidButton { text: "Refresh"; enabled: ShellState.backendReady; onClicked: root.refreshFromDaemon() }
            LiquidButton { text: "Status"; enabled: ShellState.backendReady; onClicked: ShellState.run("eqStatus") }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            LabelText { text: "Presets"; font.weight: Font.Medium; Layout.fillWidth: true } RowLayout {
                Layout.fillWidth: true; spacing: 8
                Repeater { model: ["Flat", "Bass", "Treble", "Vocal"]; delegate: LiquidButton { required property var modelData; text: modelData; onClicked: root.applyPreset(modelData) } }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Repeater { model: ["Pop", "Rock", "Jazz", "Classic"]; delegate: LiquidButton { required property var modelData; text: modelData; onClicked: root.applyPreset(modelData) } }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 6
            enabled: !root.dyneq; opacity: root.dyneq ? 0.45 : 1.0
            LabelText { text: "Output and dynamics"; font.weight: Font.Medium }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Balance"; Layout.fillWidth: true }
                LiquidSlider { Layout.fillWidth: true; from: -1; to: 1; stepSize: 0.05; value: root.balance;
                    onMoved: if (!pressed) root.balance = value
                    onPressedChanged: {
                        if (pressed) { root.adjusting = true; return; }
                        root.balance = value;
                        root.apply();
                        Qt.callLater(() => { root.adjusting = false; });
                    }
                }
                LabelText { text: root.balance.toFixed(2); Layout.preferredWidth: 45 }
            }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Mono"; Layout.fillWidth: true }
                ExpressiveSwitch { checked: root.mono; onToggled: { root.mono = checked; root.apply(); } }
            }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Swap"; Layout.fillWidth: true }
                ExpressiveSwitch { checked: root.swap; onToggled: { root.swap = checked; root.apply(); } }
            }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Dynamics"; Layout.fillWidth: true }
                LiquidComboBox { model: ["off", "balanced", "night"]; currentIndex: Math.max(0, model.indexOf(root.dynamics)); onActivated: { root.dynamics = currentText; root.apply(); } }
            }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Bypass"; Layout.fillWidth: true }
                ExpressiveSwitch { checked: root.bypass; onToggled: { root.bypass = checked; root.apply(); } }
            }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Dynamic EQ"; Layout.fillWidth: true }
                ExpressiveSwitch { checked: root.dyneq; onToggled: { root.dyneq = checked; root.apply(); } }
            }'''

        }
        Item { Layout.fillWidth: true; Layout.preferredHeight: 30; visible: root.dyneq; Rectangle { anchors.fill: parent; color: Qt.rgba(0,0,0,.35); radius: 8 }; LabelText { anchors.centerIn: parent; text: "Adapting to your sound"; color: Theme.text; font.pixelSize: 14; font.weight: Font.Medium } }
        LabelText { visible: !!root.loadStatus; text: root.loadStatus; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            Repeater {
                model: 10
                delegate: Column {
                    required property int index
                    readonly property int band: index + 1
                    width: 50
                    spacing: 4
                    Text { text: [31,63,125,250,500,1000,2000,4000,8000,16000][index].toString().replace("1000","1k").replace("2000","2k").replace("4000","4k").replace("8000","8k").replace("16000","16k"); color: Theme.muted; font.pixelSize: 9; horizontalAlignment: Text.AlignHCenter }
                    Slider {
                        id: slider
                        orientation: Qt.Vertical
                        from: -12; to: 12; stepSize: 0.5
                        value: root.gains[index] || 0
                        width: 40; height: 170
                        enabled: !root.dyneq
                        opacity: root.dyneq ? 0.35 : 1.0
                        Behavior on value {
                            enabled: !slider.pressed
                            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                        }
                        onPressedChanged: {
                            if (pressed) { root.adjusting = true; return; }
                            const next = root.gains.slice();
                            next[index] = value;
                            root.gains = next;
                            root.apply();
                            Qt.callLater(() => { root.adjusting = false; });
                        }
                    }
                }
            }
        }
    }
}