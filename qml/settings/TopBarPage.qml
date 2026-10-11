pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../bar"
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 20
    readonly property var layout: ShellState.preferences.barLayout || BarRegistry.defaults
    readonly property bool ready: ShellState.backendReady && !ShellState.pendingActions.setting
    property alias dragProxy: proxy
    function save(value) { if (ready) ShellState.run("setting", {key: "barLayout", value: value}); }
    function move(id, zone, index) {
        const next = BarRegistry.clone(layout);
        let previous = -1;
        for (const key of BarRegistry.zones) {
            const position = next[key].indexOf(id);
            if (position >= 0) { if (key === zone) previous = position; next[key].splice(position, 1); }
        }
        if (previous >= 0 && previous < index) index--;
        next[zone].splice(Math.max(0, Math.min(index, next[zone].length)), 0, id);
        save(next);
    }
    function remove(id) {
        const next = BarRegistry.clone(layout);
        for (const zone of BarRegistry.zones) next[zone] = next[zone].filter(m => m !== id);
        save(next);
    }
    SettingsCard {
        title: "A bar that fits you"
        description: "Choose connected glass or three islands. Every module can move between Left, Center and Right. Changes apply immediately."
        PreferenceSwitch { title: "Activity island"; detail: "Expand media and timers from Activity or Window title modules."; preference: "activityEnabled" }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Shape"; Layout.fillWidth: true }
            LiquidComboBox {
                model: ["Three islands", "Connected pill"]
                currentIndex: ShellState.preferences.barStyle === "islands" ? 0 : 1
                enabled: root.ready
                Accessible.name: "Top bar shape"
                onActivated: ShellState.run("setting", {key: "barStyle", value: currentIndex ? "connected" : "islands"})
            }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Bar text size"; Layout.fillWidth: true }
            LabelText { text: Math.round(fontSize.value) + " px"; color: Theme.accent; font.weight: Font.Bold }
        }
        LiquidSlider {
            id: fontSize
            Layout.fillWidth: true; from: 12; to: 16; stepSize: 1
            enabled: ShellState.backendReady
            Accessible.name: "Top bar font size"
            onPressedChanged: if (!pressed) ShellState.run("setting", {key: "barFontSize", value: Math.round(value)})
            onMoved: if (!pressed) ShellState.run("setting", {key: "barFontSize", value: Math.round(value)})
        }
        Binding { target: fontSize; property: "value"; value: ShellState.preferences.barFontSize || 13; when: !fontSize.pressed; restoreMode: Binding.RestoreNone }
    }
    SettingsCard {
        title: "Make room at the edge"
        description: "Move the horizontal bar to either edge. Popups, tray and the Activity island follow it. Space reserved for applications updates with the bar."
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Screen edge"; Layout.fillWidth: true }
            LiquidComboBox { objectName: "barEdge"; model: ["Top", "Bottom"]; currentIndex: Theme.barBottom ? 1 : 0; Accessible.name: "Bar screen edge"; onActivated: ShellState.run("setting", {key: "barEdge", value: currentIndex ? "bottom" : "top"}) }
        }
        Repeater {
            model: [{key: "barEdgeMargin", title: "Distance from edge", min: 0, max: 64}, {key: "barSideMargin", title: "Side margins", min: 0, max: 160}, {key: "barHeight", title: "Bar height", min: 36, max: 64}]
            delegate: ColumnLayout {
                id: dimension; required property var modelData; Layout.fillWidth: true; spacing: 8
                LabelText { text: dimension.modelData.title + " · " + Math.round(distance.value) + " px"; font.weight: Font.Bold }
                LiquidSlider {
                    id: distance; objectName: dimension.modelData.key; Layout.fillWidth: true; from: dimension.modelData.min; to: dimension.modelData.max; stepSize: 1
                    Accessible.name: dimension.modelData.title
                    onMoved: if (!pressed) ShellState.run("setting", {key: dimension.modelData.key, value: Math.round(value)})
                    onPressedChanged: if (!pressed) ShellState.run("setting", {key: dimension.modelData.key, value: Math.round(value)})
                }
                Binding { target: distance; property: "value"; value: ShellState.preferences[dimension.modelData.key] === undefined ? ({barEdgeMargin: 8, barSideMargin: 12, barHeight: 42})[dimension.modelData.key] : ShellState.preferences[dimension.modelData.key]; when: !distance.pressed; restoreMode: Binding.RestoreNone }
            }
        }
    }
    Repeater {
        model: BarRegistry.zones
        delegate: SettingsCard {
            id: zoneCard
            required property string modelData
            title: modelData.charAt(0).toUpperCase() + modelData.slice(1)
            description: "Drag with the grip, or use the arrows and position menu."
            LabelText { visible: root.layout[zoneCard.modelData].length === 0; text: "Drop a module here"; color: Theme.muted; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
            Repeater {
                model: root.layout[zoneCard.modelData]
                delegate: Rectangle {
                    id: moduleRow
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true; implicitHeight: 56; radius: 16
                    color: rowDrop.containsDrag ? Theme.primaryContainer : Theme.surfaceContainer
                    DropArea {
                        id: rowDrop
                        anchors.fill: parent; keys: ["bar-module"]
                        onDropped: drop => { if (drop.source === proxy) { root.move(proxy.moduleId, zoneCard.modelData, moduleRow.index); drop.acceptProposedAction(); } }
                    }
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 8; spacing: 8
                        Item {
                            Layout.preferredWidth: 30; Layout.fillHeight: true
                            LabelText { anchors.centerIn: parent; text: "⠿"; color: Theme.muted; font.pixelSize: 22 }
                            MouseArea {
                                anchors.fill: parent; enabled: root.ready
                                cursorShape: Qt.SizeAllCursor
                                drag.target: proxy; drag.axis: Drag.XAndYAxis
                                onPressed: {
                                    const p = mapToItem(proxy.parent, 0, 0);
                                    proxy.x = p.x; proxy.y = p.y; proxy.moduleId = moduleRow.modelData; proxy.visible = true;
                                }
                                onPositionChanged: proxy.Drag.active = drag.active
                                onReleased: { proxy.Drag.drop(); proxy.Drag.active = false; proxy.visible = false; }
                                onCanceled: { proxy.Drag.cancel(); proxy.Drag.active = false; proxy.visible = false; }
                            }
                        }
                        ShellIcon { name: BarRegistry.info(moduleRow.modelData).icon; color: Theme.accent; width: 18; height: 18 }
                        LabelText { text: BarRegistry.info(moduleRow.modelData).title; Layout.fillWidth: true; elide: Text.ElideRight; font.weight: Font.Medium }
                        IconButton { glyph: "↑"; implicitWidth: 28; implicitHeight: 32; enabled: root.ready && moduleRow.index > 0; tooltip: "Move module earlier"; onClicked: root.move(moduleRow.modelData, zoneCard.modelData, moduleRow.index - 1) }
                        IconButton { glyph: "↓"; implicitWidth: 28; implicitHeight: 32; enabled: root.ready && moduleRow.index < root.layout[zoneCard.modelData].length - 1; tooltip: "Move module later"; onClicked: root.move(moduleRow.modelData, zoneCard.modelData, moduleRow.index + 2) }
                        LiquidComboBox {
                            Layout.preferredWidth: 116
                            model: ["Left", "Center", "Right"]
                            currentIndex: BarRegistry.zones.indexOf(zoneCard.modelData)
                            enabled: root.ready
                            Accessible.name: BarRegistry.info(moduleRow.modelData).title + " position"
                            onActivated: root.move(moduleRow.modelData, BarRegistry.zones[currentIndex], root.layout[BarRegistry.zones[currentIndex]].length)
                        }
                        IconButton { glyph: "×"; implicitWidth: 28; implicitHeight: 32; enabled: root.ready; tooltip: "Remove " + BarRegistry.info(moduleRow.modelData).title; onClicked: root.remove(moduleRow.modelData) }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 36; radius: 12
                color: appendDrop.containsDrag ? Theme.primaryContainer : "transparent"
                border.color: Theme.outlineVariant; border.width: 1
                LabelText { anchors.centerIn: parent; text: "Drop here to append"; color: Theme.muted; font.pixelSize: 12 }
                DropArea {
                    id: appendDrop
                    anchors.fill: parent; keys: ["bar-module"]
                    onDropped: drop => { if (drop.source === proxy) { root.move(proxy.moduleId, zoneCard.modelData, root.layout[zoneCard.modelData].length); drop.acceptProposedAction(); } }
                }
            }
        }
    }
    SettingsCard {
        title: "Available modules"
        description: "Add a module to Right, then choose its position above. Tray, battery and media hide when unavailable. Crowded groups scroll horizontally."
        Repeater {
            model: BarRegistry.modules.filter(m => !BarRegistry.zones.some(z => root.layout[z].includes(m.id)))
            delegate: RowLayout {
                id: availableRow
                required property var modelData
                Layout.fillWidth: true; spacing: 16
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 4
                    LabelText { text: availableRow.modelData.title; font.weight: Font.Bold }
                    LabelText { text: availableRow.modelData.detail; color: Theme.muted; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
                }
                LiquidButton { text: "Add"; enabled: root.ready; Accessible.name: "Add " + availableRow.modelData.title; onClicked: root.move(availableRow.modelData.id, "right", root.layout.right.length) }
            }
        }
        LiquidButton { text: "Restore default layout"; enabled: root.ready; onClicked: root.save(BarRegistry.clone(BarRegistry.defaults)) }
    }
    Rectangle {
        id: proxy
        parent: root.parent
        property string moduleId: ""
        visible: false; z: 100
        width: 170; height: 44; radius: 16; color: Theme.primaryContainer
        Drag.keys: ["bar-module"]; Drag.source: proxy; Drag.hotSpot.x: 15; Drag.hotSpot.y: 20
        LabelText { anchors.centerIn: parent; text: BarRegistry.info(proxy.moduleId).title; font.weight: Font.Bold }
        // Keep the drag proxy outside layout management.
        Layout.preferredHeight: 0
    }
}
