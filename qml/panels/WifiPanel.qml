import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
GlassPanel {
    property alias connectionPopup: wifi.connectionPopup
    implicitWidth: 560; implicitHeight: 760
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 16
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Network connections"; font.pixelSize: 23; font.weight: Font.Bold; Layout.fillWidth: true }
            IconButton { glyph: "×"; tooltip: "Close networks"; onClicked: ShellState.closePanels() }
        }
        Flickable {
            id: scroll; Layout.fillWidth: true; Layout.fillHeight: true
            contentWidth: width; contentHeight: wifi.implicitHeight + 16; clip: true
            boundsBehavior: Flickable.StopAtBounds; ScrollBar.vertical: ScrollBar {}
            WifiWidget { id: wifi; width: scroll.width - 8 }
        }
    }
}
