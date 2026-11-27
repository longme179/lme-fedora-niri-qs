// Role: SystemMerge.js (shared layer, fan-in 1) — reference-stable merge of backend and native system sections.
// Shared component/helper; keep API stable for wide QML reuse.
// INVARIANT: content-equal backend snapshots and unchanged section references return the SAME merged object,
// so bar and panel bindings do not re-evaluate on every backend poll (replaces the system Identity.keep line).
.pragma library

var cache = {backend: null, base: null, merged: null};

function merge(backend, base, compose) {
    // Reference fast path first: the backend polls on a 2 s cadence and NativeState re-merges
    // on every native tick, so the cache used to JSON.stringify the whole backend snapshot on
    // each call (measured hot in run s1-n10-b). Equal references answer before any stringify;
    // the stringify remains for the poll that delivers a fresh-but-content-equal object.
    if (cache.merged && cache.backend === backend && sameSections(cache.base, base)) return cache.merged;
    const raw = JSON.stringify(backend);
    if (cache.merged && cache.rawCache === raw && sameSections(cache.base, base)) return cache.merged;
    cache = {backend: backend, rawCache: raw, base: base, merged: Object.assign({}, backend, compose(backend, base))};
    return cache.merged;
}

function sameSections(a, b) {
    if (a === b) return true; // both null in fixture modes: the pass-through still caches
    if (!a || !b || Object.keys(a).length !== Object.keys(b).length) return false;
    for (const key in a) if (a[key] !== b[key]) return false;
    return true;
}
