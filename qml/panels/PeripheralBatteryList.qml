pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    readonly property var devices: ShellState.system.peripheralBatteries || []
    readonly property int threshold: ShellState.preferences.peripheralBatteryThreshold || 20
    visible: devices.length > 0
    spacing: 8

    LabelText { text: "Device batteries"; font.weight: Font.Bold; Layout.topMargin: 8 }
    Repeater {
        model: root.devices
        delegate: Rectangle {
            id: battery
            required property var modelData
            readonly property bool reported: typeof modelData.percentage === "number" && Number.isFinite(modelData.percentage)
            readonly property bool low: reported && modelData.percentage <= root.threshold && modelData.charging !== true
            objectName: "peripheralBattery-" + modelData.id
            Layout.fillWidth: true
            implicitHeight: details.implicitHeight + 24
            radius: 14
            color: Theme.surface
            ColumnLayout {
                id: details
                x: 12; y: 12; width: parent.width - 24; spacing: 6
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    ShellIcon { name: "battery"; color: battery.low ? Theme.yellow : Theme.green; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                    LabelText { text: battery.modelData.name; font.weight: Font.Bold; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    LabelText { text: battery.reported ? Math.round(battery.modelData.percentage) + "%" : "—"; color: battery.low ? Theme.yellow : Theme.text }
                }
                LabelText {
                    text: !battery.reported ? "Battery not reported by this device"
                        : battery.modelData.charging === true ? "Charging"
                        : battery.low ? "Low battery" : "Connected"
                    color: battery.low ? Theme.yellow : Theme.muted
                    font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true
                }
                Rectangle {
                    visible: battery.reported
                    Layout.fillWidth: true; implicitHeight: 4; radius: 2; color: Theme.border
                    Rectangle { width: parent.width * (battery.modelData.percentage || 0) / 100; height: parent.height; radius: parent.radius; color: battery.low ? Theme.yellow : Theme.green }
                }
            }
        }
    }
}
