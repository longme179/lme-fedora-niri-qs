// SPDX-License-Identifier: GPL-3.0-or-later
// HSV workflow reviewed against DMS ColorPickerContent / DSaturationValuePicker (MIT).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"
Popup {
    id: root
    property color initialColor: Theme.accent
    property real hue: 0
    property real saturation: 0
    property real value: 1
    property real alpha: 1
    property color parsedColor: initialColor
    readonly property color selectedColor: Qt.hsva(hue,saturation,value,alpha)
    signal chosen(color color)
    width: 350; height: contentItem.implicitHeight + 32; padding: 16
    modal: true; closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: GlassPanel { radius: 24 }
    onOpened: { error.text=""; load(initialColor); hex.text=selectedColor.toString(); }
    onSelectedColorChanged: if (!hex.activeFocus) hex.text=selectedColor.toString()
    function load(color) {
        parsedColor=color; hue=Math.max(0,parsedColor.hsvHue);
        saturation=parsedColor.hsvSaturation; value=parsedColor.hsvValue; alpha=parsedColor.a;
    }
    contentItem: ColumnLayout {
        spacing: 12
        LabelText { text: "Choose element color"; font.weight: Font.Bold; font.pixelSize: 18 }
        Item {
            id: sv; Layout.fillWidth: true; Layout.preferredHeight: 180
            activeFocusOnTab: true
            Accessible.role: Accessible.Slider; Accessible.name: "Saturation and value; use arrow keys"
            function pick(x,y) { root.saturation=Math.max(0,Math.min(1,x/width)); root.value=1-Math.max(0,Math.min(1,y/height)); }
            Keys.onPressed: event => {
                const step=event.modifiers & Qt.ShiftModifier ? .1 : .01;
                if (event.key===Qt.Key_Left) root.saturation=Math.max(0,root.saturation-step);
                else if (event.key===Qt.Key_Right) root.saturation=Math.min(1,root.saturation+step);
                else if (event.key===Qt.Key_Up) root.value=Math.min(1,root.value+step);
                else if (event.key===Qt.Key_Down) root.value=Math.max(0,root.value-step);
                else return;
                event.accepted=true;
            }
            Rectangle { anchors.fill: parent; gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "white" } GradientStop { position: 1; color: Qt.hsva(root.hue,1,1,1) } } }
            Rectangle { anchors.fill: parent; gradient: Gradient { GradientStop { position: 0; color: "transparent" } GradientStop { position: 1; color: "black" } } }
            Rectangle { width: 14; height: 14; radius: 7; x: Math.max(0,Math.min(sv.width-width,root.saturation*sv.width-width/2)); y: Math.max(0,Math.min(sv.height-height,(1-root.value)*sv.height-height/2)); color: "transparent"; border.width: 2; border.color: "white" }
            Rectangle { anchors.fill: parent; color: "transparent"; border.width: sv.activeFocus ? 2 : 0; border.color: Theme.accent }
            MouseArea { anchors.fill: parent; onPressed: event => { sv.forceActiveFocus(); sv.pick(event.x,event.y); } onPositionChanged: event => { if(pressed) sv.pick(event.x,event.y); } }
        }
        LabelText { text: "Hue"; font.weight: Font.Bold }
        LiquidSlider { id: h; Layout.fillWidth: true; from: 0; to: 1; stepSize: .001; value: root.hue; Accessible.name: "Hue"; onMoved: root.hue=value }
        LabelText { text: "Opacity · " + Math.round(root.alpha*100) + "%"; font.weight: Font.Bold }
        LiquidSlider { Layout.fillWidth: true; from: 0; to: 1; stepSize: .01; value: root.alpha; Accessible.name: "Color opacity"; onMoved: root.alpha=value }
        RowLayout {
            Rectangle { Layout.preferredWidth: 38; Layout.preferredHeight: 38; radius: 12; color: root.selectedColor; border.width: 1; border.color: Theme.border }
            ExpressiveField {
                id: hex; objectName: "pickerHex"; Layout.fillWidth: true; maximumLength: 9
                text: root.selectedColor.toString(); Accessible.name: "Hex color; alpha first"
                onAccepted: { if (/^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(text)) { root.load(text); error.text=""; } else error.text="Use #RRGGBB or #AARRGGBB"; }
            }
        }
        LabelText { id: error; visible: !!text; color: Theme.red; Layout.fillWidth: true }
        RowLayout {
            Item { Layout.fillWidth: true }
            LiquidButton { text: "Cancel"; onClicked: root.close() }
            LiquidButton { text: "Apply color"; onClicked: { if (/^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(hex.text)) { root.load(hex.text); root.chosen(root.selectedColor); root.close(); } else error.text="Use #RRGGBB or #AARRGGBB"; } }
        }
    }
}
