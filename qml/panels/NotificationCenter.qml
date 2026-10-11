pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../services"
import "../theme"
import "../components"

Item {
    id: root
    implicitWidth: 520
    implicitHeight: 760
    focus: true
    property bool embedded: false
    property date now: new Date()
    property string query: ""
    readonly property var filtered: Notifications.history.filter(e => [e.appName, e.summary, e.body].join(" ").toLowerCase().includes(query.toLowerCase().trim()))
    readonly property var grouped: {
        const names = [...new Set(filtered.map(e => e.appName))];
        let result = [];
        for (const name of names) {
            const entries = filtered.filter(e => e.appName === name);
            result = result.concat([{group: true, appName: name, total: entries.length}], entries);
        }
        return result;
    }
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

    GlassPanel { role: "notificationFill"; anchors.fill: parent; visible: !root.embedded }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 16
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Notifications"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 23; font.weight: Font.Bold }
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
                    Text { text: "Do not disturb"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.Bold }
                    Text { text: "Keep notifications in history"; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                }
                Item { Layout.fillWidth: true }
                ExpressiveSwitch {
                    checked: Notifications.dnd
                    Accessible.name: "Do not disturb"
                    onToggled: Notifications.setDnd(checked ? -1 : 0)
                    palette.highlight: Theme.purple
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            ExpressiveField { Layout.fillWidth: true; placeholderText: "Search notification history"; Accessible.name: "Search notifications"; onTextChanged: root.query = text }
            LiquidComboBox { model: ["DND duration…", "15 minutes", "1 hour", "8 hours", "Until turned off", "Turn off DND"]; Accessible.name: "Do not disturb duration"; onActivated: { if (currentIndex) Notifications.setDnd([0, 15, 60, 480, -1, 0][currentIndex]); currentIndex = 0; } }
        }
        LabelText { visible: Notifications.dnd; Layout.fillWidth: true; color: Theme.yellow; wrapMode: Text.Wrap; text: Notifications.dndUntil === -1 ? "Popups silenced until turned off" : "Popups resume at " + Qt.formatDateTime(new Date(Notifications.dndUntil), "hh:mm") }
        RowLayout {
            visible: Notifications.mutedApps.length > 0
            Layout.fillWidth: true
            LabelText { text: "Muted apps"; font.pixelSize: 12; color: Theme.muted }
            LiquidComboBox { id: mutedSelector; Layout.fillWidth: true; model: Notifications.mutedApps; Accessible.name: "Muted notification application" }
            LiquidButton { text: "Allow popups"; enabled: mutedSelector.currentIndex >= 0; onClicked: Notifications.muteApp(mutedSelector.currentText, false) }
        }
        RowLayout {
            Layout.fillWidth: true
            Text { text: root.filtered.length + " in history"; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
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
                model: root.grouped
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    id: entry
                    required property var modelData
                    width: notificationList.width
                    height: modelData.group ? groupHeading.implicitHeight + 18 : cardContent.implicitHeight + 28
                    radius: Theme.smallRadius
                    color: modelData.group ? "transparent" : Theme.surface
                    border.color: modelData.urgency === 2 ? Theme.red : Theme.border
                    border.width: modelData.group ? 0 : 1
                    RowLayout {
                        id: groupHeading; visible: !!entry.modelData.group
                        anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                        LabelText { text: entry.modelData.appName + " · " + (entry.modelData.total || 0); Layout.fillWidth: true; elide: Text.ElideRight; font.weight: Font.Bold }
                        LiquidButton { text: Notifications.mutedApps.includes(entry.modelData.appName) ? "Allow popups" : "Mute popups"; font.pixelSize: 11; onClicked: Notifications.muteApp(entry.modelData.appName, !Notifications.mutedApps.includes(entry.modelData.appName)) }
                    }
                    ColumnLayout {
                        id: cardContent
                        visible: !entry.modelData.group
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 14
                        spacing: 8
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: entry.modelData.appName; textFormat: Text.PlainText; color: Theme.purple; font.family: Theme.fontFamily; font.pixelSize: 12; font.weight: Font.Bold; elide: Text.ElideRight }
                            Text { text: entry.modelData.group ? "" : root.timeText(entry.modelData.timestamp); color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 10 }
                            IconButton {
                                glyph: "×"
                                implicitWidth: 28
                                implicitHeight: 28
                                Accessible.name: "Dismiss " + entry.modelData.summary
                                onClicked: Notifications.dismiss(entry.modelData.id)
                                palette.button: Theme.panel
                                palette.buttonText: Theme.muted
                            }
                        }
                        Text { Layout.fillWidth: true; text: entry.modelData.summary || ""; textFormat: Text.PlainText; wrapMode: Text.WordWrap; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.Bold }
                        Text { Layout.fillWidth: true; visible: text.length > 0; text: entry.modelData.body || ""; textFormat: Text.PlainText; wrapMode: Text.WordWrap; maximumLineCount: 8; elide: Text.ElideRight; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
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
                visible: root.filtered.length === 0
                anchors.centerIn: parent
                width: parent.width - 30
                spacing: 12
                Text { width: parent.width; text: root.query ? "No matching notifications" : "All caught up"; horizontalAlignment: Text.AlignHCenter; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.weight: Font.Bold }
                Text { width: parent.width; text: "New notifications will appear here."; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 13 }
            }
        }
    }
}
