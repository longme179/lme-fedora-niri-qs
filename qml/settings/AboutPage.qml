import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"
import "../services"
ColumnLayout {
    spacing: 20
    Component.onCompleted: UpdateState.run("inspect")
    SettingsCard {
        objectName: "aboutShellName"
        title: ShellState.shellName
        description: "Fedora + niri · Quickshell and Qt Quick"
        LabelText { text: "Smoked glass meets Material 3 Expressive. Dracula Pro inspired colors, Roboto typography and a desktop you can arrange yourself."; Layout.fillWidth: true; wrapMode: Text.Wrap }
        LabelText { text: "Inspired by end-4/dots-hyprland and snowarch/iNiR. The settings registry, modular bar and Material treatment are implemented for this shell."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
        LabelText { text: "Based on iNiR by snowarch (https://github.com/snowarch/inir)"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
        LiquidButton { text: "Project on GitHub ↗"; onClicked: Qt.openUrlExternally("https://github.com/longme179/lme-fedora-niri-qs") }
    }
    SettingsCard {
        title: "Shell updates"
        description: "Update this Git checkout from origin/main. Your shell preferences stay separate."
        LabelText {
            objectName: "updateStatus"
            text: UpdateState.state.message
            Layout.fillWidth: true; wrapMode: Text.Wrap
            color: ["error", "blocked"].includes(UpdateState.state.stage) ? Theme.yellow : Theme.muted
        }
        LabelText {
            visible: !!UpdateState.state.current
            text: "Installed commit · " + (UpdateState.state.current || "").slice(0, 8)
            Layout.fillWidth: true; color: Theme.muted
        }
        RowLayout {
            Layout.fillWidth: true
            LiquidButton { objectName: "checkUpdates"; text: "Check for updates"; enabled: UpdateState.ready && !UpdateState.busy && !ShellState.demo; onClicked: UpdateState.run("check") }
            LiquidButton { objectName: "applyUpdate"; text: "Update shell"; enabled: !UpdateState.busy && UpdateState.state.canUpdate === true && !ShellState.demo; onClicked: UpdateState.run("update") }
        }
        LabelText { text: "Updates require a clean main branch and use fast-forward only. No reset, stash or package installation is performed. Restart the shell and Settings after updating."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
    SettingsCard {
        title: "Open source"
        description: "GPL-3.0-or-later, with retained upstream licenses and an AGPL-3.0-or-later Liquid renderer. No proprietary Dracula Pro assets are bundled."
        LabelText { text: "Optional Liquid glass adapts Serpantinum by Illia Miroshnichenko. Source, license and changes are recorded in THIRD_PARTY.md and third_party/Serpantinum-NOTICE."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
        LabelText { text: "See README.md, requirements-fedora.txt and docs/INSTALL.md in the checkout for packages and installation. docs/INIR_PORT.md describes the reference features and their scope."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
}
