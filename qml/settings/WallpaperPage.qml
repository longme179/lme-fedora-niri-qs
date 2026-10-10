import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    spacing: 20
    FileDialog {
        id: chooser
        title: "Choose a wallpaper"
        nameFilters: ["Images (*.png *.jpg *.jpeg *.webp)", "All files (*)"]
        fileMode: FileDialog.OpenFile
        onAccepted: {
            const url = selectedFile.toString();
            if (url.startsWith("file://")) ShellState.run("wallpaper", {path: decodeURIComponent(url.substring(7))});
        }
    }
    SettingsCard {
        title: "Your backdrop"
        description: "Choose an image. The shell applies it with swww."
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 260; radius: 20; color: Theme.surfaceContainer; clip: true
            Image { anchors.fill: parent; source: ShellState.preferences.wallpaper ? "file://" + ShellState.preferences.wallpaper : "../../assets/wallpapers/liquid-dracula.png"; fillMode: Image.PreserveAspectCrop }
        }
        LabelText { text: ShellState.preferences.wallpaper || "Bundled Liquid wallpaper"; color: Theme.muted; Layout.fillWidth: true; elide: Text.ElideMiddle }
        LiquidButton { text: "Choose an image…"; enabled: ShellState.backendReady && !ShellState.pendingActions.wallpaper; onClicked: chooser.open() }
    }
}
