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
    readonly property var tabEntries: ControlRegistry.tabs
    property var tabs: tabEntries.map(tab => tab.title)
    readonly property var tabComponents: ({ControlDashboard: controls, AudioMixer: audio, DeviceControls: devices, Agenda: agenda, NotificationCenter: notices, SystemMonitor: monitor})
    property bool editing: false
    property bool initialized: false
    // Integer properties remain compatibility boundaries for existing fixtures/imports.
    property int currentTab: Quickshell.env("LME_SHELL_CONTROL_TAB") ? ControlRegistry.indexForId(Quickshell.env("LME_SHELL_CONTROL_TAB")) : ShellState.controlTab
    readonly property var selectedTab: ControlRegistry.tabForIndex(currentTab)
    readonly property int tabIndex: ControlRegistry.positionForIndex(currentTab)
    function selectTab(id) { currentTab = ControlRegistry.indexForId(id); }
    function refreshControls() { if (initialized && visible && ControlRegistry.tabForIndex(currentTab).refresh && ShellState.backendReady) ShellState.run("controlsRefresh"); }
    function markTabRead() { if (ControlRegistry.tabForIndex(currentTab).markRead) Notifications.markRead(); }
    onCurrentTabChanged: { editing = false; ShellState.controlTab = currentTab; markTabRead(); refreshControls(); }
    onVisibleChanged: refreshControls()
    Component.onCompleted: { initialized = true; markTabRead(); refreshControls(); }
    Connections {
        target: ShellState
        function onControlTabChanged() { if (root.currentTab !== ShellState.controlTab) root.currentTab = ShellState.controlTab; }
        function onBackendReadyChanged() { if (ShellState.backendReady) root.refreshControls(); }
    }
    Keys.onEscapePressed: if (editing) editing = false; else ShellState.closePanels()
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Tab && (event.modifiers & Qt.ControlModifier)) {
            const next = ((tabIndex >= 0 ? tabIndex : currentTab) + ((event.modifiers & Qt.ShiftModifier) ? tabs.length - 1 : 1)) % tabs.length;
            if (tabIndex < 0) currentTab = next;
            else selectTab(tabEntries[next].id);
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
                enabled: !Theme.liquidGlass
                displayText: Theme.liquidGlass ? "Liquid glass" : currentIndex >= 0 ? currentText : "Custom appearance"
                Accessible.name: "Quick appearance profile"
                onActivated: ShellState.run("appearanceApply", {name: currentText})
            }
            LiquidButton { objectName: "controlEdit"; visible: root.selectedTab.id === "controls"; text: root.editing ? "Done" : "Edit layout"; selected: root.editing; onClicked: root.editing = !root.editing }
        }
        RowLayout {
            visible: root.editing; Layout.fillWidth: true
            LabelText { text: "Drop on empty cells, or swap tiles of the same size. Arrow keys find the next valid cell."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12 }
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
                objectName: "controlGridRows"
                readonly property var choices: [...new Set([8, ...((ShellState.preferences.controlGrid || {}).columns === 8 ? [4] : []), (ShellState.preferences.controlGrid || {}).rows || 8])].sort((a, b) => a - b)
                model: choices.map(rows => rows + " rows")
                currentIndex: Math.max(0, choices.indexOf((ShellState.preferences.controlGrid || {}).rows || 8))
                enabled: !ShellState.pendingActions.setting
                Accessible.name: "Control canvas rows"
                onActivated: if (dashboard.item) (dashboard.item as ControlDashboard).grid.resize((ShellState.preferences.controlGrid || {}).columns || 4, choices[currentIndex])
            }
            Item { Layout.fillWidth: true }
        }
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: tabGrid.implicitHeight
            StretchIndicator { objectName: "controlTabIndicator"; targetItem: tabRepeater.count ? tabRepeater.itemAt(root.tabIndex) as LiquidButton : null; fill: Theme.liquidGlass ? Theme.buttonSelected : Theme.accent }
        GridLayout {
            id: tabGrid; anchors.fill: parent; columnSpacing: 5; rowSpacing: 5
            columns: 3
            Repeater {
                id: tabRepeater; model: root.tabEntries
                delegate: LiquidButton {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    text: modelData.title
                    readonly property bool current: root.currentTab === modelData.legacyIndex
                    selected: Theme.animatedTabs && current; selectionFill: false
                    selectionColor: Theme.liquidGlass ? Theme.buttonSelected : Theme.accent
                    Accessible.role: Accessible.PageTab; Accessible.selected: current
                    palette.button: current && !Theme.animatedTabs ? Theme.liquidGlass ? Theme.buttonSelected : Theme.accent : Theme.surface
                    palette.buttonText: current && !Theme.liquidGlass ? Theme.background : Theme.text
                    onClicked: root.selectTab(modelData.id)
                }
            }
        }
        }
        Loader {
            id: dashboard
            Layout.fillWidth: true; Layout.fillHeight: true
            sourceComponent: root.tabComponents[root.selectedTab.entry]
        }
    }
    Component { id: monitor; SystemMonitor {} }
    Component { id: controls; ControlDashboard { editing: root.editing } }
    Component { id: audio; AudioMixer {} }
    Component { id: devices; DeviceControls {} }
    Component { id: agenda; Agenda {} }
    Component { id: notices; NotificationCenter { embedded: true } }
}
