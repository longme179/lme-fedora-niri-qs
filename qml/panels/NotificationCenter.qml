pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../services"
import "../theme"
import "../components"

Item {
    id: root
    implicitWidth: 392
    implicitHeight: 630
    focus: true
    property bool embedded: false
    property date now: new Date()
    Timer { interval: 60000; running: root.visible; repeat: true; onTriggered: root.now = new Date() }

    function timeText(timestamp) {
        const elapsed = Math.max(0, Math.floor((root.now.getTime() - timestamp) / 60000));
        return elapsed < 1 ? "Now" : elapsed < 60 ? elapsed + " min ago" : Qt.formatDateTime(new Date(timestamp), "hh:mm");
    }
    Component.onCompleted: Notifications.markRead()
    Connections {
        target: ShellState
        function onNotificationsOpenChanged() {
            if (ShellState.notificationsOpen) Notifications.markRead();
        }
    }
    Keys.onEscapePressed: ShellState.closePanels()

    GlassPanel { anchors.fill: parent; visible: !root.embedded }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 16
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Notifications"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 23; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
            LiquidButton { text: "×"; Accessible.name: "Close notifications"; onClicked: ShellState.closePanels(); palette.button: Theme.surface; palette.buttonText: Theme.text }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 68
            color: Theme.surface
            radius: Theme.smallRadius
            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                ColumnLayout {
                    spacing: 3
                    Text { text: "Do not disturb"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
                    Text { text: "Keep notifications in history"; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                }
                Item { Layout.fillWidth: true }
                Switch {
                    checked: Notifications.dnd
                    Accessible.name: "Do not disturb"
                    onToggled: Notifications.dnd = checked
                    palette.highlight: Theme.purple
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Text { text: Notifications.count + " in this session"; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
            Item { Layout.fillWidth: true }
            LiquidButton { text: "Clear all"; enabled: Notifications.count > 0; onClicked: Notifications.dismissAll(); palette.button: Theme.surface; palette.buttonText: Theme.pink }
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            ListView {
                id: notificationList
                anchors.fill: parent
                clip: true
                spacing: 10
                model: Notifications.history
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    id: entry
                    required property var modelData
                    width: notificationList.width
                    height: cardContent.implicitHeight + 28
                    radius: Theme.smallRadius
                    color: Theme.surface
                    border.color: modelData.urgency === 2 ? Theme.red : Theme.border
                    border.width: 1
                    ColumnLayout {
                        id: cardContent
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 14
                        spacing: 8
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: entry.modelData.appName; textFormat: Text.PlainText; color: Theme.purple; font.family: Theme.fontFamily; font.pixelSize: 11; font.weight: Font.DemiBold; elide: Text.ElideRight }
                            Text { text: root.timeText(entry.modelData.timestamp); color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 10 }
                            LiquidButton {
                                text: "×"
                                implicitWidth: 28
                                implicitHeight: 28
                                Accessible.name: "Dismiss " + entry.modelData.summary
                                onClicked: Notifications.dismiss(entry.modelData.id)
                                palette.button: Theme.panel
                                palette.buttonText: Theme.muted
                            }
                        }
                        Text { Layout.fillWidth: true; text: entry.modelData.summary; textFormat: Text.PlainText; wrapMode: Text.WordWrap; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.DemiBold }
                        Text { Layout.fillWidth: true; visible: text.length > 0; text: entry.modelData.body; textFormat: Text.PlainText; wrapMode: Text.WordWrap; maximumLineCount: 8; elide: Text.ElideRight; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                        Flow {
                            Layout.fillWidth: true
                            spacing: 6
                            Repeater {
                                model: entry.modelData.active ? entry.modelData.actions : []
                                delegate: LiquidButton {
                                    required property var modelData
                                    text: modelData.text || modelData.identifier
                                    onClicked: Notifications.invokeAction(entry.modelData.id, modelData.identifier)
                                    palette.button: Theme.panel
                                    palette.buttonText: Theme.cyan
                                }
                            }
                        }
                    }
                }
            }
            Column {
                visible: Notifications.count === 0
                anchors.centerIn: parent
                width: parent.width - 30
                spacing: 12
                Text { width: parent.width; text: "All caught up"; horizontalAlignment: Text.AlignHCenter; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.weight: Font.DemiBold }
                Text { width: parent.width; text: "New notifications will appear here."; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 13 }
            }
        }
    }
}
