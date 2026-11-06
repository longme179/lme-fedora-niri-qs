// SPDX-License-Identifier: GPL-3.0-or-later
.pragma library

// Floating-window origin resolution (Liquid Glass 2.0, gap A2 part 2).
// Wayland does not expose a floating QWindow's screen position; niri does.
// Priority: anchors-first, then niri IPC window id where Quickshell exposes
// it, then the shell-owned unique QsWindow title (single match only).
// Unknown or ambiguous toplevels remain centered. No per-frame work: the
// caller re-evaluates only when niri snapshots or window geometry change.
function resolve(anchors, margins, windowSize, hostSize, outputSize, windows, workspaces, outputName, windowIds, title) {
    const width = hostSize.width, height = hostSize.height;
    if (anchors) return {x: anchors.left ? margins.left : anchors.right ? outputSize.width - windowSize.width - margins.right : (outputSize.width - windowSize.width) / 2,
        y: anchors.top ? margins.top : anchors.bottom ? outputSize.height - windowSize.height - margins.bottom : (outputSize.height - windowSize.height) / 2};
    const list = windows || [];
    const spaces = workspaces || [];
    const at = win => {
        if (!win) return null;
        const ws = spaces.find(item => item.id === win.workspace_id);
        const layout = win.layout || {};
        const pos = layout.tile_pos_in_workspace_view, offset = layout.window_offset_in_tile;
        if (ws && ws.output === outputName && pos && offset && pos.length === 2 && offset.length === 2 && [...pos, ...offset].every(Number.isFinite))
            return {x: pos[0] + offset[0], y: pos[1] + offset[1]};
        return null;
    };
    for (const raw of (windowIds || [])) {
        const num = typeof raw === "string" && raw !== "" ? Number(raw) : raw;
        if (Number.isFinite(num)) { const p = at(list.find(item => item.id === num)); if (p) return p; }
    }
    if (title) { const matches = list.filter(item => item.title === title); const p = matches.length === 1 ? at(matches[0]) : null; if (p) return p; }
    return {x: (outputSize.width - width) / 2, y: (outputSize.height - height) / 2};
}
