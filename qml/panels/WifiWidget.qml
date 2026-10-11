pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    id: root
    spacing: 12
    readonly property var network: ShellState.system.network || {}
    readonly property bool connected: network.wifiConnected === undefined ? !!network.connected : !!network.wifiConnected
    readonly property var result: ShellState.wifiResult || {}
    readonly property bool busy: ["wifiScan", "wifiConnect", "wifiSaved", "wifiDisconnect", "wifiForget", "wifiToggle"].some(a => ShellState.pendingActions[a])
    property var selectedNetwork: null
    property string forgetUuid: ""
    property alias connectionPopup: connectionDialog
    RowLayout {
        Layout.fillWidth: true
        LabelText { text: "Wi-Fi"; font.pixelSize: 20; font.weight: Font.Bold; Layout.fillWidth: true }
        LiquidButton { text: root.network.enabled ? "Turn off" : "Turn on"; enabled: !!root.network.available && !root.busy; onClicked: ShellState.run("wifiToggle") }
        LiquidButton { text: ShellState.pendingActions.wifiScan ? "Scanning…" : "Scan"; enabled: !!root.network.enabled && !root.busy; onClicked: ShellState.run("wifiScan") }
    }
    LabelText { text: !root.network.available ? "NetworkManager or nmcli is unavailable." : !root.network.device && !ShellState.demo ? "No Wi-Fi adapter found." : root.connected ? "Connected to " + root.network.ssid : root.network.enabled ? "Choose a network to connect." : "Wi-Fi is turned off."; color: root.connected ? Theme.cyan : Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
    LabelText {
        visible: !!root.result.message
        text: root.result.pending ? "Connecting or updating networks…" : root.result.message || ""
        color: root.result.ok === false ? Theme.red : Theme.muted
        Layout.fillWidth: true; wrapMode: Text.Wrap
    }
    Repeater {
        model: root.network.enabled ? root.network.networks || [] : []
        delegate: Rectangle {
            id: ap; required property var modelData
            Layout.fillWidth: true; implicitHeight: 74; radius: 16; color: Theme.surfaceContainerHigh
            RowLayout {
                anchors.fill: parent; anchors.margins: 12; spacing: 12
                ShellIcon { name: "wifi"; width: 20; height: 20; color: ap.modelData.connected ? Theme.cyan : Theme.muted }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 5
                    LabelText { text: ap.modelData.ssid; Layout.fillWidth: true; elide: Text.ElideRight; font.weight: Font.Bold }
                    LabelText { text: ap.modelData.strength + "% · " + (ap.modelData.enterprise ? "Enterprise" : ap.modelData.secured ? ap.modelData.security || "Protected" : "Open network"); color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                }
                LiquidButton {
                    objectName: "wifiConnect-" + ap.modelData.ssid
                    text: ap.modelData.connected ? "Disconnect" : "Connect"; enabled: !root.busy && !!root.network.enabled
                    onClicked: {
                        if (ap.modelData.connected) ShellState.run("wifiDisconnect");
                        else if (ap.modelData.enterprise) ShellState.run("openSettings", {target: "network"});
                        else { root.selectedNetwork = ap.modelData; password.text = ""; connectionDialog.open(); }
                    }
                }
            }
        }
    }
    LabelText { visible: !!root.network.enabled && !(root.network.networks || []).length; text: "No visible networks. Run a scan or check airplane mode."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
    LabelText { text: "Saved networks"; font.weight: Font.Bold; font.pixelSize: 16; Layout.topMargin: 8 }
    Repeater {
        model: root.network.saved || []
        delegate: RowLayout {
            id: saved; required property var modelData
            Layout.fillWidth: true; spacing: 8
            LabelText { text: saved.modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
            LiquidButton { text: "Connect"; enabled: !root.busy && !!root.network.enabled; onClicked: { root.selectedNetwork = {ssid: saved.modelData.name, savedUuid: saved.modelData.uuid, secured: true}; password.text = ""; connectionDialog.open(); } }
            LiquidButton { text: root.forgetUuid === saved.modelData.uuid ? "Confirm forget" : "Forget"; enabled: !root.busy; onClicked: { if (root.forgetUuid === saved.modelData.uuid) { ShellState.run("wifiForget", {uuid: saved.modelData.uuid}); root.forgetUuid = ""; } else root.forgetUuid = saved.modelData.uuid; } }
        }
    }
    LabelText { visible: !(root.network.saved || []).length; text: "No saved Wi-Fi networks"; color: Theme.muted; font.pixelSize: 12 }
    LiquidButton { text: "Advanced network settings"; onClicked: ShellState.run("openSettings", {target: "network"}) }
    Popup {
        id: connectionDialog; objectName: "wifiPasswordDialog"
        parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(440, parent ? parent.width - 32 : 440)
        padding: 24; modal: true; focus: true; popupType: Popup.Item
        closePolicy: Popup.CloseOnEscape
        onOpened: password.forceActiveFocus()
        onClosed: { password.text = ""; reveal.checked = false; root.selectedNetwork = null; }
        background: Rectangle { radius: 24; color: Theme.panel; border.width: 1; border.color: Theme.border }
        contentItem: ColumnLayout {
            spacing: 16
            LabelText { text: "Connect to " + (root.selectedNetwork ? root.selectedNetwork.ssid : "Wi-Fi"); font.weight: Font.Bold; font.pixelSize: 20; Layout.fillWidth: true; wrapMode: Text.Wrap }
            LabelText { text: root.selectedNetwork && root.selectedNetwork.secured ? "Enter the Wi-Fi password, or leave blank to use a saved password." : "This network does not require a password."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
            ExpressiveField { id: password; objectName: "wifiPassword"; visible: !!root.selectedNetwork && !!root.selectedNetwork.secured; Layout.fillWidth: true; placeholderText: "Wi-Fi password"; maximumLength: 128; echoMode: reveal.checked ? TextInput.Normal : TextInput.Password; inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText; Accessible.name: "Wi-Fi password"; onAccepted: connectButton.clicked() }
            RowLayout {
                visible: password.visible
                ExpressiveSwitch { id: reveal; Accessible.name: "Show Wi-Fi password" }
                LabelText { text: "Show password" }
            }
            RowLayout {
                Layout.fillWidth: true
                LiquidButton { text: "Cancel"; onClicked: connectionDialog.close() }
                Item { Layout.fillWidth: true }
                LiquidButton {
                    id: connectButton; text: "Connect"; enabled: !root.busy && !!root.selectedNetwork
                    onClicked: { if (!enabled) return; ShellState.run(root.selectedNetwork.savedUuid ? "wifiSaved" : "wifiConnect", {uuid: root.selectedNetwork.savedUuid || "", bssid: root.selectedNetwork.bssid || "", ssid: root.selectedNetwork.ssid, password: password.text}); connectionDialog.close(); }
                }
            }
        }
    }
}
