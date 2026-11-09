// Role: SnapshotIdentity.js (shared layer, fan-in 1).
// Shared component/helper; keep API stable for wide QML reuse.
.pragma library

// Reuse the previous section when the backend reports the same revision. The
// string comparison keeps older backends and demo snapshots working.
function keep(next, previous, key, current, dragging) {
    if (dragging && key === "niri") return true;
    const fresh = (next && next.revisions) || {};
    const old = (previous && previous.revisions) || {};
    if (fresh[key] !== undefined) return fresh[key] === old[key];
    const value = key === "launcherUsage" ? ((next && next[key]) || {}) : (next && next[key]);
    return JSON.stringify(value) === JSON.stringify(key === "launcherUsage" ? (current || {}) : current);
}
