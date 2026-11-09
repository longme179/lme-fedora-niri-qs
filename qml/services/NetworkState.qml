// Role: NetworkState.qml (network layer, fan-in 2) — native network summary state (plan Q1).
// REL: Quickshell.Networking::Networking – devices/wifiEnabled; NetworkDevice.connected/.name; WifiNetwork.signalStrength.
// INVARIANT: section shape mirrors scripts/desktop_backend.py::network() summary fields exactly
// (tests/test_native_state.py). Scan lists (networks/saved) stay backend-fed during the Q1-Q3 A/B window:
// the Wi-Fi connect action matches networks by bssid, which the native API does not expose.
// Known fidelity edge: with NetworkManager stopped the native section reports available where the
// backend reported unavailable (the A/B comparison warns).
pragma Singleton
import QtQuick
import Quickshell.Networking

QtObject {
    id: root

    readonly property var devices: Networking.devices.values

    // The backend prefers a connected Wi-Fi adapter, then the first one.
    readonly property var wifi: devices.filter(device => device.type === DeviceType.Wifi)
        .find(device => device.connected) || devices.find(device => device.type === DeviceType.Wifi) || null
    readonly property var wired: devices.find(device => device.type === DeviceType.Wired) || null

    readonly property var state: {
        const section = {available: true, enabled: Networking.wifiEnabled, connected: false,
                         wifiConnected: false, ssid: "", strength: null, device: wifi ? wifi.name : ""};
        for (const device of devices)
            if (device.connected) {
                section.connected = true;
                if (device.type === DeviceType.Wired) section.ssid = "Ethernet";
            }
        if (wifi && wifi.connected && Networking.wifiEnabled) {
            const active = wifi.networks.values.find(network => network.connected) || null;
            section.wifiConnected = true;
            section.ssid = active ? active.name : "";
            section.strength = active ? Math.round(active.signalStrength * 100) : null;
        }
        return section;
    }
}
