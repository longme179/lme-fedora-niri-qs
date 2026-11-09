// Role: AudioDeviceModel.js (audio layer) — bounded pactl JSON normalization, server-scoped
// identities, request validation and change selection (Q3 inventory families).
// REL: scripts/audio_inventory.py + scripts/audio_pipewire.py – the pure contracts this ports
// (same bounds, same error strings, same argv plans); qml/services/AudioDeviceState.qml – the
// I/O orchestration over these helpers; qml/services/Digest.js – the server-id hash.
// GOTCHA: identities are ids, never display labels; pactl output shapes vary by PipeWire
// version, so every field is validated defensively before use. Errors are thrown as the exact
// backend message strings (the state layer surfaces String(error)).
.pragma library
.import "Digest.js" as Digest

function integer(value, maximum) {
    if (typeof value !== "number" || !Number.isInteger(value) || value < 0 || value > (maximum || 4294967295))
        throw "Invalid audio object index";
    return value;
}

function name(value) {
    if (typeof value !== "string" || value.length === 0 || value.length > 256) throw "Invalid audio option name";
    for (let index = 0; index < value.length; index++) {
        const code = value.charCodeAt(index);
        if (code < 32 || (code >= 0xd800 && code <= 0xdfff)) throw "Invalid audio option name";
    }
    return value;
}

function label(value, fallback) {
    if (typeof value !== "string") value = fallback;
    const cleaned = value.replace(/[\x00-\x1f\ud800-\udfff]/g, " ").split(/\s+/).filter(Boolean).join(" ");
    return cleaned.slice(0, 160) || fallback;
}

function serverId(info) {
    if (!info || typeof info !== "object" || Array.isArray(info)) throw "Invalid audio server information";
    const parts = [info.server_string, info.cookie, info.server_name];
    for (const part of parts)
        if (typeof part !== "string" || part.length === 0 || part.length > 4096)
            throw "Audio server identity is unavailable";
    return Digest.sha256hex(Digest.pyJson(parts));
}

function identity(kind, row) {
    const index = integer(row.index);
    const props = row.properties;
    let serial = props && typeof props === "object" ? props["object.serial"] : undefined;
    if (typeof serial === "number" && Number.isInteger(serial)) serial = String(serial);
    if (typeof serial !== "string" || !/^[0-9]{1,20}$/.test(serial) || Number(serial) > 18446744073709551615)
        throw "PipeWire object identity is unavailable; use Advanced audio settings";
    serial = String(parseInt(serial, 10));
    return {id: kind + "/" + index + "/" + serial, index: index, serial: serial};
}

function selected(value) {
    if (value !== null && typeof value === "object") return name(value.name);
    if (value === null || value === undefined || value === "") return "";
    return name(value);
}

function options(values) {
    if (values && typeof values === "object" && !Array.isArray(values)) {
        const listed = [];
        for (const key of Object.keys(values)) {
            const item = values[key];
            if (!item || typeof item !== "object") throw "Invalid audio option";
            listed.push(Object.assign({}, item, {name: key}));
        }
        values = listed;
    }
    if (!Array.isArray(values) || values.length > 64) throw "Audio options exceed the supported inventory";
    const result = [];
    for (const item of values) {
        if (!item || typeof item !== "object") throw "Invalid audio option";
        const key = name(item.name);
        let available = "availability" in item ? item.availability : item.available !== undefined ? item.available : "unknown";
        if (typeof available === "string")
            available = {available: "yes", "not available": "no", "availability unknown": "unknown"}[available] || available;
        if (!(available === null || typeof available === "boolean"
                || (typeof available === "string" && (available === "yes" || available === "no" || available === "unknown"))))
            throw "Invalid audio availability";
        result.push({name: key, title: label(item.description, key), available: available !== "no" && available !== false});
    }
    const seen = {};
    for (const item of result) {
        if (seen[item.name]) throw "Ambiguous audio options";
        seen[item.name] = true;
    }
    return result;
}

function rows(values, kind) {
    if (!Array.isArray(values)) throw "Invalid audio inventory";
    const result = [];
    const indexes = {}, serials = {};
    for (const row of values) {
        if (!row || typeof row !== "object") throw "Invalid audio object";
        const ref = identity(kind, row);
        if (indexes[ref.index] || serials[ref.serial]) throw "Ambiguous audio identities; refresh devices";
        indexes[ref.index] = true; serials[ref.serial] = true;
        result.push([ref, row]);
    }
    return result;
}

function normalize(info, cards, sinks, sources, streams) {
    const collections = [cards, sinks, sources, streams];
    let total = 0;
    for (const collection of collections) {
        if (!Array.isArray(collection)) throw "Invalid audio inventory";
        total += collection.length;
    }
    if (total > 128) throw "Audio inventory exceeds 128 objects or is malformed";
    const model = {available: true, serverId: serverId(info), server: label(info.server_name, "Audio server"),
        cards: [], sinks: [], sources: [], streams: [], error: "", stale: false};
    for (const [ref, row] of rows(cards, "card")) {
        const key = name(row.name);
        const props = row.properties || {};
        model.cards.push({id: ref.id, index: ref.index, serial: ref.serial, name: key,
            title: label(props["device.description"], key), profiles: options(row.profiles !== undefined ? row.profiles : {}),
            activeProfile: selected(row.active_profile)});
    }
    const cardIds = {};
    for (const card of model.cards) cardIds[card.index] = card.id;
    for (const [group, kind] of [["sinks", "sink"], ["sources", "source"]]) {
        for (const [ref, row] of rows(group === "sinks" ? sinks : sources, kind)) {
            const key = name(row.name);
            const card = row.card === null || row.card === undefined ? null : integer(row.card);
            model[group].push({id: ref.id, index: ref.index, serial: ref.serial, name: key,
                title: label(row.description, key), kind: kind, cardId: card === null ? "" : (cardIds[card] || ""),
                ports: options(row.ports !== undefined ? row.ports : []), activePort: selected(row.active_port)});
        }
    }
    const sinkIds = {};
    for (const sink of model.sinks) sinkIds[sink.index] = sink.id;
    for (const [ref, row] of rows(streams, "stream")) {
        const props = row.properties || {};
        const title = label(props["application.name"], "Audio application");
        model.streams.push({id: ref.id, index: ref.index, serial: ref.serial, title: title,
            detail: label(props["media.name"], title), sinkId: sinkIds[integer(row.sink)] || ""});
    }
    for (const group of ["cards", "sinks", "sources", "streams"])
        model[group].sort((left, right) => left.index - right.index);
    if (JSON.stringify(model).length > 256 * 1024) throw "Audio inventory exceeds 256 KiB";
    return model;
}

function validate(action, request) {
    if (action === "audioDevicesRefresh") return;
    const fields = {audioProfile: ["cardId", "profile"], audioPort: ["deviceId", "port"], audioRoute: ["streamId", "sinkId"]};
    if (!fields[action]) throw "Unknown audio device action";
    if (typeof request.serverId !== "string" || !/^[0-9a-f]{64}$/.test(request.serverId))
        throw "Invalid audio device request; refresh devices";
    for (const field of fields[action]) {
        const value = request[field];
        if (field.slice(-2) === "Id") {
            if (typeof value !== "string" || !/^(card|sink|source|stream)\/[0-9]{1,10}\/[0-9]{1,20}$/.test(value))
                throw "Invalid audio device identity";
        } else name(value);
    }
}

function selection(model, action, request) {
    validate(action, request);
    if (request.serverId !== model.serverId) throw "Audio server changed; refresh devices before retrying";
    function find(groups, ident) {
        const found = [];
        for (const group of groups)
            for (const row of model[group])
                if (row.id === ident) found.push([group, row]);
        if (found.length !== 1) throw "Audio object changed or disappeared; refresh devices";
        return found[0];
    }
    if (action === "audioRoute") {
        const [group, row] = find(["streams"], request.streamId);
        const target = find(["sinks"], request.sinkId)[1];
        return {argv: ["move-sink-input", String(row.index), String(target.index)], group: group, id: row.id,
            field: "sinkId", value: target.id, message: "Application output confirmed"};
    }
    const key = action === "audioProfile" ? "cardId" : "deviceId";
    const [group, row] = find(action === "audioProfile" ? ["cards"] : ["sinks", "sources"], request[key]);
    const choice = action === "audioProfile" ? request.profile : request.port;
    const choices = action === "audioProfile" ? row.profiles : row.ports;
    if (!choices.some(item => item.name === choice && item.available)) throw "This audio option is unavailable";
    const profile = action === "audioProfile";
    return {argv: [profile ? "set-card-profile" : group === "sinks" ? "set-sink-port" : "set-source-port", String(row.index), choice],
        group: group, id: row.id, field: profile ? "activeProfile" : "activePort", value: choice,
        message: profile ? "Audio profile confirmed" : "Audio port confirmed"};
}

// Port of scripts/audio_pipewire.py::route_plan — prove the Pulse/native core before metadata
// writes (cookie match, unambiguous node serials).
function routePlan(info, objects, streamSerial, sinkSerial) {
    if (!info || typeof info !== "object") throw "Invalid audio server information";
    const cookie = info.cookie;
    if (typeof cookie !== "string" || !/^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$/.test(cookie))
        throw "Cannot verify the local PipeWire core for this audio server";
    if (!Array.isArray(objects) || objects.length > 2048) throw "Invalid PipeWire inventory";
    const cores = objects.filter(obj => obj && typeof obj === "object" && obj.type === "PipeWire:Interface:Core");
    const core = cores.length === 1 ? cores[0].info : null;
    if (!core || typeof core !== "object" || typeof core.cookie !== "number" || !Number.isInteger(core.cookie)
            || core.cookie !== parseInt(cookie.replace(":", ""), 16))
        throw "Audio server does not match the local PipeWire core; use Advanced audio settings";
    function node(serial, kind) {
        const found = [];
        for (const obj of objects) {
            if (!obj || typeof obj !== "object" || obj.type !== "PipeWire:Interface:Node") continue;
            const details = obj.info;
            const props = details && typeof details === "object" ? details.props : null;
            if (!props || typeof props !== "object") continue;
            if (String(props["object.serial"]) === serial && props["media.class"] === kind)
                found.push(integer(obj.id));
        }
        if (found.length !== 1) throw "Audio node changed or is ambiguous; refresh devices";
        return found[0];
    }
    const source = node(streamSerial, "Stream/Output/Audio");
    node(sinkSerial, "Audio/Sink");
    return [source, sinkSerial];
}

// The two pw-metadata writes apply_route performs (the deprecated object.id target included).
function applyRouteArgv(node, serial) {
    return [["pw-metadata", "-n", "default", String(node), "target.object", serial, "Spa:Id"],
            ["pw-metadata", "-n", "default", String(node), "target.node"]];
}

// Port of scripts/audio_devices.py::observed — the bounded read-back check for one change.
function observed(data, change) {
    const kind = {cards: "card", sinks: "sink", sources: "source", streams: "stream"}[change.group];
    if (!Array.isArray(data) || data.length > 128) throw "Invalid audio read-back";
    for (const row of data) {
        if (!row || typeof row !== "object") throw "Invalid audio read-back";
        if (identity(kind, row).id !== change.id) continue;
        return change.group === "streams" ? integer(row.sink) === Number(change.argv[2])
            : selected(change.group === "cards" ? row.active_profile : row.active_port) === change.value;
    }
    return false;
}
