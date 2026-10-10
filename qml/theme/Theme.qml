pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../services"

QtObject {
    id: root
    property var custom: ({})
    readonly property color background: custom.background || "#22212c"
    readonly property color panel: custom.panel || "#2d293d"
    readonly property color surface: custom.surface || "#393447"
    readonly property color text: custom.text || "#f8f8f2"
    readonly property color muted: custom.muted || "#aaa6c0"
    readonly property color purple: custom.purple || "#9580ff"
    readonly property color pink: custom.pink || "#ff80bf"
    readonly property color cyan: custom.cyan || "#80ffea"
    readonly property color green: custom.green || "#8aff80"
    readonly property color yellow: custom.yellow || "#ffff80"
    readonly property color red: custom.red || "#ff9580"
    readonly property color border: custom.border || "#605975"
    readonly property color accent: ShellState.preferences.accent || purple
    readonly property real panelOpacity: ShellState.preferences.opacity === undefined ? 0.90 : ShellState.preferences.opacity
    readonly property int radius: 22
    readonly property int smallRadius: 12
    readonly property string fontFamily: "Inter"
    readonly property string monoFamily: "JetBrains Mono"
    readonly property bool animations: ShellState.preferences.animations !== false
    readonly property int animationDuration: animations ? 170 : 0
    function alpha(color, opacity) { return Qt.rgba(color.r, color.g, color.b, opacity); }
    function loadPalette() {
        try {
            const value = JSON.parse(palette.text());
            const valid = {};
            for (const key of ["background", "panel", "surface", "text", "muted", "purple", "pink", "cyan", "green", "yellow", "red", "border"]) {
                if (typeof value[key] === "string" && /^#[0-9a-fA-F]{6}$/.test(value[key])) valid[key] = value[key];
            }
            custom = valid;
        } catch (error) { console.warn("Custom palette could not be loaded:", error); }
    }
    property FileView palette: FileView {
        path: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/lme-shell/palette.json"
        watchChanges: true
        printErrors: false
        onLoaded: root.loadPalette()
        onFileChanged: reload()
        onLoadFailed: error => {
            if (error === FileViewError.FileNotFound) root.custom = {};
            else console.warn("Custom palette could not be read:", FileViewError.toString(error));
        }
    }
}
