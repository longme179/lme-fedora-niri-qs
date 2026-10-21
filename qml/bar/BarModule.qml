pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
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
    readonly property var catalogEntry: BarRegistry.info(moduleId)
    readonly property var battery: ShellState.system.battery || {}
    readonly property var player: ShellState.demo ? null : Mpris.players.values.find(p => p.isPlaying) || Mpris.players.values[0] || null
    readonly property bool available: moduleId === "launchpad" ? ShellState.preferences.launchpadEnabled !== false : moduleId === "privacy" ? ShellState.preferences.privacyIndicators !== false && PrivacyState.indicators.length > 0 : moduleId === "activity" ? ShellState.preferences.activityEnabled !== false : moduleId === "tray" ? !ShellState.demo && SystemTray.items.values.length > 0
                                   : moduleId === "battery" ? battery.available === true
                                   : moduleId === "media" ? player !== null : true
    active: available && catalogEntry.enabled !== false
    visible: active
    width: available && item ? (item as Item).implicitWidth : 0
    height: 30
    y: parent ? (parent.height - height) / 2 : 0
    sourceComponent: catalogEntry.entry ? catalogComponent : moduleId === "privacy" ? privacyComponent : (moduleId === "activity" || moduleId === "windowTitle" && ShellState.preferences.activityEnabled !== false) ? activityComponent : moduleId === "workspaces" ? workspaceComponent : moduleId === "windowTitle" ? titleComponent
                   : ["launchpad", "launcher", "overview", "tray", "notifications", "settings", "power", "desktop"].includes(moduleId) ? actionComponent : statusComponent
    ModuleGestures { anchors.fill: parent; moduleId: root.moduleId; screenInfo: root.screenInfo }
    Component {
        id: catalogComponent
        Loader {
            source: FeatureCatalog.url(root.catalogEntry.entry)
            onLoaded: {
                for (const key of ["screenInfo", "windowInfo", "compact", "titleBudget"])
                    if (key in item) item[key] = Qt.binding(() => root[key]);
            }
        }
    }
    Component { id: privacyComponent; PrivacyIndicator { function primaryAction() { return BarGestures.perform(root.moduleId, "left", root.screenInfo); } } }
    Component {
        id: activityComponent
        ActivityButton { screenInfo: root.screenInfo; windowInfo: root.windowInfo; budget: root.titleBudget; function primaryAction() { return BarGestures.perform(root.moduleId, "left", root.screenInfo); } }
    }
    Component {
        id: actionComponent
        ActionBarButton { moduleId: root.moduleId; screenInfo: root.screenInfo; windowInfo: root.windowInfo }
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
                        // This nested viewport has no vertical overdraw; retain width/radius motion.
                        scale: 1
                        leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0; hoverEnabled: true
                        Behavior on width { MotionAnimation {} }
                        Accessible.name: "Workspace " + (modelData.name || modelData.idx)
                        selected: modelData.is_focused
                        selectionColor: Theme.workspaceActive
                        palette.buttonText: modelData.is_focused ? Theme.workspaceText : Theme.barMuted
                        background: Rectangle {
                            radius: workspace.modelData.is_focused ? 12 : 15
                            color: workspace.modelData.is_focused ? Theme.workspaceActive : workspace.hovered ? Theme.barHover : "transparent"
                            border.width: workspace.visualFocus ? 2 : 0; border.color: Theme.text
                            Behavior on color { ColorAnimation { duration: Theme.animationDuration } }
                            Behavior on radius { MotionAnimation {} }
                        }
                        contentItem: LabelText {
                            text: workspace.modelData.name || workspace.modelData.idx
                            color: workspace.palette.buttonText
                            font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                        }
                        onClicked: if (!BarGestures.perform(root.moduleId, "left", root.screenInfo)) ShellState.run("workspace", {id: modelData.id})
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
            TapHandler { onTapped: BarGestures.perform(root.moduleId, "left", root.screenInfo) }
            TextMetrics { id: titleMetrics; text: titleText.text; font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight }
            LabelText {
                id: titleText
                anchors.fill: parent; leftPadding: 8; rightPadding: 8
                text: ShellState.niri.available ? ShellState.focusedTitle : ShellState.demo ? ShellState.shellName : "niri unavailable"
                color: Theme.barMuted; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight
            }
        }
    }

    Component {
        id: statusComponent
        LiquidButton {
            id: statusButton
            readonly property date now: clock.date
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
            onClicked: if (!BarGestures.perform(root.moduleId, "left", root.screenInfo)) ShellState.togglePanel(root.moduleId === "network" ? "wifi" : "control", root.screenInfo)
            background: Rectangle { radius: 15; color: statusButton.hovered || ShellState.controlOpen ? Theme.barHover : "transparent"; border.width: statusButton.visualFocus ? 2 : 0; border.color: Theme.accent }
            LabelText { id: captionMeasure; visible: false; text: statusButton.caption; font: statusText.font }
            contentItem: Item {
                Row {
                    id: content
                    anchors.centerIn: parent; spacing: 6
                    ShellIcon { visible: root.moduleId !== "clock"; name: BarRegistry.info(root.moduleId).icon; color: root.moduleId === "battery" && root.battery.percent < 20 ? Theme.red : Theme.barMuted; width: 18; height: 18; anchors.verticalCenter: parent.verticalCenter }
                    LabelText { id: statusText; text: statusButton.caption; color: Theme.barText; width: Math.max(0, statusButton.width - (root.moduleId === "clock" ? 24 : 48)); elide: Text.ElideRight; font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; font.weight: Theme.barFontWeight; anchors.verticalCenter: parent.verticalCenter }
                }
            }
            SystemClock { id: clock; precision: SystemClock.Minutes; enabled: root.moduleId === "clock" }
        }
    }
}
