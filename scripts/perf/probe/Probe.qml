// SPDX-License-Identifier: AGPL-3.0-or-later
// PERF HARNESS — SCRATCH TREE ONLY. scripts/perf/probe_patch.py copies this file into a
// throwaway copy of the tree as qml/services/Probe.qml; a normal shell never loads it.
// It never changes behaviour: it only writes one "@@PROBE <kind> <ms> ..." line per event.
//   sink epoch=<ms> clock=<ms> t0=<ms>   clock alignment, first line: a probe time `t` is
//                        epoch `t0 + t + (epoch - clock)`, so it lines up with the injector
//   m <ms> <name> [<extra>] a mark on the GUI thread
//   F <ms> <window>         frameSwapped of bar / overlay / settings
//   S <ms> <json>           state sampler, every 40 ms while Probe.watch is on
// Lines go to $LME_PERF_PROBE_LOG/probe.<process>.log through a `cat >>` helper (the
// daemonized Settings process has no stderr), or to stderr when that variable is unset.
// Nothing here may throw into the caller: every entry point catches its own errors.
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    readonly property bool isSettings: Quickshell.env("LME_SHELL_SETTINGS") === "1"
    readonly property bool hires: typeof performance !== "undefined" && typeof performance.now === "function"
    readonly property string sinkPath: {
        const dir = Quickshell.env("LME_PERF_PROBE_LOG");
        return dir ? dir + "/probe." + (isSettings ? "settings" : "shell") + ".log" : "";
    }
    property bool sinkReady: false
    property var held: []
    property real t0: 0
    property string stage: "boot"
    property bool watch: false
    property int frames: 0
    property int keyEvents: 0
    property int samples: 0
    property int hostSeq: 0
    // Registered objects. Plain var holders on purpose: functions read them directly and
    // no binding does, so no change signal is needed and no QML identity can go stale.
    property var windows: ({})
    property var hosts: ({})
    property var tabs: ({})
    property var nav: ({})
    property var cc: null
    property var settings: null
    property var island: null
    property var loader: null
    property var hover: null
    // Settings runs in its own window and its own process: its pointer position is read here.
    property var settingsHover: null

    function now() { return hires ? performance.now() : Date.now() }
    function ms() { return now() - t0 }
    function emit(text) {
        if (sinkPath === "") console.warn("@@PROBE " + text);
        else if (sinkReady) sink.write("@@PROBE " + text + "\n");
        else if (held.length < 4000) held.push(text); // boot lines wait for the helper
    }
    function out(line) {
        try { emit(line); } catch (error) { console.warn("@@PROBE !sink " + error); }
    }
    function mark(name, extra) {
        try { out("m " + ms().toFixed(2) + " " + name + (extra ? " " + extra : "")); }
        catch (error) { console.warn("@@PROBE !mark " + error); }
    }
    function frame(name) { frames++; out("F " + ms().toFixed(2) + " " + name); }
    function key(site, info) { keyEvents++; mark("key " + site, info); }
    function setStage(name) { stage = "" + name; mark("stage " + stage); }
    function watchWindow(name, win) { windows[name] = win; }
    function hostName(name) {
        if (!hosts[name]) return name;
        return name + "#" + (++hostSeq);
    }

    Component.onCompleted: t0 = now()
    property Process sink: Process {
        command: ["sh", "-c", "exec cat >> \"$1\"", "sh", sinkPath]
        stdinEnabled: true
        running: sinkPath !== ""
        onStarted: {
            sinkReady = true;
            root.out("sink epoch=" + Date.now() + " clock=" + root.now() + " t0=" + root.t0 + " hires=" + root.hires);
            const lines = root.held;
            root.held = [];
            for (let i = 0; i < lines.length; i++) root.out(lines[i]);
        }
    }

    // ---- lookups -------------------------------------------------------------------
    function find(obj, name, depth) {
        if (!obj || depth > 80) return null;
        if (obj.objectName === name) return obj;
        const kids = obj.children;
        for (let i = 0; i < kids.length; i++) {
            const hit = find(kids[i], name, depth + 1);
            if (hit) return hit;
        }
        return null;
    }
    function lookup(name) {
        if (tabs[name]) return tabs[name];
        if (nav[name]) return nav[name];
        const names = Object.keys(windows);
        for (let i = 0; i < names.length; i++) {
            const win = windows[names[i]];
            const hit = win && win.contentItem ? find(win.contentItem, name, 0) : null;
            if (hit) return hit;
        }
        return null;
    }
    // Center of a named item in output coordinates. The overlay is a small surface parked
    // at `viewport`, so items inside it get that offset; the bar sits at the output origin.
    function centreOf(item) {
        // Since Qt 6.7 many Quick types (Controls, Layouts) are not Items: their mapping
        // methods exist in the metaobject but calling them throws. A real Item (most of
        // the shell's own items) maps exactly; a Control maps through a part that fills
        // it, which keeps the transforms of its parents (the panel stage glides in by
        // translating its content: the x/y of a tab never change). Anything else falls
        // back to adding the readable x/y up the parent chain - exact only where nothing
        // transforms the tree (the Settings sidebar).
        try {
            return item.mapToScene(Qt.point(item.width / 2, item.height / 2));
        } catch (error) {
            for (const part of [item.background, item.contentItem]) {
                try {
                    if (part && Math.abs(part.width - item.width) < 1 && Math.abs(part.height - item.height) < 1)
                        return part.mapToScene(Qt.point(part.width / 2, part.height / 2));
                } catch (ignored) {}
            }
            let x = item.width / 2, y = item.height / 2, node = item, guard = 0;
            while (node && guard++ < 64) {
                x += node.x || 0;
                y += node.y || 0;
                if (!node.parent) break;
                node = node.parent;
            }
            return Qt.point(x, y);
        }
    }
    function rectJson(name) {
        try {
            const item = lookup(name);
            if (!item) return JSON.stringify({item: name, found: false});
            const overlay = windows.overlay;
            let win = "bar", shown = item.width > 0 && item.height > 0;
            for (let p = item; p; p = p.parent) {
                if (!p.visible || !p.enabled) shown = false;
                if (overlay && p === overlay.contentItem) win = "overlay";
            }
            const point = centreOf(item);
            // A clipped ancestor (the Settings sidebar's Flickable) hides everything it
            // does not cover: a delegate above its fold still maps inside the window and
            // reports geometry, but paints and takes input nowhere. mapFromScene on each
            // clipping ancestor turns the centre into that viewport's coordinates; an
            // entry the ancestor does not fully cover is not shown.
            for (let clipper = item.parent; clipper; clipper = clipper.parent) {
                if (!clipper.clip) continue;
                try {
                    // mapFromScene/mapFromItem are not callable on many Quick types
                    // since 6.7 (the metaobject lists them, calling throws). The shell's
                    // clipped trees carry no transforms, so plain x/y addition reaches
                    // the clipper's viewport: a Flickable's contentItem sits at
                    // (-contentX, -contentY) inside it, which the sum picks up by itself.
                    let cx = item.width / 2, cy = item.height / 2, walk = item;
                    while (walk && walk !== clipper) {
                        cx += walk.x || 0; cy += walk.y || 0;
                        walk = walk.parent;
                    }
                    if (walk !== clipper) continue;   // the clipper is not an ancestor
                    if (cx < item.width / 2 || cy < item.height / 2
                        || cx > clipper.width - item.width / 2
                        || cy > clipper.height - item.height / 2) {
                        shown = false;
                        break;
                    }
                } catch (error) { /* not an Item: nothing clips through it */ }
            }
            const live = win === "overlay" ? overlay.visible : true;
            return JSON.stringify({item: name, found: true, win: isSettings ? "settings" : win, shown: shown && live,
                x: point.x + (win === "overlay" ? overlay.viewport.x : 0),
                y: point.y + (win === "overlay" ? overlay.viewport.y : 0),
                w: item.width, h: item.height});
        } catch (error) {
            return JSON.stringify({item: name, found: false, error: "" + error});
        }
    }

    function hitJson(name) {
        // What lies on top of the named item's centre: every item of the Settings window that
        // contains the point, in paint order (a later sibling and its children paint over an
        // earlier one), so the last entries are what a press there reaches first.
        try {
            const item = lookup(name);
            if (!item) return JSON.stringify({item: name, found: false});
            const win = windows.settings;
            if (!win || !win.contentItem) return JSON.stringify({item: name, found: false, error: "no settings window"});
            const point = centreOf(item);
            const under = [], refs = [];
            const walk = function (node, depth, origin) {
                const kids = node.children || [];
                for (let i = 0; i < kids.length; i++) {
                    const kid = kids[i];
                    let inside = false, at = null;
                    try {
                        const local = kid.mapFromScene(point);
                        inside = local.x >= 0 && local.y >= 0 && local.x <= kid.width && local.y <= kid.height;
                        at = kid.mapToScene(Qt.point(0, 0));
                    } catch (error) { at = null; }
                    if (!at) {
                        // not an Item: the plain sum of the parent chain, exact where nothing transforms
                        at = Qt.point(origin.x + (kid.x || 0), origin.y + (kid.y || 0));
                        inside = point.x >= at.x && point.y >= at.y && point.x <= at.x + kid.width && point.y <= at.y + kid.height;
                    }
                    if (inside) {
                        under.push([depth, String(kid).split("(")[0], kid.objectName || "", Math.round(kid.width),
                                    Math.round(kid.height), kid.visible !== false, kid.enabled !== false]);
                        refs.push(kid);
                    }
                    walk(kid, depth + 1, at);
                }
            };
            walk(win.contentItem, 0, Qt.point(0, 0));
            const part = function (kid) { return kid === item || kid === item.background || kid === item.contentItem; };
            let last = -1;
            for (let i = 0; i < refs.length; i++) if (part(refs[i])) last = i;
            const top = under.slice(-12), from = under.length - top.length;
            return JSON.stringify({item: name, found: true, point: [Math.round(point.x * 10) / 10, Math.round(point.y * 10) / 10],
                depth: under.length, target: last, from: from,
                chain: top.map(function (entry, index) { return [from + index].concat(entry); })});
        } catch (error) {
            return JSON.stringify({item: name, found: false, error: "" + error});
        }
    }
    // ---- state ---------------------------------------------------------------------
    function chain(item) {
        const parts = [];
        for (let i = 0; item && i < 14; i++) {
            parts.push(item.objectName || String(item).split("(")[0]);
            item = item.parent;
        }
        return parts.join(">") || "-";
    }
    function focusOf(name) {
        const win = windows[name];
        return win ? chain(win.activeFocusItem) : "-";
    }
    function hostJson() {
        const out = {};
        for (const name of Object.keys(hosts)) {
            const host = hosts[name];
            if (host && typeof host.probeState === "function") out[name] = host.probeState();
        }
        return out;
    }
    function stateJson() {
        const s = ShellState;
        const overlay = windows.overlay;
        const o = {ms: Math.round(ms() * 100) / 100, proc: isSettings ? "settings" : "shell", stage: stage,
            panelOpen: s.panelOpen, activityOpen: s.activityOpen, controlOpen: s.controlOpen,
            settingsOpen: s.settingsOpen, kind: s.panelKind, backendReady: s.backendReady,
            status: s.statusMessage, auth: s.authenticationActive, locked: LockState.locked,
            frames: frames, keyEvents: keyEvents, beats: Heartbeat.beats, stalls: Heartbeat.stalls,
            worst: Heartbeat.worstMs, focus: focusOf("overlay"), hosts: hostJson()};
        try {
            if (cc) o.cc = {tab: cc.selectedTab ? cc.selectedTab.id : "?", tabs: cc.tabEntries.map(t => t.id), editing: cc.editing};
        } catch (error) { o.ccError = "" + error; }
        try {
            if (settings) o.settings = {page: settings.page, search: settings.searchText(), toast: s.statusMessage.length > 0,
                pages: settings.probePages ? settings.probePages() : [],
                navY: settings.probeNavY ? settings.probeNavY() : -1,
                navShown: settings.probeNavShown ? settings.probeNavShown() : {},
                flick: settings.probeFlick ? settings.probeFlick() : {},
                scan: s.pendingActions ? !!s.pendingActions.wallpaperScan : null,
                last: s.lastResult ? [s.lastResult.action, s.lastResult.ok,
                                      String(s.lastResult.message || "").slice(0, 60)] : null};
        } catch (error) { o.settingsError = "" + error; }
        // Window-relative, and only while the pointer is over the window that reports it.
        try {
            const watched = isSettings ? settingsHover : hover;
            if (watched) o.pointer = [watched.point.position.x, watched.point.position.y, watched.hovered];
        } catch (error) { o.pointerError = "" + error; }
        try {
            if (isSettings && windows.settings) o.window = [windows.settings.visible, windows.settings.width, windows.settings.height];
        } catch (error) { o.windowError = "" + error; }
        try {
            if (island) o.island = {shown: island.shown, mounted: island.mounted, dormant: island.dormant,
                warmup: island.warmupActive, moving: island.transitioning};
        } catch (error) { o.islandError = "" + error; }
        try {
            if (loader) o.panel = [loader.item ? 1 : 0, loader.shown, loader.dormant, loader.warmupActive, loader.transitioning];
        } catch (error) { o.panelError = "" + error; }
        try {
            if (overlay) o.overlay = [overlay.visible, overlay.width, overlay.height, overlay.viewport.x, overlay.viewport.y];
        } catch (error) { o.overlayError = "" + error; }
        return JSON.stringify(o);
    }
    function sample() { try { samples++; out("S " + ms().toFixed(1) + " " + stateJson()); } catch (error) { console.warn("@@PROBE !sample " + error); } }
    property Timer sampler: Timer { interval: 40; repeat: true; running: root.watch; onTriggered: root.sample() }
}
