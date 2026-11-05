import QtQuick
import QtQuick.Layouts
import "../theme"

// Serpantinum MusicPresetButton grid port; the active preset stays highlighted.
ColumnLayout {
    id: root
    property var eqData: ({})
    property var rows: ["Flat", "Bass", "Treble", "Vocal", "Pop", "Rock", "Jazz", "Classic"]
    property color accentColor: Theme.accent
    signal presetSelected(string name)
    spacing: 8

    Repeater {
        model: [root.rows.slice(0, 4), root.rows.slice(4, 8)]
        delegate: RowLayout {
            id: presetRow
            required property var modelData
            Layout.fillWidth: true
            spacing: 8

            Repeater {
                model: presetRow.modelData
                delegate: Rectangle {
                    id: chip
                    required property string modelData
                    readonly property bool active: root.eqData && root.eqData.preset === modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    radius: height / 2
                    color: active ? root.accentColor : area.containsMouse ? Theme.buttonHover : Theme.buttonFill
                    border.width: active ? 0 : 1
                    border.color: Theme.outlineVariant
                    Behavior on color { ColorMotion {} }

                    LabelText {
                        anchors.centerIn: parent
                        text: chip.modelData
                        color: chip.active ? Theme.onPrimary : Theme.muted
                        font.pixelSize: 12
                        font.weight: chip.active ? Font.DemiBold : Font.Medium
                        Behavior on color { ColorMotion {} }
                    }

                    MouseArea {
                        id: area
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.presetSelected(chip.modelData)
                    }
                }
            }
        }
    }
}
