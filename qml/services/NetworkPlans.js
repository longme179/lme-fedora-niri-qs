// Role: NetworkPlans.js (wifi layer) — fresh profile/device selection, explicit hotspot
// confirmation and the change-flow argv plan; no I/O (Q3 inventory families).
// REL: scripts/network_plans.py (+ the head of scripts/network_profiles.py::change) – the
// pure contracts this ports (same validation order, same error strings, the sha256 plan token
// over Python's exact json.dumps formatting); qml/services/NetworkModel.js – the uuid/path/
// interface validators; qml/services/Digest.js – the token hash; qml/services/
// NetworkInventoryState.qml – the I/O orchestration.
.pragma library
.import "Digest.js" as Digest
.import "NetworkModel.js" as NetworkModel

var MUTATIONS = ["networkConnect", "networkDisconnect", "networkHotspotStart", "networkEdit"];

function validate(action, request) {
    if (action === "networkRefresh") return;
    NetworkModel.uuid(request.uuid);
    if (typeof request.serverId !== "string" || !/^[0-9a-f]{64}$/.test(request.serverId))
        throw "Refresh network connections before retrying";
    if (action !== "networkEdit") {
        const device = request.deviceId;
        if (typeof device === "string" && device.indexOf("virtual/") === 0) NetworkModel.uuid(device.slice(8));
        else NetworkModel.path(device, "Devices");
    }
    if (action === "networkDisconnect") NetworkModel.path(request.activePath, "ActiveConnection");
    if (action === "networkHotspotStart" && (request.confirmed !== true
            || typeof request.planToken !== "string" || !/^[0-9a-f]{64}$/.test(request.planToken)))
        throw "Review and confirm the hotspot warning first";
}

function select(model, request, disconnect) {
    if (model.serverId !== request.serverId) throw "NetworkManager changed; refresh connections";
    const profile = model.profiles.find(entry => entry.uuid === NetworkModel.uuid(request.uuid)) || null;
    if (!profile) throw "Saved connection disappeared or is unsupported; refresh";
    const ident = request.deviceId;
    if (ident === "virtual/" + profile.uuid && profile.kind === "wireguard") {
        NetworkModel.interface(profile.interface);
        return [profile, {id: ident, interface: profile.interface, activePath: "", activeUuid: "",
            connection: "", state: 30}];
    }
    const device = model.devices.find(entry => entry.id === ident) || null;
    if (!device) throw "The selected network adapter disappeared; refresh";
    if (!disconnect) {
        if (profile.compatible.indexOf(device.id) < 0) throw "This profile is not compatible with the selected adapter";
        if (device.state >= 40 && device.state < 100) throw "This adapter is still changing; stop its connection or wait";
        if (profile.kind === "ethernet" && device.carrier === false) throw "Connect the Ethernet cable first";
    }
    return [profile, device];
}

function activeFor(model, profile, device) {
    return model.active.filter(entry => entry.uuid === profile.uuid
        && (entry.deviceId === device.id || (profile.kind === "wireguard" && entry.interface === profile.interface)));
}

function hotspotPlan(model, request) {
    const pair = select(model, request, false);
    const profile = pair[0], device = pair[1];
    if (model.active.some(entry => entry.uuid === profile.uuid && entry.deviceId !== device.id))
        throw "This hotspot profile is active on another adapter; stop it explicitly first";
    if (profile.kind !== "hotspot" || profile.mode !== "ap" || profile.settings["ipv4.method"] !== "shared"
            || (profile.security !== "wpa-psk" && profile.security !== "sae"))
        throw "Choose a saved WPA-PSK/SAE hotspot with shared IPv4 in Advanced network settings";
    if (!device.ap || !device.radio) throw "This adapter must support AP mode with hardware/software Wi-Fi enabled";
    const identity = {server: model.serverId, profile: profile,
        device: pick(device, ["id", "interface", "activePath", "activeUuid", "managed", "ap", "radio"])};
    const token = Digest.sha256hex(Digest.pyJson(identity));
    const uplinks = model.devices.filter(entry => entry.id !== device.id && entry.connected
        && ["wifi", "ethernet", "bridge", "bond", "vlan"].indexOf(entry.kind) >= 0).map(entry => entry.interface);
    return {token: token, uuid: profile.uuid, deviceId: device.id, name: profile.name,
        interface: device.interface,
        disconnectWifi: !!(device.activePath && device.activeUuid !== profile.uuid),
        previousConnection: device.connection, uplinks: uplinks,
        warning: "NetworkManager applies this profile's shared IP, DHCP/NAT, routes and firewall policy. Internet access is not verified."};
}

function pick(device, keys) {
    const chosen = {};
    for (const key of keys) chosen[key] = device[key];
    return chosen;
}

// The change flow's selection and argv plan (scripts/network_profiles.py::change's head);
// returns {already, profile, device, existing, args} or throws the backend's message.
function planChange(action, request, model) {
    const pair = select(model, request, action === "networkDisconnect");
    const profile = pair[0], device = pair[1];
    const existing = activeFor(model, profile, device);
    let args;
    if (action === "networkDisconnect") {
        const matching = existing.filter(entry => entry.path === request.activePath);
        if (matching.length !== 1 || model.active.filter(entry => entry.path === request.activePath).length !== 1)
            throw "Activation changed or spans multiple adapters; refresh or use Advanced settings";
        args = ["connection", "down", "apath", request.activePath];
    } else {
        if (model.active.some(entry => entry.uuid === profile.uuid && existing.indexOf(entry) < 0))
            throw "This profile is active on another adapter; disconnect it explicitly first";
        if (action === "networkHotspotStart") {
            if (hotspotPlan(model, request).token !== request.planToken)
                throw "Wi-Fi or hotspot settings changed; review a fresh warning";
        } else if (profile.kind === "hotspot") throw "Review the hotspot warning before starting it";
        if (existing.some(entry => entry.state === "activated"))
            return {already: true, profile: profile, device: device, existing: existing, args: []};
        if (existing.length) throw "This profile is still changing; wait or stop its reported activation";
        args = ["connection", "up", "uuid", profile.uuid];
        if (profile.kind !== "wireguard") args = args.concat(["ifname", device.interface]);
    }
    return {already: false, profile: profile, device: device, existing: existing, args: args};
}

// Port of scripts/network_profiles.py::epoch helpers — busctl identity parsing and the
// server hash over the D-Bus unique ids.
function busIdentity(raw) {
    let value;
    try { value = JSON.parse(raw); }
    catch (parse) { throw "NetworkManager identity is unavailable"; }
    if (!value || typeof value !== "object" || value.type !== "s" || !Array.isArray(value.data)
            || value.data.length !== 1 || typeof value.data[0] !== "string")
        throw "NetworkManager identity is unavailable";
    return value.data[0];
}

function epochId(bus, owner) {
    if (typeof bus !== "string" || !/^[0-9a-fA-F]{32}$/.test(bus)
            || typeof owner !== "string" || !/^:[0-9]+\.[0-9]+$/.test(owner))
        throw "NetworkManager identity is unavailable";
    return Digest.sha256hex(bus + "/" + owner);
}
