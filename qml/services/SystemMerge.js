// Role: SystemMerge.js (shared layer, fan-in 1) — reference-stable merge of backend and native system sections.
// Shared component/helper; keep API stable for wide QML reuse.
// INVARIANT: content-equal backend snapshots and unchanged section references return the SAME merged object,
// so bar and panel bindings do not re-evaluate on every backend poll (replaces the system Identity.keep line).
.pragma library

var cache = {raw: null, base: null, merged: null};

function merge(backend, base, compose) {
    const raw = JSON.stringify(backend);
    if (cache.merged && cache.raw === raw && sameSections(cache.base, base)) return cache.merged;
    cache = {raw: raw, base: base, merged: Object.assign({}, backend, compose(backend, base))};
    return cache.merged;
}

function sameSections(a, b) {
    if (a === b) return true; // both null in fixture modes: the pass-through still caches
    if (!a || !b || Object.keys(a).length !== Object.keys(b).length) return false;
    for (const key in a) if (a[key] !== b[key]) return false;
    return true;
}
