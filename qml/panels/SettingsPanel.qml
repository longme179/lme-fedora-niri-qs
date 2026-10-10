import QtQuick
import "../services"
import "../settings"
SettingsView {
    page: ShellState.settingsPage
    implicitWidth: 1060
    implicitHeight: 780
    onCloseRequested: ShellState.closePanels()
}
