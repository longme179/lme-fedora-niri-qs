pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import "../components"
import "../services"

ColumnLayout {
    id: root; spacing: 20
    readonly property var outputs: ["primary",...Quickshell.screens.map(screen=>screen.name)]
    SettingsCard {
        title: "Floating wallpaper shapes"
        description: "Material shapes drift above your wallpaper and below application windows on each display. They use your theme colors and let clicks pass through."
        PreferenceSwitch { title: "Floating media shapes"; detail: "Show while a media player is connected; pause motion when playback stops or animations are disabled. Independent of desktop widgets and media-card shapes."; preference: "desktopShapes" }
    }
    SettingsCard {
        title: "Desktop widgets"
        description: "Place clock, notes and media on your desktop. Edit mode brings widgets above apps while arranging them; Done returns them below apps. Notes share your existing Quick notes buffer."
        PreferenceSwitch { title: "Enable desktop widgets"; detail: "Keep widgets below application windows outside Edit mode"; preference: "desktopEnabled" }
        RowLayout {
            Layout.fillWidth: true
            LiquidButton { text: "Edit on desktop"; enabled: DesktopState.enabled; onClicked: DesktopState.toggleEdit() }
            Item { Layout.fillWidth: true }
        }
        Flow {
            Layout.fillWidth: true; spacing: 8
            Repeater { model: ["clock","notes","media"]; delegate: LiquidButton { required property string modelData; text: "Add " + modelData; enabled: Object.keys(DesktopState.widgets).length<12; onClicked: DesktopState.add(modelData) } }
        }
    }
    Repeater {
        model: Object.keys(DesktopState.widgets)
        delegate: SettingsCard {
            id: entry; required property string modelData
            readonly property var record: DesktopState.widgets[modelData]
            title: record.type.charAt(0).toUpperCase()+record.type.slice(1)
            description: modelData
            RowLayout {
                Layout.fillWidth: true
                ExpressiveSwitch { text: "Visible"; checked: entry.record.enabled; onToggled: DesktopState.patch(entry.modelData,{enabled:checked}) }
                ExpressiveSwitch { text: "Interactive"; checked: entry.record.interactive; onToggled: DesktopState.patch(entry.modelData,{interactive:checked}) }
            }
            LiquidComboBox {
                Layout.fillWidth: true
                readonly property var choices: [...new Set([...root.outputs,entry.record.output])]
                model: choices.map(name=>name==="primary" ? "Primary display" : name)
                currentIndex: choices.indexOf(entry.record.output)
                Accessible.name: "Widget display"
                onActivated: DesktopState.patch(entry.modelData,{output:choices[currentIndex]})
            }
            LiquidButton { text: "Remove widget"; onClicked: DesktopState.patch(entry.modelData,"") }
        }
    }
}
