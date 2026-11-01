pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    required property var inventory
    required property bool busy
    signal refreshRequested()
    readonly property var portDevices: [...(inventory.sinks || []), ...(inventory.sources || [])].filter(item => item.ports.length > 0)
    spacing: 10
    RowLayout {
        Layout.fillWidth: true
        LabelText { text: "Profiles, ports & app outputs"; font.weight: Font.Bold; Layout.fillWidth: true; wrapMode: Text.Wrap }
        LiquidButton {
            objectName: "audioRefresh"; text: root.busy ? "Working…" : "Refresh"
            enabled: ShellState.backendReady && !root.busy
            Accessible.name: "Refresh audio devices and routes"
            onClicked: root.refreshRequested()
        }
    }
    LabelText {
        Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12
        text: "Profile changes can briefly interrupt audio or reduce playback quality. App output changes affect only the selected live playback stream."
    }
    LabelText {
        objectName: "audioDeviceError"; visible: !!root.inventory.error
        Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.red
        text: root.inventory.error || ""
    }
    LabelText {
        Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12
        text: root.inventory.checkedAt ? "Checked at " + Qt.formatDateTime(new Date(root.inventory.checkedAt), "hh:mm:ss") + ". Refresh after external changes or starting another app."
            : "Read on demand; no background audio polling. Requires pactl and a compatible PipeWire Pulse session."
    }
    Repeater {
        model: root.inventory.cards || []
        delegate: ColumnLayout {
            id: card
            required property var modelData
            Layout.fillWidth: true; spacing: 5
            LabelText { text: card.modelData.title + " · Profile"; Layout.fillWidth: true; elide: Text.ElideRight }
            AudioChoice {
                objectName: "audioProfile-" + card.modelData.id
                Layout.fillWidth: true; choices: card.modelData.profiles; actual: card.modelData.activeProfile
                enabled: ShellState.backendReady && !root.busy && !!root.inventory.available && choices.some(item => item.available)
                Accessible.name: card.modelData.title + " audio profile"
                onChosen: name => ShellState.run("audioProfile", {serverId:root.inventory.serverId,cardId:card.modelData.id,profile:name})
            }
        }
    }
    Repeater {
        model: root.portDevices
        delegate: RowLayout {
            id: port
            required property var modelData
            Layout.fillWidth: true; spacing: 8
            LabelText { text: port.modelData.title + (port.modelData.kind === "source" ? " · Input port" : " · Output port"); Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight }
            AudioChoice {
                objectName: "audioPort-" + port.modelData.id
                Layout.preferredWidth: 230; choices: port.modelData.ports; actual: port.modelData.activePort
                enabled: ShellState.backendReady && !root.busy && !!root.inventory.available && choices.some(item => item.available)
                Accessible.name: port.modelData.title + " physical port"
                onChosen: name => ShellState.run("audioPort", {serverId:root.inventory.serverId,deviceId:port.modelData.id,port:name})
            }
        }
    }
    LabelText {
        visible: !!root.inventory.available && !(root.inventory.cards || []).length && !root.portDevices.length
        text: "These devices expose no switchable hardware profiles or ports."; color: Theme.muted
        Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12
    }
}
