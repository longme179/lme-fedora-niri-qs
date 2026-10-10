import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Services.SystemTray
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    property var screenInfo: null
    property var windowInfo: null
    implicitHeight: Theme.barHeight
    radius: 15
    property date now: new Date()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: root.now = new Date() }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10; anchors.rightMargin: 10
        spacing: 8
        IconButton {
            iconName: "applications"; tooltip: "Applications · Super+Space"
            Layout.preferredWidth: 30; Layout.preferredHeight: 30
            Layout.alignment: Qt.AlignVCenter
            active: ShellState.launcherOpen
            onClicked: ShellState.togglePanel("launcher", root.screenInfo)
        }
        Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 18; color: Theme.border }
        Row {
            Layout.alignment: Qt.AlignVCenter
            spacing: 4
            Repeater {
                model: (ShellState.niri.workspaces || []).filter(w => !root.screenInfo || !w.output || w.output === root.screenInfo.name)
                delegate: AbstractButton {
                    id: workspace
                    required property var modelData
                    width: modelData.is_focused ? 40 : 30; height: 30
                    padding: 0
                    hoverEnabled: true
                    Accessible.name: "Workspace " + (modelData.name || modelData.idx)
                    background: Rectangle {
                        radius: 10
                        color: workspace.modelData.is_focused ? Theme.accent
                              : workspace.hovered ? Theme.alpha(Theme.accent, 0.22) : Theme.alpha(Theme.surface, 0.65)
                        border.width: workspace.visualFocus ? 2 : 0; border.color: Theme.text
                    }
                    contentItem: LabelText {
                        text: workspace.modelData.name || workspace.modelData.idx
                        color: workspace.modelData.is_focused ? Theme.background : Theme.muted
                        font.pixelSize: 12; font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                    onClicked: ShellState.run("workspace", {id: modelData.id})
                    Behavior on width { NumberAnimation { duration: Theme.animationDuration } }
                }
            }
        }
        LabelText {
            text: ShellState.niri.available ? ShellState.focusedTitle : ShellState.demo ? "Demo session" : "niri unavailable"
            color: Theme.muted
            Layout.maximumWidth: Math.max(80, root.width * 0.22)
            Layout.alignment: Qt.AlignVCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            font.pixelSize: 12
        }
        Item { Layout.fillWidth: true }
        IconButton {
            id: trayToggle
            visible: !ShellState.demo && SystemTray.items.values.length > 0
            Layout.preferredWidth: 30; Layout.preferredHeight: 30
            Layout.alignment: Qt.AlignVCenter
            iconName: "tray"
            tooltip: "System tray"
            active: ShellState.trayOpen && ShellState.panelScreen === root.screenInfo
            onClicked: {
                const position = trayToggle.mapToItem(null, trayToggle.width, 0);
                ShellState.trayAnchorX = position.x + (root.windowInfo ? Theme.barSideMargin : 0);
                ShellState.togglePanel("tray", root.screenInfo);
            }
        }
        IconButton {
            iconName: Notifications.dnd ? "bell-off" : "bell"
            Layout.preferredWidth: 30; Layout.preferredHeight: 30
            Layout.alignment: Qt.AlignVCenter
            tooltip: "Notifications · " + Notifications.unreadCount + " unread"
            active: ShellState.notificationsOpen
            onClicked: ShellState.togglePanel("notifications", root.screenInfo)
            Rectangle {
                visible: Notifications.unreadCount > 0
                width: 6; height: 6; radius: 3; color: Theme.pink
                anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 5
            }
        }
        AbstractButton {
            id: status
            Layout.preferredWidth: statusRow.implicitWidth + 24; Layout.preferredHeight: 30
            Layout.alignment: Qt.AlignVCenter
            padding: 0
            hoverEnabled: true
            Accessible.name: "Open control center"
            onClicked: ShellState.togglePanel("control", root.screenInfo)
            background: Rectangle { radius: 10; color: status.hovered || ShellState.controlOpen ? Theme.alpha(Theme.accent, 0.18) : Theme.alpha(Theme.surface, 0.5) }
            contentItem: Item {
                Row {
                    id: statusRow
                    spacing: 10
                    anchors.centerIn: parent
                    LabelText { text: ShellState.system.network && ShellState.system.network.connected ? "Wi-Fi" : "Offline"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                    LabelText {
                        text: ShellState.system.audio && ShellState.system.audio.available ? ShellState.system.audio.muted ? "Mute" : Math.round(ShellState.system.audio.volume) + "%" : "Audio —"
                        font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter
                    }
                    LabelText {
                        readonly property var battery: ShellState.system.battery || {}
                        visible: battery.available === true
                        text: battery.available ? (battery.charging ? "+ " : "") + Math.round(battery.percent) + "%" : ""
                        color: battery.available && battery.percent < 20 ? Theme.red : Theme.green
                        font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
        AbstractButton {
            id: clock
            Layout.preferredWidth: 100; Layout.preferredHeight: 30
            Layout.alignment: Qt.AlignVCenter
            padding: 0
            hoverEnabled: true
            Accessible.name: "Clock and control center"
            onClicked: ShellState.togglePanel("control", root.screenInfo)
            background: Rectangle {
                radius: 10
                color: clock.hovered || ShellState.controlOpen ? Theme.alpha(Theme.accent, 0.18) : Theme.alpha(Theme.surface, 0.5)
                border.width: clock.visualFocus ? 2 : 0; border.color: Theme.accent
            }
            contentItem: Item {
                Column {
                    anchors.centerIn: parent
                    spacing: 1
                    LabelText { text: Qt.formatDateTime(root.now, "ddd, MMM d"); color: Theme.muted; font.pixelSize: 10; anchors.horizontalCenter: parent.horizontalCenter }
                    LabelText { text: Qt.formatDateTime(root.now, "HH:mm"); font.pixelSize: 12; font.weight: Font.DemiBold; anchors.horizontalCenter: parent.horizontalCenter }
                }
            }
        }
    }
}
