pragma ComponentBehavior: Bound
import QtQuick
import "../services"
import "../theme"
Item {
    id: root
    visible: ShellState.preferences.audioVisualizer === true
    property bool playing: false
    readonly property bool wanted: visible && playing && ShellState.preferences.audioVisualizer === true && !ShellState.demo
    property bool subscribed: false
    implicitHeight: ShellState.preferences.audioVisualizer === true ? 38 : 0
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
                Behavior on height { NumberAnimation { duration: Theme.animations ? 50 : 0 } }
            }
        }
    }
    LabelText { anchors.fill: parent; text: VisualizerState.error; font.pixelSize: 12; color: Theme.muted; wrapMode: Text.Wrap; visible: !!text }
}
