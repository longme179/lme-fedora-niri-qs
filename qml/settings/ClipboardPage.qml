import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    spacing: 20
    SettingsCard {
        title: "Your clipboard, within reach"
        description: "Open history with Super+V or add Clipboard to your top bar. Search, pin and copy text or images."
        PreferenceSwitch { title: "Capture clipboard history"; detail: "Save new clipboard selections locally while the shell is running."; preference: "clipboardEnabled" }
        PreferenceSwitch { title: "Include images"; detail: "Capture PNG, JPEG, WebP, GIF and BMP selections up to 8 MB."; preference: "clipboardImages" }
        RowLayout {
            Layout.fillWidth: true; spacing: 16
            LabelText { text: "History size"; Layout.fillWidth: true; font.weight: Font.Medium }
            LiquidComboBox {
                model: ["20 items", "50 items", "100 items", "200 items", "500 items"]
                readonly property var limits: [20, 50, 100, 200, 500]
                currentIndex: limits.indexOf(ShellState.preferences.clipboardLimit || 100)
                enabled: ShellState.backendReady && !ShellState.pendingActions.setting
                Accessible.name: "Clipboard history size"
                onActivated: ShellState.run("setting", {key: "clipboardLimit", value: limits[currentIndex]})
            }
        }
    }
    SettingsCard {
        title: "Local and bounded"
        description: "History survives shell restarts. Pause capture or clear history from the Clipboard panel."
        LabelText { text: "Up to 20 pinned items are kept during automatic cleanup. Unpinned items are removed oldest first, with a 64 MB content budget. Text selections are limited to 1 MB. Clipboard contents stay in local storage."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
}
