// Role: AudioMixer.qml (audio layer, fan-in 3).
// Panel/feature UI; dispatches backend actions via ShellState.run(action,payload) where applicable.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.Pipewire
import "../components"
import "../services"
import "../theme"

Flickable {
    id: root
    contentWidth: width; contentHeight: content.implicitHeight + 16
    clip: true; boundsBehavior: Flickable.StopAtBounds
    readonly property var nodes: ShellState.demo ? [] : Pipewire.nodes.values.filter(node => node.audio)
    readonly property var outputs: nodes.filter(node => !node.isStream && node.isSink)
    readonly property var inputs: nodes.filter(node => !node.isStream && !node.isSink)
    readonly property var streams: nodes.filter(node => node.isStream)
    readonly property bool deviceTools: FeatureCatalog.ready && !FeatureCatalog.error && FeatureCatalog.records.some(record => record.id === "audio" && record.enabled)
    readonly property var devices: deviceTools ? ShellState.snapshot.audioDevices || {} : {}
    readonly property bool audioBusy: ["audioDevicesRefresh", "audioPort", "audioProfile", "audioRoute", "bluetoothDevice"].some(action => ShellState.pendingActions[action])
    readonly property var extraStreams: (devices.streams || []).filter(entry => !streams.some(node => node.ready && String(node.properties["object.serial"]) === entry.serial))
    property bool initialized: false
    function refreshDevices() { if (initialized && visible && deviceTools && ShellState.backendReady && !audioBusy) ShellState.run("audioDevicesRefresh"); }
    Component.onCompleted: { initialized = true; refreshDevices(); }
    onDeviceToolsChanged: if (deviceTools) refreshDevices()
    onVisibleChanged: if (visible) refreshDevices()
    Connections { target: ShellState; function onBackendReadyChanged() { if (ShellState.backendReady) root.refreshDevices(); } }
    PwObjectTracker { objects: root.nodes }
    ScrollBar.vertical: ScrollBar {}
    function label(node) { return node.description || node.nickname || node.name; }
    component MixerRow: Rectangle {
        id: row
        required property var node
        readonly property var routeEntry: root.deviceTools && node.isStream && node.ready ? (root.devices.streams || []).find(item => item.serial === String(node.properties["object.serial"])) || null : null
        Layout.fillWidth: true; implicitHeight: routeEntry ? 132 : 86; radius: 14; color: Theme.surface
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 6
            RowLayout {
                LabelText { Layout.fillWidth: true; text: row.node.ready && row.node.properties["application.name"] || root.label(row.node); elide: Text.ElideRight }
                LabelText { text: row.node.ready ? Math.round(row.node.audio.volume * 100) + "%" : "Connecting…"; color: Theme.muted; font.pixelSize: 12 }
                LiquidButton { text: row.node.audio.muted ? "Unmute" : "Mute"; enabled: row.node.ready; onClicked: row.node.audio.muted = !row.node.audio.muted }
            }
            LiquidSlider {
                id: level
                Layout.fillWidth: true; from: 0; to: 1; stepSize: 0.01
                enabled: row.node.ready
                Accessible.name: root.label(row.node) + " volume"
                onMoved: row.node.audio.volume = value
            }
            Binding { target: level; property: "value"; value: row.node.ready ? row.node.audio.volume : 0; when: !level.pressed; restoreMode: Binding.RestoreNone }
            Loader {
                Layout.fillWidth: true; active: !!row.routeEntry; visible: active
                sourceComponent: Component { AudioRoute { inventory: root.devices; busy: root.audioBusy; entry: row.routeEntry } }
            }
        }
    }
    ColumnLayout {
        id: content
        x: 4; width: parent.width - 8; spacing: 14
        LabelText { text: "Audio devices & mixer"; font.pixelSize: 18; font.weight: Font.Bold; Layout.topMargin: 8 }
        LabelText { Layout.fillWidth: true; text: "Choose default devices and adjust each app independently."; color: Theme.muted; wrapMode: Text.Wrap }
        Loader {
            Layout.fillWidth: true; active: root.deviceTools; visible: active
            sourceComponent: Component { AudioHardware { inventory: root.devices; busy: root.audioBusy; onRefreshRequested: root.refreshDevices() } }
        }
        LabelText { text: "Output device"; color: Theme.cyan }
        LiquidComboBox {
            Layout.fillWidth: true; enabled: root.outputs.length > 0
            model: root.outputs.length ? root.outputs.map(node => root.label(node)) : [ShellState.demo ? "Available in a real audio session" : "No output device"]
            currentIndex: Math.max(0, root.outputs.findIndex(node => Pipewire.defaultAudioSink && node.id === Pipewire.defaultAudioSink.id))
            onActivated: Pipewire.preferredDefaultAudioSink = root.outputs[currentIndex]
            Accessible.name: "Default audio output"
        }
        Repeater { model: root.outputs; delegate: MixerRow { required property var modelData; node: modelData } }
        LabelText { text: "Input device"; color: Theme.pink }
        LiquidComboBox {
            Layout.fillWidth: true; enabled: root.inputs.length > 0
            model: root.inputs.length ? root.inputs.map(node => root.label(node)) : [ShellState.demo ? "Available in a real audio session" : "No input device"]
            currentIndex: Math.max(0, root.inputs.findIndex(node => Pipewire.defaultAudioSource && node.id === Pipewire.defaultAudioSource.id))
            onActivated: Pipewire.preferredDefaultAudioSource = root.inputs[currentIndex]
            Accessible.name: "Default microphone"
        }
        Repeater { model: root.inputs; delegate: MixerRow { required property var modelData; node: modelData } }
        LabelText { text: "Applications"; color: Theme.accent }
        Repeater { model: root.streams; delegate: MixerRow { required property var modelData; node: modelData } }
        Repeater {
            model: root.extraStreams
            delegate: ColumnLayout {
                id: extra
                required property var modelData
                Layout.fillWidth: true
                LabelText { text: extra.modelData.title + " · " + extra.modelData.detail; Layout.fillWidth: true; elide: Text.ElideRight }
                AudioRoute { Layout.fillWidth: true; entry: extra.modelData; inventory: root.devices; busy: root.audioBusy }
            }
        }
        LabelText {
            visible: root.deviceTools && (root.streams.length > 0 || root.extraStreams.length > 0)
            text: "Output routing is available for reported PipeWire Pulse playback streams. Native-only or newly started streams may need Refresh or Advanced audio settings."
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12
        }
        LabelText { visible: root.streams.length === 0; text: "App sliders appear while audio streams are active."; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
        LiquidButton { text: "Advanced audio settings"; onClicked: ShellState.run("openSettings", {target: "audio"}); Layout.fillWidth: true }
        LiquidButton { text: "Equalizer"; onClicked: ShellState.togglePanel("equalizer"); Layout.fillWidth: true }
    }
}
