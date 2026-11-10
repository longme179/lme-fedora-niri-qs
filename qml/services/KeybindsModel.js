// Role: KeybindsModel.js (shared layer) — niri keybinding section builder (Q4 session
// families).
// REL: scripts/niri_keybinds.py::read_keybinds – the traversal this ports as an explicit
// state machine so a QML FileView can drive it one file at a time: start()/nextRead()/
// ingest()/ingestError()/finish() walk the include chain depth-first in document order
// (an include's bindings land between the parent's binds around it, exactly like the
// recursive visit), with the documented bounds — 32 distinct files, 12 levels, 512 KiB per
// file, 2 MiB total — and the exact backend error strings.
// INVARIANT: a path handed out by nextRead() is consumed exactly once through ingest() or
// ingestError(); the root load failure yields the "Niri config not found" section. Known
// native edges: the per-file size gate counts characters where the backend stats bytes
// (equal for ASCII configs), and a missing include reports "File could not be read" where
// the backend echoes the OS errno text; paths are normalized lexically (~ expands, but
// symlinked configs are not resolved through). Keys iterate in insertion order like
// Python dicts for the property rendering.
.pragma library
.import "KeybindsKdl.js" as KeybindsKdl

function start(rootPath, home) {
    const root = normalize(expandHome(String(rootPath || ""), home || ""));
    return {root: root, home: home || "", pending: root, stack: [], visited: [],
        bindings: [], errors: [], total: 0};
}

// Walk the stack tops, collecting binds nodes, until a file must be read (an include) or
// the traversal ends. Returns the next absolute path to read, or null when finished.
function nextRead(state) {
    while (true) {
        if (state.pending !== null) return state.pending;
        const frame = state.stack.length ? state.stack[state.stack.length - 1] : null;
        if (!frame) return null;
        if (frame.index >= frame.nodes.length) { state.stack.pop(); continue; }
        const node = frame.nodes[frame.index++];
        if (node.disabled) continue;
        if (node.name === "include" && node.args.length) {
            const raw = node.args[0];
            const path = normalize(expandHome(raw.charAt(0) === "/" ? raw : dirname(frame.path) + "/" + raw, state.home));
            if (state.visited.indexOf(path) >= 0) continue;  // a repeat include is silent
            if (state.stack.length > 12 || state.visited.length >= 32) {
                state.errors.push("Include limit reached (32 files / 12 levels).");
                continue;
            }
            state.pending = path;
            return path;
        }
        if (node.name === "binds") collectBinds(state, node, frame.path);
    }
}

function ingest(state, text) {
    const path = state.pending;
    state.pending = null;
    state.visited.push(path);
    if (text.length > 512 * 1024) { state.errors.push(basename(path) + ": Config exceeds 512 KiB"); return state; }
    state.total += text.length;
    if (state.total > 2 * 1024 * 1024) { state.errors.push(basename(path) + ": Included configs exceed 2 MiB"); return state; }
    let nodes;
    try { nodes = KeybindsKdl.nodes(text); }
    catch (error) { state.errors.push(basename(path) + ": " + error); return state; }
    state.stack.push({path: path, nodes: nodes, index: 0});
    return state;
}

function ingestError(state, reason) {
    const path = state.pending;
    state.pending = null;
    if (state.stack.length === 0 && path === state.root) {
        state.visited.push(path);
        state.errors.push("Niri config not found. Set its path below if you use --config.");
        return state;
    }
    state.visited.push(path);
    state.errors.push(basename(path) + ": File could not be read");
    return state;
}

function finish(state) {
    return {path: state.root, bindings: state.bindings, errors: state.errors};
}

function collectBinds(state, node, path) {
    for (const bind of node.children) {
        if (bind.disabled) continue;
        const actions = bind.children.filter(child => !child.disabled);
        const command = actions.map(actionNode => {
            let text = actionNode.name;
            if (actionNode.args.length) text += " " + actionNode.args.join(" ");
            for (const key of Object.keys(actionNode.props)) text += " " + key + "=" + actionNode.props[key];
            return text;
        }).join("; ");
        const title = bind.props["hotkey-overlay-title"] || command || "No action";
        state.bindings.push({key: bind.name, title: title, action: command, source: path, line: bind.line});
    }
}

function expandHome(path, home) {
    if (!home) return path;
    if (path === "~") return home;
    if (path.slice(0, 2) === "~/") return home + path.slice(1);
    return path;
}

function normalize(path) {
    const absolute = path.charAt(0) === "/";
    const out = [];
    for (const part of path.split("/")) {
        if (part === "" || part === ".") continue;
        if (part === "..") {
            if (out.length && out[out.length - 1] !== "..") { out.pop(); continue; }
            if (!absolute) out.push("..");
            continue;
        }
        out.push(part);
    }
    return (absolute ? "/" : "") + out.join("/");
}

function basename(path) {
    const cut = path.lastIndexOf("/");
    return cut < 0 ? path : path.slice(cut + 1);
}

function dirname(path) {
    const cut = path.lastIndexOf("/");
    if (cut < 0) return "";
    if (cut === 0) return "/";
    return path.slice(0, cut);
}
