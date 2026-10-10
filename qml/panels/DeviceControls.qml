pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

Flickable {
    id: root
    readonly property var bluetooth: ShellState.system.bluetooth || {}
    readonly property var network: ShellState.system.network || {}
    readonly property var adapters: bluetooth.adapters || []
    contentWidth: width; contentHeight: content.implicitHeight + 16
    clip: true; boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar {}
    ColumnLayout {
        id: content
        width: parent.width; spacing: 12
        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 8
            LabelText { text: "Bluetooth"; font.pixelSize: 20; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
            LiquidButton {
                text: ShellState.pendingActions.bluetoothToggle ? "Please wait…" : root.bluetooth.enabled ? "Turn off" : "Turn on"
                enabled: !!root.bluetooth.available && !root.bluetooth.hardBlocked && !ShellState.pendingActions.bluetoothToggle
                onClicked: ShellState.run("bluetoothToggle")
            }
        }
        LabelText {
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
            text: root.bluetooth.hardBlocked ? "Hardware blocked. Disable airplane mode or use the laptop radio switch."
                  : root.bluetooth.softBlocked ? "Software blocked. Enabling will ask BlueZ to unblock the adapter."
                  : !root.bluetooth.available ? "No adapter found. Check bluetooth.service and the installed firmware."
                  : root.bluetooth.enabled ? "Powered on · known devices below" : "Powered off"
        }
        LabelText {
            visible: ShellState.lastResult && !ShellState.lastResult.ok && String(ShellState.lastResult.action).startsWith("bluetooth")
            text: visible ? ShellState.lastResult.message : ""
            color: Theme.red; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        LiquidComboBox {
            visible: root.adapters.length > 1
            Layout.fillWidth: true
            model: root.adapters.map(adapter => adapter.name)
            currentIndex: Math.max(0, root.adapters.findIndex(adapter => adapter.path === root.bluetooth.adapter))
            onActivated: ShellState.run("setting", {key: "bluetoothAdapter", value: root.adapters[currentIndex].path})
            Accessible.name: "Bluetooth adapter"
        }
        Repeater {
            model: root.bluetooth.devices || []
            delegate: Rectangle {
                id: device
                required property var modelData
                Layout.fillWidth: true; Layout.preferredHeight: 68; radius: 14; color: Theme.surface
                RowLayout {
                    anchors.fill: parent; anchors.margins: 12
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 4
                        LabelText { text: device.modelData.name; elide: Text.ElideRight; Layout.fillWidth: true }
                        LabelText { text: device.modelData.connected ? "Connected" : "Paired"; color: device.modelData.connected ? Theme.green : Theme.muted; font.pixelSize: 11 }
                    }
                    LiquidButton {
                        text: device.modelData.connected ? "Disconnect" : "Connect"
                        enabled: !!root.bluetooth.enabled && !ShellState.pendingActions.bluetoothDevice
                        onClicked: ShellState.run("bluetoothDevice", {path: device.modelData.path, connected: !device.modelData.connected})
                    }
                }
            }
        }
        LabelText { visible: !(root.bluetooth.devices || []).length; text: "No paired devices. Open device settings to pair a new device."; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            LiquidButton { text: "Pair & device settings"; Layout.fillWidth: true; onClicked: ShellState.run("openSettings", {target: "bluetooth"}) }
            LiquidButton { text: "Refresh"; onClicked: ShellState.run("refresh") }
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.border; Layout.topMargin: 8; Layout.bottomMargin: 8 }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Network"; font.pixelSize: 20; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
            LiquidButton { text: root.network.enabled ? "Wi-Fi off" : "Wi-Fi on"; enabled: !!root.network.available; onClicked: ShellState.run("wifiToggle") }
        }
        LabelText { text: root.network.connected ? "Connected to " + root.network.ssid : "Not connected"; color: root.network.connected ? Theme.cyan : Theme.muted; Layout.fillWidth: true; elide: Text.ElideRight }
        Repeater {
            model: root.network.networks || []
            delegate: Rectangle {
                id: networkEntry
                required property var modelData
                Layout.fillWidth: true; Layout.preferredHeight: 52; radius: 12; color: Theme.surface
                RowLayout {
                    anchors.fill: parent; anchors.margins: 12
                    LabelText { text: networkEntry.modelData.ssid; Layout.fillWidth: true; elide: Text.ElideRight }
                    LabelText { text: networkEntry.modelData.connected ? "Connected" : networkEntry.modelData.strength + "%"; color: networkEntry.modelData.connected ? Theme.cyan : Theme.muted; font.pixelSize: 11 }
                }
            }
        }
        LabelText { text: "Networks use NetworkManager's cached scan. Manage connections and passwords in Fedora's network settings."; color: Theme.muted; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true }
        LiquidButton { text: "Network settings"; onClicked: ShellState.run("openSettings", {target: "network"}); Layout.fillWidth: true }
    }
}
