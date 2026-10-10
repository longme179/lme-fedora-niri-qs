pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import "../services"
import "../theme"
import "../components"

Item {
    id: root
    implicitWidth: 440
    implicitHeight: 430
    focus: true
    property string pendingAction: ""
    property string pendingLabel: ""

    function requestAction(action, label) {
        pendingAction = action;
        pendingLabel = label;
    }

    Connections {
        target: ShellState
        function onPowerOpenChanged() { root.pendingAction = ""; }
    }
    Keys.onEscapePressed: ShellState.closePanels()

    component PowerButton: LiquidButton {
        id: powerButton
        required property string actionName
        required property string label
        property string symbol: ""
        property color accent: Theme.purple
        Layout.fillWidth: true
        Layout.preferredHeight: 58
        Accessible.name: label
        onClicked: {
            if (actionName === "lock") {
                ShellState.run("lock");
                ShellState.closePanels();
            } else root.requestAction(actionName, label);
        }
        background: Rectangle {
            radius: Theme.smallRadius
            color: powerButton.hovered ? Theme.surface : Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, 0.55)
            border.color: powerButton.activeFocus ? powerButton.accent : Theme.border
            border.width: 1
        }
        contentItem: RowLayout {
            spacing: 12
            Text { text: powerButton.symbol; color: powerButton.accent; font.family: Theme.fontFamily; font.pixelSize: 20; Layout.preferredWidth: 28; horizontalAlignment: Text.AlignHCenter }
            Text { text: powerButton.label; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14 }
            Item { Layout.fillWidth: true }
            Text { text: "›"; color: Theme.muted; font.pixelSize: 22 }
        }
    }

    GlassPanel { anchors.fill: parent }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 3
                Text { text: root.pendingAction ? root.pendingLabel + "?" : "Take a break"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 24; font.weight: Font.Bold }
                Text { text: root.pendingAction ? "Confirm to continue." : "Your session, your pace."; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 13 }
            }
            Item { Layout.fillWidth: true }
            LiquidButton { text: "×"; Accessible.name: "Close power menu"; onClicked: ShellState.closePanels(); palette.button: Theme.surface; palette.buttonText: Theme.text }
        }

        GridLayout {
            visible: !root.pendingAction
            columns: 2
            columnSpacing: 12
            rowSpacing: 12
            Layout.fillWidth: true
            PowerButton { actionName: "lock"; label: "Lock"; symbol: "◈"; accent: Theme.cyan }
            PowerButton { actionName: "suspend"; label: "Suspend"; symbol: "☾" }
            PowerButton { actionName: "logout"; label: "Log out"; symbol: "↗"; accent: Theme.yellow }
            PowerButton { actionName: "reboot"; label: "Restart"; symbol: "↻"; accent: Theme.pink }
            PowerButton { actionName: "poweroff"; label: "Shut down"; symbol: "⏻"; accent: Theme.red; Layout.columnSpan: 2 }
        }

        Rectangle {
            visible: root.pendingAction.length > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.smallRadius
            color: Theme.surface
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 16
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: root.pendingAction === "suspend" ? "Your session will stay open while the laptop sleeps." : "Save your work before continuing. Open applications may close."
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                }
                Item { Layout.fillHeight: true }
                RowLayout {
                    Layout.fillWidth: true
                    LiquidButton {
                        text: "Go back"
                        Layout.fillWidth: true
                        onClicked: root.pendingAction = ""
                        palette.button: Theme.panel
                        palette.buttonText: Theme.text
                    }
                    LiquidButton {
                        text: "Confirm " + root.pendingLabel.toLowerCase()
                        Layout.fillWidth: true
                        onClicked: {
                            ShellState.run(root.pendingAction);
                            ShellState.closePanels();
                            root.pendingAction = "";
                        }
                        palette.button: Theme.red
                        palette.buttonText: Theme.background
                    }
                }
            }
        }
        Item { Layout.fillHeight: true; visible: !root.pendingAction }
        Text { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "Session actions run through Fedora’s user session and logind."; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
    }
}
