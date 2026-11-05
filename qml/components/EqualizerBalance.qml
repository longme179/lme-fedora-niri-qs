import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../services"
import "../theme"

// Serpantinum MusicAudioView balance card port: notch scale, center-origin
// fill, L/R percentages and a descriptive center label.
Rectangle {
    id: root
    property var eqData: ({})
    property color accentColor: Theme.accent
    signal balanceMoved(real value)
    implicitHeight: 96
    radius: 16
    color: Theme.alpha(Theme.surfaceContainerHigh, 0.5)
    border.width: 1
    border.color: Theme.outlineVariant

    Item {
        id: scaleArea
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        anchors.topMargin: 12
        height: 46
        opacity: root.eqData && root.eqData.mono === true ? 0.45 : 1.0
        Behavior on opacity { NumberAnimation { duration: 150 } }

        Repeater {
            model: 9
            Rectangle {
                required property int index
                x: index * (scaleArea.width - width) / 8
                anchors.verticalCenter: parent.verticalCenter
                width: index === 4 ? 3 : 2
                height: index === 4 ? 33 : (index % 2 === 0 ? 25 : 18)
                radius: width / 2
                color: Theme.muted
                opacity: index === 4 ? 0.7 : 0.32
            }
        }

        Slider {
            id: balanceSlider
            anchors.fill: parent
            from: -1.0
            to: 1.0
            stepSize: 0.01
            hoverEnabled: true
            enabled: root.eqData && root.eqData.mono !== true
            opacity: enabled ? 1 : 0.35
            readonly property real trackHeight: 14
            readonly property real handleSize: 22

            Component.onCompleted: {
                const initial = Number(root.eqData && root.eqData.balance);
                if (Number.isFinite(initial))
                    value = initial;
            }
            Connections {
                target: root
                function onEqDataChanged() {
                    if (balanceSlider.pressed)
                        return;
                    const next = Number(root.eqData && root.eqData.balance);
                    if (Number.isFinite(next))
                        balanceSlider.value = next;
                }
            }
            onPressedChanged: if (!pressed) root.balanceMoved(value)

            background: Rectangle {
                x: balanceSlider.leftPadding
                y: balanceSlider.topPadding + balanceSlider.availableHeight / 2 - height / 2
                width: balanceSlider.availableWidth
                height: balanceSlider.trackHeight
                radius: height / 2
                color: Theme.sliderTrack

                // Fill grows from the center toward the handle.
                Item {
                    property real handleCenter: balanceSlider.handleSize / 2 + balanceSlider.visualPosition * (parent.width - balanceSlider.handleSize)
                    x: Math.min(parent.width / 2, handleCenter)
                    width: Math.abs(handleCenter - parent.width / 2)
                    height: parent.height
                    clip: true
                    opacity: width > 0.5 ? 1.0 : 0.0
                    Behavior on opacity { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

                    Rectangle {
                        x: balanceSlider.value < 0 ? 0 : -height / 2
                        width: parent.width + height / 2
                        height: parent.height
                        radius: height / 2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop {
                                position: 0.0
                                color: balanceSlider.value < 0 ? Qt.lighter(root.accentColor, 1.10) : root.accentColor
                            }
                            GradientStop { position: 0.5; color: Qt.lighter(root.accentColor, 1.05) }
                            GradientStop {
                                position: 1.0
                                color: balanceSlider.value < 0 ? root.accentColor : Qt.lighter(root.accentColor, 1.10)
                            }
                        }
                    }
                }
            }

            handle: Rectangle {
                id: balanceHandle
                x: balanceSlider.leftPadding + balanceSlider.visualPosition * (balanceSlider.availableWidth - width)
                y: balanceSlider.topPadding + balanceSlider.availableHeight / 2 - height / 2
                width: balanceSlider.handleSize
                height: balanceSlider.handleSize
                radius: height / 2
                color: balanceSlider.pressed ? Qt.lighter(root.accentColor, 1.30)
                    : balanceSlider.hovered ? Qt.lighter(root.accentColor, 1.15)
                    : root.accentColor
                border.width: 2
                border.color: Theme.alpha(Theme.text, 0.25)
                scale: balanceSlider.pressed ? 1.25 : (balanceSlider.hovered ? 1.12 : 1.0)
                Behavior on color { ColorAnimation { duration: 150 } }
                Behavior on scale { NumberAnimation { duration: 150; easing.type: Easing.OutBack } }
            }
        }
    }

    RowLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        anchors.bottomMargin: 10

        LabelText {
            text: "L  " + Math.round((balanceSlider.value > 0 ? 1 - balanceSlider.value : 1) * 100) + "%"
            color: Theme.muted
            font.pixelSize: 11
            font.bold: true
        }
        Item { Layout.fillWidth: true }
        LabelText {
            readonly property real value: balanceSlider.value
            text: Math.abs(value) >= 0.995
                ? (value < 0 ? qsTr("Left only") : qsTr("Right only"))
                : (Math.abs(value) < 0.005 ? qsTr("Centered")
                : (Math.abs(value) < 0.25
                    ? (value < 0 ? qsTr("Slightly left favored") : qsTr("Slightly right favored"))
                    : (value < 0 ? qsTr("Left favored") : qsTr("Right favored"))))
            color: root.accentColor
            font.pixelSize: 11
            font.bold: true
        }
        Item { Layout.fillWidth: true }
        LabelText {
            text: Math.round((balanceSlider.value < 0 ? 1 + balanceSlider.value : 1) * 100) + "%  R"
            color: Theme.muted
            font.pixelSize: 11
            font.bold: true
        }
    }
}
