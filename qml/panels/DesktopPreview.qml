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
    Bar { objectName: "desktopBar"; x: Theme.barSideMargin; y: Theme.barBottom ? parent.height - Theme.barTopMargin - height : Theme.barTopMargin; width: parent.width - Theme.barSideMargin * 2; height: Theme.barHeight }
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
            LabelText { text: "Sample data · System actions disabled"; font.pixelSize: 16; font.weight: Font.Bold }
            LabelText { text: "The panels shown here are the actual QML components."; font.pixelSize: 12; color: Theme.muted }
        }
    }
    ActivityIsland { z: 2 }
    SlideLoader {
        id: panelLoader
        objectName: "desktopPanel"
        readonly property Item panel: item as Item
        readonly property bool centered: ["launcher", "power", "overview", "settings", "clipboard"].includes(ShellState.panelKind)
        direction: centered ? "up" : ShellState.panelKind === "tray" ? Theme.barBottom ? "up" : "down" : "right"
        shown: ShellState.panelOpen && !ShellState.activityOpen
        content: ShellState.panelKind === "launcher" ? launcher : ShellState.panelKind === "control" ? control
                         : ShellState.panelKind === "notifications" ? notifications : ShellState.panelKind === "wifi" ? wifi : ShellState.panelKind === "settings" ? settings : ShellState.panelKind === "tray" ? tray : ShellState.panelKind === "overview" ? overview : ShellState.panelKind === "clipboard" ? clipboard : power
        width: panel ? Math.min(panel.implicitWidth, root.width - 32) : 400
        height: panel ? Math.min(panel.implicitHeight, root.height - Theme.panelTopMargin - 16) : 600
        x: centered ? (root.width - width) / 2 : root.width - width - 14
        y: centered ? (root.height - height) / 2 : Theme.barBottom ? root.height - height - Theme.panelTopMargin : Theme.panelTopMargin
    }
    Component { id: launcher; Launcher {} }
    Component { id: control; ControlCenter {} }
    Component { id: notifications; NotificationCenter {} }
    Component { id: settings; SettingsPanel {} }
    Component { id: power; PowerMenu {} }
    Component { id: tray; TrayMenu {} }
    Component { id: overview; Overview {} }
    Component { id: clipboard; ClipboardPanel {} }
    Component { id: wifi; WifiPanel {} }
}
