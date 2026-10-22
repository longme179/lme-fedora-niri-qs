import QtQuick
import Quickshell
import "../services"

Scope {
    Component.onCompleted: Notifications.start()
    NotificationToasts { preview: Quickshell.env("LME_SHELL_PREVIEW") === "1" }
}
