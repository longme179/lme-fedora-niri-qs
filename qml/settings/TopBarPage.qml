pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../bar"
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 20
    readonly property var layout: ShellState.preferences.barLayout || BarRegistry.defaults
    readonly property bool ready: ShellState.backendReady && !ShellState.pendingActions.setting
    readonly property var cornerKeys: ["topLeft", "topRight", "bottomLeft", "bottomRight"]
    readonly property var cornerPresets: [[-1, -1, -1, -1], [0, 0, 0, 0], [0, -1, 0, -1], [-1, 0, -1, 0]]
    readonly property bool islands: ShellState.preferences.barStyle === "islands"
    readonly property string styleZone: styleTarget.currentIndex > 0 ? BarRegistry.zones[styleTarget.currentIndex - 1] : ""
    readonly property var selectedStyle: styleZone ? Theme.islandStyle(styleZone) : ({})
    readonly property var selectedCorners: Theme.cornersFor(styleZone)
    readonly property int selectedBorderWidth: styleZone ? (selectedStyle.borderWidth === undefined ? 1 : selectedStyle.borderWidth) : Theme.barBorderWidth
    property string pickerField: "borderColor"
    onIslandsChanged: styleTarget.currentIndex = islands ? 1 : 0
    ColorPicker {
        id: borderPicker; parent: Overlay.overlay; anchors.centerIn: parent
        onChosen: color => root.patchStyle(root.pickerField, color.toString())
    }
    function patchStyle(field, value) {
        if (styleZone) ShellState.run("setting", {key: "barIslandStyles", token: styleZone, value: Object.assign({}, selectedStyle, {[field]: value})});
        else if (field === "corners" || field === "borderWidth") ShellState.run("setting", {key: field === "corners" ? "barCorners" : "barBorderWidth", value: value});
        else ShellState.run("setting", {key: "themeOverrides", token: field === "borderColor" ? "barBorder" : "barFill", value: value});
    }
    function styleColor(field) { return selectedStyle[field] || (field === "borderColor" ? Theme.barBorder : Theme.barFill); }
    function corner(key, value) { patchStyle("corners", Object.assign({}, selectedCorners, {[key]: value})); }
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
    SettingsCard {
        title: "Edges and outline"
        description: "Choose the connected bar or one island. Each island has independent corners, fill and outline; changing the connected bar does not reshape islands. Automatic corners follow the bar height; 0 px is square."
        LiquidComboBox {
            id: styleTarget; objectName: "barStyleTarget"; Layout.fillWidth: true
            model: ["Connected bar", "Left island", "Center island", "Right island"]
            Accessible.name: "Bar surface to customize"
            Component.onCompleted: currentIndex = root.islands ? 1 : 0
        }
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: Theme.barHeight + 16
            BarSurface { zone: root.styleZone; anchors.fill: parent; anchors.margins: 8 }
            LabelText { anchors.centerIn: parent; text: "Live bar preview"; font.family: Theme.barFamily; font.pixelSize: Theme.barFontSize; color: Theme.barText }
        }
        LiquidComboBox {
            objectName: "barCornerPreset"; Layout.fillWidth: true
            model: ["Pill", "Square", "Square left end", "Square right end", "Custom corners"]
            currentIndex: {
                const found = root.cornerPresets.findIndex(p => root.cornerKeys.every((key, index) => root.selectedCorners[key] === p[index]));
                return found < 0 ? 4 : found;
            }
            enabled: root.ready; Accessible.name: "Bar corner preset"
            onActivated: {
                if (currentIndex >= root.cornerPresets.length) return;
                const next = {};
                root.cornerKeys.forEach((key, index) => next[key] = root.cornerPresets[currentIndex][index]);
                root.patchStyle("corners", next);
            }
        }
        Repeater {
            model: root.cornerKeys
            delegate: ColumnLayout {
                id: cornerRow; required property string modelData
                Layout.fillWidth: true; spacing: 6
                readonly property bool automatic: root.selectedCorners[modelData] < 0
                RowLayout {
                    Layout.fillWidth: true
                    LabelText { text: Theme.tokenTitle(cornerRow.modelData); font.weight: Font.Bold; Layout.fillWidth: true }
                    LabelText { text: cornerRow.automatic ? "Automatic" : root.selectedCorners[cornerRow.modelData] + " px"; color: Theme.muted }
                    ExpressiveSwitch {
                        checked: cornerRow.automatic; enabled: root.ready
                        Accessible.name: "Automatic " + Theme.tokenTitle(cornerRow.modelData) + " corner"
                        onToggled: root.corner(cornerRow.modelData, checked ? -1 : Math.round(Theme.barHeight / 2))
                    }
                }
                LiquidSlider {
                    id: cornerRadius; objectName: "barCorner-" + cornerRow.modelData
                    Layout.fillWidth: true; from: 0; to: 32; stepSize: 1
                    enabled: root.ready && !cornerRow.automatic
                    Accessible.name: Theme.tokenTitle(cornerRow.modelData) + " corner radius"
                    onMoved: if (!pressed) root.corner(cornerRow.modelData, Math.round(value))
                    onPressedChanged: if (!pressed) root.corner(cornerRow.modelData, Math.round(value))
                }
                Binding { target: cornerRadius; property: "value"; value: Theme.barCornerRadius(cornerRow.modelData, Theme.barHeight, root.styleZone); when: !cornerRadius.pressed; restoreMode: Binding.RestoreNone }
            }
        }
        LabelText { text: "Outline · " + Math.round(outline.value) + " px (0 hides the border)"; font.weight: Font.Bold }
        LiquidSlider {
            id: outline; objectName: "barBorderWidth"; Layout.fillWidth: true; from: 0; to: 4; stepSize: 1
            enabled: root.ready; Accessible.name: "Bar border thickness"
            onMoved: if (!pressed) root.patchStyle("borderWidth", Math.round(value))
            onPressedChanged: if (!pressed) root.patchStyle("borderWidth", Math.round(value))
        }
        Binding { target: outline; property: "value"; value: root.selectedBorderWidth; when: !outline.pressed; restoreMode: Binding.RestoreNone }
        Repeater {
            model: [{key: "borderColor", title: "Border color"}, {key: "fillColor", title: "Fill color"}]
            delegate: ColumnLayout {
                id: colorRow; required property var modelData; Layout.fillWidth: true
                property string error: ""
                readonly property color selectedColor: root.styleColor(modelData.key)
                function sync() { if (hex && !hex.activeFocus) hex.text = selectedColor.toString(); }
                RowLayout {
                    Layout.fillWidth: true
                    LabelText { text: colorRow.modelData.title; Layout.fillWidth: true }
                    IconButton {
                        visible: ShellState.preferences.colorPicker !== false; enabled: root.ready; tooltip: "Choose " + colorRow.modelData.title.toLowerCase()
                        contentItem: Rectangle { color: colorRow.selectedColor; radius: 8; border.width: 1; border.color: Theme.border }
                        onClicked: { root.pickerField = colorRow.modelData.key; borderPicker.initialColor = colorRow.selectedColor; borderPicker.open(); }
                    }
                    ExpressiveField {
                        id: hex; objectName: colorRow.modelData.key === "borderColor" ? "barBorderColor" : "barFillColor"; Layout.preferredWidth: 126; maximumLength: 9
                        text: colorRow.selectedColor.toString(); Accessible.name: colorRow.modelData.title + " hex color"
                        onEditingFinished: {
                            const value = text.trim();
                            if (!/^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(value)) { colorRow.error = "Use #RRGGBB or #AARRGGBB"; return; }
                            colorRow.error = ""; root.patchStyle(colorRow.modelData.key, value);
                        }
                    }
                    LiquidButton { text: "Reset"; enabled: root.ready; onClicked: { colorRow.error = ""; root.patchStyle(colorRow.modelData.key, ""); } }
                }
                onSelectedColorChanged: sync()
                Connections { target: root; function onStyleZoneChanged() { colorRow.error = ""; colorRow.sync(); } }
                LabelText { visible: !!colorRow.error; text: colorRow.error; color: Theme.red; Layout.fillWidth: true }
            }
        }
        LiquidButton { visible: !!root.styleZone; text: "Reset this island"; enabled: root.ready; onClicked: ShellState.run("setting", {key: "barIslandStyles", token: root.styleZone, value: ""}) }
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
