import QtQuick
import "../theme"

// Animated pill segment control (Serpantinum Switch port); drives tabs and modes.
Rectangle {
    id: root
    property var options: []
    property int currentIndex: 0
    property real pillHeight: 30
    property color accentColor: Theme.accent
    signal activated(int index)
    implicitWidth: row.implicitWidth + 8
    implicitHeight: pillHeight + 8
    radius: height / 2
    color: Theme.alpha(Theme.surfaceContainerHigh, 0.5)
    border.width: 1
    border.color: Theme.outlineVariant

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 4

        Repeater {
            model: root.options
            delegate: Rectangle {
                id: segment
                required property string modelData
                required property int index
                readonly property bool active: root.currentIndex === index
                width: label.implicitWidth + 22
                height: root.pillHeight
                radius: height / 2
                color: active ? root.accentColor : area.containsMouse ? Theme.buttonHover : "transparent"
                Behavior on color { enabled: Theme.animations; ColorMotion {} }

                LabelText {
                    id: label
                    anchors.centerIn: parent
                    text: segment.modelData
                    color: segment.active ? Theme.onPrimary : Theme.muted
                    font.pixelSize: 12
                    font.weight: segment.active ? Font.DemiBold : Font.Medium
                    Behavior on color { enabled: Theme.animations; ColorMotion {} }
                }

                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (root.currentIndex === segment.index)
                            return;
                        root.currentIndex = segment.index;
                        root.activated(segment.index);
                    }
                }
            }
        }
    }
}
