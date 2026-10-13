pragma ComponentBehavior: Bound
// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Avenge Media LLC
// Adapted installed-family enumeration from SettingsFontDropdownRow.qml (6640a943).
// Modified: LME editable field, searchable popup, no DMS runtime dependencies.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../services"
import "../theme"
ExpressiveField {
    id: root
    property var families: []
    signal fontSelected(string family)
    rightPadding: ShellState.preferences.fontPicker === false ? 12 : 42
    maximumLength: 80
    Component.onCompleted: Qt.callLater(() => families=Qt.fontFamilies().filter(f => !f.startsWith(".")).sort((a,b) => a.localeCompare(b)))
    IconButton {
        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        visible: ShellState.preferences.fontPicker !== false
        objectName: root.objectName + "-menu"
        glyph: "⌄"; implicitWidth: 32; implicitHeight: 32; tooltip: "Choose installed font"
        onClicked: { search.text=""; menu.open(); search.forceActiveFocus(); }
    }
    Popup {
        id: menu
        width: Math.max(300,root.width); height: 340; y: root.height + 6
        padding: 12; closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: GlassPanel { radius: 20 }
        enter: Transition { ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.animationDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.effectsCurve }
            NumberAnimation { property: "scale"; from: .97; to: 1; duration: Theme.animationDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.effectsCurve }
        } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Math.round(120 / Theme.motionSpeed) * (Theme.animations ? 1 : 0); easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.effectsCurve } }
        contentItem: ColumnLayout {
            ExpressiveField {
                id: search; objectName: "fontSearch"; Layout.fillWidth: true
                placeholderText: "Search installed fonts"; Accessible.name: "Search installed fonts"
                onAccepted: if (list.count) root.choose(list.model[0])
                Keys.onDownPressed: { list.currentIndex=0; list.forceActiveFocus(); }
            }
            ListView {
                id: list; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                model: root.families.filter(f => f.toLowerCase().includes(search.text.trim().toLowerCase()))
                currentIndex: -1; boundsBehavior: Flickable.StopAtBounds
                spacing: 4
                header: Item { height: 4 }
                footer: Item { height: 4 }
                ScrollBar.vertical: ScrollBar {}
                Keys.onReturnPressed: if (currentIndex>=0) root.choose(model[currentIndex])
                delegate: Item {
                    id: fontRow
                    required property string modelData
                    required property int index
                    width: list.width; height: option.implicitHeight + 8
                    LiquidButton {
                        id: option; x: 4; y: 4; width: parent.width - 12
                        text: fontRow.modelData; font.family: fontRow.modelData
                        selected: list.currentIndex === fontRow.index
                        onClicked: root.choose(fontRow.modelData)
                    }
                }
            }
            LabelText { visible: !list.count; text: "No installed fonts match"; color: Theme.muted }
        }
    }
    function choose(family) { root.text=family; fontSelected(family); menu.close(); root.forceActiveFocus(); }
}
