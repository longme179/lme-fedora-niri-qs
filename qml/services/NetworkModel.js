// Role: NetworkModel.js (wifi layer) — bounded, secret-free nmcli normalization and the shared
// error mapping (Q3 inventory families).
// REL: scripts/network_inventory.py + scripts/desktop_backend.py::split_nmcli + scripts/
// network_profiles.py::safe_error – the pure contracts this ports (same bounds, same error
// strings); qml/services/NetworkInventoryState.qml – the I/O orchestration; qml/services/
// Digest.js – the server identity hash.
// GOTCHA: nmcli terse/multiline formatting varies by version — parse defensively, identifiers
// are never display labels, and secrets never appear in parsed fields. Errors are thrown as
// the exact backend message strings.
.pragma library
.import "Digest.js" as Digest

var BASE = "/org/freedesktop/NetworkManager/";
var UUID = /^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$/;
var PROFILE_FIELDS = ["connection.uuid", "connection.id", "connection.type", "connection.interface-name",
    "connection.master", "connection.slave-type", "802-11-wireless.mode",
    "802-11-wireless-security.key-mgmt", "ipv4.method", "ipv4.addresses", "ipv4.gateway", "ipv4.dns",
    "ipv6.method", "ipv6.addresses", "ipv6.gateway", "ipv6.dns"];
var DEVICE_FIELDS = "GENERAL,WIFI-PROPERTIES,WIRED-PROPERTIES,CONNECTIONS,IP4,IP6";
var LIST_FIELDS = "UUID,TYPE,NAME,DEVICE,STATE,ACTIVE-PATH,SLAVE";
var TYPES = {vpn: "vpn", wireguard: "wireguard", "802-3-ethernet": "ethernet", ethernet: "ethernet",
    "802-11-wireless": "wifi", wifi: "wifi"};

// Port of scripts/desktop_backend.py::split_nmcli — escape-aware ':' split.
function splitNmcli(line) {
    const fields = [];
    let current = "", escaped = false;
    for (const character of String(line)) {
        if (escaped) { current += character; escaped = false; }
        else if (character === "\\") escaped = true;
        else if (character === ":") { fields.push(current); current = ""; }
        else current += character;
    }
    fields.push(current + (escaped ? "\\" : ""));
    return fields;
}

// Python str.splitlines parity (no trailing empty segment, interior blanks kept).
function lines(raw) {
    const split = String(raw).split(/\r\n|\n|\r/);
    if (split.length && split[split.length - 1] === "") split.pop();
    return split;
}

// Port of scripts/network_profiles.py::safe_error — the user-facing failure mapping.
function safeError(error) {
    const value = String(error).toLowerCase();
    if (value.indexOf("secret") >= 0 || value.indexOf("password") >= 0 || value.indexOf("authentication") >= 0)
        return "NetworkManager needs credentials or an authentication agent. Use Advanced network settings.";
    if (value.indexOf("not authorized") >= 0 || value.indexOf("permission") >= 0 || value.indexOf("not permitted") >= 0)
        return "NetworkManager denied permission. Check the session agent or Advanced network settings.";
    if (value.indexOf("plugin") >= 0 || value.indexOf("vpn service") >= 0)
        return "The VPN plugin is unavailable. Install its NetworkManager plugin and use Advanced network settings.";
    if (value.indexOf("timed out") >= 0 || value.indexOf("timeout") >= 0)
        return "Network operation timed out. Refresh the observed state before retrying.";
    return "NetworkManager could not complete the operation. Refresh or use Advanced network settings.";
}

function text(value) {
    if (typeof value !== "string" || value.length > 4096) throw "Invalid NetworkManager value";
    return value === "--" ? "" : value;
}

function label(value) {
    return text(value).split(/\s+/).filter(Boolean).join(" ").slice(0, 160);
}

function uuid(value) {
    if (typeof value !== "string" || !UUID.test(value)) throw "Invalid saved connection UUID";
    return value.toLowerCase();
}

function interface(value) {
    if (typeof value !== "string" || !/^[A-Za-z0-9_][A-Za-z0-9_.:-]{0,62}$/.test(value))
        throw "Unsupported network interface name";
    return value;
}

function escapeExpression(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function path(value, kind) {
    if (typeof value !== "string" || value.length > 256
            || !new RegExp("^" + escapeExpression(BASE + kind + "/") + "[0-9]+$").test(value))
        throw "Invalid NetworkManager object identity";
    return value;
}

function blocks(raw, first) {
    const result = [];
    for (const line of lines(raw)) {
        if (!line.trim()) continue;
        const fields = splitNmcli(line);
        if (fields.length !== 2) throw "Invalid NetworkManager property row";
        const key = fields[0], value = text(fields[1]);
        if (key === first) result.push({});
        if (!result.length || key in result[result.length - 1]) throw "Ambiguous NetworkManager property block";
        result[result.length - 1][key] = value;
    }
    return result;
}

function connections(raw) {
    const result = [];
    for (const line of lines(raw)) {
        const fields = splitNmcli(line);
        if (fields.length !== 7 || result.length >= 256) throw "Invalid or oversized connection listing";
        const parts = fields.map(text);
        result.push({uuid: uuid(parts[0]), type: parts[1], name: label(parts[2]), interfaces: parts[3],
            state: parts[4], path: parts[5] ? path(parts[5], "ActiveConnection") : "", slave: parts[6]});
    }
    return result;
}

function candidates(rows) {
    const seen = {}, ids = [];
    for (const row of rows)
        if (TYPES[row.type] && !row.slave && !seen[row.uuid]) { seen[row.uuid] = true; ids.push(row.uuid); }
    if (ids.length > 128) throw "Too many saved profiles to inspect safely";
    return ids;
}

function devices(raw, radio) {
    const values = blocks(raw, "GENERAL.DEVICE");
    if (values.length > 64) throw "Network device inventory exceeds 64 objects";
    const enabled = splitNmcli(String(radio).trim());
    if (enabled.length !== 2 || enabled.some(value => value !== "enabled" && value !== "disabled"))
        throw "Invalid Wi-Fi radio state";
    const result = [];
    for (const value of values) {
        const ident = path(value["GENERAL.DBUS-PATH"], "Devices");
        const name = interface(value["GENERAL.DEVICE"]);
        const stateText = String(value["GENERAL.STATE"] || "").split(" ")[0];
        if (!/^-?[0-9]+$/.test(stateText)) throw "Invalid network device state";
        const state = parseInt(stateText, 10);
        const compatible = [];
        for (const key of Object.keys(value))
            if (key.indexOf("CONNECTIONS.AVAILABLE-CONNECTIONS") === 0 && value[key])
                compatible.push(uuid(value[key].split("|", 1)[0].trim()));
        const addresses = (family, field) => {
            const found = [];
            for (const key of Object.keys(value))
                if (key.indexOf(family + "." + field + "[") === 0 && value[key]) found.push(label(value[key]));
            return found;
        };
        result.push({id: ident, interface: name, kind: value["GENERAL.TYPE"] || "", state: state,
            managed: value["GENERAL.NM-MANAGED"] === "yes", connected: state === 100,
            activeUuid: value["GENERAL.CON-UUID"] ? uuid(value["GENERAL.CON-UUID"]) : "",
            activePath: value["GENERAL.CON-PATH"] ? path(value["GENERAL.CON-PATH"], "ActiveConnection") : "",
            connection: label(value["GENERAL.CONNECTION"] || ""),
            compatible: compatible.filter((item, index) => compatible.indexOf(item) === index),
            ap: value["WIFI-PROPERTIES.AP"] === "yes", radio: enabled.every(flag => flag === "enabled"),
            carrier: !value["WIRED-PROPERTIES.CARRIER"] ? null : value["WIRED-PROPERTIES.CARRIER"] === "yes",
            ip4: addresses("IP4", "ADDRESS"), ip6: addresses("IP6", "ADDRESS"),
            dns4: addresses("IP4", "DNS"), dns6: addresses("IP6", "DNS"),
            gateway4: label(value["IP4.GATEWAY"] || ""), gateway6: label(value["IP6.GATEWAY"] || "")});
    }
    const ids = {}, names = {};
    for (const device of result) {
        if (ids[device.id] || names[device.interface]) throw "Ambiguous network devices";
        ids[device.id] = true; names[device.interface] = true;
    }
    return result;
}

// Order-insensitive comparison for the duplicate-detail guard (Python dict equality).
function canonical(value) {
    if (value === null || typeof value !== "object") return value === undefined ? "null" : JSON.stringify(value);
    if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
    return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + canonical(value[key])).join(",") + "}";
}

function inventory(server, deviceRaw, rows, detailRaw, radioRaw) {
    const devs = devices(deviceRaw, radioRaw);
    const details = blocks(detailRaw, "connection.uuid");
    const wanted = {}; for (const id of candidates(rows)) wanted[id] = true;
    const found = {}, profiles = [];
    for (const p of details) {
        const ident = uuid(p["connection.uuid"]);
        if (!wanted[ident]) continue;
        if (found[ident]) {
            if (canonical(found[ident]) !== canonical(p)) throw "Conflicting saved connection details";
            continue;
        }
        found[ident] = p;
        const kind = TYPES[p["connection.type"]];
        for (const row of rows)
            if (row.uuid === ident && TYPES[row.type] !== kind) throw "Saved connection types changed during inspection; refresh";
        if (!kind || p["connection.master"] || p["connection.controller"] || p["connection.slave-type"] || p["connection.port-type"]) continue;
        const mode = p["802-11-wireless.mode"] || "";
        if (kind === "wifi" && mode !== "ap") continue;
        const hotspot = kind === "wifi";
        const bound = p["connection.interface-name"] || "";
        if (bound) interface(bound);
        const settings = {};
        for (const key of PROFILE_FIELDS)
            if (key.indexOf("ipv4.") === 0 || key.indexOf("ipv6.") === 0) settings[key] = label(p[key] || "");
        const compatible = [];
        for (const d of devs) {
            if (!d.managed) continue;
            let eligible;
            if (kind === "vpn") eligible = d.connected && ["wifi", "ethernet", "bridge", "bond", "vlan"].indexOf(d.kind) >= 0;
            else eligible = d.compatible.indexOf(ident) >= 0 && d.kind === (hotspot ? "wifi" : "ethernet") && (!bound || bound === d.interface);
            if (eligible) compatible.push(d.id);
        }
        if (kind === "wireguard") { compatible.length = 0; if (bound) compatible.push("virtual/" + ident); }
        profiles.push({uuid: ident, name: label(p["connection.id"] || ""), kind: hotspot ? "hotspot" : kind,
            interface: bound, compatible: compatible, settings: settings, mode: mode,
            security: p["802-11-wireless-security.key-mgmt"] || ""});
    }
    for (const id of Object.keys(wanted))
        if (!found[id]) throw "Saved connections changed during inspection";
    if (profiles.length > 64) throw "Connection inventory exceeds 64 profiles";
    const ids = {}; for (const profile of profiles) ids[profile.uuid] = true;
    const active = [];
    for (const row of rows) {
        if (!ids[row.uuid] || !row.path) continue;
        const interfaces = row.interfaces.split(",").map(piece => piece.trim()).filter(Boolean).map(interface);
        for (const name of interfaces.length ? interfaces : [""]) {
            const d = devs.find(device => device.interface === name) || null;
            active.push({uuid: row.uuid, deviceId: d ? d.id : "", interface: name,
                path: row.path, state: row.state});
        }
    }
    const seen = {};
    for (const entry of active) {
        const key = entry.path + "\u0000" + entry.deviceId;
        if (seen[key] || active.length > 128) throw "Ambiguous or oversized active connections";
        seen[key] = true;
    }
    const model = {available: true, serverId: server, devices: devs, profiles: profiles, active: active,
        error: "", notice: "", hotspotPlan: null};
    if (JSON.stringify(model).length > 126 * 1024) throw "Network metadata exceeds 128 KiB";
    return model;
}
