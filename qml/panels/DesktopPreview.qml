import QtQuick
import QtQuick.Layouts
import Quickshell
import "../services"
import "../theme"
import "../components"

Item {
    id: root
    property string initialPanel: Quickshell.env("LME_SHELL_PREVIEW_PANEL") || "control"
    Component.onCompleted: ShellState.togglePanel(initialPanel)
    Image { anchors.fill: parent; source: "../../assets/wallpapers/liquid-dracula.png"; fillMode: Image.PreserveAspectCrop }
    Bar { x: 12; y: 10; width: parent.width - 24; height: 46 }
    Column {
        x: 110; y: 240
        spacing: 18
        LabelText { text: "LME"; font.pixelSize: 14; font.letterSpacing: 12; color: Theme.purple }
        LabelText { text: "A little less noise.\nA little more space."; font.pixelSize: 59; font.weight: Font.Light; lineHeight: 1.12 }
        LabelText { text: "LIQUID DESKTOP  /  FEDORA + NIRI"; font.pixelSize: 12; font.letterSpacing: 3; color: Theme.muted }
    }
    GlassPanel {
        x: 112; y: 580; width: 490; height: 112
        radius: 20
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 24; spacing: 9
            LabelText { text: "DEMO SESSION"; color: Theme.cyan; font.pixelSize: 10; font.letterSpacing: 2 }
            LabelText { text: "Sample data · System actions disabled"; font.pixelSize: 16; font.weight: Font.DemiBold }
            LabelText { text: "The panels shown here are the actual QML components."; font.pixelSize: 12; color: Theme.muted }
        }
    }
    Dock { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 14 }
    Loader {
        id: panelLoader
        active: ShellState.panelOpen
        sourceComponent: ShellState.launcherOpen ? launcher : ShellState.controlOpen ? control
                         : ShellState.notificationsOpen ? notifications : ShellState.settingsOpen ? settings : power
        width: item ? item.implicitWidth : 400; height: item ? item.implicitHeight : 600
        x: ShellState.launcherOpen || ShellState.powerOpen ? (root.width - width) / 2 : root.width - width - 14
        y: ShellState.launcherOpen || ShellState.powerOpen ? (root.height - height) / 2 : 70
        onLoaded: item.forceActiveFocus()
    }
    Component { id: launcher; Launcher {} }
    Component { id: control; ControlCenter {} }
    Component { id: notifications; NotificationCenter {} }
    Component { id: settings; SettingsPanel {} }
    Component { id: power; PowerMenu {} }
}
