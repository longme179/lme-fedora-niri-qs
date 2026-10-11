pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 20
    function save(key, value, fonts) {
        const preference = fonts ? "fontOverrides" : "themeOverrides";
        ShellState.run("setting", {key: preference, token: key, value: value.trim()});
    }
    SettingsCard {
        title: "Live element preview"
        description: "Hover and press these controls while editing. They use the same colors, fonts and motion as the desktop."
        Flow {
            Layout.fillWidth: true; spacing: 12
            LiquidButton { objectName: "elementPreviewButton"; text: "Preview" }
            IconButton { iconName: "settings"; tooltip: "Preview icon" }
            ExpressiveSwitch { checked: true; Accessible.name: "Preview switch" }
            ExpressiveField { width: 160; placeholderText: "Preview input"; Accessible.name: "Preview input" }
        }
    }
    SettingsCard {
        title: "Color your elements"
        description: "Change individual UI classes using #RRGGBB or #AARRGGBB (alpha first). Reset returns an element to its inherited palette. Changes apply immediately and save in Appearance profiles."
        RowLayout {
            Layout.fillWidth: true
            LiquidComboBox { id: group; objectName: "elementGroup"; model: Theme.catalog.colors.map(g => g.title); Accessible.name: "Element color group" }
            ExpressiveField { id: filter; Layout.fillWidth: true; placeholderText: "Filter elements"; Accessible.name: "Filter theme elements" }
        }
        Repeater {
            model: (Theme.catalog.colors[group.currentIndex] || {tokens: []}).tokens.filter(key => Theme.tokenTitle(key).toLowerCase().includes(filter.text.toLowerCase()))
            delegate: ColumnLayout {
                id: row
                required property string modelData
                Layout.fillWidth: true; spacing: 4
                property string error: ""
                function apply() {
                    const value = hex.text.trim();
                    if (!/^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(value)) { error = "Use #RRGGBB or #AARRGGBB"; return; }
                    error = ""; root.save(modelData, value, false);
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    Rectangle { Layout.preferredWidth: 26; Layout.preferredHeight: 26; radius: 9; color: Theme.tokenColor(row.modelData); border.width: 1; border.color: Theme.border }
                    LabelText { text: Theme.tokenTitle(row.modelData); Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Medium }
                    ExpressiveField {
                        id: hex; objectName: "element-" + row.modelData; Layout.preferredWidth: 126; maximumLength: 9
                        text: (ShellState.preferences.themeOverrides || {})[row.modelData] || Theme.tokenColor(row.modelData).toString()
                        Accessible.name: Theme.tokenTitle(row.modelData) + " hex color"
                        onAccepted: row.apply()
                    }
                    LiquidButton { text: "Apply"; enabled: ShellState.backendReady; Accessible.name: "Apply " + Theme.tokenTitle(row.modelData); onClicked: row.apply() }
                    IconButton { glyph: "↺"; tooltip: "Reset " + Theme.tokenTitle(row.modelData); enabled: ShellState.backendReady; onClicked: { row.error = ""; root.save(row.modelData, "", false); } }
                }
                LabelText { visible: !!row.error; text: row.error; color: Theme.red; Layout.fillWidth: true }
                Connections { target: ShellState; function onPreferencesChanged() { if (!hex.activeFocus) hex.text = (ShellState.preferences.themeOverrides || {})[row.modelData] || Theme.tokenColor(row.modelData).toString(); } }
            }
        }
        LiquidButton { text: "Reset all element colors"; onClicked: ShellState.run("setting", {key: "themeOverrides", value: {}}) }
    }
    SettingsCard {
        title: "Type that feels like you"
        description: "Enter an installed font family name. Qt uses a fallback when that font is missing. Headings keep their bold weight; uncustomized roles follow the body family."
        Repeater {
            model: Theme.catalog.fonts
            delegate: ColumnLayout {
                id: fontRow; required property var modelData
                Layout.fillWidth: true; spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    LabelText { text: fontRow.modelData.title; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.Wrap; font.weight: Font.Bold }
                    ExpressiveField { id: family; objectName: "font-" + fontRow.modelData.key; Layout.preferredWidth: 230; Layout.minimumWidth: 120; maximumLength: 80; text: Theme.fontFor(fontRow.modelData.key); Accessible.name: fontRow.modelData.title + " font family"; onAccepted: root.save(fontRow.modelData.key, text, true) }
                    LiquidButton { text: "Apply"; enabled: !!family.text.trim() && ShellState.backendReady; Accessible.name: "Apply " + fontRow.modelData.title + " font"; onClicked: root.save(fontRow.modelData.key, family.text, true) }
                    IconButton { glyph: "↺"; tooltip: "Reset " + fontRow.modelData.title + " font"; onClicked: root.save(fontRow.modelData.key, "", true) }
                }
                LabelText { text: "The quick brown fox · 0123456789"; font.family: family.text || Theme.fontFamily; font.weight: fontRow.modelData.key === "heading" ? Font.Bold : Font.Normal; Layout.fillWidth: true; elide: Text.ElideRight }
                Connections { target: ShellState; function onPreferencesChanged() { if (!family.activeFocus) family.text = Theme.fontFor(fontRow.modelData.key); } }
            }
        }
        LabelText { text: "Body size · " + Math.round(bodySize.value) + " px"; font.weight: Font.Bold }
        LiquidSlider { id: bodySize; Layout.fillWidth: true; from: 12; to: 20; stepSize: 1; Accessible.name: "Body text size"; onMoved: if (!pressed) ShellState.run("setting", {key: "fontSize", value: Math.round(value)}); onPressedChanged: if (!pressed) ShellState.run("setting", {key: "fontSize", value: Math.round(value)}) }
        Binding { target: bodySize; property: "value"; value: Theme.bodySize; when: !bodySize.pressed; restoreMode: Binding.RestoreNone }
        LiquidButton { text: "Reset font overrides"; onClicked: ShellState.run("setting", {key: "fontOverrides", value: {}}) }
    }
}
