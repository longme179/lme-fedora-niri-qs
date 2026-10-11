import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    id: root
    spacing: 20
    SettingsCard {
        title: "Appearance profiles"
        description: "Save accent, opacity, density and motion together. Dracula is your built-in default."
        RowLayout {
            Layout.fillWidth: true
            LiquidComboBox { id: profiles; Layout.fillWidth: true; model: (ShellState.preferences.appearanceProfiles || []).map(p => p.name); Accessible.name: "Appearance profile" }
            LiquidButton { text: "Apply"; enabled: profiles.currentIndex >= 0 && ShellState.backendReady; onClicked: ShellState.run("appearanceApply", {name: profiles.currentText}) }
            LiquidButton { text: "Delete"; enabled: profiles.currentText !== "Dracula" && profiles.currentIndex >= 0; onClicked: ShellState.run("appearanceDelete", {name: profiles.currentText}) }
        }
        RowLayout {
            Layout.fillWidth: true
            ExpressiveField { id: profileName; objectName: "appearanceProfileName"; Layout.fillWidth: true; placeholderText: "New profile name"; maximumLength: 40; Accessible.name: "Profile name"; onAccepted: if (text.trim()) ShellState.run("appearanceSave", {name: text.trim()}) }
            LiquidButton { text: "Save current"; enabled: profileName.text.trim().length > 0 && ShellState.backendReady; onClicked: ShellState.run("appearanceSave", {name: profileName.text.trim()}) }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Interface density"; Layout.fillWidth: true }
            LiquidComboBox { model: ["Comfortable", "Compact"]; currentIndex: Theme.compact ? 1 : 0; Accessible.name: "Interface density"; onActivated: ShellState.run("setting", {key: "density", value: currentIndex ? "compact" : "comfortable"}) }
        }
    }
    SettingsCard {
        title: "Material, through glass"
        description: "Expressive shapes and flat tonal surfaces, with the transparency of your Liquid desktop."
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Rectangle {
                Layout.preferredWidth: 64; Layout.preferredHeight: 64; radius: 24; color: Theme.primaryContainer
                ShellIcon { anchors.centerIn: parent; width: 28; height: 28; name: "settings"; color: Theme.accent }
            }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                LabelText { text: "Dracula Pro inspired"; font.weight: Font.Bold; font.pixelSize: 16 }
                LabelText { text: "Roboto · bold headings · no gradients"; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
        }
    }
    SettingsCard {
        title: "Accent color"
        description: "Your accent flows into selected controls and surface colors. A licensed palette can be loaded from palette.json."
        RowLayout {
            spacing: 12
            Repeater {
                model: [Theme.purple, Theme.pink, Theme.cyan, Theme.green, Theme.yellow]
                delegate: LiquidButton {
                    id: accentChoice
                    required property var modelData
                    Layout.preferredWidth: 48; Layout.preferredHeight: 48
                    Accessible.name: "Set accent " + modelData
                    enabled: ShellState.backendReady && !ShellState.pendingActions.setting
                    onClicked: ShellState.run("setting", {key: "accent", value: modelData.toString()})
                    background: Rectangle {
                        radius: 18; color: accentChoice.modelData
                        border.width: Theme.accent.toString().toLowerCase() === color.toString().toLowerCase() ? 3 : 0
                        border.color: Theme.text
                    }
                }
            }
        }
    }
    SettingsCard {
        title: "Glass and motion"
        PreferenceSwitch { title: "Gentle motion"; detail: "Smooth slide transitions and subtle shape changes"; preference: "animations" }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Panel opacity"; Layout.fillWidth: true }
            LabelText { text: Math.round(opacitySlider.value * 100) + "%"; color: Theme.accent; font.weight: Font.Bold }
        }
        LiquidSlider {
            id: opacitySlider
            Layout.fillWidth: true; from: 0.72; to: 1; stepSize: 0.01
            enabled: ShellState.backendReady
            Accessible.name: "Panel opacity"
            onPressedChanged: if (!pressed) ShellState.run("setting", {key: "opacity", value: Math.round(value * 100) / 100})
            onMoved: if (!pressed) ShellState.run("setting", {key: "opacity", value: Math.round(value * 100) / 100})
        }
        Binding { target: opacitySlider; property: "value"; value: ShellState.preferences.opacity || 0.90; when: !opacitySlider.pressed; restoreMode: Binding.RestoreNone }
        LabelText { text: "Transparency is drawn by the shell. Background blur depends on your compositor."; color: Theme.muted; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
}
