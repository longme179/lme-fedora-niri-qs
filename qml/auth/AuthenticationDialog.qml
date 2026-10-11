pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"

GlassPanel {
    id: root
    required property var flow
    readonly property bool waitingForInput: !!flow && flow.isResponseRequired && !flow.isCompleted
    implicitWidth: 480
    implicitHeight: content.implicitHeight + 48
    focus: true
    Keys.onEscapePressed: cancel()

    function focusInput() {
        if (waitingForInput) response.forceActiveFocus();
    }
    function submit() {
        if (!waitingForInput) return;
        // Submit directly to the Polkit conversation, never to the JSON backend.
        flow.submit(response.text);
        response.clear();
    }
    function cancel() {
        response.clear();
        if (flow && !flow.isCompleted) flow.cancelAuthenticationRequest();
    }
    function resetInput() {
        response.clear();
        Qt.callLater(focusInput);
    }
    onFlowChanged: resetInput()
    Component.onCompleted: Qt.callLater(focusInput)
    Connections {
        target: root.flow
        function onIsResponseRequiredChanged() { root.resetInput(); }
        function onSelectedIdentityChanged() { root.resetInput(); }
        function onAuthenticationFailed() { root.resetInput(); }
        function onIsCompletedChanged() { root.resetInput(); }
    }

    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 24 }
        spacing: 16
        RowLayout {
            spacing: 14
            Rectangle {
                Layout.preferredWidth: 48; Layout.preferredHeight: 48
                radius: 18; color: Theme.primaryContainer
                ShellIcon { anchors.centerIn: parent; name: "lock"; color: Theme.accent; width: 24; height: 24 }
            }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                LabelText { text: "Authentication required"; font.pixelSize: 20; font.weight: Theme.headingWeight; Layout.fillWidth: true; wrapMode: Text.Wrap }
                LabelText {
                    text: root.flow && root.flow.selectedIdentity ? "Continue as " + root.flow.selectedIdentity.displayName : "Administrator permission"
                    color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap
                }
            }
        }
        LabelText {
            text: root.flow ? root.flow.message : ""
            Layout.fillWidth: true; wrapMode: Text.Wrap
            maximumLineCount: 6; elide: Text.ElideRight
        }
        LiquidComboBox {
            visible: !!root.flow && root.flow.identities.length > 1
            Layout.fillWidth: true
            model: root.flow ? root.flow.identities : []
            textRole: "displayName"
            currentIndex: root.flow ? Array.from(root.flow.identities).indexOf(root.flow.selectedIdentity) : -1
            Accessible.name: "Authentication account"
            onActivated: index => { if (root.flow) root.flow.selectedIdentity = root.flow.identities[index]; }
        }
        Rectangle {
            visible: !!root.flow && (!!root.flow.supplementaryMessage || root.flow.failed)
            Layout.fillWidth: true
            implicitHeight: feedback.implicitHeight + 24
            radius: Theme.smallRadius
            color: Theme.alpha(root.flow && (root.flow.supplementaryIsError || root.flow.failed) ? Theme.red : Theme.accent, 0.12)
            LabelText {
                id: feedback
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                text: root.flow ? root.flow.supplementaryMessage || (root.flow.failed ? "Authentication failed. Please try again." : "") : ""
                color: root.flow && (root.flow.supplementaryIsError || root.flow.failed) ? Theme.red : Theme.text
                wrapMode: Text.Wrap
                maximumLineCount: 4; elide: Text.ElideRight
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 8
            LabelText {
                text: root.waitingForInput ? root.flow.inputPrompt || "Password" : "Waiting for authentication…"
                color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap
            }
            ExpressiveField {
                id: response
                objectName: "authenticationResponse"
                Layout.fillWidth: true
                enabled: root.waitingForInput
                placeholderText: root.flow && root.flow.responseVisible ? "Enter response" : "Enter password"
                echoMode: root.flow && root.flow.responseVisible ? TextInput.Normal : TextInput.Password
                inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
                Accessible.name: root.flow ? root.flow.inputPrompt || "Password" : "Password"
                onAccepted: root.submit()
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            Item { Layout.fillWidth: true }
            LiquidButton { text: "Cancel"; onClicked: root.cancel() }
            LiquidButton {
                text: root.waitingForInput ? "Authenticate" : "Authenticating…"
                enabled: root.waitingForInput
                palette.button: Theme.accent; palette.buttonText: Theme.onPrimary
                onClicked: root.submit()
            }
        }
    }
}
