// Role: ImeModule.qml (ime layer, fan-in 2).
// Bar surface item; opens/toggles panels or islands via ShellState/registries.
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

Rectangle {
    id: root

    implicitWidth: label.implicitWidth + 16
    implicitHeight: 30
    radius: 15
    color: Theme.barHover

    Component.onCompleted: ImeState.consumers++
    Component.onDestruction: ImeState.consumers = Math.max(0, ImeState.consumers - 1)

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 4

        LabelText {
            id: label
            text: ImeState.currentIMLabel || "IME"
            color: Theme.text
            font.pixelSize: 12
            Layout.alignment: Qt.AlignVCenter
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
    }
}