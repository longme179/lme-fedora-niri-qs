// Role: PowerState.qml (power layer, fan-in 2) — native battery/AC, power profiles, UPower peripherals (plan Q1).
// REL: Quickshell.Services.UPower::UPower – displayDevice/onBattery/devices; PowerProfiles – profile/hasPerformanceProfile.
// INVARIANT: section shapes mirror scripts/desktop_backend.py::battery()/power_profile()/power_profiles()
// and scripts/peripheral_battery.py::kernel_batteries (tests/test_native_state.py freezes them).
// Known fidelity edges (A/B window catches both): without power-profiles-daemon PowerProfiles keeps its
// default enum (the section reports "power-saver" where the backend reported null); UPower peripheral ids
// use the UPower native path where the backend used the sysfs node name.
pragma Singleton
import QtQuick
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
        return {available: true, percent: Math.round(device.percentage),
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
        percentage: Peripheral.percentage(device.percentage),
        connected: true,
        charging: device.state === UPowerDeviceState.Charging ? true
            : device.state === UPowerDeviceState.Discharging || device.state === UPowerDeviceState.FullyCharged ? false : null
    }))

    function laptopBatteries() {
        return UPower.devices.values.filter(device => device.isLaptopBattery && device.isPresent);
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
}
