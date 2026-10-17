// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 20
    signal fontSettingsRequested()
    property string colorToken: "notificationFill"
    ColorPicker {
        id: picker
        parent: Overlay.overlay; anchors.centerIn: parent
        onChosen: color => ShellState.run("setting", {key: "themeOverrides", token: root.colorToken, value: color.toString()})
    }
    SettingsCard {
        title: "Live preview"
        description: "Cards grow with their content. Long messages scroll inside the card; actions wrap onto more rows."
        NotificationCard {
            objectName: "notificationPreview"
            Layout.fillWidth: true
            Layout.preferredWidth: Theme.notificationWidth
            Layout.maximumWidth: Theme.notificationWidth
            Layout.preferredHeight: implicitHeight
            maximumHeight: 360
            dismissible: false
            entry: ({appName: ShellState.shellName, summary: "A little more expressive", body: "Your notification colors, typography and shape update here as you edit. The bell stays still while its soft outline turns.", actions: []})
        }
        LiquidButton { text: "Send test notification"; onClicked: Notifications.local("Notification preview", "A longer message wraps naturally without losing its last line. Change the width, padding or text size to find your fit.") }
    }
    SettingsCard {
        title: "Placement and shape"
        description: "Applies to popup notifications. Shell status messages stay at the bottom center."
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Popup position"; Layout.fillWidth: true; wrapMode: Text.Wrap }
            LiquidComboBox {
                objectName: "notificationPosition"
                readonly property var positions: ["bar", "top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"]
                model: ["Follow the bar", "Top left", "Top center", "Top right", "Bottom left", "Bottom center", "Bottom right"]
                currentIndex: positions.indexOf(ShellState.preferences.notificationPosition || "bar")
                Accessible.name: "Notification position"
                onActivated: ShellState.run("setting", {key: "notificationPosition", value: positions[currentIndex]})
            }
        }
        Repeater {
            model: [
                {key: "notificationWidth", title: "Width", low: 300, high: 640, unit: " px"},
                {key: "notificationMargin", title: "Screen margin", low: 0, high: 64, unit: " px"},
                {key: "notificationRadius", title: "Corner radius", low: 0, high: 48, unit: " px"},
                {key: "notificationPadding", title: "Inner padding", low: 12, high: 28, unit: " px"},
                {key: "notificationBorderWidth", title: "Border width", low: 0, high: 4, unit: " px"},
                {key: "notificationOpacity", title: "Surface opacity", low: 60, high: 100, unit: "%"},
                {key: "notificationTitleSize", title: "Title size", low: 12, high: 24, unit: " px"},
                {key: "notificationBodySize", title: "Body size", low: 11, high: 22, unit: " px"}
            ]
            delegate: ColumnLayout {
                id: row
                required property var modelData
                Layout.fillWidth: true; spacing: 6
                readonly property real factor: modelData.key === "notificationOpacity" ? 100 : 1
                function save() { ShellState.run("setting", {key: modelData.key, value: Math.round(slider.value) / factor}); }
                LabelText { text: row.modelData.title + " · " + Math.round(slider.value) + row.modelData.unit; font.weight: Font.Medium }
                LiquidSlider {
                    id: slider; objectName: row.modelData.key
                    Layout.fillWidth: true; from: row.modelData.low; to: row.modelData.high; stepSize: 1
                    enabled: ShellState.backendReady && (!Theme.liquidGlass || !["notificationOpacity", "notificationBorderWidth"].includes(row.modelData.key))
                    Accessible.name: "Notification " + row.modelData.title.toLowerCase()
                    onMoved: if (!pressed) row.save()
                    onPressedChanged: if (!pressed) row.save()
                }
                Binding { target: slider; property: "value"; value: (ShellState.preferences[row.modelData.key] ?? Theme[row.modelData.key]) * row.factor; when: !slider.pressed; restoreMode: Binding.RestoreNone }
            }
        }
    }
    SettingsCard {
        title: "Colors and fonts"
        description: Theme.liquidGlass ? "Liquid glass uses neutral colors, its own opacity and a thin outline. Switch it off in Appearance to edit saved colors. Font and layout settings still apply."
            : "Choose a color to edit HSV, alpha or hex. Notification colors also appear in Elements and fonts and are saved with Appearance profiles."
        Flow {
            id: swatches
            enabled: !Theme.liquidGlass
            Layout.fillWidth: true; spacing: 8
            Repeater {
                model: ["notificationFill", "notificationTitle", "notificationBody", "notificationAccent", "notificationBorder"]
                delegate: LiquidButton {
                    id: swatch
                    required property string modelData
                    text: Theme.tokenTitle(modelData).replace("Notification ", "")
                    width: Math.min(implicitWidth, swatches.width)
                    onClicked: { root.colorToken = modelData; picker.initialColor = Theme.tokenColor(modelData); picker.open(); }
                    contentItem: RowLayout {
                        spacing: 8
                        Rectangle { implicitWidth: 18; implicitHeight: 18; radius: 6; color: Theme.tokenColor(swatch.modelData); border.width: 1; border.color: Theme.border }
                        LabelText { text: swatch.text; Layout.fillWidth: true; elide: Text.ElideRight }
                    }
                }
            }
        }
        Flow {
            Layout.fillWidth: true; spacing: 8
            LiquidButton { text: "Reset notification colors"; enabled: !Theme.liquidGlass; onClicked: { const colors = Object.assign({}, ShellState.preferences.themeOverrides || {}); for (const key of ["notificationFill", "notificationTitle", "notificationBody", "notificationAccent", "notificationBorder"]) delete colors[key]; ShellState.run("setting", {key: "themeOverrides", value: colors}); } }
            LiquidButton { text: "Font families…"; onClicked: root.fontSettingsRequested() }
        }
    }
    SettingsCard {
        title: "Idle motion"
        description: "A slow, cloud-like outline rotates around the bell. Text stays steady. Motion stops for hidden cards and when animations are disabled; history icons stay still."
        PreferenceSwitch { title: "Rotating notification emblem"; detail: "Animate popup and shell-status icons while they are visible."; preference: "notificationIdleAnimation" }
        LabelText { text: "One turn · " + Math.round(idleSpeed.value) + " s"; font.weight: Font.Medium }
        LiquidSlider {
            id: idleSpeed; objectName: "notificationIdleSpeed"
            Layout.fillWidth: true; from: 6; to: 40; stepSize: 1
            enabled: ShellState.backendReady && Theme.notificationIdleAnimation
            Accessible.name: "Notification rotation period"
            onMoved: if (!pressed) ShellState.run("setting", {key: "notificationIdleSpeed", value: Math.round(value)})
            onPressedChanged: if (!pressed) ShellState.run("setting", {key: "notificationIdleSpeed", value: Math.round(value)})
        }
        Binding { target: idleSpeed; property: "value"; value: Theme.notificationIdleSpeed; when: !idleSpeed.pressed; restoreMode: Binding.RestoreNone }
    }
}
