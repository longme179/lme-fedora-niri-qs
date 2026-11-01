pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"

RowLayout {
    id: root
    required property var entry
    required property var inventory
    required property bool busy
    readonly property bool ready: !!entry && !!inventory.available
    visible: ready
    spacing: 8
    LabelText { text: "Output"; font.pixelSize: 12 }
    AudioChoice {
        objectName: "audioRoute-" + (root.entry ? root.entry.id : "")
        Layout.fillWidth: true
        choices: (root.inventory.sinks || []).map(item => ({name:item.id,title:item.title,available:true}))
        actual: root.entry ? root.entry.sinkId : ""; unknownText: "Not linked to a reported output"
        enabled: ShellState.backendReady && !root.busy && root.ready && choices.length > 0
        Accessible.name: (root.entry ? root.entry.title : "Application") + " playback output"
        onChosen: name => ShellState.run("audioRoute", {serverId:root.inventory.serverId,streamId:root.entry.id,sinkId:name})
    }
}
