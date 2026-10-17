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
        PreferenceSwitch { title: "Floating wallpaper shapes"; detail: "Always drift while enabled, with or without media. Turn off to remove all wallpaper shapes. The global Animations switch pauses motion."; preference: "desktopShapes" }
        Repeater {
            model: [{key:"desktopShapeCount",title:"Number of shapes",min:1,max:12,step:1,fallback:4,unit:""},
                {key:"desktopShapeScale",title:"Size",min:.5,max:2,step:.1,fallback:1,unit:"×"},
                {key:"desktopShapeOpacity",title:"Opacity",min:.02,max:.6,step:.01,fallback:.14,unit:"%"},
                {key:"desktopShapeSpeed",title:"Motion speed",min:.1,max:3,step:.1,fallback:1,unit:"×"}]
            delegate: ColumnLayout {
                id: option; required property var modelData
                Layout.fillWidth: true; spacing: 6
                enabled: ShellState.preferences.desktopShapes === true
                LabelText {
                    Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold
                    text: option.modelData.title + " · " + (option.modelData.unit === "%" ? Math.round(slider.value * 100) : option.modelData.unit ? slider.value.toFixed(1) : Math.round(slider.value)) + option.modelData.unit
                }
                LiquidSlider {
                    id: slider; objectName: option.modelData.key
                    Layout.fillWidth: true
                    from: option.modelData.min; to: option.modelData.max; stepSize: option.modelData.step
                    enabled: ShellState.backendReady && !ShellState.pendingActions.setting
                    Accessible.name: option.modelData.title
                    function save() { ShellState.run("setting", {key:option.modelData.key,value:Math.round(value * 100) / 100}); }
                    onMoved: if (!pressed) save()
                    onPressedChanged: if (!pressed) save()
                }
                Binding { target: slider; property: "value"; value: ShellState.preferences[option.modelData.key] ?? option.modelData.fallback; when: !slider.pressed; restoreMode: Binding.RestoreNone }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            enabled: ShellState.preferences.desktopShapes === true
            LabelText { text: "Shape style"; Layout.fillWidth: true }
            LiquidComboBox {
                objectName: "desktopShapeStyle"
                readonly property var styles: ["mixed", "flower", "circle", "square"]
                model: ["Mixed", "Flowers", "Circles", "Rounded squares"]
                currentIndex: styles.indexOf(ShellState.preferences.desktopShapeStyle || "mixed")
                enabled: ShellState.backendReady && !ShellState.pendingActions.setting
                Accessible.name: "Wallpaper shape style"
                onActivated: ShellState.run("setting", {key:"desktopShapeStyle",value:styles[currentIndex]})
            }
        }
        PreferenceSwitch { enabled: ShellState.preferences.desktopShapes === true; title: "Rotate shapes"; detail: "Gently spin each shape as it drifts"; preference: "desktopShapeRotation" }
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
