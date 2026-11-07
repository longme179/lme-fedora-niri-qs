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
    description: "These controls apply to glass backgrounds across the shell. Text contrast is kept above 3:1 on bright backdrops by the contrast floor. Your Smoked palette and element overrides stay separate. Changes save automatically; Reset restores the original glass."
    property string error: ""
    readonly property bool blurSupported: (ShellState.snapshot.platform || {}).popupBlurSupported === true
    property string materialPreset: "Clear"
    readonly property var materialPresetValues: {
        "Clear": {tint:"#f0081420", opacity:0.65, blur:1, rim:1, edgeWidth:1, grain:0.004, passes:2, offset:3},
        "Frosted": {tint:"#f0182436", opacity:0.9, blur:3, rim:0.8, edgeWidth:0.5, grain:0.01, passes:1, offset:2},
        "Vivid": {tint:"#f00a1a28", opacity:0.55, blur:1.5, rim:1.6, edgeWidth:1.5, grain:0.002, passes:3, offset:4.5}
    }
    readonly property var materialPresetDesc: {
        "Clear": "Default crisp lens: tint 65%, blur 1, rim 1, grain 0.004, 2 blur passes.",
        "Frosted": "Budget matte: tint 90%, lens blur 3, thin edge, grain 0.01, 1 blur pass.",
        "Vivid": "Vivid refraction: tint 55%, rim 1.6, edge 1.5, minimal grain (0.002), 3 passes."
    }
    readonly property string blurStatusText: {
        if (!blurSupported) return "unsupported (niri < 26.04, detected " + ((ShellState.snapshot.platform || {}).niriVersion || "checking…") + ")";
        const applied = Theme.glass.appliedBlur || "";
        const selected = Theme.glass.blurPreset || "frosted";
        if (applied && applied === selected) return "applied (" + applied + ")";
        return "pending (save snippet)";
    }
    function save(key, value) { ShellState.run("setting", {key:"liquidGlass", token:key, value:value}); }
    function applyMaterialPreset(name) { materialPreset = name; const values = materialPresetValues[name]; for (const key in values) root.save(key, values[key]); }

    // Presets at the very top of the material card (starting points, not modes).
    ColumnLayout {
        Layout.fillWidth: true; spacing: 6
        LabelText { Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold; text: "Material presets" }
        LiquidComboBox {
            objectName: "glassMaterialPreset"; Layout.fillWidth: true; Accessible.name: "Material preset"
            model: ["Clear","Frosted","Vivid"]
            currentIndex: ["Clear","Frosted","Vivid"].indexOf(root.materialPreset)
            onActivated: root.applyMaterialPreset(model[currentIndex])
        }
        LabelText { objectName: "glassMaterialPresetDesc"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; text: root.materialPresetDesc[root.materialPreset] || "" }
        LabelText { Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12; text: "Clear — Default crisp lens: tint 65%, blur 1, rim 1, grain 0.004, 2 blur passes.  Frosted — Budget matte: tint 90%, lens blur 3, thin edge, grain 0.01, 1 blur pass.  Vivid — Vivid refraction: tint 55%, rim 1.6, edge 1.5, minimal grain, 3 passes. Presets are starting points; sliders stay editable." }
    }
    PreferenceSwitch { title: "Refractive selection"; detail: "A glass lens follows the selected tab or Settings page"; preference: "glassSelection" }
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

    ColumnLayout {
        Layout.fillWidth: true; spacing: 8
        LabelText { objectName: "glassLensHeader"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold; text: "Lens" }
        PreferenceSwitch { title: "Adaptive contrast"; detail: "Darken glass on bright backdrops, clear it on dark ones"; preference: "adaptiveContrast" }
        Repeater {
            model: ["blur","rim","edgeWidth","grain","opacity"]
            delegate: ColumnLayout {
                id: lens
                required property string modelData
                readonly property var control: Theme.glassControls[modelData] || ({})
                Layout.fillWidth: true; spacing: 8
                LabelText {
                    Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold
                    text: (lens.modelData === "opacity" ? "Panel tint opacity" : (lens.control.title || lens.modelData)) + " · " + slider.value.toFixed(lens.modelData === "grain" ? 3 : 2)
                }
                LiquidSlider {
                    id: slider; objectName: "glass-" + lens.modelData
                    Layout.fillWidth: true; from: lens.control.min ?? 0; to: lens.control.max ?? 1; stepSize: lens.control.step ?? 0.01
                    enabled: ShellState.backendReady; Accessible.name: lens.control.title || lens.modelData
                    function save() { const scale = lens.modelData === "grain" ? 1000 : 100; root.save(lens.modelData, Math.round(value * scale) / scale); }
                    onMoved: if (!pressed) save()
                    onPressedChanged: if (!pressed) save()
                }
                Binding { target: slider; property: "value"; value: Theme.glass[lens.modelData] ?? lens.control.default; when: !slider.pressed; restoreMode: Binding.RestoreNone }
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true; spacing: 8
        LabelText { objectName: "glassCompositorHeader"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold; text: "Compositor" }
        LabelText { objectName: "glassBlurStatus"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; text: "Compositor blur: " + root.blurStatusText }
        LiquidComboBox {
            objectName: "glassBlurPreset"; Layout.fillWidth: true; Accessible.name: "Backdrop blur preset"; visible: root.blurSupported
            model: ["Frosted (wallpaper only, default)","True backdrop (experimental)"]
            currentIndex: Theme.glass.blurPreset === "true" ? 1 : 0
            onActivated: root.save("blurPreset", currentIndex === 1 ? "true" : "frosted")
        }
        LabelText {
            visible: root.blurSupported; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
            text: "Frosted blurs only the wallpaper behind panels and is cheapest on the iGPU (default). True backdrop also blurs app windows — experimental and can dip during window animations. Save the snippet to apply a preset."
        }
        LabelText {
            visible: !root.blurSupported; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
            text: "Compositor blur needs niri 26.04+ (running: " + ((ShellState.snapshot.platform || {}).niriVersion || "checking…") + "). Lens blur, tint and the snapshot backdrop keep working without it."
        }
        LabelText {
            visible: root.blurSupported; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
            text: "Compositor-wide: the controls below apply only when you save the niri snippet; they affect every surface requesting blur, including Smoked mode. Higher values cost GPU time."
        }
        Repeater {
            model: root.blurSupported ? ["passes","offset"] : []
            delegate: ColumnLayout {
                id: comp
                required property string modelData
                readonly property var control: Theme.glassControls[modelData] || ({})
                Layout.fillWidth: true; spacing: 8
                LabelText {
                    Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold
                    text: (comp.control.title || comp.modelData) + " · " + (comp.modelData === "passes" ? Math.round(slider.value) : slider.value.toFixed(2))
                }
                LiquidSlider {
                    id: slider; objectName: "glass-" + comp.modelData
                    Layout.fillWidth: true; from: comp.control.min ?? 0; to: comp.control.max ?? 1; stepSize: comp.control.step ?? 1
                    enabled: ShellState.backendReady; Accessible.name: comp.control.title || comp.modelData
                    function save() { const scale = 100; root.save(comp.modelData, Math.round(value * scale) / scale); }
                    onMoved: if (!pressed) save()
                    onPressedChanged: if (!pressed) save()
                }
                Binding { target: slider; property: "value"; value: Theme.glass[comp.modelData] ?? comp.control.default; when: !slider.pressed; restoreMode: Binding.RestoreNone }
            }
        }
    }
    LabelText {
        Layout.fillWidth:true; wrapMode:Text.Wrap; color:Theme.muted
        text:'One-time setup: include "~/.config/lme-shell/liquid-blur.kdl" after popup-blur.kdl in your niri config. Use your XDG_CONFIG_HOME path if customized. Run niri validate. Later applications of the snippet reload automatically.'
    }
    RowLayout {
        Layout.fillWidth:true
        LiquidButton { objectName:"glassBlurApply"; visible:root.blurSupported; text:"Save niri blur snippet"; enabled:ShellState.backendReady; onClicked:ShellState.run("glassBlurApply", {preset:Theme.glass.blurPreset || "frosted"}) }
        LiquidButton { objectName:"glassReset"; text:"Reset glass"; enabled:ShellState.backendReady; onClicked: { root.error=""; hex.focus=false; ShellState.run("setting", {key:"liquidGlass", value:{}}); } }
    }
    LabelText {
        Layout.fillWidth:true; wrapMode:Text.Wrap; color:Theme.muted
        text:"Edge highlight and lens blur shape the hairline; edge width sets the bezel. While a preset is applied, panels gain a 1px glass-border hairline that masks rounded-corner aliasing; it clears when no preset is applied. Reset does not rewrite an already applied niri snippet; save it again to restore the default blur."
    }
}
