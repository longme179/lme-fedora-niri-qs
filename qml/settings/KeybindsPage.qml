pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    id: root; objectName: "keybindPage"; spacing: 16
    property string savedPath: ""
    readonly property var state: ShellState.snapshot.keybinds || {}
    property string query: ""
    readonly property var matches: (state.bindings || []).filter(b => query.toLowerCase().trim().split(/\s+/).every(word => (b.key+" "+b.title+" "+b.action).toLowerCase().includes(word)))
    function refresh() { if (ShellState.backendReady) ShellState.run("keybindRefresh"); }
    Component.onCompleted: { savedPath = ShellState.preferences.niriConfigPath || ""; refresh(); }
    Connections {
        target: ShellState
        function onBackendReadyChanged() { if (ShellState.backendReady) { root.savedPath = ShellState.preferences.niriConfigPath || ""; root.refresh(); } }
        function onPreferencesChanged() { if (ShellState.backendReady && (ShellState.preferences.niriConfigPath || "") !== root.savedPath) { root.savedPath = ShellState.preferences.niriConfigPath || ""; configPath.text = root.savedPath; root.refresh(); } }
    }
    SettingsCard {
        title: "Niri keybindings"
        description: "Read your config and included files. This viewer never changes keybindings. Mod means your configured niri modifier."
        RowLayout {
            Layout.fillWidth: true
            ExpressiveField { id: configPath; objectName: "keybindConfig"; Layout.fillWidth: true; placeholderText: "Auto: NIRI_CONFIG or ~/.config/niri/config.kdl"; text: ShellState.preferences.niriConfigPath || ""; maximumLength: 4096; Accessible.name: "Niri config path"; onAccepted: savePath.clicked() }
            LiquidButton { id: savePath; text: "Use path"; enabled: ShellState.backendReady; onClicked: ShellState.run("setting", {key: "niriConfigPath", value: configPath.text.trim()}) }
            IconButton { iconName: "refresh"; Accessible.name: "Refresh keybindings"; tooltip: "Refresh keybindings"; onClicked: root.refresh() }
        }
        LabelText { text: root.state.path || "Connecting…"; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; color: Theme.muted; font.pixelSize: 12; textFormat: Text.PlainText }
        Repeater { model: root.state.errors || []; delegate: LabelText { required property string modelData; text: modelData; textFormat: Text.PlainText; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.yellow } }
    }
    ExpressiveField { objectName: "keybindSearch"; Layout.fillWidth: true; placeholderText: "Search shortcut or action"; maximumLength: 160; Accessible.name: placeholderText; onTextChanged: root.query = text }
    LabelText { text: root.matches.length+" shortcuts"; font.weight: Font.Bold; color: Theme.muted }
    ListView {
        id: list; objectName: "keybindList"; Layout.fillWidth: true; Layout.preferredHeight: 420; clip: true
        model: root.matches; spacing: 8; boundsBehavior: Flickable.StopAtBounds; ScrollBar.vertical: ScrollBar {}
        delegate: Rectangle {
            id: bind; required property var modelData
            width: list.width-12; height: content.implicitHeight+28; radius: 18; color: Theme.surfaceContainer
            RowLayout {
                id: content; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 14
                LabelText { text: bind.modelData.key.split('+').join(' + '); textFormat: Text.PlainText; font.weight: Font.Bold; color: Theme.accent; Layout.preferredWidth: root.width < 500 ? 125 : 168; wrapMode: Text.WrapAnywhere }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 4
                    LabelText { text: bind.modelData.title; textFormat: Text.PlainText; font.weight: Font.Bold; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    LabelText { visible: text !== bind.modelData.title; text: bind.modelData.action; textFormat: Text.PlainText; font.pixelSize: 11; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                    LabelText { text: bind.modelData.source.split('/').pop()+":"+bind.modelData.line; font.pixelSize: 10; color: Theme.muted; Layout.fillWidth: true; elide: Text.ElideMiddle }
                }
            }
        }
        LabelText { visible: list.count === 0; anchors.centerIn: parent; text: "No matching shortcuts"; color: Theme.muted }
    }
}
