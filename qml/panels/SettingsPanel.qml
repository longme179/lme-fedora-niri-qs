// Role: SettingsPanel.qml (host layer, fan-in 3).
// Panel/feature UI; dispatches backend actions via ShellState.run(action,payload) where applicable.
import QtQuick
import "../services"
import "../settings"
SettingsView {
    page: ShellState.settingsPage
    implicitWidth: 1060
    implicitHeight: 780
    onCloseRequested: ShellState.closePanels()
}
