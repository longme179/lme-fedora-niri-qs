// Role: PowerState.qml (power layer, fan-in 2) — native battery/AC, power profiles, UPower peripherals (plan Q1).
// REL: Quickshell.Services.UPower::UPower – displayDevice/onBattery/devices; PowerProfiles – profile/hasPerformanceProfile.
// INVARIANT: section shapes mirror scripts/desktop_backend.py::battery()/power_profile()/power_profiles()
// and scripts/peripheral_battery.py::kernel_batteries (tests/test_native_state.py freezes them).
// Known fidelity edges (A/B window catches both): without power-profiles-daemon PowerProfiles keeps its
// default enum (the section reports "power-saver" where the backend reported null); UPower peripheral ids
// use the UPower native path where the backend used the sysfs node name.
pragma Singleton
import QtQuick
import Quickshell.Io
import Quickshell.Services.UPower
import "PeripheralIdentity.js" as Peripheral

QtObject {
    id: root

    readonly property var battery: {
        const device = UPower.displayDevice;
        if (!device || !device.isLaptopBattery || !device.isPresent)
            return {available: false, percent: null, charging: false, acOnline: !UPower.onBattery,
                    devices: [], health: null, powerW: null, secondsRemaining: null};
        const devices = laptopBatteries().map(batteryDetails);
        const health = devices.map(item => item.health).filter(value => value !== null);
        const power = devices.filter(item => item.powerW !== null);
        return {available: true, percent: percent100(device.percentage),
                charging: device.state === UPowerDeviceState.Charging, acOnline: !UPower.onBattery,
                devices: devices,
                health: health.length ? round1(health.reduce((sum, value) => sum + value, 0) / health.length) : null,
                powerW: devices.length && power.length === devices.length ? round2(power.reduce((sum, item) => sum + item.powerW, 0)) : null,
                secondsRemaining: devices.length === 1 ? devices[0].secondsRemaining : null};
    }

    readonly property string profile: ["power-saver", "balanced", "performance"][PowerProfiles.profile] || "power-saver"

    readonly property var profiles: PowerProfiles.hasPerformanceProfile
        ? ["power-saver", "balanced", "performance"] : ["power-saver", "balanced"]

    // UPower peripheral supplies (mice, keyboards, headsets): the native counterpart
    // of scripts/peripheral_battery.py::kernel_batteries; NativeState merges the
    // BlueZ device batteries on top (merge_batteries order).
    readonly property var upowerPeripherals: UPower.devices.values.filter(device => device.isPresent && !device.isLaptopBattery).map(device => ({
        id: "power_supply:" + String(device.nativePath || "").split("/").filter(Boolean).pop(),
        name: device.model || String(device.nativePath || "").split("/").filter(Boolean).pop() || "Peripheral",
        kind: device.type === UPowerDeviceType.Mouse || device.type === UPowerDeviceType.Keyboard
              ? (device.type === UPowerDeviceType.Mouse ? "mouse" : "keyboard") : Peripheral.kind(device.model || device.nativePath),
        percentage: Peripheral.percentage(percent100(device.percentage)),
        connected: true,
        charging: device.state === UPowerDeviceState.Charging ? true
            : device.state === UPowerDeviceState.Discharging || device.state === UPowerDeviceState.FullyCharged ? false : null
    }))

    function laptopBatteries() {
        return UPower.devices.values.filter(device => device.isLaptopBattery && device.isPresent);
    }

    // Quickshell normalizes the UPower D-Bus Percentage (0-100) into a 0-1 fraction
    // (DBusDataTransform<PowerPercentage> applies *0.01 — quickshell 0.3.2 src/services/
    // upower/device.cpp), the same convention as Pipewire volume, wifi signalStrength and
    // Bluetooth battery. The backend contract and every panel expect 0-100, so both UPower
    // read sites rescale here; missing it renders an 80% battery as Math.round(0.8) = 1%.
    function percent100(value) {
        return typeof value === "number" && isFinite(value) ? Math.round(value * 100) : null;
    }

    // Port of scripts/battery_info.py::battery_details over UPower properties.
    function batteryDetails(device) {
        const charging = device.state === UPowerDeviceState.Charging;
        const remaining = charging ? device.timeToFull : device.timeToEmpty;
        return {name: String(device.nativePath || "").split("/").filter(Boolean).pop() || "BAT",
                status: statusText(device.state),
                health: device.healthSupported ? round1(Math.min(100, device.healthPercentage)) : null,
                // UPower signs changeRate negative while discharging; the sysfs reader reports magnitude.
                powerW: round2(Math.abs(device.changeRate)),
                secondsRemaining: remaining > 0 ? Math.round(remaining) : null};
    }

    function statusText(state) {
        return ["Unknown", "Charging", "Discharging", "Empty", "Fully charged", "Pending charge", "Pending discharge"][state] || "Unknown";
    }

    function round1(value) { return Math.round(value * 10) / 10; }
    function round2(value) { return Math.round(value * 100) / 100; }

    // ---- Q3 write path: the router's charge leg (scripts/charge_actions.py +
    // scripts/desktop_backend.py::set_charge). The sysfs charge state stays backend-fed
    // (its discovery needs /sys/class/power_supply directory listing — no quickshell 0.3.2
    // API), so admission reads the merged section through the router's context; the write
    // goes through the same privileged helper the backend uses (plan §6 keeps it Python). ----

    readonly property var handledActions: ["chargeMode"]
    function handles(action) { return handledActions.includes(action); }

    property bool chargeBusy: false

    // canSet carries the helper/pkexec availability and the canonical reason.
    function canRoute(action, payload, context) {
        const charging = context && context.system ? context.system.charging : null;
        return !!charging && charging.canSet === true;
    }

    // Pure admission port of charge_actions.py + set_charge's prechecks: exact strings.
    function chargeProblem(request, charging, busy) {
        if (busy) return "A charge-mode change is already running.";
        const limit = request && request.value;
        if (typeof limit !== "number" || !Number.isInteger(limit) || (limit !== 85 && limit !== 100))
            return "Choose conservation (85) or maximum charge (100).";
        if (!charging || charging.canSet !== true)
            return (charging && charging.reason) || "Install the administrator charge helper. See docs/CHARGING.md.";
        return "";
    }

    function perform(action, request, done, context) {
        const charging = context && context.system ? context.system.charging : null;
        const problem = chargeProblem(request, charging, chargeBusy);
        if (problem) return done(false, problem);
        if (context && context.status)
            context.status("Changing charge mode; administrator authentication may be required");
        chargeTool.dispatch(["pkexec", "--disable-internal-agent", "/usr/bin/python3", "-I", "/usr/local/libexec/lme-shell-charge", String(request.value)], request.value, done);
    }

    // The helper prints its post-write state as JSON; the port verifies it exactly like
    // set_charge does (mode + threshold for threshold-kind interfaces). Failure shapes
    // mirror scripts/command_runner.py's CommandError strings.
    property Process chargeTool: Process {
        id: tool
        property var current: null           // [limit, done]
        property bool settled: false
        property bool timedOut: false
        property Timer watchdog: Timer {
            interval: 90000
            onTriggered: { tool.timedOut = true; tool.running = false; }
        }
        stdinEnabled: false
        stdout: StdioCollector {}
        stderr: StdioCollector {}
        onExited: code => {
            tool.settled = true; tool.watchdog.stop();
            if (timedOut) finish(false, "pkexec timed out");
            else if (code !== 0) {
                const detail = String(stderr.text || stdout.text || "").trim().slice(0, 350);
                finish(false, "pkexec failed (" + code + ")" + (detail ? ": " + detail : ""));
            } else finish(evaluate());
        }
        onRunningChanged: if (!running && !settled && current) {  // FailedToStart
            tool.settled = true; tool.watchdog.stop();
            finish(false, "Required command is unavailable: pkexec");
        }
        function evaluate() {
            const limit = current[0];
            let state = null;
            try { state = JSON.parse(String(stdout.text)); } catch (error) { state = null; }
            const desired = limit === 85 ? "conservation" : "max";
            if (!state || state.mode !== desired
                    || (state.supports85 === true && state.limitPercent !== limit))
                return [false, "The kernel did not confirm the requested charge mode."];
            return [true, "Charge mode updated" + (state.supports85 === true ? " · " + limit + "%" : " · firmware limit")];
        }
        function dispatch(argv, limit, done) {
            if (current) return done(false, "A charge-mode change is already running.");
            current = [limit, done]; settled = false; timedOut = false;
            root.chargeBusy = true;
            command = argv; running = true; watchdog.restart();
        }
        function finish(ok, message) {
            const done = current ? current[1] : null;
            current = null; timedOut = false;
            root.chargeBusy = false;
            if (done) done(ok, message);
        }
    }
}
