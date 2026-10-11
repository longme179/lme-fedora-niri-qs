//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env LME_SHELL_DEMO=1
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/auth"

// Isolated conversation fixture. It never registers with Polkit or runs PAM.
// Only the public AuthenticationWindow/Dialog components are exercised.
ShellRoot {
    id: root
    property var currentFlow: null
    property int submissions: 0
    property bool succeeded: false
    property bool cancelled: false
    function responseField(item) {
        if (item.objectName === "authenticationResponse") return item;
        for (const child of item.children || []) {
            const field = responseField(child);
            if (field) return field;
        }
        return null;
    }
    function start() {
        const previous = currentFlow;
        currentFlow = null;
        if (previous) previous.destroy();
        submissions = 0; succeeded = false; cancelled = false;
        currentFlow = conversation.createObject(root);
    }
    AuthenticationWindow { id: window; flow: root.currentFlow }
    Component {
        id: conversation
        QtObject {
            id: flow
            property string message: "Administrator permission is needed to change the battery charge mode."
            property string actionId: "org.example.test.authentication"
            property bool isResponseRequired: true
            property bool responseVisible: false
            property string inputPrompt: "Password"
            property string supplementaryMessage: ""
            property bool supplementaryIsError: false
            property bool isCompleted: false
            property bool failed: false
            property QtObject firstIdentity: QtObject { property string displayName: "Demo user" }
            property QtObject secondIdentity: QtObject { property string displayName: "Other administrator" }
            property var identities: [firstIdentity, secondIdentity]
            property var selectedIdentity: firstIdentity
            property bool accepted: false
            signal authenticationFailed()
            function submit(value) {
                if (!isResponseRequired) return;
                root.submissions++;
                accepted = value === "test-only";
                isResponseRequired = false;
                completion.restart();
            }
            function cancelAuthenticationRequest() {
                completion.stop();
                root.cancelled = true;
                isCompleted = true;
            }
            property Timer completion: Timer {
                interval: 350
                onTriggered: {
                    if (flow.accepted) {
                        root.succeeded = true;
                        flow.isCompleted = true;
                    } else {
                        flow.failed = true;
                        flow.supplementaryIsError = true;
                        flow.supplementaryMessage = "Authentication failed. Please try again.";
                        flow.isResponseRequired = true;
                        flow.authenticationFailed();
                    }
                }
            }
        }
    }
    IpcHandler {
        target: "authFixture"
        function open(): void { root.start(); }
        function close(): void { if (root.currentFlow) root.currentFlow.cancelAuthenticationRequest(); }
        function selectIdentity(): void { root.currentFlow.selectedIdentity = root.currentFlow.secondIdentity; }
        function visibleResponse(): void { root.currentFlow.responseVisible = true; }
        function status(): string {
            const field = root.responseField(window.contentItem);
            return JSON.stringify({
                visible: window.visible, submissions: root.submissions,
                succeeded: root.succeeded, cancelled: root.cancelled,
                failed: !!root.currentFlow && root.currentFlow.failed,
                inputEmpty: !field || field.length === 0,
                focused: !!field && field.activeFocus,
                masked: !!field && field.echoMode === TextInput.Password,
                waiting: !!root.currentFlow && root.currentFlow.isResponseRequired
            });
        }
    }
    Component.onCompleted: start()
}
