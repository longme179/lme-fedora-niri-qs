import QtQuick
import QtQuick.Layouts
import "../services"
import "../theme"

// Serpantinum MusicAudioView port: balance card, mono/swap toggles and the
// three-mode dynamic range selector, all driving EqualizerState directly.
// Shared by the shell panel and the Settings page.
ColumnLayout {
    id: root
    property var eqData: EqualizerState.eqData
    property color accentColor: Theme.accent
    property real introBalance: 1
    property real introFlags: 1
    property real introDynamics: 1
    spacing: 8

    EqualizerBalance {
        Layout.fillWidth: true
        eqData: root.eqData
        accentColor: root.accentColor
        opacity: root.introBalance
        transform: Translate { y: 14 * (1 - root.introBalance) }
        onBalanceMoved: value => EqualizerState.setBalance(value)
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        opacity: root.introFlags
        transform: Translate { y: 14 * (1 - root.introFlags) }

        Repeater {
            model: [{key: "mono", label: qsTr("Mono audio")}, {key: "swap", label: qsTr("Swap L/R")}]
            delegate: Rectangle {
                id: flagCard
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                radius: 16
                color: Theme.alpha(Theme.surfaceContainerHigh, 0.5)
                border.width: 1
                border.color: Theme.outlineVariant

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 10
                    spacing: 8

                    LabelText {
                        text: flagCard.modelData.label
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    ExpressiveSwitch {
                        checked: root.eqData && root.eqData[flagCard.modelData.key] === true
                        onToggled: {
                            const requested = checked;
                            checked = Qt.binding(() => root.eqData && root.eqData[flagCard.modelData.key] === true);
                            EqualizerState.setFlag(flagCard.modelData.key, requested);
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: 48
        radius: 16
        color: Theme.alpha(Theme.surfaceContainerHigh, 0.5)
        border.width: 1
        border.color: Theme.outlineVariant
        opacity: root.introDynamics
        transform: Translate { y: 14 * (1 - root.introDynamics) }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 10
            spacing: 8

            LabelText {
                text: qsTr("Dynamic range")
                font.pixelSize: 12
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }
            SegmentSwitch {
                pillHeight: 28
                accentColor: root.accentColor
                options: [qsTr("Off"), qsTr("Balanced"), qsTr("Night")]
                currentIndex: root.eqData && root.eqData.dynamics === "night" ? 2
                    : (root.eqData && root.eqData.dynamics === "balanced" ? 1 : 0)
                onActivated: index => EqualizerState.setDynamics(["off", "balanced", "night"][index])
            }
        }
    }
}
