import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"
ColumnLayout {
    spacing: 20
    SettingsCard {
        title: "LME Shell"
        description: "Fedora + niri · Quickshell and Qt Quick"
        LabelText { text: "Liquid glass meets Material 3 Expressive. Dracula Pro inspired colors, Roboto typography and a desktop you can arrange yourself."; Layout.fillWidth: true; wrapMode: Text.Wrap }
        LabelText { text: "Inspired by end-4/dots-hyprland and snowarch/iNiR. The settings registry, modular bar and Material treatment are implemented for this shell."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
        LiquidButton { text: "Project on GitHub ↗"; onClicked: Qt.openUrlExternally("https://github.com/longme179/lme-fedora-niri-qs") }
    }
    SettingsCard {
        title: "Open source"
        description: "GPL-3.0-or-later. No proprietary Dracula Pro assets are bundled."
        LabelText { text: "See README.md, requirements-fedora.txt and docs/INSTALL.md in the checkout for packages and installation. docs/INIR_PORT.md describes the reference features and their scope."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
}
