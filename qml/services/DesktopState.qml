pragma Singleton
import QtQuick
import Quickshell

QtObject {
    id: root
    property bool editing: false
    readonly property bool enabled: ShellState.preferences.desktopEnabled === true
    readonly property var widgets: ShellState.preferences.desktopWidgets || {}
    onEnabledChanged: if (!enabled) editing = false
    function matches(record, screen) {
        return record && record.enabled && (record.output === screen.name || record.output === "primary" && screen === Quickshell.screens[0]);
    }
    function patch(id, values) { ShellState.run("setting", {key: "desktopWidgets", token: id, value: values}); }
    function add(type, output) {
        if (Object.keys(widgets).length >= 12) return;
        const count = Object.keys(widgets).length;
        const id = type + "-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
        patch(id, {type: type, output: output || "primary", x: .08 + (count % 4) * .18, y: .12 + (count % 3) * .15,
            width: type === "clock" ? 320 : 420, height: type === "clock" ? 200 : 440, enabled: true, interactive: true});
    }
    function toggleEdit() {
        if (ShellState.settingsApp && !ShellState.demo) ShellState.run("desktopEdit");
        else if (enabled) editing = !editing;
        else ShellState.openSettingsPage("desktop");
    }
}
