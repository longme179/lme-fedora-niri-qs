pragma Singleton
import QtQuick

QtObject {
    id: root
    property int mode: 0
    readonly property var durations: [25 * 60, 5 * 60, 15 * 60]
    property int remaining: 25 * 60
    property bool running: false
    property double deadline: 0
    property bool stopwatchRunning: false
    property double stopwatchStarted: 0
    property int stopwatchSaved: 0
    property int stopwatchElapsed: 0
    function format(seconds) {
        const minutes = Math.floor(seconds / 60);
        return String(minutes).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
    }
    function selectMode(value) { running = false; mode = value; remaining = durations[mode]; }
    function start() {
        if (remaining <= 0) remaining = durations[mode];
        deadline = Date.now() + remaining * 1000; running = true;
    }
    function pause() { remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000)); running = false; }
    function reset() { running = false; remaining = durations[mode]; }
    function toggleStopwatch() {
        if (stopwatchRunning) { stopwatchSaved = stopwatchElapsed; stopwatchRunning = false; }
        else { stopwatchStarted = Date.now(); stopwatchRunning = true; }
    }
    function resetStopwatch() { stopwatchRunning = false; stopwatchSaved = 0; stopwatchElapsed = 0; }
    property Timer ticker: Timer {
        interval: 250; repeat: true; running: root.running || root.stopwatchRunning
        onTriggered: {
            if (root.running) {
                root.remaining = Math.max(0, Math.ceil((root.deadline - Date.now()) / 1000));
                if (root.remaining === 0) {
                    root.running = false;
                    Notifications.local(root.mode === 0 ? "Focus session complete" : "Break complete", root.mode === 0 ? "Take a moment to rest." : "Ready for another focus session?");
                }
            }
            if (root.stopwatchRunning)
                root.stopwatchElapsed = root.stopwatchSaved + Math.floor((Date.now() - root.stopwatchStarted) / 1000);
        }
    }
}
