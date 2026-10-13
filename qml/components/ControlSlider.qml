pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../services"
import "../theme"

Rectangle {
    id: root
    required property string channel
    property bool editing: false
    readonly property var device: ShellState.system[channel === "micLevel" ? "microphone" : channel === "volume" ? "audio" : "brightness"] || {}
    readonly property string action: channel === "micLevel" ? "micVolume" : channel
    readonly property string label: channel === "micLevel" ? "Microphone" : channel === "volume" ? "Volume" : "Brightness"
    readonly property string icon: channel === "micLevel" ? "microphone" : channel === "volume" ? "audio" : "weather-sun"
    readonly property real percent: channel === "brightness" ? device.percent || 1 : device.volume || 0
    readonly property color accent: channel === "micLevel" ? Theme.pink : channel === "volume" ? Theme.purple : Theme.yellow
    property int desired: -1
    property bool awaiting: false
    radius: Theme.smallRadius
    color: Theme.surfaceContainerHigh
    border.width: slider.visualFocus ? 2 : 1
    border.color: slider.visualFocus ? accent : Theme.border
    implicitHeight: Theme.compact ? 82 : 90
    function flush() {
        delay.stop();
        const value = desired; desired = -1;
        if (value >= 0 && !editing) { awaiting = true; ShellState.run(action, {value: value}); }
    }
    onEditingChanged: if (editing) { delay.stop(); desired = -1; }
    Timer { id: delay; interval: 100; onTriggered: root.flush() }
    Connections {
        target: ShellState
        function onLastResultChanged() {
            if (ShellState.lastResult && ShellState.lastResult.action === root.action && !ShellState.lastResult.pending) root.awaiting = false;
        }
    }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 10; spacing: 0
        RowLayout {
            Layout.fillWidth: true; spacing: 6
            IconButton {
                objectName: "controlMute-" + root.channel
                visible: root.channel !== "brightness"
                implicitWidth: 30; implicitHeight: 30
                iconName: root.icon; active: !!root.device.muted
                enabled: !!root.device.available && !root.editing
                Accessible.name: (root.device.muted ? "Unmute " : "Mute ") + root.label.toLowerCase()
                onClicked: ShellState.run(root.channel === "micLevel" ? "micMute" : "mute")
            }
            ShellIcon { visible: root.channel === "brightness"; name: root.icon; color: root.accent; Layout.preferredWidth: 24; Layout.preferredHeight: 24 }
            LabelText { text: root.label; Layout.fillWidth: true; font.weight: Font.Bold; font.pixelSize: 14; elide: Text.ElideRight }
            LabelText { text: !root.device.available ? "Unavailable" : root.device.muted ? "Muted" : Math.round(slider.value) + "%"; color: root.device.muted ? Theme.pink : Theme.muted; font.pixelSize: 12 }
            IconButton { visible: root.channel === "volume"; iconName: "settings"; implicitWidth: 30; implicitHeight: 30; tooltip: "Audio settings"; enabled: !root.editing; onClicked: ShellState.run("openSettings", {target: "audio"}) }
        }
        LiquidSlider {
            id: slider
            objectName: "controlSlider-" + root.channel
            Layout.fillWidth: true
            from: root.channel === "brightness" ? 1 : 0; to: 100; stepSize: 1
            enabled: !!root.device.available && !root.editing
            opacity: root.editing || enabled ? 1 : .35
            Accessible.name: root.label + " level"
            palette.highlight: root.accent
            onMoved: { root.desired = Math.round(value); if (!delay.running) delay.start(); }
            onPressedChanged: if (!pressed) root.flush()
        }
        Binding { target: slider; property: "value"; value: root.percent; when: !slider.pressed && root.desired < 0 && !root.awaiting; restoreMode: Binding.RestoreNone }
    }
}
