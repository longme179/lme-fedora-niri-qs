// Role: DisplayModel.js (shared layer) — the niri outputs normalizer (Q4 display/mirror
// families; plan §5 Q4: display_control/display_actions/display_mirror/display_layout).
// REL: scripts/display_control.py::normalized_outputs – the exact shape this ports: the
// mode table (width/height/refresh + the "W × H · R Hz" label), the current-mode gating
// that marks an output enabled, the logical geometry with the backend's defaults, the
// make/model description join and the name sort. display_layout.py's validation and
// application stay with the Settings preview flow (their owning phase).
// INVARIANT: a non-object payload returns null (the caller degrades to the empty list —
// the backend's outputs() catch); numeric fields use the backend's strict-int semantics
// (booleans rejected like Python's `type(x) is int`). GOTCHA: the label's refresh uses
// Python's f'{x:g}' — 6 significant digits with trailing zeros stripped — reproduced
// with toPrecision(6) + Number() (59.9997 -> "60", 144.002 -> "144").
.pragma library

function gFormat(value) {
    if (!isFinite(value)) return String(value);
    return String(Number(value.toPrecision(6)));
}

function normalizedOutputs(raw) {
    if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return null;
    const outputs = [];
    for (const name of Object.keys(raw)) {
        const output = raw[name];
        if (typeof output !== "object" || output === null) continue;
        const modes = [];
        for (const mode of (output.modes || [])) {
            if (typeof mode !== "object" || mode === null) continue;
            if (!Number.isInteger(mode.width) || !Number.isInteger(mode.height) || !Number.isInteger(mode.refresh_rate)) continue;
            if (mode.width <= 0 || mode.height <= 0 || mode.refresh_rate <= 0) continue;
            modes.push({width: mode.width, height: mode.height, refresh: mode.refresh_rate,
                        label: mode.width + " × " + mode.height + " · " + gFormat(mode.refresh_rate / 1000) + " Hz"});
        }
        const index = output.current_mode;
        const logical = output.logical || {};
        const current = (typeof index === "number" && Number.isInteger(index) && index >= 0 && index < modes.length)
            ? modes[index] : null;
        outputs.push({name: name,
                      description: [String(output.make || ""), String(output.model || "")].join(" ").trim(),
                      modes: modes, current: current, enabled: current !== null,
                      scale: logical.scale !== undefined ? logical.scale : 1,
                      x: logical.x !== undefined ? logical.x : 0,
                      y: logical.y !== undefined ? logical.y : 0,
                      width: logical.width !== undefined ? logical.width : 0,
                      height: logical.height !== undefined ? logical.height : 0});
    }
    outputs.sort((left, right) => left.name < right.name ? -1 : left.name > right.name ? 1 : 0);
    return outputs;
}
