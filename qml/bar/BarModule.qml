pragma ComponentBehavior: Bound
import QtQuick
import Quickshell.Services.SystemTray
import Quickshell.Services.Mpris
import "../components"
import "../services"
import "../theme"

Loader {
    id: root
    required property string moduleId
    property var screenInfo: null
    property var windowInfo: null
    property bool compact: false
    property real titleBudget: 360
    readonly property var battery: ShellState.system.battery || {}
    readonly property var player: ShellState.demo ? null : Mpris.players.values.find(p => p.isPlaying) || Mpris.players.values[0] || null
    readonly property bool available: moduleId === "activity" ? ShellState.preferences.activityEnabled !== false : moduleId === "tray" ? !ShellState.demo && SystemTray.items.values.length > 0
                                   : moduleId === "battery" ? battery.available === true
                                   : moduleId === "media" ? player !== null : true
    active: available
    visible: available
    width: available && item ? (item as Item).implicitWidth : 0
    height: 30
    y: parent ? (parent.height - height) / 2 : 0
    sourceComponent: (moduleId === "activity" || moduleId === "windowTitle" && ShellState.preferences.activityEnabled !== false) ? activityComponent : moduleId === "workspaces" ? workspaceComponent : moduleId === "windowTitle" ? titleComponent
                   : ["launcher", "overview", "tray", "notifications", "settings", "clipboard"].includes(moduleId) ? actionComponent : statusComponent
    Component {
        id: activityComponent
        ActivityButton { screenInfo: root.screenInfo; windowInfo: root.windowInfo; budget: root.titleBudget }
    }
    Component {
        id: actionComponent
        IconButton {
            id: button
            implicitWidth: 30; implicitHeight: 30
            iconName: root.moduleId === "notifications" ? (Notifications.dnd ? "bell-off" : "bell") : BarRegistry.info(root.moduleId).icon
            tooltip: ["overview", "launcher"].includes(root.moduleId) ? "" : BarRegistry.info(root.moduleId).title
            Accessible.name: BarRegistry.info(root.moduleId).title
            active: root.moduleId === "notifications" ? ShellState.notificationsOpen : root.moduleId === "launcher" ? ShellState.launcherOpen : root.moduleId === "tray" ? ShellState.trayOpen : root.moduleId === "clipboard" ? ShellState.clipboardOpen : false
            onClicked: {
                if (root.moduleId === "overview") ShellState.nativeOverview();
                else {
                    if (root.moduleId === "tray") {
                        const position = button.mapToItem(null, button.width, 0);
                        ShellState.trayAnchorX = position.x + (root.windowInfo ? Theme.barSideMargin : 0);
                    }
                    ShellState.togglePanel(root.moduleId, root.screenInfo);
                }
            }
            TapHandler { enabled: root.moduleId === "overview"; acceptedButtons: Qt.RightButton; onTapped: ShellState.togglePanel("overview", root.screenInfo) }
            Rectangle { visible: root.moduleId === "notifications" && Notifications.unreadCount > 0; width: 6; height: 6; radius: 3; color: Theme.pink; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 4 }
        }
    }
    Component {
        id: workspaceComponent
        Flickable {
            id: workspaceScroller
            implicitWidth: Math.min(workspaceRow.implicitWidth, root.compact ? 150 : 280)
            contentWidth: workspaceRow.implicitWidth; contentHeight: height
            clip: true; flickableDirection: Flickable.HorizontalFlick; boundsBehavior: Flickable.StopAtBounds
            Row {
                id: workspaceRow
                height: 30; spacing: 4
                Repeater {
                    model: ShellState.workspacesFor(root.screenInfo)
                    delegate: LiquidButton {
                        id: workspace
                        required property var modelData
                        width: modelData.is_focused ? 42 : 34; height: 30; implicitHeight: 30
                        leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0; hoverEnabled: true
                        Behavior on width { MotionAnimation {} }
                        Accessible.name: "Workspace " + (modelData.name || modelData.idx)
                        background: Rectangle {
                            radius: workspace.modelData.is_focused ? 12 : 15
                            color: workspace.modelData.is_focused ? Theme.workspaceActive : workspace.hovered ? Theme.barHover : "transparent"
                            border.width: workspace.visualFocus ? 2 : 0; border.color: Theme.text
                            Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
                            Behavior on radius { MotionAnimation {} }
                        }
                        contentItem: LabelText {
                            text: workspace.modelData.name || workspace.modelData.idx
                            color: workspace.modelData.is_focused ? Theme.workspaceText : Theme.barMuted
                            font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                        }
                        onClicked: ShellState.run("workspace", {id: modelData.id})
                        onActiveFocusChanged: if (activeFocus) workspaceScroller.contentX = Math.max(0, Math.min(x, workspaceScroller.contentWidth - workspaceScroller.width))
                    }
                }
            }
        }
    }
    Component {
        id: titleComponent
        Item {
            implicitWidth: Math.min(titleMetrics.width + 16, Math.max(0, root.titleBudget))
            TextMetrics { id: titleMetrics; text: titleText.text; font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight }
            LabelText {
                id: titleText
                anchors.fill: parent; leftPadding: 8; rightPadding: 8
                text: ShellState.niri.available ? ShellState.focusedTitle : ShellState.demo ? "LME / Liquid Desktop" : "niri unavailable"
                color: Theme.barMuted; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight
            }
        }
    }

    Component {
        id: statusComponent
        LiquidButton {
            id: button
            property date now: new Date()
            readonly property var audio: ShellState.system.audio || {}
            readonly property var network: ShellState.system.network || {}
            readonly property string caption: root.moduleId === "clock" ? Qt.locale("en_US").toString(now, root.compact ? "HH:mm" : "ddd, MMM d  ·  HH:mm")
                : root.moduleId === "audio" ? audio.available ? audio.muted ? "Mute" : Math.round(audio.volume) + "%" : "—"
                : root.moduleId === "network" ? network.connected ? network.ssid === "Ethernet" ? "Ethernet" : "Wi-Fi" : "Offline"
                : root.moduleId === "battery" ? (root.battery.charging ? "+" : "") + Math.round(root.battery.percent || 0) + "%"
                : root.moduleId === "resources" ? Math.round(ShellState.system.cpu || 0) + "% CPU · " + Math.round(ShellState.system.memoryPercent || 0) + "% RAM"
                : root.player ? root.player.trackTitle || root.player.identity : "Media"
            // Measure an unconstrained label with the exact rendered font. A
            // separately configured TextMetrics can undercount hinted glyphs.
            implicitWidth: Math.min(Math.ceil(captionMeasure.implicitWidth) + 2 + (root.moduleId === "clock" ? 24 : 48), root.moduleId === "media" ? 220 : 300)
            implicitHeight: 30; leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0; hoverEnabled: true
            Accessible.name: BarRegistry.info(root.moduleId).title + ": " + caption
            onClicked: ShellState.togglePanel(root.moduleId === "network" ? "wifi" : "control", root.screenInfo)
            background: Rectangle { radius: 15; color: button.hovered || ShellState.controlOpen ? Theme.barHover : "transparent"; border.width: button.visualFocus ? 2 : 0; border.color: Theme.accent }
            LabelText { id: captionMeasure; visible: false; text: button.caption; font: statusText.font }
            contentItem: Item {
                Row {
                    id: content
                    anchors.centerIn: parent; spacing: 6
                    ShellIcon { visible: root.moduleId !== "clock"; name: BarRegistry.info(root.moduleId).icon; color: root.moduleId === "battery" && root.battery.percent < 20 ? Theme.red : Theme.barMuted; width: 18; height: 18; anchors.verticalCenter: parent.verticalCenter }
                    LabelText { id: statusText; text: button.caption; color: Theme.barText; width: Math.max(0, button.width - (root.moduleId === "clock" ? 24 : 48)); elide: Text.ElideRight; font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight; anchors.verticalCenter: parent.verticalCenter }
                }
            }
            Timer { interval: 1000; running: root.moduleId === "clock"; repeat: true; onTriggered: button.now = new Date() }
        }
    }
}
