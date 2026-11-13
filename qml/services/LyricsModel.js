// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: LyricsModel.js (lyrics layer, fan-in 1) — pure LRC contracts for the Q5 native lyrics.
// REL: scripts/lyrics.py::parse/track/result – DEPRECATED(Q5->Q6); bounds (512 KiB, 4000 lines/
// cues), the offset tag, equal-time grouping and every status are frozen by
// tests/test_native_weather_lyrics.py.
// INVARIANT: byte budgets use UTF-8 code-point sums (JS strings are UTF-16; the estimate
// matches Python len(str.encode('utf-8')) for every representable code point).
// GOTCHA: the BOM is stripped before parsing (the Python side decoded utf-8-sig).
.pragma library

var MAX_BYTES = 512 * 1024;
var MAX_LINES = 4000;
var STAMP = /\[(\d{1,3}):([0-5]\d)(?:[.:](\d{1,3}))?\]/g;
var OFFSET = /\[offset:([+-]?\d+)\]/i;
var TAG_LINE = /^\s*\[[a-zA-Z]+:.*\]\s*$/;

function byteLength(text) {
    var total = 0;
    for (var i = 0; i < text.length; i++) {
        const code = text.charCodeAt(i);
        if (code < 0x80) total += 1;
        else if (code < 0x800) total += 2;
        else if (code >= 0xd800 && code <= 0xdbff) { total += 4; i++; }  // surrogate pair
        else total += 3;
    }
    return total;
}

function parse(text) {
    if (typeof text !== "string" || byteLength(text) > MAX_BYTES) throw new Error("Lyrics are too large or invalid");
    if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
    const found = text.match(OFFSET);
    const offset = found ? parseInt(found[1], 10) / 1000 : 0;
    var cues = [], expanded = 0;
    const lines = text.split("\n");
    for (var i = 0; i < lines.length && i < MAX_LINES; i++) {
        var stamps = [];
        var match;
        STAMP.lastIndex = 0;
        while ((match = STAMP.exec(lines[i])) !== null) stamps.push(match);
        const words = lines[i].replace(STAMP, "").trim();
        for (var s = 0; s < stamps.length; s++) {
            expanded += byteLength(words) + 64;
            if (expanded > MAX_BYTES) throw new Error("Expanded lyrics are too large");
            const stamp = stamps[s];
            const fraction = stamp[3] ? parseInt(stamp[3], 10) / Math.pow(10, stamp[3].length) : 0;
            const seconds = parseInt(stamp[1], 10) * 60 + parseInt(stamp[2], 10) + fraction;
            cues.push({time: Math.round(Math.max(0, seconds - offset) * 1000) / 1000, text: words});
            if (cues.length >= MAX_LINES) break;
        }
        if (cues.length >= MAX_LINES) break;
    }
    cues.sort(function (a, b) { return a.time - b.time; });
    // Group equal timestamps so translations/duets remain visible together.
    var grouped = [];
    for (var c = 0; c < cues.length; c++) {
        const cue = cues[c];
        if (grouped.length && grouped[grouped.length - 1].time === cue.time) {
            const previous = grouped[grouped.length - 1];
            if (cue.text && previous.text.split("\n").indexOf(cue.text) < 0) previous.text += "\n" + cue.text;
        } else grouped.push({time: cue.time, text: cue.text});
    }
    var plain = [];
    for (var p = 0; p < lines.length && p < MAX_LINES; p++) if (!TAG_LINE.test(lines[p])) plain.push(lines[p]);
    return {synced: grouped.length > 0, lines: grouped, plain: grouped.length ? "" : plain.join("\n").trim()};
}

function track(request) {
    if (!request || typeof request !== "object" || Array.isArray(request)) throw new Error("Expected a lyric request");
    var result = {};
    const limits = {title: 512, artist: 512, album: 512, url: 4096, embedded: MAX_BYTES};
    for (var key in limits) {
        var value = request[key] === undefined ? "" : request[key];
        if (typeof value !== "string" || byteLength(value) > limits[key]) throw new Error("Invalid " + key);
        result[key] = value.trim();
    }
    var duration = request.duration === undefined ? 0 : request.duration;
    if (typeof duration !== "number" || !isFinite(duration) || duration < 0 || duration > 86400) throw new Error("Invalid duration");
    if (typeof (request.online === undefined ? false : request.online) !== "boolean") throw new Error("Online lookup must be boolean");
    result.duration = Math.round(duration);
    result.online = request.online === true;
    return result;
}

function result(text, source, instrumental) {
    const parsed = parse(text || "");
    const status = instrumental ? "instrumental" : (parsed.lines.length || parsed.plain) ? "ready" : "none";
    return {synced: parsed.synced, lines: parsed.lines, plain: parsed.plain, status: status, source: source || ""};
}

// The native cache slug (QML has no sha256): encodeURIComponent keeps every Linux-filename
// byte except '/' (encoded as %2F), so the join is collision-free for distinct songs.
function cacheSlug(song) {
    return [song.title, song.artist, song.album, song.duration].map(function (part) {
        return encodeURIComponent(String(part === undefined ? "" : part));
    }).join("~");
}
