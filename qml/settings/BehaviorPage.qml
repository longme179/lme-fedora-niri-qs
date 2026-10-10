import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    spacing: 20
    SettingsCard {
        title: "Default terminal"
        description: "Executable name only, for example kitty or foot."
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ExpressiveField {
                id: terminal
                Layout.fillWidth: true
                text: ShellState.preferences.terminal || "kitty"
                placeholderText: "kitty"
                Accessible.name: "Default terminal executable"
                onAccepted: if (save.enabled) save.clicked()
            }
            LiquidButton {
                id: save
                text: "Save"
                enabled: terminal.text.trim().length > 0 && ShellState.backendReady && !ShellState.pendingActions.setting
                onClicked: ShellState.run("setting", {key: "terminal", value: terminal.text.trim()})
            }
        }
    }
    SettingsCard {
        title: "Made for your session"
        description: "The settings app and shell share preferences. Changes are saved automatically and appear in the running shell."
        LabelText { text: "Use Super+Comma or the top bar settings button to open this window. You can also start it from your application launcher."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
}
