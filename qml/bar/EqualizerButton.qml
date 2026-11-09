// Role: EqualizerButton.qml (equalizer layer, fan-in 2).
// Bar surface item; opens/toggles panels or islands via ShellState/registries.
import QtQuick
import "../components"
import "../services"
import "../theme"

IconButton {
    id: root
    objectName: "barAction-equalizer"
    property var screenInfo: null
    implicitWidth: 30
    implicitHeight: 30
    iconName: BarRegistry.info("equalizer").icon
    tooltip: BarRegistry.info("equalizer").title
    Accessible.name: BarRegistry.info("equalizer").title
    active: ShellState.isPanelOpen("equalizer")
    onClicked: ShellState.togglePanel("equalizer", screenInfo)
}
