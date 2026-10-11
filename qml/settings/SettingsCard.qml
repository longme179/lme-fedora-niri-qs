import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"
Rectangle {
    id: root
    property string title: ""
    property string description: ""
    default property alias content: body.data
    Layout.fillWidth: true
    implicitHeight: column.implicitHeight + Theme.cardPadding * 2
    radius: 24
    color: Theme.alpha(Theme.cardFill, 0.78)
    ColumnLayout {
        id: column
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: Theme.cardPadding
        spacing: Theme.cardSpacing
        ColumnLayout {
            visible: root.title.length > 0
            Layout.fillWidth: true; spacing: 6
            LabelText { text: root.title; font.pixelSize: 18; font.weight: Font.Bold; Layout.fillWidth: true; wrapMode: Text.Wrap }
            LabelText { visible: text.length > 0; text: root.description; color: Theme.muted; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
        }
        ColumnLayout { id: body; Layout.fillWidth: true; spacing: Theme.cardSpacing }
    }
}
