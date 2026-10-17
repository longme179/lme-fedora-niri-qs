pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../services"
import "../theme"

Rectangle {
    id: root
    readonly property var request: BluetoothState.request
    readonly property string kind: request.kind || ""
    readonly property bool inputRequired: kind === "pin" || kind === "passkey"
    readonly property bool displayOnly: kind === "display-pin" || kind === "display-passkey"
    readonly property bool validInput: kind === "passkey" ? /^[0-9]{1,6}$/.test(input.text) : input.text.length > 0
    visible: !!request.token
    implicitHeight: content.implicitHeight + 28
    radius: 20; color: Theme.surfaceContainerHigh; border.color: Theme.accent; border.width: 1
    Connections {
        target: BluetoothState
        function onRequestChanged() {
            if (input.requestToken !== (root.request.token || "")) {
                input.requestToken = root.request.token || ""; input.clear();
                if (root.inputRequired) Qt.callLater(() => input.forceActiveFocus());
            }
        }
    }
    ColumnLayout {
        id: content; anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
        spacing: 10
        LabelText { text: "Pair Bluetooth device"; font.weight: Font.Bold; Layout.fillWidth: true; wrapMode: Text.Wrap }
        LabelText { text: root.request.name || ""; Layout.fillWidth: true; wrapMode: Text.Wrap }
        LabelText {
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
            text: root.kind === "confirm" ? "Confirm that this code matches the code on your device."
                : root.displayOnly ? "Enter this code on the other device."
                : root.kind === "pin" ? "Enter the device PIN."
                : root.kind === "passkey" ? "Enter the numeric passkey shown on the device."
                : root.kind === "service" ? "Allow this device to use the requested Bluetooth service?"
                : "Allow pairing with this device?"
        }
        LabelText {
            objectName: "bluetoothPasskey"; visible: !!root.request.code
            text: root.request.code || ""; font.pixelSize: 30; font.weight: Font.Bold
            Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
        }
        LabelText { visible: root.kind === "display-passkey"; text: (root.request.entered || 0) + " of 6 digits entered"; color: Theme.muted }
        LabelText { visible: root.kind === "service"; text: root.request.service || ""; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; color: Theme.muted; font.pixelSize: 12 }
        ExpressiveField {
            id: input; objectName: "bluetoothPairInput"; property string requestToken: ""
            visible: root.inputRequired; Layout.fillWidth: true
            maximumLength: root.kind === "passkey" ? 6 : 16
            placeholderText: root.kind === "pin" ? "PIN" : "Passkey"
            Accessible.name: placeholderText
            onAccepted: if (root.validInput) BluetoothState.reply(root.request.token, true, text)
        }
        RowLayout {
            Layout.fillWidth: true
            LiquidButton { objectName: "bluetoothPairCancel"; text: "Cancel"; onClicked: BluetoothState.reply(root.request.token, false, "") }
            Item { Layout.fillWidth: true }
            LiquidButton {
                objectName: "bluetoothPairConfirm"; visible: !root.displayOnly
                text: root.inputRequired ? "Submit" : "Confirm"; selected: true
                enabled: !root.inputRequired || root.validInput
                onClicked: BluetoothState.reply(root.request.token, true, input.text)
            }
        }
    }
}
