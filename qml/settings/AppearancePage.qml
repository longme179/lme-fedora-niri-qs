import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    id: root
    spacing: 20
    function refreshPlatform() {
        const version = (ShellState.snapshot.platform || {}).niriVersion;
        if (ShellState.backendReady && (!version || version === "Not checked")) ShellState.run("platformRefresh");
    }
    Component.onCompleted: root.refreshPlatform()
    Connections { target: ShellState; function onBackendReadyChanged() { root.refreshPlatform(); } }
    SettingsCard {
        visible: ShellState.batterySaverActive
        title: "Battery saver is on"
        description: "Opaque Material surfaces and reduced motion temporarily override your saved appearance. Turn off Battery saver in Behavior to restore Liquid glass, transparency and animations."
        LiquidButton { text: "Open Battery saver settings"; onClicked: ShellState.openSettingsPage("behavior") }
    }
    SettingsCard {
        title: "Surface style"
        description: "Liquid glass combines a frosted backdrop, refractive edges and white text. Your saved palette, accent, opacity and element colors stay unchanged; switch back to restore them."
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Liquid glass"; Layout.fillWidth: true; font.weight: Font.Medium }
            ExpressiveSwitch {
                objectName: "surfaceStyle"; Accessible.name: "Liquid glass"
                checked: Theme.liquidGlass
                enabled: ShellState.backendReady && !ShellState.batterySaverActive && !ShellState.pendingActions.setting
                onToggled: ShellState.run("setting", {key: "surfaceStyle", value: checked ? "liquid" : "smoked"})
            }
        }
        LabelText {
            visible: Theme.liquidGlass; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
            text: "Glass blurs only the area beneath each panel or popup on niri 26.04+. Full-screen popup blur and palette controls are paused. Fonts, layout, corners and motion still apply."
        }
    }
    LiquidGlassSettings {}
    SettingsCard {
        title: "Shell name"
        description: "Your display name in Settings, the bar's empty-window title and shell notifications."
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            ExpressiveField {
                id: shellName; objectName: "shellNameInput"
                Layout.fillWidth: true; maximumLength: 48
                text: ShellState.shellName; placeholderText: "LME Shell"
                Accessible.name: "Shell display name"
                onAccepted: if (saveName.enabled) saveName.clicked()
            }
            LiquidButton {
                id: saveName; objectName: "shellNameSave"; text: "Save"
                enabled: ShellState.backendReady && !ShellState.pendingActions.setting && !!shellName.text.trim() && shellName.text.trim() !== ShellState.shellName
                onClicked: ShellState.run("setting", {key: "shellName", value: shellName.text.trim()})
            }
            IconButton {
                objectName: "shellNameReset"; glyph: "↺"; tooltip: "Reset shell name"
                enabled: ShellState.backendReady && ShellState.shellName !== "LME Shell"
                onClicked: { shellName.text = "LME Shell"; ShellState.run("setting", {key: "shellName", value: "LME Shell"}); }
            }
        }
        Connections { target: ShellState; function onPreferencesChanged() { if (!shellName.activeFocus) shellName.text = ShellState.shellName; } }
    }
    SettingsCard {
        title: "Appearance profiles"
        description: "Save accent, opacity, density and motion together. Dracula is your built-in default."
        RowLayout {
            Layout.fillWidth: true; enabled: !Theme.liquidGlass
            LiquidComboBox { id: profiles; Layout.fillWidth: true; model: (ShellState.preferences.appearanceProfiles || []).map(p => p.name); Accessible.name: "Appearance profile" }
            LiquidButton { text: "Apply"; enabled: profiles.currentIndex >= 0 && ShellState.backendReady; onClicked: ShellState.run("appearanceApply", {name: profiles.currentText}) }
            LiquidButton { text: "Delete"; enabled: profiles.currentText !== "Dracula" && profiles.currentIndex >= 0; onClicked: ShellState.run("appearanceDelete", {name: profiles.currentText}) }
        }
        RowLayout {
            Layout.fillWidth: true; enabled: !Theme.liquidGlass
            ExpressiveField { id: profileName; objectName: "appearanceProfileName"; Layout.fillWidth: true; placeholderText: "New profile name"; maximumLength: 40; Accessible.name: "Profile name"; onAccepted: if (text.trim()) ShellState.run("appearanceSave", {name: text.trim()}) }
            LiquidButton { text: "Save current"; enabled: profileName.text.trim().length > 0 && ShellState.backendReady; onClicked: ShellState.run("appearanceSave", {name: profileName.text.trim()}) }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Interface density"; Layout.fillWidth: true }
            LiquidComboBox { model: ["Comfortable", "Compact"]; currentIndex: Theme.compact ? 1 : 0; Accessible.name: "Interface density"; onActivated: ShellState.run("setting", {key: "density", value: currentIndex ? "compact" : "comfortable"}) }
        }
    }
    SettingsCard {
        title: "Color palettes"
        enabled: !Theme.liquidGlass
        description: (Math.max(0, Theme.paletteCatalog.length - 1)) + " Gowall palettes plus LME Dracula. Preview dark or light palettes without changing your desktop, then apply. Save the result as an Appearance profile to switch quickly."
        PalettePicker {}
    }
    SettingsCard {
        title: "Material, through glass"
        description: "Expressive shapes and flat tonal surfaces, with smoked glass transparency."
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Rectangle {
                Layout.preferredWidth: 64; Layout.preferredHeight: 64; radius: 24; color: Theme.primaryContainer
                ShellIcon { anchors.centerIn: parent; width: 28; height: 28; name: "settings"; color: Theme.accent }
            }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                LabelText { text: ShellState.preferences.paletteSource === "preset" ? Theme.activePreset.name || "Color palette" : ShellState.preferences.paletteSource === "wallpaper" ? "Material from wallpaper" : "Dracula Pro inspired"; font.weight: Font.Bold; font.pixelSize: 16 }
                LabelText { text: "Roboto · bold headings · no gradients"; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
        }
    }
    SettingsCard {
        title: "Accent color"
        enabled: !Theme.liquidGlass
        description: "Your accent flows into selected controls and surface colors. A licensed palette can be loaded from palette.json."
        RowLayout {
            spacing: 12
            Repeater {
                model: [Theme.purple, Theme.pink, Theme.cyan, Theme.green, Theme.yellow]
                delegate: LiquidButton {
                    id: accentChoice
                    glassBackground: false
                    required property var modelData
                    Layout.preferredWidth: 48; Layout.preferredHeight: 48
                    Accessible.name: "Set accent " + modelData
                    enabled: ShellState.backendReady && !ShellState.pendingActions.setting
                    onClicked: ShellState.run("setting", {key: "accent", value: modelData.toString()})
                    background: Rectangle {
                        radius: 18; color: accentChoice.modelData
                        border.width: Theme.accent.toString().toLowerCase() === color.toString().toLowerCase() ? 3 : 0
                        border.color: Theme.text
                    }
                }
            }
        }
    }
    SettingsCard {
        title: "Activity Island size"
        description: "Set limits for the bar pill and its expanded popup. The available screen and bar space always take priority. Height 0 fits the content to the screen; overflow scrolls inside the popup."
        Repeater {
            model: [{key:"activityCompactMaxWidth",title:"Maximum bar pill width",min:120,max:1200,step:10},
                {key:"activityPopupMaxWidth",title:"Maximum popup width",min:400,max:1600,step:20},
                {key:"activityPopupMaxHeight",title:"Maximum popup height",min:0,max:2160,step:40}]
            delegate: ColumnLayout {
                id: limit; required property var modelData
                Layout.fillWidth: true; spacing: 8
                LabelText { Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold; text: limit.modelData.title + " · " + (dimension.value === 0 ? "Auto" : Math.round(dimension.value) + " px") }
                LiquidSlider {
                    id: dimension; objectName: limit.modelData.key
                    Layout.fillWidth: true; from: limit.modelData.min; to: limit.modelData.max; stepSize: limit.modelData.step
                    enabled: ShellState.backendReady
                    Accessible.name: limit.modelData.title
                    function save() {
                        const size = Math.round(value);
                        ShellState.run("setting", {key:limit.modelData.key, value:limit.modelData.key === "activityPopupMaxHeight" && size > 0 ? Math.max(320,size) : size});
                    }
                    onMoved: if (!pressed) save()
                    onPressedChanged: if (!pressed) save()
                }
                Binding { target: dimension; property: "value"; value: ShellState.preferences[limit.modelData.key] ?? Theme[limit.modelData.key]; when: !dimension.pressed; restoreMode: Binding.RestoreNone }
            }
        }
    }
    SettingsCard {
        title: "Glass and motion"
        enabled: !ShellState.batterySaverActive
        PreferenceSwitch {
            title: "Blur behind popups"; preference: "popupBlur"; enabled: !Theme.liquidGlass
            detail: Theme.liquidGlass ? "Full-screen blur is paused; each glass panel has its own local blur. Your saved preference applies in Smoked mode."
                : "Full-screen compositor blur for Island and shell panels. Requires niri 26.04+ and the popup-blur config fragment."
        }
        PreferenceSwitch { title: "Blur behind the bar"; detail: "Blur through the bar's glass, following each island and its corners. Uses the same niri 26.04+ config fragment."; preference: "barBlur" }
        LabelText { text: "Compositor: "+((ShellState.snapshot.platform || {}).niriVersion || "Checking…"); color: Theme.muted; font.pixelSize: 12 }
        PreferenceSwitch { title: "Animations"; detail: "Disable to remove spatial motion and press deformation"; preference: "animations" }
        PreferenceSwitch { title: "Geometric shape morph"; detail: "Icon buttons morph rounded polygons on hover and press"; preference: "shapeMorph" }
        PreferenceSwitch { title: "Moving tab indicator"; detail: "Stretch the selected tab between choices"; preference: "animatedTabs" }
        PreferenceSwitch { title: "Stable media cards"; detail: "Keep artwork and labels through brief incomplete metadata updates"; preference: "mediaStability" }
        PreferenceSwitch { title: "Extended media controls"; detail: "Seek, shuffle and repeat when supported by the selected player"; preference: "mediaControls" }
        PreferenceSwitch { title: "Moving media shapes"; detail: "Subtle Material shapes while the media card is visible and playing"; preference: "mediaShapes" }
        PreferenceSwitch { title: "Wavy media progress"; detail: "Animate media timelines in Activity Island and Control Center while playing"; preference: "mediaWave" }
        PreferenceSwitch { title: "Pointer-origin ripple"; detail: "Press waves start at the pointer and clip to rounded corners"; preference: "pointerRipple" }
        PreferenceSwitch { title: "Spring motion"; detail: "Keep momentum through hover, toggles, tabs and popup reversals"; preference: "springMotion" }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Motion preset"; Layout.fillWidth: true }
            LiquidComboBox {
                objectName: "motionPreset"; model: ["Smooth", "Expressive", "Jelly", "Jelly-v2"]
                currentIndex: ["smooth", "expressive", "jelly", "jelly-v2"].indexOf(Theme.motionPreset)
                Accessible.name: "Motion preset"
                onActivated: ShellState.run("setting", {key: "motionPreset", value: ["smooth", "expressive", "jelly", "jelly-v2"][currentIndex]})
            }
        }
        LabelText { text: "Speed · " + Theme.motionSpeed.toFixed(1) + "×"; font.weight: Font.Bold }
        LiquidSlider {
            id: speed; objectName: "motionSpeed"; Layout.fillWidth: true; from: .5; to: 2; stepSize: .1
            Accessible.name: "Animation speed"
            onPressedChanged: if (!pressed) ShellState.run("setting", {key: "motionSpeed", value: Math.round(value * 10) / 10})
            onMoved: if (!pressed) ShellState.run("setting", {key: "motionSpeed", value: Math.round(value * 10) / 10})
        }
        Binding { target: speed; property: "value"; value: Theme.motionSpeed; when: !speed.pressed; restoreMode: Binding.RestoreNone }
        LabelText { text: "Bounce · " + Math.round(Theme.motionBounce * 100) + "%"; font.weight: Font.Bold }
        LiquidSlider {
            id: bounce; objectName: "motionBounce"; Layout.fillWidth: true; from: 0; to: 1; stepSize: .05; enabled: Theme.motionPreset !== "smooth"
            Accessible.name: "Animation bounce"
            onPressedChanged: if (!pressed) ShellState.run("setting", {key: "motionBounce", value: Math.round(value * 100) / 100})
            onMoved: if (!pressed) ShellState.run("setting", {key: "motionBounce", value: Math.round(value * 100) / 100})
        }
        Binding { target: bounce; property: "value"; value: Theme.motionBounce; when: !bounce.pressed; restoreMode: Binding.RestoreNone }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 118; radius: 20; color: Theme.surfaceContainer
            SlideLoader {
                id: motionPreview; objectName: "motionPreview"; anchors.centerIn: parent; width: Math.min(260, parent.width - 32); height: 70; direction: "up"
                content: GlassPanel { radius: 28; LabelText { anchors.centerIn: parent; text: "Move with your desktop"; font.weight: Font.Bold } }
            }
        }
        LiquidButton { text: "Replay preview"; onClicked: { motionPreview.replay(); } }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Panel opacity"; Layout.fillWidth: true }
            LabelText { text: Math.round(opacitySlider.value * 100) + "%"; color: Theme.accent; font.weight: Font.Bold }
        }
        LiquidSlider {
            id: opacitySlider
            Layout.fillWidth: true; from: 0.72; to: 1; stepSize: 0.01
            enabled: ShellState.backendReady && !Theme.liquidGlass
            Accessible.name: "Panel opacity"
            onPressedChanged: if (!pressed) ShellState.run("setting", {key: "opacity", value: Math.round(value * 100) / 100})
            onMoved: if (!pressed) ShellState.run("setting", {key: "opacity", value: Math.round(value * 100) / 100})
        }
        Binding { target: opacitySlider; property: "value"; value: ShellState.preferences.opacity || 0.90; when: !opacitySlider.pressed; restoreMode: Binding.RestoreNone }
        LabelText { text: "Transparency is drawn by the shell. Background blur depends on your compositor."; color: Theme.muted; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
}
