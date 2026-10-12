pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../services"
import "../theme"

ColumnLayout {
    id: root
    Layout.fillWidth: true; spacing: 12
    property string query: ""
    property string chosenId: ShellState.preferences.palettePreset || "lme-dracula"
    readonly property var matches: Theme.paletteCatalog.filter(p => (p.name + " " + p.id).toLowerCase().includes(query.toLowerCase()))
    readonly property var selected: Theme.paletteCatalog.find(p => p.id === chosenId) || ({colors: {}})
    readonly property var colors: selected.colors || ({})
    ExpressiveField {
        Layout.fillWidth: true; placeholderText: "Search palettes · Rose Pine, Gruvbox, Nord…"
        Accessible.name: "Search built-in palettes"; onTextChanged: root.query = text
    }
    LiquidComboBox {
        objectName: "palettePresetChoice"; Layout.fillWidth: true
        model: root.matches.map(p => p.name)
        currentIndex: root.matches.findIndex(p => p.id === root.chosenId)
        Accessible.name: "Built-in color palette"
        onActivated: root.chosenId = root.matches[currentIndex].id
    }
    Rectangle {
        Layout.fillWidth: true; implicitHeight: preview.implicitHeight + 32; radius: 20
        color: root.colors.background || Theme.background
        border.width: 1; border.color: root.colors.border || Theme.border
        ColumnLayout {
            id: preview; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; spacing: 12
            LabelText { text: root.selected.name || "Loading palettes…"; font.weight: Font.Bold; font.pixelSize: 18; color: root.colors.text || Theme.text; Layout.fillWidth: true }
            LabelText { text: "Preview only · your current theme stays active until Apply"; color: root.colors.muted || Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                Repeater {
                    model: ["purple", "pink", "cyan", "green", "yellow", "red"]
                    delegate: Rectangle { required property string modelData; Layout.fillWidth: true; Layout.preferredHeight: 28; radius: 12; color: root.colors[modelData] || Theme.accent }
                }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 44; radius: 16; color: root.colors.panel || Theme.panel
                LabelText { anchors.centerIn: parent; text: "Readable text and tonal surfaces"; color: root.colors.text || Theme.text }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        LiquidButton { objectName: "applyPalettePreset"; text: "Apply palette"; enabled: !!root.selected.id && ShellState.backendReady && !ShellState.pendingActions.palettePreset; onClicked: ShellState.run("palettePreset", {id: root.chosenId}) }
        LabelText { text: "Manual element and island colors are preserved."; Layout.fillWidth: true; color: Theme.muted; wrapMode: Text.Wrap }
    }
}
