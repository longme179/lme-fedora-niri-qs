import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"
GlassPanel {
    implicitWidth:700; implicitHeight:700
    ColumnLayout {
        anchors.fill:parent; anchors.margins:24; spacing:16
        RowLayout {
            Layout.fillWidth:true
            LabelText { text:"Launchpad"; font.pixelSize:24; font.weight:Font.Bold; Layout.fillWidth:true }
            IconButton { glyph:"×"; tooltip:"Close Launchpad"; onClicked:ShellState.closePanels() }
        }
        ScrollView {
            Layout.fillWidth:true; Layout.fillHeight:true; clip:true; contentWidth:availableWidth
            LaunchpadEditor { width:parent.width }
        }
    }
}
