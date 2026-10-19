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
    readonly property bool nativePairing: !ShellState.demo && ShellState.preferences.bluetoothPairing !== false
    readonly property var devices: nativePairing && BluetoothState.state.ready ? BluetoothState.state.devices || [] : bluetooth.devices || []
    function watch() { BluetoothState.watch(root, visible && nativePairing); }
    Component.onCompleted: watch()
    Component.onDestruction: BluetoothState.watch(root, false)
    onVisibleChanged: watch()
    onNativePairingChanged: watch()
    readonly property var adapters: bluetooth.adapters || []
    contentWidth: width; contentHeight: content.implicitHeight + 16
    clip: true; boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar {}
    ColumnLayout {
        id: content
        x: 4; width: parent.width - 8; spacing: 12
        RowLayout {
            Layout.fillWidth: true; Layout.topMargin: 8
            LabelText { text: "Bluetooth"; font.pixelSize: 20; font.weight: Font.Bold }
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
                  : root.bluetooth.enabled ? "Powered on · scan to find nearby devices" : "Powered off"
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
        LabelText { visible: root.nativePairing && !!BluetoothState.error; text: BluetoothState.error; color: Theme.red; wrapMode: Text.Wrap; Layout.fillWidth: true }
        RowLayout {
            visible: root.nativePairing; Layout.fillWidth: true
            LiquidButton {
                objectName: "bluetoothScan"
                text: BluetoothState.state.scanPending ? "Starting scan…" : BluetoothState.state.scanning ? "Stop scanning" : "Scan for devices"
                enabled: !!root.bluetooth.enabled && BluetoothState.state.ready && !BluetoothState.state.scanPending
                onClicked: BluetoothState.scan(!BluetoothState.state.scanning)
            }
            LiquidButton { visible: !BluetoothState.state.ready; text: "Retry"; onClicked: BluetoothState.retry() }
            Item { Layout.fillWidth: true }
        }
        BluetoothPairing { Layout.fillWidth: true }
        RowLayout {
            visible: root.nativePairing && !!BluetoothState.state.pairing && !BluetoothState.request.token
            Layout.fillWidth: true
            LabelText { text: "Pairing device…"; Layout.fillWidth: true }
            LiquidButton { text: "Cancel"; onClicked: BluetoothState.cancel() }
        }
        Repeater {
            model: root.devices
            delegate: Rectangle {
                id: device
                required property var modelData
                Layout.fillWidth: true; Layout.preferredHeight: 68; radius: 14; color: Theme.surface
                RowLayout {
                    anchors.fill: parent; anchors.margins: 12
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 4
                        LabelText { text: device.modelData.name; elide: Text.ElideRight; Layout.fillWidth: true }
                        LabelText { text: device.modelData.connected ? "Connected" : device.modelData.paired === false ? "Available to pair" : "Paired"; color: device.modelData.connected ? Theme.green : Theme.muted; font.pixelSize: 12 }
                    }
                    LiquidButton {
                        objectName: "bluetoothDevice-" + device.modelData.path
                        text: BluetoothState.state.pairing === device.modelData.path ? "Pairing…" : device.modelData.connected ? "Disconnect" : device.modelData.paired === false ? "Pair" : "Connect"
                        enabled: !!root.bluetooth.enabled && !ShellState.pendingActions.bluetoothDevice && !BluetoothState.state.pairing
                        onClicked: if (device.modelData.paired === false) BluetoothState.pair(device.modelData.path); else ShellState.run("bluetoothDevice", {path: device.modelData.path, connected: !device.modelData.connected})
                    }
                }
            }
        }
        LabelText { visible: !root.devices.length; text: root.nativePairing ? "No devices found. Make your device discoverable, then scan." : "No paired devices. Open device settings to pair a new device."; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
        PeripheralBatteryList { Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true
            LiquidButton { text: "External device settings"; Layout.fillWidth: true; onClicked: ShellState.run("openSettings", {target: "bluetooth"}) }
            LiquidButton { text: "Refresh"; onClicked: ShellState.run("refresh") }
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.border; Layout.topMargin: 8; Layout.bottomMargin: 8 }
        WifiWidget { Layout.fillWidth: true }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.border; Layout.topMargin: 8; Layout.bottomMargin: 8 }
        MirrorControls { Layout.fillWidth: true }
    }
}
