import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

Rectangle {
    id: root
    readonly property var charging: ShellState.system.charging || {}
    readonly property bool busy: !!ShellState.pendingActions.chargeMode || !!charging.busy
    implicitHeight: content.implicitHeight + 32
    radius: 24; color: Theme.alpha(Theme.surfaceContainerHigh, 0.78)
    ColumnLayout {
        id: content
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            ShellIcon { name: "battery"; width: 18; height: 18; color: Theme.green }
            LabelText { text: "Battery charging"; font.weight: Font.Bold; font.pixelSize: root.width < 340 ? 14 : 16; Layout.fillWidth: true; wrapMode: Text.Wrap }
            LabelText { text: root.busy ? "Changing…" : root.charging.limitPercent !== undefined && root.charging.limitPercent !== null ? root.charging.limitPercent + "% limit" : root.charging.mode === "conservation" ? "Conservation" : root.charging.mode === "max" ? "Max charge" : "Unavailable"; font.pixelSize: 12; color: Theme.muted }
        }
        GridLayout {
            Layout.fillWidth: true; columnSpacing: 8; rowSpacing: 8
            columns: root.width < 340 ? 1 : 2
            LiquidButton {
                text: root.charging.supports85 ? "Conservation · 85%" : "Conservation"
                selected: root.charging.mode === "conservation" && (!root.charging.supports85 || root.charging.limitPercent === 85)
                Layout.fillWidth: true
                enabled: ShellState.backendReady && !!root.charging.canSet && !root.busy
                Accessible.name: text + " charging mode"
                onClicked: ShellState.run("chargeMode", {value: 85})
            }
            LiquidButton {
                text: "Max charge · 100%"; selected: root.charging.mode === "max"
                Layout.fillWidth: true
                enabled: ShellState.backendReady && !!root.charging.canSet && !root.busy
                Accessible.name: "Maximum battery charge, 100 percent"
                onClicked: ShellState.run("chargeMode", {value: 100})
            }
        }
        LabelText {
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12
            text: root.busy ? "Complete the administrator prompt if one appears."
                : root.charging.reason || "Conservation protects battery lifespan when plugged in."
        }
    }
}
