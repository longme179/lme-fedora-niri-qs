import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.SystemTray
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    property var screenInfo: null
    property var windowInfo: null
    implicitHeight: 46
    radius: 17
    property date now: new Date()
    function displayTrayMenu(trayItem, button) {
        if (!windowInfo || !trayItem.hasMenu) return;
        const position = windowInfo.itemPosition(button);
        trayItem.display(windowInfo, Math.round(position.x), Math.round(position.y + button.height));
    }
    Timer { interval: 1000; running: true; repeat: true; onTriggered: root.now = new Date() }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10; anchors.rightMargin: 10
        spacing: 10
        IconButton {
            glyph: "◈"; tooltip: "Applications · Super+Space"
            active: ShellState.launcherOpen
            onClicked: ShellState.togglePanel("launcher", root.screenInfo)
        }
        Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 18; color: Theme.border }
        Row {
            spacing: 4
            Repeater {
                model: (ShellState.niri.workspaces || []).filter(w => !root.screenInfo || !w.output || w.output === root.screenInfo.name)
                delegate: AbstractButton {
                    id: workspace
                    required property var modelData
                    width: modelData.is_focused ? 42 : 30; height: 28
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
            elide: Text.ElideRight
            font.pixelSize: 12
        }
        Item { Layout.fillWidth: true }
        Repeater {
            model: ShellState.demo ? [] : SystemTray.items
            delegate: AbstractButton {
                id: trayButton
                required property var modelData
                Layout.preferredWidth: 28; Layout.preferredHeight: 30
                hoverEnabled: true
                Accessible.name: modelData.tooltipTitle || modelData.title || modelData.id
                background: Rectangle { radius: 9; color: trayButton.hovered ? Theme.alpha(Theme.text, 0.09) : "transparent" }
                contentItem: Image { source: trayButton.modelData.icon; sourceSize.width: 18; sourceSize.height: 18; fillMode: Image.PreserveAspectFit }
                onClicked: {
                    if (modelData.onlyMenu) root.displayTrayMenu(modelData, trayButton);
                    else modelData.activate();
                }
                TapHandler {
                    acceptedButtons: Qt.RightButton
                    onTapped: root.displayTrayMenu(trayButton.modelData, trayButton)
                }
                WheelHandler { onWheel: event => trayButton.modelData.scroll(event.angleDelta.y, false) }
                ToolTip.visible: hovered
                ToolTip.text: modelData.tooltipTitle || modelData.title
                ToolTip.delay: 500
            }
        }
        Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 18; color: Theme.border; visible: !ShellState.demo && SystemTray.items.values.length > 0 }
        IconButton {
            glyph: Notifications.dnd ? "◌" : "♧"
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
            Layout.preferredWidth: statusRow.implicitWidth + 20; Layout.preferredHeight: 30
            hoverEnabled: true
            Accessible.name: "Open control center"
            onClicked: ShellState.togglePanel("control", root.screenInfo)
            background: Rectangle { radius: 10; color: status.hovered || ShellState.controlOpen ? Theme.alpha(Theme.accent, 0.18) : Theme.alpha(Theme.surface, 0.5) }
            contentItem: Row {
                id: statusRow
                spacing: 10
                anchors.centerIn: parent
                LabelText { text: ShellState.system.network && ShellState.system.network.connected ? "Wi-Fi" : "Offline"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                LabelText {
                    text: ShellState.system.audio && ShellState.system.audio.available ? ShellState.system.audio.muted ? "Mute" : Math.round(ShellState.system.audio.volume) + "%" : "Audio —"
                    font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter
                }
                LabelText {
                    readonly property var battery: ShellState.system.battery || {}
                    visible: battery.available === true
                    text: battery.available ? (battery.charging ? "+ " : "") + Math.round(battery.percent) + "%" : ""
                    color: battery.available && battery.percent < 20 ? Theme.red : Theme.green
                    font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
        AbstractButton {
            Layout.preferredWidth: 118; Layout.preferredHeight: 32
            Accessible.name: "Clock and control center"
            onClicked: ShellState.togglePanel("control", root.screenInfo)
            contentItem: Column {
                LabelText { text: Qt.formatDateTime(root.now, "ddd, MMM d"); color: Theme.muted; font.pixelSize: 10; anchors.horizontalCenter: parent.horizontalCenter }
                LabelText { text: Qt.formatDateTime(root.now, "HH:mm"); font.pixelSize: 14; font.weight: Font.DemiBold; anchors.horizontalCenter: parent.horizontalCenter }
            }
        }
    }
}
