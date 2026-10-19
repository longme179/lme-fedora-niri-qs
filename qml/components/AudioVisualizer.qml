pragma ComponentBehavior: Bound
import QtQuick
import "../services"
import "../theme"
Item {
    id: root
    readonly property bool spectrumEnabled: !ShellState.batterySaverActive && ShellState.preferences.audioVisualizer === true
    visible: spectrumEnabled
    property bool playing: false
    readonly property bool wanted: visible && playing && ShellState.preferences.audioVisualizer === true && !ShellState.demo
    property bool subscribed: false
    implicitHeight: spectrumEnabled ? 38 : 0
    function sync() { if (wanted===subscribed) return; if(wanted) VisualizerState.addRef(); else VisualizerState.removeRef(); subscribed=wanted; }
    onWantedChanged: sync()
    Component.onCompleted: sync()
    Component.onDestruction: if(subscribed) VisualizerState.removeRef()
    Row {
        anchors.fill: parent; spacing: 3; visible: !VisualizerState.error
        Repeater {
            model: 16
            delegate: Rectangle {
                required property int index
                width: Math.max(1,(root.width-45)/16); height: Math.max(2,root.height*(VisualizerState.bars[index] || 0)); anchors.bottom: parent.bottom
                radius: 2; color: Theme.accent
                // Cava smooths the signal; another animation here delays every new frame.
            }
        }
    }
    LabelText { anchors.fill: parent; text: VisualizerState.error; font.pixelSize: 12; color: Theme.muted; wrapMode: Text.Wrap; visible: !!text }
}
