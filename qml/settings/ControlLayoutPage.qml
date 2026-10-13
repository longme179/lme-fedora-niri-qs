pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 20
    readonly property var titles: ControlRegistry.titles
    readonly property var layout: ShellState.preferences.controlLayout || []
    readonly property var cards: layout.filter(item => ControlRegistry.cardIds.includes(item.id))
    readonly property var buttons: ControlRegistry.tiles.map(tile => layout.find(item => item.id === tile.id)).filter(item => item)
    readonly property bool ready: ShellState.backendReady && !ShellState.pendingActions.setting
    function save(next) { if (ready) ShellState.run("setting", {key: "controlLayout", value: next}); }
    function move(id, index) {
        const next = cards.map(item => Object.assign({}, item));
        const previous = next.findIndex(item => item.id === id);
        if (previous < 0) return;
        const item = next.splice(previous, 1)[0];
        if (previous < index) index--;
        next.splice(Math.max(0, Math.min(index, next.length)), 0, item);
        save(layout.map(item => ControlRegistry.cardIds.includes(item.id) ? next.shift() : item));
    }
    function patch(id, changes) { save(layout.map(item => item.id === id ? Object.assign({}, item, changes) : item)); }
    component ModuleRow: Rectangle {
        id: row
        required property var modelData
        required property int index
        property bool card: false
        Layout.fillWidth: true; implicitHeight: 62; radius: 16
        color: target.containsDrag ? Theme.primaryContainer : Theme.surfaceContainer
        DropArea {
            id: target; anchors.fill: parent; enabled: row.card; keys: ["control-module"]
            onDropped: drop => { if (drop.source === proxy) { root.move(proxy.moduleId, row.index); drop.acceptProposedAction(); } }
        }
        RowLayout {
            anchors.fill: parent; anchors.margins: 8; spacing: 6
            Item {
                objectName: "controlGrip-" + row.modelData.id
                visible: row.card
                Layout.preferredWidth: 26; Layout.fillHeight: true
                LabelText { anchors.centerIn: parent; text: "⠿"; font.pixelSize: 22; color: Theme.muted }
                MouseArea {
                    anchors.fill: parent; enabled: root.ready; cursorShape: Qt.SizeAllCursor; drag.target: proxy
                    onPressed: { const p = mapToItem(proxy.parent, 0, 0); proxy.x = p.x; proxy.y = p.y; proxy.moduleId = row.modelData.id; proxy.visible = true; }
                    onPositionChanged: proxy.Drag.active = drag.active
                    onReleased: { proxy.Drag.drop(); proxy.Drag.active = false; proxy.visible = false; }
                    onCanceled: { proxy.Drag.cancel(); proxy.Drag.active = false; proxy.visible = false; }
                }
            }
            LabelText { text: root.titles[row.modelData.id] || row.modelData.id; Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold; font.pixelSize: 13 }
            IconButton { visible: row.card; glyph: "↑"; implicitWidth: 26; tooltip: "Move earlier"; enabled: root.ready && row.index > 0; onClicked: root.move(row.modelData.id, row.index - 1) }
            IconButton { visible: row.card; glyph: "↓"; implicitWidth: 26; tooltip: "Move later"; enabled: root.ready && row.index < root.cards.length - 1; onClicked: root.move(row.modelData.id, row.index + 2) }
            LiquidComboBox { visible: row.card; implicitWidth: 96; model: ["Full", "Half"]; currentIndex: row.modelData.size === "half" ? 1 : 0; enabled: root.ready; Accessible.name: root.titles[row.modelData.id] + " card size"; onActivated: root.patch(row.modelData.id, {size: currentIndex ? "half" : "full"}) }
            ExpressiveSwitch { objectName: "controlShow-" + row.modelData.id; checked: row.modelData.enabled; enabled: root.ready; Accessible.name: "Show " + root.titles[row.modelData.id]; onToggled: root.patch(row.modelData.id, {enabled: checked}) }
        }
    }
    SettingsCard {
        title: "Control center"
        description: "Buttons keep independent canvas positions. Arrange them in the popup's Edit layout mode; this page only controls their visibility. Detailed cards retain order and width settings."
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Panel width"; Layout.fillWidth: true }
            LabelText { text: Math.round(panelWidth.value) + " px"; color: Theme.accent }
        }
        LiquidSlider { id: panelWidth; Layout.fillWidth: true; from: 480; to: 900; stepSize: 20; Accessible.name: "Control center width"; onMoved: if (!pressed) ShellState.run("setting", {key: "controlWidth", value: Math.round(value)}); onPressedChanged: if (!pressed) ShellState.run("setting", {key: "controlWidth", value: Math.round(value)}) }
        Binding { target: panelWidth; property: "value"; value: ShellState.preferences.controlWidth || 600; when: !panelWidth.pressed; restoreMode: Binding.RestoreNone }
    }
    SettingsCard {
        title: "Canvas buttons"
        Repeater { model: root.buttons; delegate: ModuleRow {} }
    }
    SettingsCard {
        title: "Detailed cards"
        Repeater { model: root.cards; delegate: ModuleRow { card: true } }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 40; radius: 16; color: append.containsDrag ? Theme.primaryContainer : Theme.surfaceContainer
            LabelText { anchors.centerIn: parent; text: "Drop here to move a card to the end"; color: Theme.muted; font.pixelSize: 12 }
            DropArea { id: append; anchors.fill: parent; keys: ["control-module"]; onDropped: drop => { if (drop.source === proxy) { root.move(proxy.moduleId, root.cards.length); drop.acceptProposedAction(); } } }
        }
        LiquidButton { text: "Restore default layout"; enabled: root.ready; onClicked: root.save(ControlRegistry.defaults) }
    }
    Rectangle {
        id: proxy; parent: root.parent; property string moduleId: ""
        visible: false; z: 100; width: 190; height: 44; radius: 16; color: Theme.primaryContainer
        Drag.keys: ["control-module"]; Drag.source: proxy; Drag.hotSpot.x: 14; Drag.hotSpot.y: 20
        LabelText { anchors.centerIn: parent; text: root.titles[proxy.moduleId] || ""; font.weight: Font.Bold }
        Layout.preferredHeight: 0
    }
}
