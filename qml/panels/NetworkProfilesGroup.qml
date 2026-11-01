pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    required property var controller
    required property string title
    required property var entries
    spacing: 8
    LabelText { text: root.title; font.weight: Font.Bold; font.pixelSize: 18 }
    LabelText { visible: root.entries.length === 0; text: "No supported saved profiles."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
    Repeater {
        model: root.entries
        delegate: Rectangle {
            id: card
            required property var modelData
            readonly property var activeConnections: root.controller.activations(modelData)
            readonly property string selected: root.controller.selected(modelData)
            readonly property var selectedDevice: root.controller.device(selected)
            Layout.fillWidth: true; implicitHeight: content.implicitHeight + 24
            radius: 16; color: Theme.surface
            border.width: 1; border.color: Theme.border
            GlassMaterial { anchors.fill: parent; radius: parent.radius }
            ColumnLayout {
                id: content; x: 12; y: 12; width: parent.width - 24; spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    LabelText {
                        text: card.modelData.name + " · " + card.modelData.uuid.slice(-8)
                        Layout.fillWidth: true; elide: Text.ElideRight; font.weight: Font.Bold
                        Accessible.name: card.modelData.name + " " + card.modelData.uuid
                    }
                    LiquidButton {
                        objectName: "networkEdit-" + card.modelData.uuid; text: "Edit"
                        enabled: ShellState.backendReady && !root.controller.busy
                        onClicked: ShellState.run("networkEdit",{serverId:root.controller.inventory.serverId,uuid:card.modelData.uuid})
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    LiquidComboBox {
                        id: adapter; objectName: "networkAdapter-" + card.modelData.uuid
                        Layout.fillWidth: true
                        model: card.modelData.compatible.length ? card.modelData.compatible.map(id => {
                            const device = root.controller.device(id);
                            return device ? device.interface + (device.carrier === false && card.modelData.kind === "ethernet" ? " · cable unplugged" : "") : card.modelData.interface + " · saved virtual adapter";
                        }) : ["No compatible adapter"]
                        currentIndex: Math.max(0,card.modelData.compatible.indexOf(card.selected))
                        enabled: !root.controller.busy && card.modelData.compatible.length > 0 && card.activeConnections.length === 0
                        Accessible.name: card.modelData.name + " network adapter"
                        onActivated: index => root.controller.choose(card.modelData,card.modelData.compatible[index])
                    }
                    LiquidButton {
                        objectName: "networkConnect-" + card.modelData.uuid
                        text: card.activeConnections.length ? "In use" : card.modelData.kind === "hotspot" ? "Review hotspot…" : "Connect"
                        enabled: ShellState.backendReady && !root.controller.busy && !!card.selected && card.activeConnections.length === 0
                            && !(card.modelData.kind === "ethernet" && card.selectedDevice && card.selectedDevice.carrier === false)
                        onClicked: root.controller.request(card.modelData,"networkConnect")
                    }
                }
                LabelText {
                    visible: card.modelData.kind === "ethernet"
                    text: "Saved IPv4: " + (card.modelData.settings["ipv4.method"] || "not reported") +
                        (card.modelData.settings["ipv4.addresses"] ? " · " + card.modelData.settings["ipv4.addresses"] : "") +
                        (card.modelData.settings["ipv4.dns"] ? " · DNS " + card.modelData.settings["ipv4.dns"] : "") +
                        "\nSaved IPv6: " + (card.modelData.settings["ipv6.method"] || "not reported")
                    color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap
                }
                Repeater {
                    model: card.activeConnections
                    delegate: RowLayout {
                        id: active
                        required property var modelData
                        Layout.fillWidth: true
                        readonly property var device: root.controller.device(modelData.deviceId)
                        LabelText {
                            text: active.modelData.state + " · " + (active.modelData.interface || "adapter not reported") +
                                (active.device && active.device.ip4.length ? "\nIPv4 " + active.device.ip4.join(", ") : "") +
                                (active.device && active.device.ip6.length ? "\nIPv6 " + active.device.ip6.join(", ") : "")
                            color: Theme.cyan; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap
                        }
                        LiquidButton {
                            objectName: "networkDisconnect-" + card.modelData.uuid + "-" + active.modelData.deviceId
                            text: active.modelData.state === "activated" ? "Disconnect" : "Stop"
                            enabled: ShellState.backendReady && !root.controller.busy && !!active.modelData.deviceId
                            onClicked: ShellState.run("networkDisconnect",{serverId:root.controller.inventory.serverId,
                                uuid:card.modelData.uuid,deviceId:active.modelData.deviceId,activePath:active.modelData.path})
                        }
                    }
                }
            }
        }
    }
}
