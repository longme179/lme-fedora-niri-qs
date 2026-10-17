pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import QtQuick.Layouts
import "../services"
import "../components"
import "../theme"

Scope {
    Variants {
        model: DesktopState.enabled ? Quickshell.screens : []
        delegate: Scope {
            id: output
            required property var modelData
            Variants {
                model: Object.keys(DesktopState.widgets).filter(id => DesktopState.matches(DesktopState.widgets[id],output.modelData))
                delegate: DesktopWidgetWindow { required property string modelData; widgetId: modelData; screenInfo: output.modelData }
            }
        }
    }
    PanelWindow {
        visible: DesktopState.enabled && DesktopState.editing
        anchors.bottom: true; margins.bottom: 18
        implicitWidth: Math.min(680,screen ? screen.width-28 : 680); implicitHeight: toolbar.implicitHeight+28
        color: "transparent"; exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "lme-desktop-edit"; WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
        GlassPanel { anchors.fill: parent }
        ColumnLayout {
            id: toolbar; anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Editing desktop"; font.weight: Font.Bold; Layout.fillWidth: true }
                LiquidButton { text: "Done"; selected: true; onClicked: DesktopState.editing=false }
            }
            Flow {
                Layout.fillWidth: true; spacing: 8
                Repeater { model: ["clock","notes","media"]; delegate: LiquidButton { required property string modelData; text: "Add " + modelData; enabled: Object.keys(DesktopState.widgets).length<12; onClicked: DesktopState.add(modelData) } }
                LiquidButton { text: "Widget settings"; onClicked: ShellState.openSettingsPage("desktop") }
            }
            LabelText { text: "Drag a header or resize its corner. Widgets stay below apps outside Edit."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12 }
        }
    }
}
