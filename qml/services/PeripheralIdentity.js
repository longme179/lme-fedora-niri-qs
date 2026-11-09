// Role: PeripheralIdentity.js (shared layer, fan-in 2) — QML port of scripts/peripheral_values.py.
// Shared component/helper; keep API stable for wide QML reuse.
// INVARIANT: identity/kind/percentage mirror the Python helpers exactly (tests freeze the section shapes).
.pragma library

function percentage(value) {
    return typeof value === "number" && isFinite(value) && value >= 0 && value <= 100 ? value : null;
}

function identity(address, fallback) {
    address = typeof address === "string" ? address.toUpperCase().replace(/_/g, ":").replace(/-/g, ":") : "";
    return /^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$/.test(address) ? "bluetooth:" + address : fallback;
}

function kind(value) {
    value = String(value || "").toLowerCase();
    if (value.indexOf("head") >= 0 || value.indexOf("earbud") >= 0) return "headphones";
    if (value.indexOf("mouse") >= 0) return "mouse";
    if (value.indexOf("keyboard") >= 0) return "keyboard";
    return "device";
}
