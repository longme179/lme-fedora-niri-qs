import QtQuick
import "../components"
import "../services"
import "../theme"

IconButton {
    id: root
    required property string moduleId
    property var screenInfo: null
    property var windowInfo: null
    objectName: "barAction-" + moduleId
    implicitWidth: 30; implicitHeight: 30
    iconName: moduleId === "notifications" ? (Notifications.dnd ? "bell-off" : "bell") : BarRegistry.info(moduleId).icon
    tooltip: ["overview", "launcher"].includes(moduleId) ? "" : BarRegistry.info(moduleId).title
    Accessible.name: BarRegistry.info(moduleId).title
    active: !["overview", "desktop", "settings"].includes(moduleId) && ShellState.isPanelOpen(moduleId)
    onClicked: {
        if (BarGestures.perform(moduleId, "left", screenInfo)) return;
        if (moduleId === "desktop") DesktopState.toggleEdit();
        else if (moduleId === "overview") ShellState.nativeOverview();
        else {
            if (moduleId === "tray") {
                const position = root.mapToItem(null, root.width, 0);
                ShellState.trayAnchorX = position.x + (windowInfo ? Theme.barSideMargin : 0);
            }
            ShellState.togglePanel(moduleId, screenInfo);
        }
    }
    Rectangle { visible: root.moduleId === "notifications" && Notifications.unreadCount > 0; width: 6; height: 6; radius: 3; color: Theme.pink; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 4 }
}
