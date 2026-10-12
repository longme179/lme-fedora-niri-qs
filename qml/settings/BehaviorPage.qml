import QtQuick
import QtQuick.Layouts
import Quickshell
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    spacing: 20
    SettingsCard {
        title: "Privacy indicators"
        description: "PipeWire capture activity and niri screen casts. Direct V4L2 camera access outside PipeWire is not detected."
        PreferenceSwitch { title: "Capture indicators"; detail: "Show active microphone, camera and screen sharing"; preference: "privacyIndicators" }
        PreferenceSwitch { title: "Silence popups while sharing"; detail: "Automatic suppression preserves your manual DND setting"; preference: "dndWhileSharing" }
    }
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
        title: "Settings export and restore"
        description: "Portable presets exclude tasks, location, device IDs and file paths. Private backups include all settings, but not clipboard, notifications or notes. Import validates every field and backs up current settings first."
        ExpressiveField { id: transfer; Layout.fillWidth: true; text: Quickshell.env("HOME") + "/lme-preset.json"; placeholderText: "Absolute JSON file path"; Accessible.name: "Settings transfer path" }
        Flow {
            Layout.fillWidth: true; spacing: 8
            LiquidButton { text: "Export preset"; enabled: !ShellState.demo; onClicked: ShellState.run("settingsExport",{path:transfer.text,kind:"preset"}) }
            LiquidButton { text: "Export private backup"; enabled: !ShellState.demo; onClicked: ShellState.run("settingsExport",{path:transfer.text,kind:"backup"}) }
            LiquidButton { text: "Import and back up current"; enabled: !ShellState.demo; onClicked: ShellState.run("settingsImport",{path:transfer.text}) }
        }
        LabelText { text: "Exports refuse to replace existing files. Choose a new filename. To propose factory defaults, send only the portable preset JSON."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
    SettingsCard {
        title: "Made for your session"
        description: "The settings app and shell share preferences. Changes are saved automatically and appear in the running shell."
        LabelText { text: "Use Super+Comma or the top bar settings button to open this window. You can also start it from your application launcher."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
}
