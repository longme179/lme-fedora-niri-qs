// Role: DesktopState.qml (desktop layer, fan-in 7).
// Shared component/helper; keep API stable for wide QML reuse.
pragma Singleton
import QtQuick
import Quickshell

QtObject {
    id: root
    property bool editing: false
    readonly property bool enabled: ShellState.settingsPageAvailable("desktop") && ShellState.preferences.desktopEnabled === true
    readonly property var widgets: ShellState.preferences.desktopWidgets || {}
    onEnabledChanged: if (!enabled) editing = false
    function matches(record, screen) {
        return record && record.enabled && (record.output === screen.name || record.output === "primary" && screen === Quickshell.screens[0]);
    }
    function patch(id, values) { ShellState.run("setting", {key: "desktopWidgets", token: id, value: values}); }
    function add(type, output, screen) {
        if (Object.keys(widgets).length >= 12) return;
        const id = type + "-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
        const size = ({clock: [320, 200], weather: [360, 300], calendar: [340, 400], user: [340, 240]})[type] || [420, 440];
        const spot = place(size[0], size[1], screen);
        patch(id, {type: type, output: output || (screen ? screen.name : "primary"), x: spot[0], y: spot[1],
            width: size[0], height: size[1], enabled: true, interactive: true});
    }
    // P2: new widgets land in the first empty region of the target screen — a coarse
    // grid scan that skips candidates overlapping any widget already shown there
    // (matches() defines "shown on this screen"). The old cascade stays as the
    // fallback for crowded screens or callers without screen information.
    function place(width, height, screen) {
        const count = Object.keys(widgets).length;
        if (!screen || !screen.width) return [.08 + (count % 4) * .18, .12 + (count % 3) * .15];
        const taken = [];
        for (const id of Object.keys(widgets)) {
            const record = widgets[id];
            if (!matches(record, screen)) continue;
            const w = record.width || 320, h = record.height || 240;
            taken.push([record.x * Math.max(1, screen.width - w), record.y * Math.max(1, screen.height - h), w, h]);
        }
        for (let gy = .05; gy <= .9; gy += .12) {
            for (let gx = .04; gx <= .92; gx += .08) {
                const x = gx * screen.width, y = gy * screen.height;
                if (x + width > screen.width || y + height > screen.height) continue;
                if (taken.every(rect => x + width <= rect[0] + 8 || x >= rect[0] + rect[2] - 8
                    || y + height <= rect[1] + 8 || y >= rect[1] + rect[3] - 8))
                    return [Math.min(1, x / Math.max(1, screen.width - width)), Math.min(1, y / Math.max(1, screen.height - height))];
            }
        }
        return [.08 + (count % 4) * .18, .12 + (count % 3) * .15];
    }
    function toggleEdit() {
        if (ShellState.settingsApp && !ShellState.demo) ShellState.run("desktopEdit");
        else if (enabled) editing = !editing;
        else ShellState.openSettingsPage("desktop");
    }
}
