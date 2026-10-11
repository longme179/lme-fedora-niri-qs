pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
ColumnLayout {
    id: root
    spacing: 20
    readonly property var titles: ({weather: "Weather", charging: "Battery charging", wifi: "Wi-Fi", bluetooth: "Bluetooth", microphone: "Microphone", dnd: "Do not disturb", stayAwake: "Stay awake", motion: "Motion", nightLight: "Night Light", sliders: "Volume & brightness", powerProfile: "Power profile", media: "Media player", resources: "System resources", capture: "Capture & actions", overview: "Workspace overview"})
    readonly property var layout: ShellState.preferences.controlLayout || []
    readonly property bool ready: ShellState.backendReady && !ShellState.pendingActions.setting
    function save(next) { if (ready) ShellState.run("setting", {key: "controlLayout", value: next}); }
    function move(id, index) {
        const next = layout.map(m => Object.assign({}, m));
        const previous = next.findIndex(m => m.id === id);
        if (previous < 0) return;
        const item = next.splice(previous, 1)[0];
        if (previous < index) index--;
        next.splice(Math.max(0, Math.min(index, next.length)), 0, item); save(next);
    }
    function patch(id, changes) { save(layout.map(m => m.id === id ? Object.assign({}, m, changes) : m)); }
    SettingsCard {
        title: "Your controls, in your order"
        description: "Drag the grip or use the arrows. Hidden cards keep their positions. Half-width cards become full-width in a narrow panel."
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Panel width"; Layout.fillWidth: true }
            LabelText { text: Math.round(panelWidth.value) + " px"; color: Theme.accent }
        }
        LiquidSlider { id: panelWidth; Layout.fillWidth: true; from: 480; to: 900; stepSize: 20; Accessible.name: "Control center width"; onMoved: if (!pressed) ShellState.run("setting", {key: "controlWidth", value: Math.round(value)}); onPressedChanged: if (!pressed) ShellState.run("setting", {key: "controlWidth", value: Math.round(value)}) }
        Binding { target: panelWidth; property: "value"; value: ShellState.preferences.controlWidth || 600; when: !panelWidth.pressed; restoreMode: Binding.RestoreNone }
    }
    SettingsCard {
        title: "Tiles and cards"
        Repeater {
            model: root.layout
            delegate: Rectangle {
                id: row; required property var modelData; required property int index
                Layout.fillWidth: true; implicitHeight: 62; radius: 16
                color: target.containsDrag ? Theme.primaryContainer : Theme.surfaceContainer
                DropArea { id: target; anchors.fill: parent; keys: ["control-module"]; onDropped: drop => { if (drop.source === proxy) { root.move(proxy.moduleId, row.index); drop.acceptProposedAction(); } } }
                RowLayout {
                    anchors.fill: parent; anchors.margins: 8; spacing: 6
                    Item {
                        objectName: "controlGrip-" + row.modelData.id
                        Layout.preferredWidth: 26; Layout.fillHeight: true
                        LabelText { anchors.centerIn: parent; text: "⠿"; font.pixelSize: 22; color: Theme.muted }
                        MouseArea {
                            anchors.fill: parent; enabled: root.ready; cursorShape: Qt.SizeAllCursor
                            drag.target: proxy
                            onPressed: { const p = mapToItem(proxy.parent, 0, 0); proxy.x = p.x; proxy.y = p.y; proxy.moduleId = row.modelData.id; proxy.visible = true; }
                            onPositionChanged: proxy.Drag.active = drag.active
                            onReleased: { proxy.Drag.drop(); proxy.Drag.active = false; proxy.visible = false; }
                            onCanceled: { proxy.Drag.cancel(); proxy.Drag.active = false; proxy.visible = false; }
                        }
                    }
                    LabelText { text: root.titles[row.modelData.id]; Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold; font.pixelSize: 13 }
                    IconButton { glyph: "↑"; implicitWidth: 26; tooltip: "Move earlier"; enabled: root.ready && row.index > 0; onClicked: root.move(row.modelData.id, row.index - 1) }
                    IconButton { glyph: "↓"; implicitWidth: 26; tooltip: "Move later"; enabled: root.ready && row.index < root.layout.length - 1; onClicked: root.move(row.modelData.id, row.index + 2) }
                    LiquidComboBox { implicitWidth: 96; model: ["Full", "Half"]; currentIndex: row.modelData.size === "half" ? 1 : 0; enabled: root.ready; Accessible.name: root.titles[row.modelData.id] + " card size"; onActivated: root.patch(row.modelData.id, {size: currentIndex ? "half" : "full"}) }
                    ExpressiveSwitch { checked: row.modelData.enabled; enabled: root.ready; Accessible.name: "Show " + root.titles[row.modelData.id]; onToggled: root.patch(row.modelData.id, {enabled: checked}) }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 40; radius: 16; color: append.containsDrag ? Theme.primaryContainer : Theme.surfaceContainer
            LabelText { anchors.centerIn: parent; text: "Drop here to move to the end"; color: Theme.muted; font.pixelSize: 12 }
            DropArea { id: append; anchors.fill: parent; keys: ["control-module"]; onDropped: drop => { if (drop.source === proxy) { root.move(proxy.moduleId, root.layout.length); drop.acceptProposedAction(); } } }
        }
        LiquidButton { text: "Restore default layout"; enabled: root.ready; onClicked: root.save(Object.keys(root.titles).map(id => ({id: id, enabled: true, size: ["wifi", "bluetooth", "microphone", "dnd", "stayAwake", "motion", "nightLight"].includes(id) ? "half" : "full"}))) }
    }
    Rectangle {
        id: proxy; parent: root.parent; property string moduleId: ""
        visible: false; z: 100; width: 190; height: 44; radius: 16; color: Theme.primaryContainer
        Drag.keys: ["control-module"]; Drag.source: proxy; Drag.hotSpot.x: 14; Drag.hotSpot.y: 20
        LabelText { anchors.centerIn: parent; text: root.titles[proxy.moduleId] || ""; font.weight: Font.Bold }
        Layout.preferredHeight: 0
    }
}
