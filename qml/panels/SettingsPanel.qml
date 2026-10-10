pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../services"
import "../theme"
import "../components"

Item {
    id: root
    implicitWidth: 438
    implicitHeight: 660
    focus: true
    property bool terminalEditing: false
    readonly property var preferences: ShellState.preferences || {}
    Keys.onEscapePressed: ShellState.closePanels()

    FileDialog {
        id: wallpaperDialog
        title: "Choose a wallpaper"
        nameFilters: ["Images (*.png *.jpg *.jpeg *.webp)", "All files (*)"]
        fileMode: FileDialog.OpenFile
        onAccepted: {
            const url = selectedFile.toString();
            if (url.startsWith("file://")) ShellState.run("wallpaper", { path: decodeURIComponent(url.substring(7)) });
        }
    }

    component SectionLabel: Text {
        color: Theme.purple
        font.family: Theme.fontFamily
        font.pixelSize: 11
        font.weight: Font.DemiBold
        font.letterSpacing: 1.5
    }

    component SettingSwitch: RowLayout {
        id: settingSwitch
        required property string title
        required property string detail
        required property string preference
        Layout.fillWidth: true
        spacing: 12
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Text { text: settingSwitch.title; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14 }
            Text { Layout.fillWidth: true; text: settingSwitch.detail; wrapMode: Text.WordWrap; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 11 }
        }
        Switch {
            checked: root.preferences[settingSwitch.preference] !== false
            Accessible.name: settingSwitch.title
            onToggled: ShellState.run("setting", { key: settingSwitch.preference, value: checked })
            palette.highlight: Theme.purple
        }
    }

    GlassPanel { anchors.fill: parent }
    Flickable {
        anchors.fill: parent
        anchors.margins: 24
        contentWidth: width
        contentHeight: settingsContent.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        ColumnLayout {
            id: settingsContent
            width: parent.width
            spacing: 18
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 3
                    Text { text: "Make it yours"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 24; font.weight: Font.DemiBold }
                    Text { text: "LME Shell · Fedora + niri"; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                }
                Item { Layout.fillWidth: true }
                LiquidButton { text: "×"; Accessible.name: "Close settings"; onClicked: ShellState.closePanels(); palette.button: Theme.surface; palette.buttonText: Theme.text }
            }
            SectionLabel { text: "APPEARANCE" }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: paletteContent.implicitHeight + 28
                radius: Theme.smallRadius
                color: Theme.surface
                ColumnLayout {
                    id: paletteContent
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10
                    Text { text: "Dracula Pro inspired"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 15; font.weight: Font.DemiBold }
                    Text { Layout.fillWidth: true; text: "Choose an accent. Your licensed palette can be loaded from palette.json."; wrapMode: Text.WordWrap; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 12 }
                    RowLayout {
                        spacing: 10
                        Repeater {
                            model: [Theme.purple, Theme.pink, Theme.cyan, Theme.green, Theme.yellow]
                            delegate: LiquidButton {
                                id: accentButton
                                required property var modelData
                                Layout.preferredWidth: 40
                                Layout.preferredHeight: 40
                                Accessible.name: "Set accent " + modelData
                                onClicked: ShellState.run("setting", { key: "accent", value: modelData.toString() })
                                background: Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 3
                                    color: accentButton.modelData
                                    radius: width / 2
                                    border.width: Theme.accent.toString().toLowerCase() === accentButton.modelData.toString().toLowerCase() ? 3 : 0
                                    border.color: Theme.text
                                }
                            }
                        }
                    }
                }
            }
            SettingSwitch { title: "Gentle motion"; detail: "Short transitions for a calmer desktop"; preference: "animations" }
            SettingSwitch { title: "Auto-hide dock"; detail: "Reveal the dock at the bottom edge"; preference: "dockAutoHide" }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 7
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Panel opacity"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14 }
                    Item { Layout.fillWidth: true }
                    Text { text: Math.round(opacitySlider.value * 100) + "%"; color: Theme.muted; font.family: Theme.monoFamily; font.pixelSize: 12 }
                }
                LiquidSlider {
                    id: opacitySlider
                    Layout.fillWidth: true
                    from: 0.72
                    to: 1
                    stepSize: 0.01
                    Accessible.name: "Panel opacity"
                    palette.highlight: Theme.purple
                    onMoved: { if (!opacityDelay.running) opacityDelay.start(); }
                    onPressedChanged: {
                        if (!pressed && opacityDelay.running) {
                            opacityDelay.stop();
                            ShellState.run("setting", { key: "opacity", value: Math.round(value * 100) / 100 });
                        }
                    }
                }
                Binding { target: opacitySlider; property: "value"; value: root.preferences.opacity === undefined ? 0.90 : root.preferences.opacity; when: !opacitySlider.pressed; restoreMode: Binding.RestoreNone }
                Timer { id: opacityDelay; interval: 140; onTriggered: ShellState.run("setting", { key: "opacity", value: Math.round(opacitySlider.value * 100) / 100 }) }
            }
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: "Wallpaper"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14 }
                    Text { Layout.fillWidth: true; text: root.preferences.wallpaper ? root.preferences.wallpaper.split("/").pop() : "Choose an image you love"; textFormat: Text.PlainText; elide: Text.ElideMiddle; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 11 }
                }
                LiquidButton { text: "Choose…"; onClicked: wallpaperDialog.open(); palette.button: Theme.surface; palette.buttonText: Theme.purple }
            }
            SectionLabel { text: "APPLICATIONS" }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                Text { text: "Default terminal"; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: 14 }
                RowLayout {
                    Layout.fillWidth: true
                    TextField {
                        id: terminal
                        Layout.fillWidth: true
                        text: root.preferences.terminal || "kitty"
                        placeholderText: "kitty"
                        color: Theme.text
                        font.family: Theme.monoFamily
                        font.pixelSize: 13
                        selectByMouse: true
                        Accessible.name: "Default terminal executable"
                        background: Rectangle { color: Theme.surface; radius: Theme.smallRadius; border.width: 1; border.color: terminal.activeFocus ? Theme.purple : Theme.border }
                        onAccepted: saveTerminal.clicked()
                    }
                    LiquidButton {
                        id: saveTerminal
                        text: "Save"
                        enabled: terminal.text.trim().length > 0
                        onClicked: ShellState.run("setting", { key: "terminal", value: terminal.text.trim() })
                        palette.button: Theme.surface
                        palette.buttonText: Theme.purple
                    }
                }
                Text { Layout.fillWidth: true; text: "Executable name only, for example kitty or foot."; wrapMode: Text.WordWrap; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 11 }
            }
            Text { Layout.fillWidth: true; text: "Preferences are saved automatically. English is used throughout the shell."; wrapMode: Text.WordWrap; color: Theme.muted; font.family: Theme.fontFamily; font.pixelSize: 11 }
        }
    }
}
