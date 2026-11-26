// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: Heartbeat.qml (shared layer) — GUI-thread stall watchdog, off unless LME_SHELL_WATCHDOG=1.
// REL: qml/components/PageHost.qml – build marks; scripts/perf/README.md – the harness that reads the lines.
pragma Singleton

import QtQuick
import Quickshell

// A 4 ms timer can only fire when the GUI thread is free, so the gap between two beats is the
// time the thread was unavailable to input and rendering. Off by default: the timer never runs
// and mark() returns on its first line, so a normal session carries nothing but this object.
QtObject {
    id: root
    readonly property bool enabled: Quickshell.env("LME_SHELL_WATCHDOG") === "1"
    readonly property int intervalMs: 4
    readonly property int thresholdMs: 30
    // The clock is resolved once; Date.now() (1 ms steps) is the fallback on engines without
    // performance.now().
    readonly property bool hires: typeof performance !== "undefined" && typeof performance.now === "function"
    property int beats: 0
    property int stalls: 0
    property real worstMs: 0
    // Marks made since the previous beat: {n: name, t: clock}. A stall line names them.
    property var marks: []
    property real last: 0
    signal stalled(real lateMs, real epochMs, string marks)

    function now() { return hires ? performance.now() : Date.now() }
    function mark(name) { if (enabled) marks.push({n: ("" + name).replace(/[;|\s]+/g, "_"), t: now()}) }
    function beat() {
        const t = now();
        if (last > 0) {
            const late = t - last - intervalMs;
            if (late > thresholdMs) {
                stalls++;
                if (late > worstMs) worstMs = late;
                // "<name>+<ms>" is the offset from the beat that opened the window, so the
                // last marks before a stall are the handlers or builds that ran inside it.
                const names = marks.map(m => m.n + "+" + Math.max(0, m.t - last).toFixed(1)).join(";");
                stalled(late, Date.now(), names);
            }
        }
        last = t;
        if (marks.length) marks = [];
        beats++;
    }
    onStalled: (late, epoch, names) => {
        console.warn("@@HEARTBEAT stall late=" + late.toFixed(1) + " at=" + epoch + " beats=" + beats
            + " marks=" + (names || "-"));
    }
    property Timer timer: Timer { interval: root.intervalMs; repeat: true; running: root.enabled; onTriggered: root.beat() }
}
