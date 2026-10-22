import QtQuick
import QtQuick.Layouts
import "../panels"
import "../components"
import "../services"
ColumnLayout {
    id:root
    signal wallpaperRequested()
    signal navigateRequested(string pageId)
    spacing:20
    GowallSettings { Layout.fillWidth:true }
    SettingsCard {
        title:"Wallpaper engine"
        description:"Awww transition, scaling and display controls are shared with Wallpaper settings."
        LiquidButton { text:"Open awww controls"; enabled:ShellState.settingsPageAvailable("wallpaper"); onClicked:{ root.wallpaperRequested(); root.navigateRequested("wallpaper"); } }
    }
    SettingsCard {
        title:"Launchpad"
        description:"Save named commands and Bash scripts. Find them in the launcher, or add the Launchpad module in Top bar."
        PreferenceSwitch { title:"Launchpad"; detail:"Show your commands in the launcher and optional top bar module."; preference:"launchpadEnabled" }
        LaunchpadEditor { Layout.fillWidth:true }
    }
}
