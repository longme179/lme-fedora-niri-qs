import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 20
    readonly property var state: ShellState.snapshot.nightLight || {}
    function refresh(retry) { if (ShellState.backendReady) ShellState.run("nightLightRefresh", {retry: !!retry}); }
    Component.onCompleted: refresh()
    Connections { target: ShellState; function onBackendReadyChanged() { if (ShellState.backendReady) root.refresh(); } }
    Timer { interval: 2500; running: root.visible && ShellState.settingsApp; repeat: true; onTriggered: root.refresh() }
    SettingsCard {
        title: "Warmer evenings"
        description: "Reduce blue light with display gamma control. Stop other gamma controllers before enabling."
        PreferenceSwitch { title: "Night Light"; preference: "nightLightEnabled"; detail: root.state.active ? "Active · " + (root.state.temperature || 4500) + " K" : "A warmer display when you need it" }
        LabelText { visible: !!root.state.error; text: root.state.error || ""; color: Theme.red; Layout.fillWidth: true; wrapMode: Text.Wrap }
        LabelText { visible: root.state.available === false; text: "Install wlsunset and restart the shell. Your compositor and driver must support gamma control."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Schedule"; Layout.fillWidth: true }
            LiquidComboBox {
                objectName: "nightLightMode"; model: ["Manual", "Custom times", "Sunset to sunrise"]
                currentIndex: ["manual", "schedule", "sunset"].indexOf(ShellState.preferences.nightLightMode || "manual")
                Accessible.name: "Night Light schedule"
                onActivated: ShellState.run("setting", {key: "nightLightMode", value: ["manual", "schedule", "sunset"][currentIndex]})
            }
        }
        RowLayout {
            Layout.fillWidth: true; visible: ShellState.preferences.nightLightMode === "schedule"
            LabelText { text: "From" }
            ExpressiveField {
                objectName: "nightLightStart"; Layout.fillWidth: true; maximumLength: 5; placeholderText: "20:00"; text: ShellState.preferences.nightLightStart || "20:00"
                Accessible.name: "Night Light start time"
                onEditingFinished: if (text !== ShellState.preferences.nightLightStart) ShellState.run("setting", {key: "nightLightStart", value: text})
            }
            LabelText { text: "Until" }
            ExpressiveField {
                objectName: "nightLightEnd"; Layout.fillWidth: true; maximumLength: 5; placeholderText: "07:00"; text: ShellState.preferences.nightLightEnd || "07:00"
                Accessible.name: "Night Light end time"
                onEditingFinished: if (text !== ShellState.preferences.nightLightEnd) ShellState.run("setting", {key: "nightLightEnd", value: text})
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; visible: ShellState.preferences.nightLightMode === "sunset"
            LabelText { text: "Uses your Weather location and local timezone. Approximate sunrise/sunset; no additional location request."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
            LabelText { text: root.state.start && root.state.end ? "Sunset " + root.state.start + " · Sunrise " + root.state.end : "Waiting for location"; color: Theme.accent; font.weight: Font.Bold }
            LiquidButton { text: "Weather location settings"; onClicked: ShellState.openSettingsPage("weather") }
        }
    }
    SettingsCard {
        title: "Color temperature"
        description: "Lower values are warmer. 6500 K is close to the normal display white point."
        LabelText { text: Math.round(temperature.value) + " K"; font.pixelSize: 24; font.weight: Font.Bold; color: Theme.yellow }
        LiquidSlider {
            id: temperature; objectName: "nightLightTemperature"; Layout.fillWidth: true; from: 2500; to: 6500; stepSize: 100
            Accessible.name: "Night Light temperature"
            onPressedChanged: if (!pressed) ShellState.run("setting", {key: "nightLightTemperature", value: Math.round(value)})
            onMoved: if (!pressed) ShellState.run("setting", {key: "nightLightTemperature", value: Math.round(value)})
        }
        Binding { target: temperature; property: "value"; value: ShellState.preferences.nightLightTemperature || 4500; when: !temperature.pressed; restoreMode: Binding.RestoreNone }
        RowLayout { Layout.fillWidth: true; LabelText { text: "Warm"; color: Theme.muted } Item { Layout.fillWidth: true } LabelText { text: "Neutral"; color: Theme.muted } }
        LiquidButton { text: "Retry gamma control"; onClicked: root.refresh(true) }
    }
}
