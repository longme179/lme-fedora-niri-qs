import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    property bool stopwatch: false
    spacing: 22
    RowLayout {
        Layout.fillWidth: true
        LiquidButton { text: "Focus timer"; Layout.fillWidth: true; palette.button: !root.stopwatch ? Theme.accent : Theme.surface; palette.buttonText: !root.stopwatch ? Theme.background : Theme.text; onClicked: root.stopwatch = false }
        LiquidButton { text: "Stopwatch"; Layout.fillWidth: true; palette.button: root.stopwatch ? Theme.accent : Theme.surface; palette.buttonText: root.stopwatch ? Theme.background : Theme.text; onClicked: root.stopwatch = true }
    }
    LiquidComboBox {
        visible: !root.stopwatch
        Layout.fillWidth: true
        model: ["Focus · 25 minutes", "Short break · 5 minutes", "Long break · 15 minutes"]
        currentIndex: FocusTimer.mode
        onActivated: FocusTimer.selectMode(currentIndex)
        Accessible.name: "Focus timer session"
    }
    Item { Layout.fillHeight: true }
    LabelText {
        text: FocusTimer.format(root.stopwatch ? FocusTimer.stopwatchElapsed : FocusTimer.remaining)
        font.family: Theme.monoFamily; font.pixelSize: 70
        Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
        color: root.stopwatch ? Theme.cyan : Theme.accent
    }
    LabelText { text: root.stopwatch ? "Measure your time." : FocusTimer.running ? "One thing at a time." : "Make room for focused work."; color: Theme.muted; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        LiquidButton {
            text: root.stopwatch ? FocusTimer.stopwatchRunning ? "Pause" : "Start" : FocusTimer.running ? "Pause" : "Start"
            onClicked: { if (root.stopwatch) FocusTimer.toggleStopwatch(); else if (FocusTimer.running) FocusTimer.pause(); else FocusTimer.start(); }
        }
        LiquidButton { text: "Reset"; onClicked: { if (root.stopwatch) FocusTimer.resetStopwatch(); else FocusTimer.reset(); } }
    }
    Item { Layout.fillHeight: true }
    LabelText { text: "The timer keeps running when the panel closes. It resets when the shell restarts."; wrapMode: Text.Wrap; Layout.fillWidth: true; color: Theme.muted; font.pixelSize: 12 }
}
