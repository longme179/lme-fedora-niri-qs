pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    property var consumers: []
    property var state: ({ready: false, devices: [], request: {}})
    property string error: ""
    property bool failed: false
    property bool restartOnExit: false
    readonly property string adapter: ShellState.preferences.bluetoothAdapter || ShellState.system.bluetooth?.adapter || ""
    readonly property bool wanted: consumers.length > 0 && !ShellState.demo && !ShellState.settingsApp && ShellState.preferences.bluetoothPairing !== false
    readonly property var request: state.request || {}
    onWantedChanged: {
        if (wanted) { failed = false; if (stopDeadline.running && agent.running) restartOnExit = true; else start(); }
        else if (agent.running) { send({action: "close"}); stopDeadline.restart(); }
    }
    onAdapterChanged: if (agent.running) send({action: "watch", adapter: adapter})
    function watch(consumer, enabled) {
        const next = consumers.filter(item => item !== consumer);
        if (enabled) next.push(consumer);
        consumers = next;
    }
    function start() { if (wanted && !agent.running) { state = {ready: false, devices: [], request: {}}; error = ""; agent.running = true; } }
    function send(data) { if (agent.running) agent.write(JSON.stringify(data) + "\n"); }
    function scan(enabled) { send({action: "scan", enabled: enabled}); }
    function pair(path) { send({action: "pair", path: path}); }
    function reply(token, accepted, value) { send({action: "reply", token: token, accept: accepted, value: value || ""}); }
    function cancel() { send({action: "cancel"}); }
    function retry() { failed = false; if (agent.running) { restartOnExit = true; agent.running = false; } else start(); }
    Timer { id: stopDeadline; interval: 2000; onTriggered: if (!root.wanted) agent.running = false }
    Process {
        id: agent
        // Gio is supplied by Fedora's system Python / python3-gobject-base.
        command: ["/usr/bin/python3", "-u", Quickshell.shellPath("scripts/bluetooth_agent.py")]
        stdinEnabled: true
        onStarted: root.send({action: "watch", adapter: root.adapter})
        stdout: SplitParser {
            onRead: line => {
                try {
                    const value = JSON.parse(line);
                    root.state = value;
                    root.error = value.error || "";
                } catch (error) { root.error = "Invalid Bluetooth agent response"; }
            }
        }
        // Quickshell 0.3.2 does not export QProcess::ExitStatus to qmllint; the handler does not use it.
        // qmllint disable signal-handler-parameters
        onExited: {
            stopDeadline.stop(); root.state = {ready: false, devices: [], request: {}};
            if (root.restartOnExit) { root.restartOnExit = false; Qt.callLater(root.start); }
            else if (root.wanted) { root.failed = true; if (!root.error) root.error = "Bluetooth pairing agent stopped. Retry to reconnect."; }
        }
    }
}
