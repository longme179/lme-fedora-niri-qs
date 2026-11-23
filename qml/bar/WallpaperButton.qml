// Role: WallpaperButton.qml (wallpaper layer, fan-in 1).
// Bar surface item; advances the wallpaper playlist via the wallpaperNext action.
import QtQuick
import "../components"
import "../services"
import "../theme"

IconButton {
    id: root
    objectName: "barAction-wallpaper"
    property var screenInfo: null
    implicitWidth: 30
    implicitHeight: 30
    iconName: BarRegistry.info("wallpaper").icon
    tooltip: BarRegistry.info("wallpaper").title
    Accessible.name: BarRegistry.info("wallpaper").title
    enabled: (ShellState.preferences.wallpaperPlaylist || []).length > 0
        && !ShellState.pendingActions.wallpaperNext
    onClicked: ShellState.run("wallpaperNext", {output: ShellState.preferences.wallpaperPlaylistOutput || ""})
}
