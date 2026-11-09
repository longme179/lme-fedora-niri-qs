// Role: BluetoothState.qml (bluetooth layer, fan-in 3) — pairing agent host + native adapter/device state (plan Q1)
// and the Q3 device/radio writes (scripts/audio_actions.py's bluetooth handlers).
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

    // ---- Q3 write path: the router's bluetooth leg (scripts/audio_actions.py's
    // bluetoothToggle/bluetoothDevice over scripts/desktop_backend.py::set_bluetooth).
    // Pairing stays with the agent above. INVARIANT: the user-facing strings are the
    // backend's exact contract (tests/test_native_controls.py). ----

    readonly property var handledActions: ["bluetoothToggle", "bluetoothDevice"]
    function handles(action) { return handledActions.includes(action); }

    // Pure admission for the router: enabling through an rfkill block falls back to the
    // backend registry (it can unblock rfkill and retry — quickshell has no rfkill API);
    // turning the radio off always routes natively. Unknown flags (backend not ready yet)
    // route natively — the write confirmation catches a real block.
    function toggleRoutes(enabled, softBlocked, hardBlocked) {
        return enabled || !(softBlocked === true || hardBlocked === true);
    }

    // Port of scripts/audio_actions.py::bluetooth_device's validation: the org.bluez path
    // shape, a boolean state and membership in the live device set (all adapters — a
    // superset of the backend's selected-adapter section; the UI only offers those).
    function deviceProblem(request, paths) {
        const path = request && request.path, connected = request && request.connected;
        if (typeof path !== "string"
                || !/^\/org\/bluez\/hci[0-9]+\/dev_([0-9A-Fa-f]{2}_){5}[0-9A-Fa-f]{2}$/.test(path)
                || typeof connected !== "boolean" || !paths.includes(path))
            return "Unknown Bluetooth device or state";
        return "";
    }

    // The sectionFor selection rule over live objects: the preferred adapter, else first.
    function selectedAdapter() {
        for (const item of Bluetooth.adapters.values)
            if (item.dbusPath === adapter) return item;
        return Bluetooth.adapters.values[0] || null;
    }

    function nativeDevicePaths() {
        const paths = [];
        for (const item of Bluetooth.adapters.values)
            for (const device of item.devices.values)
                paths.push(device.dbusPath);
        return paths;
    }

    function findDevice(path) {
        for (const item of Bluetooth.adapters.values)
            for (const device of item.devices.values)
                if (device.dbusPath === path) return device;
        return null;
    }

    function canRoute(action, payload, context) {
        if (!Bluetooth.adapters.values.length) return false;  // backend: canonical adapter error
        if (action === "bluetoothDevice") return true;
        if (action === "bluetoothToggle") {
            const item = selectedAdapter();
            if (!item) return false;
            const bluetooth = (context && context.system ? context.system.bluetooth : null) || {};
            return toggleRoutes(item.enabled, bluetooth.softBlocked, bluetooth.hardBlocked);
        }
        return false;
    }

    function perform(action, request, done, context) {
        if (action === "bluetoothToggle") {
            const item = selectedAdapter();
            if (!item) return done(false, "No Bluetooth adapter is available. Check bluetooth.service and the adapter firmware.");
            const enabling = !item.enabled;
            item.enabled = enabling;
            toggleConfirm.enabling = enabling; toggleConfirm.done = done; toggleConfirm.ticks = 0;
            toggleConfirm.restart();
            return;
        }
        if (deviceTarget) return done(false, "An audio device operation is already running.");
        const problem = deviceProblem(request, nativeDevicePaths());
        if (problem) return done(false, problem);
        const device = findDevice(String(request.path));
        const wanted = request.connected === true;
        if (!device || device.connected === wanted)
            return done(true, wanted ? "Bluetooth device connected" : "Bluetooth device disconnected");
        deviceTarget = device; deviceDone = done; deviceWanted = wanted;
        device.connected = wanted;  // setConnected -> connect()/disconnect()
        deviceTimeout.restart();
    }

    // set_bluetooth's confirmation loop: three 120 ms re-checks backend-side; BlueZ property
    // writes can lag, so the native poll keeps the same cadence with a wider ceiling and
    // the same terminal message.
    property Timer toggleConfirm: Timer {
        interval: 120
        property int ticks: 0
        property bool enabling: false
        property var done: null
        onTriggered: {
            const item = root.selectedAdapter();
            if (item && item.enabled === enabling) {
                const done = toggleConfirm.done; toggleConfirm.done = null;
                if (done) done(true, "Bluetooth turned " + (enabling ? "on" : "off"));
                return;
            }
            if (++ticks >= 8) {
                const done = toggleConfirm.done; toggleConfirm.done = null;
                if (done) done(false, "BlueZ did not confirm the requested power state. Check journalctl -b -u bluetooth and rfkill list bluetooth.");
                return;
            }
            restart();
        }
    }

    // busctl Connect/Disconnect's 15 s ceiling, event-driven: the connection settles when
    // the device reports the wanted state (a failure never signals — the timeout speaks).
    property var deviceTarget: null
    property var deviceDone: null
    property bool deviceWanted: false
    property Timer deviceTimeout: Timer {
        interval: 15000
        onTriggered: root.finishDevice(false, "Bluetooth device did not respond. Check the device and try again.")
    }
    property Connections deviceWatch: Connections {
        target: root.deviceTarget
        function onConnectedChanged() {
            if (root.deviceTarget && root.deviceTarget.connected === root.deviceWanted)
                root.finishDevice(true, root.deviceWanted ? "Bluetooth device connected" : "Bluetooth device disconnected");
        }
    }
    function finishDevice(ok, message) {
        const done = deviceDone;
        deviceTarget = null; deviceDone = null;
        deviceTimeout.stop();
        if (done) done(ok, message);
    }
}
