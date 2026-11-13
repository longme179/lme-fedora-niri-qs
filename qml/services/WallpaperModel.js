// SPDX-License-Identifier: GPL-3.0-or-later
// Role: WallpaperModel.js (wallpaper layer, fan-in 1) — pure contracts for the Q5 native wallpaper.
// REL: scripts/wallpaper.py (TRANSITIONS/output_name/query_outputs/query_images/image_arguments/
// Wallpapers.due/_advance) – DEPRECATED(Q5->Q6); every message and the deadline semantics are
// frozen by tests/test_native_wallpaper.py.
// INVARIANT: the plan() machine is a pure port of Wallpapers.due() — same bookkeeping order
// (connected/applied, signature reset, paused/remaining, then restore before advance).
// GOTCHA: file-existence prefilters become apply-failure-driven in the native port (quickshell
// 0.3.2 cannot stat); a missing single playlist image surfaces as 'No wallpaper could be applied'
// instead of the Python prefilter's 'The playlist has no available images'.
.pragma library

var TRANSITIONS = ['fade', 'wipe', 'wave', 'grow', 'outer', 'left', 'right', 'top', 'bottom', 'simple', 'none', 'random'];
var OUTPUT_NAME = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;

function outputName(value, shared) {
    if (typeof value === "string" && ((shared && value === "") || OUTPUT_NAME.test(value))) return value;
    throw new Error(shared ? "Choose a valid display name" : "Choose a valid display name");
}

// swww-style query parsing: both "OUTPUT: WxH" and "NAMESPACE: OUTPUT: WxH" rows.
function queryOutputs(text) {
    var found = new Set(), match;
    const lines = String(text || "").split("\n");
    for (var i = 0; i < lines.length; i++) {
        match = /^(?:[^:\n]*:\s*)?([A-Za-z0-9][A-Za-z0-9_.-]*):\s*\d+x\d+\b/.exec(lines[i]);
        if (match) found.add(match[1]);
    }
    return found;
}

function queryImages(text) {
    var found = {}, match;
    const lines = String(text || "").split("\n");
    for (var i = 0; i < lines.length; i++) {
        match = /^(?:[^:\n]*:\s*)?([A-Za-z0-9][A-Za-z0-9_.-]*):\s*\d+x\d+[^\n]*?currently displaying:\s*image:\s*(.+)$/.exec(lines[i]);
        if (match) found[match[1]] = match[2].trim();
    }
    return found;
}

function imageArguments(path, preferences, animate) {
    const transition = animate && preferences.animations ? preferences.wallpaperTransition : "none";
    var args = ["img", String(path), "--transition-type", transition, "--resize", preferences.wallpaperResize,
        "--filter", preferences.wallpaperFilter, "--fill-color", String(preferences.wallpaperFillColor).slice(1)];
    if (transition !== "none") {
        args = args.concat(["--transition-fps", String(preferences.wallpaperTransitionFps),
            "--transition-step", String(transition === "simple" ? preferences.wallpaperTransitionStep : 90)]);
        if (transition !== "simple") {
            args = args.concat(["--transition-duration", String(preferences.wallpaperTransitionDuration),
                "--transition-angle", String(preferences.wallpaperTransitionAngle),
                "--transition-pos", preferences.wallpaperTransitionPosition,
                "--transition-bezier", preferences.wallpaperTransitionBezier,
                "--transition-wave", preferences.wallpaperTransitionWave]);
        }
    }
    return args;
}

function signature(preferences) {
    return JSON.stringify([preferences.wallpaperPlaylist || [], preferences.wallpaperPlaylistEnabled === true,
        preferences.wallpaperPlaylistShuffle === true, preferences.wallpaperPlaylistInterval || 300,
        preferences.wallpaperPlaylistOutput || "", preferences.wallpaper || "",
        Object.keys(preferences.wallpaperOutputs || {}).sort().map(function (name) { return [name, preferences.wallpaperOutputs[name]]; })]);
}

// The due() port. state = {connected: [...]|null, applied: {name: path}, signature: string|null,
// cursor: [output, path, current]|null, deadline: number|null, remaining: number|null,
// wasPaused: bool, retryAt: number}. Returns {state, job} where job is
// {kind: "restore", outputs: [names]} | {kind: "advance", output: string} | null.
function plan(state, preferences, outputs, now, powerSaving) {
    var next = JSON.parse(JSON.stringify(state));
    var names = Array.from(outputs || []);
    if (JSON.stringify(names.slice().sort()) !== JSON.stringify((next.connected || []).slice().sort())) next.retryAt = 0;
    if (next.connected === null && names.length) {
        // start.sh owns the initial shared image, including its --wallpaper override.
        var applied = Object.assign({}, next.applied);
        for (var i = 0; i < names.length; i++)
            if (!(names[i] in (preferences.wallpaperOutputs || {})) && preferences.wallpaper)
                applied[names[i]] = preferences.wallpaper;
        next.applied = applied;
    }
    if (names.length || next.connected !== null) next.connected = names;
    var kept = {};
    for (var name in next.applied) if (names.indexOf(name) >= 0) kept[name] = next.applied[name];
    next.applied = kept;
    var mark = signature(preferences);
    if (mark !== next.signature) { next.signature = mark; next.cursor = null; next.remaining = null; next.deadline = null; next.retryAt = 0; }
    var paused = preferences.wallpaperPlaylistPaused === true || powerSaving === true;
    if (preferences.wallpaperPlaylistEnabled !== true || !(preferences.wallpaperPlaylist || []).length) {
        next.deadline = null; next.remaining = null;
    } else if (paused) {
        if (next.deadline !== null) next.remaining = Math.max(0, next.deadline - now);
        next.deadline = null;
    } else if (next.deadline === null) {
        next.deadline = now + (next.wasPaused && next.remaining !== null ? next.remaining : (preferences.wallpaperPlaylistInterval || 300));
        next.remaining = null;
    }
    next.wasPaused = paused;
    if (!names.length) return {state: next, job: null};
    // Restore only changed or newly connected displays, preserving fixed overrides.
    var desired = {};
    for (var d = 0; d < names.length; d++) {
        const name = names[d];
        desired[name] = (preferences.wallpaperOutputs || {})[name] || preferences.wallpaper || "";
    }
    var restore = [];
    for (var r in desired) if (desired[r] && next.applied[r] !== desired[r]) restore.push(r);
    if (restore.length && now >= next.retryAt) {
        next.retryAt = now + 30;
        if (next.deadline !== null && next.deadline <= now) next.deadline = now + (preferences.wallpaperPlaylistInterval || 300);
        return {state: next, job: {kind: "restore", outputs: restore}};
    }
    if (next.deadline !== null && now >= next.deadline) {
        next.deadline = now + (preferences.wallpaperPlaylistInterval || 300);
        if (preferences.wallpaperPlaylistOutput && names.indexOf(preferences.wallpaperPlaylistOutput) < 0)
            return {state: next, job: null};
        return {state: next, job: {kind: "advance", output: preferences.wallpaperPlaylistOutput || ""}};
    }
    return {state: next, job: null};
}

// The _advance choice rotation. current = the output's resolved path; returns up to 10 paths
// to try in order (shuffle picks randomly excluding current, sequential follows the cursor).
function advanceChoices(preferences, output, cursor, current, random) {
    const paths = preferences.wallpaperPlaylist || [];
    if (!paths.length) throw new Error("The playlist has no available images");
    if (paths.length === 1 && paths[0] === current) return {note: "The only playlist image is already active", choices: []};
    var ordered;
    if (random) {
        ordered = paths.filter(function (path) { return path !== current; });
        for (var i = ordered.length - 1; i > 0; i--) {
            const swap = Math.floor(Math.random() * (i + 1));
            const hold = ordered[i]; ordered[i] = ordered[swap]; ordered[swap] = hold;
        }
    } else {
        var previous = cursor && cursor[0] === output && cursor[2] === current ? cursor[1] : current;
        var at = paths.indexOf(previous);
        var index = at < 0 ? 0 : (at + 1) % paths.length;
        ordered = paths.slice(index).concat(paths.slice(0, index)).filter(function (path) { return path !== current; });
    }
    return {note: "", choices: ordered.slice(0, 10)};
}
