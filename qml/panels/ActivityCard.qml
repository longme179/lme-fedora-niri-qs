pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 12
    Rectangle {
        visible: ActivityState.recording.active === true
        Layout.fillWidth: true; implicitHeight: recordingContent.implicitHeight + 28
        radius: 20; color: Theme.secondaryContainer
        GlassMaterial { anchors.fill: parent; radius: parent.radius }
        RowLayout {
            id: recordingContent
            anchors.fill: parent; anchors.margins: 14; spacing: 12
            ShellIcon { name: "record"; width: 22; height: 22; color: Theme.red }
            ColumnLayout {
                Layout.fillWidth: true
                LabelText { text: "Recording · " + FocusTimer.format(ActivityState.recording.elapsed || 0); font.weight: Font.Bold; Layout.fillWidth: true }
                LabelText { text: (ActivityState.recording.name || "Recorder") + (ActivityState.recording.owned ? " · captured by this shell" : " · stop in the recording app"); color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
            LiquidButton { visible: !!ActivityState.recording.owned; text: "Stop and save"; enabled: !ShellState.pendingActions.recordStop; onClicked: ShellState.run("recordStop") }
        }
    }
    Rectangle {
        Layout.fillWidth: true; implicitHeight: mediaContent.implicitHeight + 28
        radius: 22; color: Theme.surfaceContainerHigh
        GlassMaterial { anchors.fill: parent; radius: parent.radius }
        MediaAmbient { anchors.fill: parent; anchors.margins: 12; playing: ActivityState.playing }
        ColumnLayout {
            id: mediaContent
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
            spacing: 12
            RowLayout {
                Layout.fillWidth: true; spacing: 12
                Rectangle {
                    width: 62; height: 62; radius: 18; color: Theme.tertiaryContainer; clip: true
                    Image { anchors.fill: parent; source: ActivityState.artwork; retainWhileLoading: true; sourceSize.width: 124; sourceSize.height: 124; asynchronous: true; fillMode: Image.PreserveAspectCrop }
                    ShellIcon { visible: !ActivityState.artwork; anchors.centerIn: parent; width: 28; height: 28; name: "media"; color: Theme.cyan }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 5
                    LabelText { text: ActivityState.track; Layout.fillWidth: true; font.pixelSize: 18; font.weight: Font.Bold; maximumLineCount: 2; wrapMode: Text.Wrap; elide: Text.ElideRight }
                    LabelText { text: ActivityState.artist; Layout.fillWidth: true; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight }
                }
            }
            AudioVisualizer { Layout.fillWidth: true; visible: ActivityState.hasMedia && ShellState.preferences.audioVisualizer === true; playing: ActivityState.playing }
            MediaProgress { objectName: "activityMediaProgress"; Layout.fillWidth: true; player: ActivityState.player; playing: ActivityState.playing }
            RowLayout {
                visible: ActivityState.players.length > 1; Layout.fillWidth: true
                LiquidComboBox {
                    objectName: "activityPlayerSelector"
                    Layout.fillWidth: true; model: ActivityState.players.map(p => p.identity)
                    currentIndex: Math.max(0, ActivityState.players.indexOf(ActivityState.player))
                    onActivated: ActivityState.preferredPlayer = ActivityState.players[currentIndex].dbusName
                }
            }
            MediaActions { Layout.fillWidth: true; player: ActivityState.player; prefix: "activity" }
            LyricsView { Layout.fillWidth: true; player: ActivityState.player }
        }
    }
    Rectangle {
        Layout.fillWidth: true; implicitHeight: timerContent.implicitHeight + 28
        objectName: "activityTimerCard"
        radius: 22; color: Theme.cardFill
        GlassMaterial { anchors.fill: parent; radius: parent.radius }
        ColumnLayout {
            id: timerContent
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                LabelText { text: "Focus timer"; font.weight: Font.Bold; Layout.fillWidth: true; font.pixelSize: 16 }
                LabelText { text: FocusTimer.running ? "Running" : FocusTimer.remaining === 0 ? "Complete" : "Paused"; color: Theme.muted; font.pixelSize: 12 }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 6
                Repeater {
                    model: ["Focus", "Short break", "Long break"]
                    delegate: LiquidButton { required property string modelData; required property int index; objectName: "activityMode-" + index; text: modelData; selected: FocusTimer.mode === index; Layout.fillWidth: true; onClicked: FocusTimer.selectMode(index) }
                }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                LabelText { text: FocusTimer.format(FocusTimer.remaining); font.pixelSize: 34; font.weight: Font.Bold; Layout.fillWidth: true }
                LiquidButton { objectName: "activityTimer"; text: FocusTimer.running ? "Pause" : "Start"; selected: true; onClicked: FocusTimer.running ? FocusTimer.pause() : FocusTimer.start() }
                LiquidButton { objectName: "activityTimerReset"; text: "Reset"; onClicked: FocusTimer.reset() }
            }
            Rectangle { Layout.fillWidth: true; height: 5; radius: 3; color: Theme.alpha(Theme.text, 0.10); Rectangle { width: parent.width * Math.max(0, Math.min(1, 1 - FocusTimer.remaining / FocusTimer.durations[FocusTimer.mode])); height: parent.height; radius: 3; color: Theme.accent } }
        }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 10
        ColumnLayout {
            Layout.fillWidth: true; spacing: 4
            LabelText { text: "Stopwatch"; font.weight: Font.Bold }
            LabelText { text: FocusTimer.format(FocusTimer.stopwatchElapsed); color: Theme.muted; font.pixelSize: 18 }
        }
        LiquidButton { objectName: "activityStopwatch"; text: FocusTimer.stopwatchRunning ? "Pause" : "Start"; onClicked: FocusTimer.toggleStopwatch() }
        LiquidButton { objectName: "activityStopwatchReset"; text: "Reset"; onClicked: FocusTimer.resetStopwatch() }
    }
}
