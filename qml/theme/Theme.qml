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
    // Material color roles retain the user's Dracula palette and glass opacity.
    readonly property color primaryContainer: mix(panel, accent, 0.30)
    readonly property color secondaryContainer: mix(panel, pink, 0.22)
    readonly property color tertiaryContainer: mix(panel, cyan, 0.19)
    readonly property color surfaceContainer: mix(background, surface, 0.66)
    readonly property color surfaceContainerHigh: mix(panel, surface, 0.74)
    readonly property color outlineVariant: alpha(border, 0.52)
    readonly property color onPrimary: background
    readonly property real panelOpacity: ShellState.preferences.opacity === undefined ? 0.90 : ShellState.preferences.opacity
    readonly property int radius: 28
    readonly property int smallRadius: 16
    readonly property int barHeight: 42
    readonly property int barFontSize: ShellState.preferences.barFontSize || 13
    readonly property int barFontWeight: Font.Medium
    readonly property int barTopMargin: 8
    readonly property int barSideMargin: 12
    readonly property int panelTopMargin: barTopMargin + barHeight + 8
    readonly property string fontFamily: "Roboto"
    readonly property int bodySize: 14
    readonly property int labelSize: 12
    readonly property int headingWeight: Font.Bold
    readonly property bool compact: ShellState.preferences.density === "compact"
    readonly property int cardPadding: compact ? 14 : 20
    readonly property int cardSpacing: compact ? 10 : 16
    readonly property string monoFamily: "JetBrains Mono"
    readonly property bool animations: ShellState.preferences.animations !== false
    readonly property string motionPreset: ShellState.preferences.motionPreset || "expressive"
    readonly property real motionSpeed: ShellState.preferences.motionSpeed || 1
    readonly property real motionBounce: ShellState.preferences.motionBounce === undefined ? .35 : ShellState.preferences.motionBounce
    readonly property int animationDuration: animations ? Math.round(190 / motionSpeed) : 0
    readonly property int slideDuration: animations ? Math.round((motionPreset === "jelly" ? 600 : motionPreset === "smooth" ? 360 : 460) / motionSpeed) : 0
    // Spatial curves may overshoot; colors/opacity use monotonic effects easing.
    readonly property var spatialCurve: motionPreset === "smooth" ? [.18, .8, .22, 1, 1, 1]
        : motionPreset === "jelly" ? [.32, 1 + .9 * motionBounce, .18, 1, 1, 1]
        : [.38, 1 + .6 * motionBounce, .22, 1, 1, 1]
    readonly property real deformation: animations && motionPreset === "jelly" ? .09 * motionBounce : 0
    function alpha(color, opacity) { return Qt.rgba(color.r, color.g, color.b, opacity); }
    function mix(a, b, amount) { return Qt.rgba(a.r * (1 - amount) + b.r * amount, a.g * (1 - amount) + b.g * amount, a.b * (1 - amount) + b.b * amount, 1); }
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
