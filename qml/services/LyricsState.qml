// SPDX-License-Identifier: GPL-3.0-or-later
// Role: LyricsState.qml (lyrics layer, fan-in 1) — Q5 native lyric lookup.
// REL: scripts/lyrics.py::lookup – DEPRECATED(Q5->Q6); the chain (embedded → local LRC sidecar
// → metadata check → disk cache → offline check → LRCLIB) and the result shapes are frozen by
// tests/test_native_weather_lyrics.py.
// INVARIANT: fixture modes never spawn the store helper or the network; the worker protocol
// (LyricsSession's Process) is retired with this port.
// GOTCHA: the cache key is the LyricsModel.cacheSlug filename with a storedAt timestamp inside
// the JSON (FileView exposes no mtime); the old sha256 entries simply expire unread. Cache
// writes go through `lyrics.py --store` (write_json + the 128-entry maintenance) — quickshell
// 0.3.2 has no file-write API.
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "LyricsModel.js" as Lyrics

QtObject {
    id: root

    property var loader
    readonly property bool inert: Quickshell.env("LME_SHELL_DEMO") === "1" || Quickshell.env("LME_SHELL_PREVIEW") === "1"
        || Quickshell.env("LME_SHELL_BACKEND_DEMO") === "1" || Quickshell.env("LME_SHELL_SETTINGS") === "1"
    property int serial: 0
    property var pending: null  // {serial, song, next} — the in-flight flow after the async reads

    readonly property var xhrLoader: (url, onDone, onFail) => {
        const request = new XMLHttpRequest();
        request.open("GET", url);
        request.setRequestHeader("User-Agent", "LME-Shell/2 (https://github.com/longme179/lme-fedora-niri-qs)");
        request.setRequestHeader("Accept", "application/json");
        request.timeout = 7000;
        request.onload = () => {
            if (request.status === 404) return onDone({});
            try {
                const body = String(request.responseText || "");
                if (body.length > Lyrics.MAX_BYTES) throw new Error("Lyrics response is too large");
                const parsed = JSON.parse(body);
                if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Invalid lyrics response");
                onDone(parsed);
            } catch (failure) { onFail("Lyrics unavailable. Check your connection or retry."); }
        };
        request.onerror = request.ontimeout = () => onFail("Lyrics unavailable. Check your connection or retry.");
        request.send();
    }

    // The lookup entry point; done(result) fires exactly once per call (a newer call retires
    // the older one silently, matching the worker's requestKey guard in LyricsSession).
    function lookup(song, done) {
        const mine = ++serial;
        const settle = value => { if (mine === serial) done(value); };
        const fail = (message, status) => settle(Object.assign(Lyrics.result(), {status: status || "error", error: String(message).slice(0, 300)}));
        var request;
        try { request = Lyrics.track(song); }
        catch (failure) { return fail(failure.message || failure); }
        if (inert) return settle(Object.assign(Lyrics.result(), {status: "none"}));
        if (request.embedded) return settle(Lyrics.result(request.embedded, "Player metadata"));
        // Local LRC sidecar next (file:// URLs only, like the Python urlsplit guard).
        const url = String(request.url || "");
        if (url.indexOf("file://") === 0) {
            let path = url.slice(7);
            if (path.indexOf("localhost") === 0) path = path.slice(9);
            const sidecar = decodeURIComponent(path).replace(/\.[^.]*$/, ".lrc");
            return readFile(sidecar, body => {
                if (body) {
                    try { return settle(Lyrics.result(body, "Local LRC")); }
                    catch (failure) { /* oversized/corrupt sidecar falls through */ }
                }
                continueLookup(mine, settle, fail, request);
            });
        }
        continueLookup(mine, settle, fail, request);
    }

    function continueLookup(mine, settle, fail, request) {
        if (!request.title || !request.artist) return settle(Object.assign(Lyrics.result(), {status: "metadata"}));
        const directory = cacheDirectory();
        readFile(directory + "/" + Lyrics.cacheSlug(request) + ".json", body => {
            if (body) {
                try {
                    const cached = JSON.parse(body);
                    const ttl = cached.status === "none" ? 6 * 3600 : 14 * 86400;
                    if (typeof cached.storedAt === "number" && Date.now() / 1000 - cached.storedAt >= 0
                            && Date.now() / 1000 - cached.storedAt < ttl
                            && ["ready", "instrumental", "none"].indexOf(cached.status) >= 0)
                        return settle(Lyrics.result(cached.raw || "", "LRCLIB · cached", cached.status === "instrumental"));
                } catch (failure) { /* unreadable cache falls through */ }
            }
            if (!request.online) return settle(Object.assign(Lyrics.result(), {status: "offline"}));
            onlineLookup(mine, settle, fail, request, directory);
        });
    }

    function onlineLookup(mine, settle, fail, request, directory) {
        const params = {track_name: request.title, artist_name: request.artist};
        if (request.album) params.album_name = request.album;
        if (request.duration) params.duration = request.duration;
        const parts = [];
        for (var key in params) parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(params[key]));
        const transport = loader || xhrLoader;
        transport("https://lrclib.net/api/get?" + parts.join("&"), value => {
            const raw = value && (value.syncedLyrics || value.plainLyrics) || "";
            const found = Lyrics.result(raw, "LRCLIB", value && value.instrumental === true);
            if (mine !== serial) return;
            settle(found);
            store(directory, Lyrics.cacheSlug(request), raw, found.status);  // best-effort, like the Python path
        }, message => fail(message));
    }

    property bool storing: false
    function store(directory, filename, raw, status) {
        // One in-flight store; a second write while one runs is dropped (best-effort, like
        // the Python path's except OSError: pass).
        if (inert || !directory || storing) return;
        storing = true;
        storeWorker.payload = JSON.stringify({directory: directory, filename: filename, raw: raw, status: status});
        storeWorker.running = true;
    }

    property Process storeWorker: Process {
        id: worker
        command: ["python3", "-u", Quickshell.shellPath("scripts/lyrics.py"), "--store"]
        stdinEnabled: true
        property string payload: ""
        onStarted: write(payload + "\n")
        stdout: SplitParser { onRead: value => {} }
        stderr: SplitParser { onRead: line => console.warn("[lyrics-store]", line) }
        onExited: root.storing = false
    }

    function cacheDirectory() {
        const base = Quickshell.env("XDG_CACHE_HOME") || (Quickshell.env("HOME") || "") + "/.cache";
        return base + "/lme-shell/lyrics";
    }

    // One async file read with a settle-anyway fallback: whichever of onLoaded / the 400 ms
    // timer fires first wins (FileView prints missing-file errors; every unreadable file is
    // absent to the flow, like the Python try/except). reload() covers re-reading the same
    // path (onLoaded does not re-fire for an unchanged path).
    property FileView reader: FileView {
        id: view
        printErrors: false
        property var callback: null
        onLoaded: root.readerSettled(text())
    }
    property Timer readerFallback: Timer {
        interval: 400
        onTriggered: root.readerSettled("")
    }
    function readFile(path, callback) {
        reader.callback = callback;
        if (reader.path === path) reader.reload(); else reader.path = path;
        readerFallback.restart();
    }
    function readerSettled(body) {
        readerFallback.stop();
        const done = reader.callback;
        if (!done) return;
        reader.callback = null;
        done(body);
    }
}
