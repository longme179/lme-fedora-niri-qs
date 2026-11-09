// Role: BluetoothState.qml (bluetooth layer, fan-in 3) — pairing agent host + native adapter/device state (plan Q1).
// Shared component/helper; keep API stable for wide QML reuse.
// REL: Quickshell.Bluetooth::Bluetooth – defaultAdapter/adapters/devices; BluetoothAdapter.enabled/.dbusPath;
// BluetoothDevice.paired/.connected/.battery. INVARIANT: sectionFor() mirrors scripts/desktop_backend.py::bluetooth()
// (tests/test_native_state.py); rfkill soft/hard-block flags have no native API and stay backend-fed until Q6.
// GOTCHA: this singleton is created while the merged-system binding evaluates — never read that merged
// property from here (binding loop); preferences/demo/settingsApp reads are safe (different properties).
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Bluetooth
import "PeripheralIdentity.js" as Peripheral

Singleton {
    id: root
    property var consumers: []
    property var state: ({ready: false, devices: [], request: {}})
    property string error: ""
    property bool failed: false
    property bool restartOnExit: false
    readonly property string adapter: ShellState.preferences.bluetoothAdapter || nativeAdapterPath
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

    // Native section (Q1): preferred adapter selection mirrors the backend — the
    // preference path when it exists, else the first adapter. `batteries` carries
    // every paired-or-connected device across ALL adapters (peripheral merge input);
    // `devices` is scoped to the selected adapter like the backend section.
    readonly property var nativeAdapters: Bluetooth.adapters.values.map(adapter => ({
        path: adapter.dbusPath, name: adapter.name, enabled: adapter.enabled
    }))
    readonly property string nativeAdapterPath: Bluetooth.defaultAdapter ? Bluetooth.defaultAdapter.dbusPath : ""

    function sectionFor(preferred) {
        const adapters = nativeAdapters;
        const selected = adapters.find(item => item.path === preferred) || adapters[0] || null;
        const section = {available: !!selected, enabled: selected ? selected.enabled : false,
                         adapters: adapters, devices: [], batteries: [], adapter: selected ? selected.path : ""};
        for (const adapter of Bluetooth.adapters.values) {
            for (const device of adapter.devices.values) {
                if (!device.paired && !device.connected) continue;
                const record = nativeDevice(device);
                section.batteries.push(record);
                if (selected && record.path.startsWith(selected.path + "/dev_")) section.devices.push(record);
            }
        }
        return section;
    }

    // Port of scripts/peripheral_values.py::bluetooth_device over the Quickshell device API.
    function nativeDevice(device) {
        return {path: device.dbusPath, id: Peripheral.identity(device.address, "bluez:" + device.dbusPath),
                name: device.name || device.deviceName || device.address || "Bluetooth device",
                kind: Peripheral.kind(device.icon || device.name),
                connected: device.connected, paired: device.paired,
                percentage: device.connected && device.batteryAvailable ? Math.round(device.battery * 100) : null,
                charging: null};
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
