pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import "../components"
import "../services"
import "../theme"

GlassPanel {
    id: root
    role: "controlFill"
    implicitWidth: Math.max(ShellState.preferences.controlWidth || 600, (ShellState.preferences.controlGrid || {}).columns === 8 ? 900 : 480)
    implicitHeight: 900
    focus: true
    property var tabs: ["Controls", "Audio", "Devices", "Agenda", "Notifications", "System"]
    property bool editing: false
    property int currentTab: Quickshell.env("LME_SHELL_CONTROL_TAB") ? Math.max(0, ["controls", "audio", "devices", "agenda", "notifications", "system"].indexOf(Quickshell.env("LME_SHELL_CONTROL_TAB"))) : ShellState.controlTab
    onCurrentTabChanged: { editing = false; ShellState.controlTab = currentTab; if (currentTab === 4) Notifications.markRead(); }
    Component.onCompleted: if (currentTab === 4) Notifications.markRead()
    Connections { target: ShellState; function onControlTabChanged() { if (root.currentTab !== ShellState.controlTab) root.currentTab = ShellState.controlTab; } }
    Keys.onEscapePressed: if (editing) editing = false; else ShellState.closePanels()
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
            PrivacyIndicator {}
            IconButton { iconName: "settings"; tooltip: "Shell settings"; onClicked: ShellState.togglePanel("settings") }
            IconButton { glyph: "×"; tooltip: "Close control center"; onClicked: ShellState.closePanels() }
        }
        LabelText { visible: !!(ShellState.snapshot.idle || {}).error; text: (ShellState.snapshot.idle || {}).error || ""; textFormat: Text.PlainText; color: Theme.red; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
        RowLayout {
            Layout.fillWidth: true
            LiquidComboBox {
                Layout.fillWidth: true
                property var profiles: ShellState.preferences.appearanceProfiles || []
                model: profiles.map(p => p.name)
                currentIndex: profiles.findIndex(p => Object.keys(p).filter(k => k !== "name").every(k => Theme.settingsEqual(p[k], ShellState.preferences[k])))
                displayText: currentIndex >= 0 ? currentText : "Custom appearance"
                Accessible.name: "Quick appearance profile"
                onActivated: ShellState.run("appearanceApply", {name: currentText})
            }
            LiquidButton { objectName: "controlEdit"; visible: root.currentTab === 0; text: root.editing ? "Done" : "Edit layout"; selected: root.editing; onClicked: root.editing = !root.editing }
        }
        RowLayout {
            visible: root.editing; Layout.fillWidth: true
            LabelText { text: "Drag a tile, or focus it and use arrow keys."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12 }
            LiquidButton { text: "Widgets…"; onClicked: ShellState.openSettingsPage("controlLayout") }
        }
        RowLayout {
            visible: root.editing; Layout.fillWidth: true
            LiquidComboBox {
                objectName: "controlGridColumns"; model: ["4 columns", "8 columns"]
                currentIndex: (ShellState.preferences.controlGrid || {}).columns === 8 ? 1 : 0
                enabled: !ShellState.pendingActions.setting
                Accessible.name: "Control canvas columns"
                onActivated: if (dashboard.item) (dashboard.item as ControlDashboard).grid.resize(currentIndex ? 8 : 4, (ShellState.preferences.controlGrid || {}).rows || 4)
            }
            LiquidComboBox {
                objectName: "controlGridRows"; model: ["4 rows", "8 rows"]
                currentIndex: (ShellState.preferences.controlGrid || {}).rows === 8 ? 1 : 0
                enabled: !ShellState.pendingActions.setting
                Accessible.name: "Control canvas rows"
                onActivated: if (dashboard.item) (dashboard.item as ControlDashboard).grid.resize((ShellState.preferences.controlGrid || {}).columns || 4, currentIndex ? 8 : 4)
            }
            Item { Layout.fillWidth: true }
        }
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: tabGrid.implicitHeight
            StretchIndicator { objectName: "controlTabIndicator"; targetItem: tabRepeater.count ? tabRepeater.itemAt(root.currentTab) as LiquidButton : null; fill: Theme.accent }
        GridLayout {
            id: tabGrid; anchors.fill: parent; columnSpacing: 5; rowSpacing: 5
            columns: 3
            Repeater {
                id: tabRepeater; model: root.tabs
                delegate: LiquidButton {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    text: modelData
                    selected: Theme.animatedTabs && root.currentTab === index; selectionFill: false
                    Accessible.role: Accessible.PageTab; Accessible.selected: root.currentTab === index
                    palette.button: root.currentTab === index && !Theme.animatedTabs ? Theme.accent : Theme.surface
                    palette.buttonText: root.currentTab === index ? Theme.background : Theme.text
                    onClicked: root.currentTab = index
                }
            }
        }
        }
        Loader {
            id: dashboard
            Layout.fillWidth: true; Layout.fillHeight: true
            sourceComponent: root.currentTab === 0 ? controls : root.currentTab === 1 ? audio : root.currentTab === 2 ? devices : root.currentTab === 3 ? agenda : root.currentTab === 4 ? notices : monitor
        }
    }
    Component { id: monitor; SystemMonitor {} }
    Component { id: controls; ControlDashboard { editing: root.editing } }
    Component { id: audio; AudioMixer {} }
    Component { id: devices; DeviceControls {} }
    Component { id: agenda; Agenda {} }
    Component { id: notices; NotificationCenter { embedded: true } }
}
