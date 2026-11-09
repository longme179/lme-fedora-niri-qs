// Role: NotificationsFeature.qml (notifications layer, fan-in 2).
// Panel/feature UI; dispatches backend actions via ShellState.run(action,payload) where applicable.
import QtQuick
import Quickshell
import "../services"

Scope {
    Component.onCompleted: Notifications.start()
    NotificationToasts { preview: Quickshell.env("LME_SHELL_PREVIEW") === "1" }
}
