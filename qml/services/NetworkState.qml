// Role: NetworkState.qml (network layer, fan-in 2) — native network summary, Wi-Fi lists and actions (plan Q1/Q3).
// REL: Quickshell.Networking::Networking – devices/wifiEnabled/backend; NetworkDevice.disconnect;
// WifiNetwork.signalStrength/.security/.nmSettings/.connect/.connectWithPsk; NMSettings.uuid/.id/.forget.
// INVARIANT: section shape mirrors scripts/desktop_backend.py::network() exactly (tests/test_native_state.py
// freezes the summary; tests/test_native_wifi.py freezes the lists, actions and messages). The scan lists
// populate only while a Wi-Fi consumer is watching — the scanner runs while the panel is open (A6). The
// native item keeps the backend's bssid key as "" (quickshell exposes no BSSID): connect matches by ssid,
// saved operations by uuid. wifiScan re-arms the scanner (RequestScan is rate-limited ~10 s by quickshell).
// Known fidelity edges: with NetworkManager stopped the section reports available where the backend reported
// unavailable; saved profiles in hotspot (ap) mode are not enumerated by quickshell 0.3.2; the security
// string uses quickshell's names ("WPA2 Enterprise") where nmcli printed "802.1X".
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

    // Q3 scan gating (A6): the scanner runs only while a Wi-Fi consumer is watching. The device's
    // model keeps NM's cached access points and updates event-driven; the explicit scan action
    // re-arms the scanner to force a RequestScan.
    property bool watching: false
    property var scannerDevice: null
    onWatchingChanged: applyScanner()
    onWifiChanged: applyScanner()
    function applyScanner() {
        const device = watching ? wifi : null;
        if (scannerDevice === device) return;
        if (scannerDevice) scannerDevice.scannerEnabled = false;
        scannerDevice = device;
        if (device) device.scannerEnabled = true;
    }

    readonly property var state: {
        const section = {available: true, enabled: Networking.wifiEnabled, connected: false,
                         wifiConnected: false, ssid: "", strength: null, device: wifi ? wifi.name : "",
                         networks: [], saved: []};
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
        if (watching) {
            section.networks = networksList();
            section.saved = savedList();
        }
        return section;
    }

    // Port of the backend's `nmcli device wifi list` mapping: SSID-deduped (quickshell keys the
    // model by SSID like the backend's first-seen dedupe), 0-100 strength, connected first then
    // descending strength, capped at 60.
    function networksList() {
        if (!wifi) return [];
        const rows = [];
        for (const network of wifi.networks.values) {
            if (!network.name) continue;
            rows.push({ssid: network.name, strength: Math.round(network.signalStrength * 100),
                       connected: network.connected === true,
                       security: securityName(network.security), secured: isSecured(network.security),
                       enterprise: isEnterprise(network.security), bssid: ""});
        }
        rows.sort((a, b) => a.connected === b.connected ? b.strength - a.strength : (a.connected ? -1 : 1));
        return rows.slice(0, 60);
    }

    // Port of the backend's saved list (`nmcli connection show`, wifi type): every profile the
    // device exposes through its networks, as {uuid, name}. Hotspot (ap) mode profiles are a
    // known quickshell 0.3.2 gap (A/B compare warns on the count).
    function savedList() {
        if (!wifi) return [];
        const rows = [];
        for (const network of wifi.networks.values)
            for (const settings of network.nmSettings || [])
                rows.push({uuid: settings.uuid, name: settings.id});
        rows.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()) || a.uuid.localeCompare(b.uuid));
        return rows;
    }

    // WifiSecurityType -> display string (quickshell's names; the backend printed nmcli's).
    function securityName(security) {
        switch (security) {
        case WifiSecurityType.Wpa3SuiteB192: return "WPA3";
        case WifiSecurityType.Sae: return "WPA3";
        case WifiSecurityType.Wpa2Eap: return "WPA2 Enterprise";
        case WifiSecurityType.Wpa2Psk: return "WPA2";
        case WifiSecurityType.WpaEap: return "WPA Enterprise";
        case WifiSecurityType.WpaPsk: return "WPA";
        case WifiSecurityType.StaticWep: return "WEP";
        case WifiSecurityType.DynamicWep: return "WEP";
        case WifiSecurityType.Leap: return "LEAP";
        case WifiSecurityType.Owe: return "OWE";
        default: return "";
        }
    }
    function isSecured(security) {
        return security !== WifiSecurityType.Open && security !== WifiSecurityType.Unknown;
    }
    // The backend's enterprise test was "802.1X" or "EAP" in the nmcli security string —
    // the same families as these enum members (LEAP contains "EAP" in the backend's test).
    function isEnterprise(security) {
        return security === WifiSecurityType.Wpa2Eap || security === WifiSecurityType.WpaEap
            || security === WifiSecurityType.Leap || security === WifiSecurityType.DynamicWep;
    }

    // UTF-8 byte length without TextEncoder (V4 has no ES2019 encoders): every %XX escape in
    // encodeURIComponent is exactly one byte.
    function utf8Length(text) {
        const escaped = encodeURIComponent(text);
        let percents = 0;
        for (let index = 0; index < escaped.length; index++)
            if (escaped.charAt(index) === "%") percents++;
        return escaped.length - 2 * percents;
    }

    // Port of wifi_actions.py's request validation: the shared password bounds (length <= 128,
    // no CR/LF/NUL) and the wifiConnect-only WPA/WPA2 rule (8-63 UTF-8 bytes or 64 hex digits;
    // WPA3/SAE exempt). Returns "" when acceptable.
    function passwordProblem(password, security, forConnect) {
        const nul = String.fromCharCode(0);
        if (typeof password !== "string" || password.length > 128
                || password.indexOf("\r") >= 0 || password.indexOf("\n") >= 0 || password.indexOf(nul) >= 0)
            return "Invalid Wi-Fi password";
        if (!password || !forConnect) return "";
        if (security !== WifiSecurityType.WpaPsk && security !== WifiSecurityType.Wpa2Psk) return "";
        const bytes = utf8Length(password);
        if (bytes >= 8 && bytes <= 63) return "";
        if (bytes === 64 && /^[0-9a-fA-F]{64}$/.test(password)) return "";
        return "WPA/WPA2 passwords need 8–63 bytes or 64 hexadecimal digits.";
    }

    // ---- Q3 write path: the router's Wi-Fi leg (ShellState.run dispatches; done(ok, message)
    // resolves the pending slot exactly like a backend result would). ----

    readonly property var handledActions: ["wifiScan", "wifiConnect", "wifiSaved", "wifiDisconnect", "wifiForget", "wifiToggle"]
    function handles(action) { return handledActions.includes(action); }
    // Route natively only when quickshell's NetworkManager backend and an adapter are present;
    // otherwise fall back to the backend registry (canonical errors, A/B window).
    function canRoute() { return Networking.backend === NetworkBackendType.NetworkManager && !!wifi; }

    function perform(action, request, done) {
        if (action === "wifiToggle") {
            Networking.wifiEnabled = !Networking.wifiEnabled;
            return done(true, "Wi-Fi toggled");
        }
        if (!wifi) return done(false, "No Wi-Fi adapter is available");
        if (action === "wifiScan") {
            wifi.scannerEnabled = false;
            wifi.scannerEnabled = true;  // false->true re-arms RequestScan (rate-limited ~10 s)
            if (!watching) wifi.scannerEnabled = false;  // never leave the scanner on without a consumer
            return done(true, "Wi-Fi scan requested");
        }
        if (action === "wifiDisconnect") {
            wifi.disconnect();
            return done(true, "Wi-Fi disconnected");
        }
        if (action === "wifiForget") {
            const settings = findSettings(String(request.uuid || ""));
            if (!settings) return done(false, "Saved network is no longer available");
            settings.forget();  // the specific profile (Network.forget() would drop every profile on the SSID)
            return done(true, "Saved network removed");
        }
        const saved = action === "wifiSaved";
        const network = saved ? findNetworkByUuid(String(request.uuid || "")) : findNetworkBySsid(String(request.ssid || ""));
        if (!network) return done(false, saved ? "Saved network is no longer available" : "Network is no longer visible; scan again");
        if (isEnterprise(network.security))
            return done(false, "Enterprise Wi-Fi needs a certificate or account. Use Advanced network settings.");
        const problem = passwordProblem(request.password, network.security, !saved);
        if (problem) return done(false, problem);
        beginConnect(network, request.password || "", done);
    }

    function findSettings(uuid) {
        if (!wifi || !uuid) return null;
        for (const network of wifi.networks.values)
            for (const settings of network.nmSettings || [])
                if (settings.uuid === uuid) return settings;
        return null;
    }
    function findNetworkByUuid(uuid) {
        if (!wifi || !uuid) return null;
        for (const network of wifi.networks.values)
            for (const settings of network.nmSettings || [])
                if (settings.uuid === uuid) return network;
        return null;
    }
    function findNetworkBySsid(ssid) {
        if (!wifi || !ssid) return null;
        return wifi.networks.values.find(network => network.name === ssid) || null;
    }

    // The connect flow: connectWithPsk updates the existing profile's PSK and activates (or
    // add-and-activates for new SSIDs); connect() activates stored credentials. Completion is
    // event-driven (state/connectionFailed on the target) with the backend's 45 s ceiling —
    // reason mapping mirrors wifi_auth.py's messages.
    property var connectTarget: null
    property var connectDone: null
    property bool connectHadPassword: false
    property Timer connectTimeout: Timer {
        interval: 45000
        onTriggered: root.finishConnect(false, "Wi-Fi connection timed out. Check the signal and try again.")
    }
    property Connections connectWatch: Connections {
        target: root.connectTarget
        function onStateChanged() {
            if (root.connectTarget && root.connectTarget.connected) root.finishConnect(true, "Wi-Fi connected");
        }
        function onConnectionFailed(reason) { root.failConnect(reason); }
    }
    function beginConnect(network, password, done) {
        connectTarget = network; connectDone = done; connectHadPassword = !!password;
        connectTimeout.restart();
        if (password) network.connectWithPsk(password); else network.connect();
        if (network.connected) finishConnect(true, "Wi-Fi connected");
    }
    function finishConnect(ok, message) {
        const done = connectDone;
        connectTarget = null; connectDone = null; connectHadPassword = false;
        connectTimeout.stop();
        if (done) done(ok, message);
    }
    function failConnect(reason) {
        if (reason === ConnectionFailReason.NoSecrets)
            return finishConnect(false, connectHadPassword ? "Wi-Fi needs a valid password. Check it and try again."
                                                           : "Enter a Wi-Fi password to connect.");
        if (reason === ConnectionFailReason.WifiClientDisconnected || reason === ConnectionFailReason.WifiClientFailed)
            return finishConnect(false, "Wi-Fi needs a valid password. Check it and try again.");
        if (reason === ConnectionFailReason.WifiAuthTimeout)
            return finishConnect(false, "Wi-Fi authentication did not finish. Check the password or signal and try again.");
        finishConnect(false, "Wi-Fi connection timed out. Check the signal and try again.");
    }
}
