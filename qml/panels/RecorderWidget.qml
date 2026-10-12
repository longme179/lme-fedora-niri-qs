import QtQuick
import QtQuick.Layouts
import Quickshell
import "../components"
import "../services"
import "../theme"
Rectangle {
    id: root
    readonly property var recording: ShellState.snapshot.recorder || {active:false}
    readonly property var outputs: Quickshell.screens.map(s=>s.name)
    implicitHeight: content.implicitHeight+28; radius: 20; color: Theme.cardFill
    visible: ShellState.preferences.recordingEnabled !== false
    ColumnLayout {
        id: content; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; spacing: 10
        LabelText { text: root.recording.preparing ? "Checking recording encoder…" : root.recording.finishing ? "Saving recording…" : root.recording.active ? "Screen recording · " + FocusTimer.format(root.recording.elapsed || 0) : "Screen recording"; font.weight: Font.Bold }
        RowLayout {
            Layout.fillWidth: true
            LiquidComboBox { id: output; Layout.fillWidth: true; model: root.outputs; Accessible.name: "Recording output" }
            LiquidComboBox { id: mode; model:["Output","Region"]; Accessible.name:"Recording area" }
        }
        RowLayout {
            Layout.fillWidth: true
            LiquidComboBox { id: audio; objectName: "recordingAudio"; Layout.fillWidth:true; model:["No audio","System audio","Microphone"]; Accessible.name:"Recording audio"; currentIndex: ["none","system","microphone"].indexOf(ShellState.preferences.recordingAudio || "system"); enabled: !root.recording.active; onActivated: ShellState.run("setting", {key:"recordingAudio",value:["none","system","microphone"][currentIndex]}) }
            LiquidButton { text: root.recording.active ? "Stop and save" : "Record"; enabled: !ShellState.demo && ShellState.backendReady && !root.recording.preparing && !root.recording.finishing && !ShellState.pendingActions.recordStart && !ShellState.pendingActions.recordStop && !!output.currentText; onClicked: { if(root.recording.active) ShellState.run("recordStop"); else ShellState.startRecording({mode:mode.currentIndex ? "region" : "output",output:output.currentText,audio:["none","system","microphone"][audio.currentIndex]}); } }
        }
        LabelText { visible: !!root.recording.error; text: root.recording.error || ""; color: Theme.red; wrapMode:Text.Wrap; Layout.fillWidth:true }
        LabelText { visible: !!root.recording.encoder; text: (root.recording.gpu || "") + " · " + root.recording.encoder + (root.recording.fps ? " · " + root.recording.fps + " fps · " + String(root.recording.format || "mkv").toUpperCase() : ""); color: Theme.accent; wrapMode: Text.Wrap; Layout.fillWidth: true }
        LabelText { visible: !!root.recording.audioSource; text: "Audio · " + root.recording.audioSource; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
        LabelText { visible: !!root.recording.fallback; text: "Fallback: " + (root.recording.fallback || ""); color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
        LiquidButton { text: "Recording settings"; onClicked: ShellState.openSettingsPage("behavior") }
        LabelText { text: root.recording.path || (ShellState.preferences.recordingFps || 30) + " fps · " + String(ShellState.preferences.recordingFormat || "mkv").toUpperCase() + " · choose a region within the selected output"; color:Theme.muted; font.pixelSize:12; elide:Text.ElideMiddle; Layout.fillWidth:true }
    }
}
