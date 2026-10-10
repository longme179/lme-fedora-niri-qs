pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    implicitWidth: 600
    implicitHeight: 900
    focus: true
    property var tabs: ["Controls", "Audio", "Devices", "Agenda", "Notifications"]
    property int currentTab: Math.max(0, ["controls", "audio", "devices", "agenda", "notifications"].indexOf(Quickshell.env("LME_SHELL_CONTROL_TAB") || "controls"))
    onCurrentTabChanged: if (currentTab === 4) Notifications.markRead()
    Component.onCompleted: if (currentTab === 4) Notifications.markRead()
    Keys.onEscapePressed: ShellState.closePanels()
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Tab && (event.modifiers & Qt.ControlModifier)) {
            currentTab = (currentTab + ((event.modifiers & Qt.ShiftModifier) ? tabs.length - 1 : 1)) % tabs.length;
            event.accepted = true;
        }
    }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 14; spacing: 10
        RowLayout {
            Layout.fillWidth: true; Layout.margins: 8
            ColumnLayout {
                spacing: 3
                LabelText { text: "Control center"; font.pixelSize: 23; font.weight: Font.Bold }
                LabelText { text: "Your desktop, within reach."; color: Theme.muted; font.pixelSize: 12 }
            }
            Item { Layout.fillWidth: true }
            IconButton { iconName: "settings"; tooltip: "Shell settings"; onClicked: ShellState.togglePanel("settings") }
            IconButton { glyph: "×"; tooltip: "Close control center"; onClicked: ShellState.closePanels() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 5
            Repeater {
                model: root.tabs
                delegate: LiquidButton {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    text: modelData
                    palette.button: root.currentTab === index ? Theme.accent : Theme.surface
                    palette.buttonText: root.currentTab === index ? Theme.background : Theme.text
                    onClicked: root.currentTab = index
                }
            }
        }
        Loader {
            Layout.fillWidth: true; Layout.fillHeight: true
            sourceComponent: root.currentTab === 0 ? controls : root.currentTab === 1 ? audio : root.currentTab === 2 ? devices : root.currentTab === 3 ? agenda : notices
        }
    }
    Component { id: controls; ControlDashboard {} }
    Component { id: audio; AudioMixer {} }
    Component { id: devices; DeviceControls {} }
    Component { id: agenda; Agenda {} }
    Component { id: notices; NotificationCenter { embedded: true } }
}
