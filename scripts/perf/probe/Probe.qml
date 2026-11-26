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
            const point = item.mapToScene(Qt.point(item.width / 2, item.height / 2));
            const live = win === "overlay" ? overlay.visible : true;
            return JSON.stringify({item: name, found: true, win: isSettings ? "settings" : win, shown: shown && live,
                x: point.x + (win === "overlay" ? overlay.viewport.x : 0),
                y: point.y + (win === "overlay" ? overlay.viewport.y : 0),
                w: item.width, h: item.height});
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
            if (settings) o.settings = {page: settings.page, search: settings.searchText(), toast: s.statusMessage.length > 0};
        } catch (error) { o.settingsError = "" + error; }
        // Window-relative, and only while the pointer is over the window that reports it.
        try {
            const watched = isSettings ? settingsHover : hover;
            if (watched) o.pointer = [watched.point.position.x, watched.point.position.y, watched.hovered];
        } catch (error) { o.pointerError = "" + error; }
        try {
            if (island) o.island = {shown: island.shown, mounted: island.mounted, dormant: island.dormant,
                warmup: island.warmupActive, moving: island.transitioning};
        } catch (error) { o.islandError = "" + error; }
        try {
            if (loader) o.stage = [loader.item ? 1 : 0, loader.shown, loader.dormant, loader.warmupActive];
        } catch (error) { o.stageError = "" + error; }
        try {
            if (overlay) o.overlay = [overlay.visible, overlay.width, overlay.height, overlay.viewport.x, overlay.viewport.y];
        } catch (error) { o.overlayError = "" + error; }
        return JSON.stringify(o);
    }
    function sample() { try { samples++; out("S " + ms().toFixed(1) + " " + stateJson()); } catch (error) { console.warn("@@PROBE !sample " + error); } }
    property Timer sampler: Timer { interval: 40; repeat: true; running: root.watch; onTriggered: root.sample() }
}
