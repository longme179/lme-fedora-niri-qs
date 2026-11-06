// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton

import QtQuick
import Quickshell

QtObject {
    property bool enabled: Quickshell.env("LME_GLASS_TELEMETRY") === "1"
    property var ring: []
    property real lastTs: 0

    function sample(ts) {
        if (!enabled) return;
        const dt = lastTs ? ts - lastTs : 0;
        lastTs = ts;
        if (ring.length < 128) ring.push(dt);
        else { ring.shift(); ring.push(dt); }
    }

    function format(): string {
        if (!ring.length) return "glass telemetry: no samples";
        const sorted = [...ring].sort((a, b) => a - b);
        const p50 = sorted[Math.floor(sorted.length * 0.5)];
        const p99 = sorted[Math.floor(sorted.length * 0.99)] ?? sorted[sorted.length - 1];
        return `glass telemetry: p50=${p50.toFixed(2)}ms p99=${p99.toFixed(2)}ms count=${sorted.length}`;
    }

    function flush(): string {
        const line = format();
        console.log(line);
        return line;
    }
}
