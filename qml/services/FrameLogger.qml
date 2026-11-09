// SPDX-License-Identifier: GPL-3.0-or-later
// Role: FrameLogger.qml (shared layer, fan-in 1).
// Shared component/helper; keep API stable for wide QML reuse.
pragma Singleton

import QtQuick
import Quickshell

QtObject {
    id: root
    property bool enabled: Quickshell.env("LME_GLASS_TELEMETRY") === "1"
    property var rings: ({})
    property var lastTs: ({})

    function sample(ts, cls) {
        if (!enabled) return;
        const key = cls || "default";
        const prev = lastTs[key] || 0;
        const dt = prev ? ts - prev : 0;
        lastTs[key] = ts;
        const ring = rings[key] || [];
        if (ring.length < 128) ring.push(dt);
        else { ring.shift(); ring.push(dt); }
        rings[key] = ring;
    }

    function format(cls) {
        const key = cls || "default";
        const ring = rings[key] || [];
        if (!ring.length) return "glass telemetry[" + key + "]: no samples";
        const sorted = [...ring].sort((a, b) => a - b);
        const p50 = sorted[Math.floor(sorted.length * 0.5)];
        const p99 = sorted[Math.floor(sorted.length * 0.99)] ?? sorted[sorted.length - 1];
        return "glass telemetry[" + key + "]: p50=" + p50.toFixed(2) + "ms p99=" + p99.toFixed(2) + "ms count=" + sorted.length;
    }

    function flush() {
        const keys = Object.keys(rings);
        const lines = keys.length ? keys.map(k => format(k)) : [format()];
        for (const line of lines) console.log(line);
        return lines.join("\n");
    }

    property Timer flushTimer: Timer { interval: 10000; running: root.enabled; repeat: true; onTriggered: root.flush() }
}
