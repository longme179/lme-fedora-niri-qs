import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
RowLayout {
    id: root
    required property string title
    required property string detail
    required property string preference
    Layout.fillWidth: true; spacing: 20
    ColumnLayout {
        Layout.fillWidth: true; spacing: 5
        LabelText { text: root.title; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.Wrap }
        LabelText { text: root.detail; color: Theme.muted; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
    ExpressiveSwitch {
        checked: ShellState.preferences[root.preference] !== false
        enabled: ShellState.backendReady && !ShellState.pendingActions.setting
        Accessible.name: root.title
        onToggled: ShellState.run("setting", {key: root.preference, value: checked})
    }
}
