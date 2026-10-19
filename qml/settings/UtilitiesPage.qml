import QtQuick
import QtQuick.Layouts
import "../panels"
ColumnLayout {
    spacing:20
    SettingsCard {
        title:"Launchpad"
        description:"Save named commands and Bash scripts. Find them in the launcher, or add the Launchpad module in Top bar."
        PreferenceSwitch { title:"Launchpad"; detail:"Show your commands in the launcher and optional top bar module."; preference:"launchpadEnabled" }
        LaunchpadEditor { Layout.fillWidth:true }
    }
}
