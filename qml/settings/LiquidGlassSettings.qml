// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

SettingsCard {
    id: root
    objectName: "liquidGlassSettings"
    visible: Theme.liquidGlass
    title: "Liquid glass material"
    description: "These controls apply to glass backgrounds across the shell. Text stays white. Your Smoked palette and element overrides stay separate. Changes save automatically; Reset restores the original glass."
    property string error: ""
    function save(key, value) { ShellState.run("setting", {key:"liquidGlass", token:key, value:value}); }
    RowLayout {
        Layout.fillWidth: true; spacing: 10
        IconButton {
            objectName: "glassTintPicker"; tooltip: "Choose glass tint"
            contentItem: Item { Rectangle { anchors.centerIn: parent; width:24; height:24; radius:8; color:Theme.glassBase; border.width:1; border.color:Theme.border } }
            onClicked: { picker.initialColor = Theme.glassBase; picker.open(); }
        }
        LabelText { text:"Panel tint"; Layout.fillWidth:true; wrapMode:Text.Wrap; font.weight:Font.Bold }
        ExpressiveField {
            id: hex; objectName:"glassTint"; Layout.preferredWidth:132; maximumLength:9
            text: Theme.glass.tint || "#f0081420"; Accessible.name:"Glass tint; #RRGGBB or #AARRGGBB"
            function apply() {
                if (/^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(text)) { root.error=""; root.save("tint", text); }
                else root.error="Use #RRGGBB or #AARRGGBB (alpha first).";
            }
            onAccepted: apply()
        }
        LiquidButton { objectName:"glassTintApply"; text:"Apply"; enabled:ShellState.backendReady; onClicked:hex.apply() }
    }
    LabelText { objectName:"glassTintError"; visible:!!root.error; text:root.error; color:Theme.red; Layout.fillWidth:true; wrapMode:Text.Wrap }
    Connections { target:ShellState; function onPreferencesChanged() { if (!hex.activeFocus) hex.text=Theme.glass.tint || "#f0081420"; } }
    ColorPicker { id:picker; objectName:"glassColorPicker"; parent:Overlay.overlay; anchors.centerIn:parent; onChosen:color => { hex.text=color.toString(); root.error=""; root.save("tint", hex.text); } }
    Repeater {
        model: Object.keys(Theme.glassControls).filter(key => key !== "tint")
        delegate: ColumnLayout {
            id: row
            required property string modelData
            readonly property var control: Theme.glassControls[modelData]
            Layout.fillWidth:true; spacing:8
            LabelText {
                visible: row.modelData === "passes"; Layout.fillWidth:true; wrapMode:Text.Wrap; font.weight:Font.Bold
                text:"niri backdrop blur · compositor-wide"
            }
            LabelText {
                visible: row.modelData === "passes"; Layout.fillWidth:true; wrapMode:Text.Wrap; color:Theme.muted
                text:"Lens blur softens only refracted edges. True blur behind applications uses niri 26.04+. The two controls below apply only when you save the niri snippet; they affect every surface requesting blur, including Smoked mode. Higher values cost GPU time."
            }
            LabelText {
                Layout.fillWidth:true; wrapMode:Text.Wrap; font.weight:Font.Bold
                text: row.control.title + " · " + (row.modelData === "passes" ? Math.round(slider.value) : slider.value.toFixed(2))
            }
            LiquidSlider {
                id:slider; objectName:"glass-" + row.modelData
                Layout.fillWidth:true; from:row.control.min; to:row.control.max; stepSize:row.control.step
                enabled:ShellState.backendReady; Accessible.name:row.control.title
                function save() { root.save(row.modelData, Math.round(value * 100) / 100); }
                onMoved:if (!pressed) save()
                onPressedChanged:if (!pressed) save()
            }
            Binding { target:slider; property:"value"; value:Theme.glass[row.modelData] ?? row.control.default; when:!slider.pressed; restoreMode:Binding.RestoreNone }
        }
    }
    LabelText {
        Layout.fillWidth:true; wrapMode:Text.Wrap; color:Theme.muted
        text:'One-time setup: include "~/.config/lme-shell/liquid-blur.kdl" after popup-blur.kdl in your niri config. Use your XDG_CONFIG_HOME path if customized. Run niri validate. Later applications of the snippet reload automatically.'
    }
    RowLayout {
        Layout.fillWidth:true
        LiquidButton { objectName:"glassBlurApply"; text:"Save niri blur snippet"; enabled:ShellState.backendReady; onClicked:ShellState.run("glassBlurApply") }
        LiquidButton { objectName:"glassReset"; text:"Reset glass"; enabled:ShellState.backendReady; onClicked: { root.error=""; hex.focus=false; ShellState.run("setting", {key:"liquidGlass", value:{}}); } }
    }
    LabelText {
        Layout.fillWidth:true; wrapMode:Text.Wrap; color:Theme.muted
        text:"Feather softens the reflective rim; smearing stretches its refraction. These change the existing shader, without adding render layers. Brightness darkens the glass itself. Reset does not rewrite an already applied niri snippet; save it again to restore the default blur."
    }
}
