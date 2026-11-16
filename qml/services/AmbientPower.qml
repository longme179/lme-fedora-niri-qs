pragma Singleton
import QtQuick
import Quickshell

// PB-31: ambient power predicate. Whether always-on decorative surfaces
// (desktop ambient shapes, audio spectrum) may run at all.
//
// NAME NOTE: the design called this singleton "PowerState", but that name is
// already taken by the battery/AC/UPower service (qml/services/PowerState.qml).
// This is the same predicate under a non-conflicting name; consumers reference
// it as AmbientPower.
//
// Reactive on purpose — no timers, no debounce: a stale fullscreen cache
// outlives the real exit (iNiR's GameMode documented this exact bug).
//
// "Covered" derivation: niri 26.04 exposes no is_fullscreen flag, so a
// window whose layout covers >= 98% of both dimensions of an output counts.
// niri reserves the bar's exclusive zone plus margins, so a normal maximized
// tiled window tops out around ~94% height and stays active; only truly
// fullscreen windows (100%) pause ambient.
// Both failure modes are benign: a false positive only freezes decoration
// the user cannot see; a false negative only animates hidden decoration.

QtObject {
    id: root

    // Manual override hook for a future GameMode toggle (PB-11). false = automatic.
    property bool ambientSuppressed: false

    readonly property bool ambientActive: !ShellState.batterySaverActive
                                        && !root.outputCovered
                                        && !root.ambientSuppressed

    // Human-readable cause, for logs and settings display.
    readonly property string state: root.ambientActive ? "active"
        : root.ambientSuppressed ? "suppressed"
        : ShellState.batterySaverActive ? "battery"
        : "covered"

    // niri's windows[].layout has carried different shapes across versions.
    // 26.04 ships window_size as a [w, h] array; other builds use
    // {width,height} or {size:{width,height}}. Handle all three.
    function _windowSize(win) {
        const l = win && win.layout;
        if (!l) return null;
        if (l.width && l.height) return { width: l.width, height: l.height };
        const ws = l.window_size || l.size;
        if (Array.isArray(ws) && ws.length >= 2) return { width: ws[0], height: ws[1] };
        if (ws && ws.width && ws.height) return { width: ws.width, height: ws.height };
        return null;
    }

    readonly property bool outputCovered: {
        const wins = (NiriState.section && NiriState.section.windows) || [];
        const screens = Quickshell.screens;
        for (let i = 0; i < wins.length; i++) {
            const size = root._windowSize(wins[i]);
            if (!size) continue;
            for (let s = 0; s < screens.length; s++) {
                // NB: ShellScreen width/height match niri logical size at scale 1.0;
                // on scaled outputs the ratio shrinks (benign: ambient may keep animating while hidden).
                const w = screens[s].width ?? 0;
                const h = screens[s].height ?? 0;
                if (w <= 0 || h <= 0) continue;
                if (size.width >= w * 0.98 && size.height >= h * 0.98) return true;
            }
        }
        return false;
    }
}