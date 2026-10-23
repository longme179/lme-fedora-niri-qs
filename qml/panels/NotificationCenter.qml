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
            ShellText { text: "Notifications"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 23; font.weight: Font.Bold }
            Item { Layout.fillWidth: true }
            IconButton { iconName: "settings"; tooltip: "Notification settings"; onClicked: ShellState.openSettingsPage("notifications") }
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
                    ShellText { text: "Do not disturb"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14; font.weight: Font.Bold }
                    ShellText { text: "Keep notifications in history"; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
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
        LabelText { visible: Notifications.sharingDnd; text: "Notification popups are paused while sharing your screen"; color: Theme.green; Layout.fillWidth: true; wrapMode: Text.Wrap }
        LabelText { visible: Notifications.dnd; Layout.fillWidth: true; color: Theme.yellow; wrapMode: Text.Wrap; text: Notifications.dndUntil === -1 ? "Popups silenced until turned off" : "Popups resume at " + Qt.formatDateTime(new Date(Notifications.dndUntil), "hh:mm") }
        RowLayout {
            visible: Notifications.saveError !== ""
            Layout.fillWidth: true
            LabelText { Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap; color: Theme.yellow; text: "Notification history has unsaved changes. " + Notifications.saveError }
            LiquidButton {
                objectName: "notificationSaveRetry"; text: Notifications.saving ? "Saving…" : "Retry"
                Accessible.name: "Retry saving notification history"
                enabled: ShellState.backendReady && !Notifications.saving
                onClicked: Notifications.retrySave()
            }
        }
        RowLayout {
            visible: Notifications.mutedApps.length > 0
            Layout.fillWidth: true
            LabelText { text: "Muted apps"; font.pixelSize: 12; color: Theme.muted }
            LiquidComboBox { id: mutedSelector; Layout.fillWidth: true; model: Notifications.mutedApps; Accessible.name: "Muted notification application" }
            LiquidButton { text: "Allow popups"; enabled: mutedSelector.currentIndex >= 0; onClicked: Notifications.muteApp(mutedSelector.currentText, false) }
        }
        RowLayout {
            Layout.fillWidth: true
            ShellText { text: root.filtered.length + " in history"; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
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
                delegate: Item {
                    id: historyEntry
                    objectName: "notificationCard-" + (modelData.id || modelData.appName)
                    required property var modelData
                    width: notificationList.width
                    height: modelData.group ? groupHeading.implicitHeight + 18 : cardContent.implicitHeight
                    RowLayout {
                        id: groupHeading; visible: !!historyEntry.modelData.group
                        anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 8
                        LabelText { text: historyEntry.modelData.appName + " · " + (historyEntry.modelData.total || 0); Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight; font.weight: Font.Bold }
                        LiquidButton { text: Notifications.mutedApps.includes(historyEntry.modelData.appName) ? "Allow popups" : "Mute popups"; font.pixelSize: 11; onClicked: Notifications.muteApp(historyEntry.modelData.appName, !Notifications.mutedApps.includes(historyEntry.modelData.appName)) }
                    }
                    NotificationCard {
                        id: cardContent
                        anchors.left: parent.left; anchors.right: parent.right
                        height: implicitHeight
                        visible: !historyEntry.modelData.group
                        entry: historyEntry.modelData
                        timeText: historyEntry.modelData.group ? "" : root.timeText(historyEntry.modelData.timestamp)
                        animateIdle: false
                        onDismissRequested: Notifications.dismiss(historyEntry.modelData.id)
                        onAnnotateRequested: Notifications.openImage(historyEntry.modelData.id)
                        onActionRequested: identifier => Notifications.invokeAction(historyEntry.modelData.id, identifier)
                    }
                }
            }
            Column {
                visible: root.filtered.length === 0
                anchors.centerIn: parent
                width: parent.width - 30
                spacing: 12
                ShellText { width: parent.width; text: root.query ? "No matching notifications" : "All caught up"; horizontalAlignment: Text.AlignHCenter; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 20; font.weight: Font.Bold }
                ShellText { width: parent.width; text: "New notifications will appear here."; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 13 }
            }
        }
    }
}
