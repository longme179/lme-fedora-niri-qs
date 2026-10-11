pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../services"

QtObject {
    id: root
    property var custom: ({})
    readonly property var overrides: ShellState.preferences.themeOverrides || ({})
    readonly property var fonts: ShellState.preferences.fontOverrides || ({})
    property var catalog: ({colors: [], fonts: []})
    function colorFor(key, fallback) { return overrides[key] || fallback; }
    function tokenColor(key) { return root[key]; }
    function tokenTitle(key) { return key.replace(/([A-Z])/g, " $1").replace(/^./, c => c.toUpperCase()); }
    function fontFor(key) { return fonts[key] || (key === "mono" ? "JetBrains Mono" : key === "body" ? "Roboto" : fontFamily); }
    property FileView catalogFile: FileView {
        path: Quickshell.shellPath("config/theme-tokens.json")
        onLoaded: root.catalog = JSON.parse(text())
    }
    readonly property color background: colorFor("background", custom.background || "#22212c")
    readonly property color panel: colorFor("panel", custom.panel || "#2d293d")
    readonly property color surface: colorFor("surface", custom.surface || "#393447")
    readonly property color text: colorFor("text", custom.text || "#f8f8f2")
    readonly property color muted: colorFor("muted", custom.muted || "#aaa6c0")
    readonly property color purple: colorFor("purple", custom.purple || "#9580ff")
    readonly property color pink: colorFor("pink", custom.pink || "#ff80bf")
    readonly property color cyan: colorFor("cyan", custom.cyan || "#80ffea")
    readonly property color green: colorFor("green", custom.green || "#8aff80")
    readonly property color yellow: colorFor("yellow", custom.yellow || "#ffff80")
    readonly property color red: colorFor("red", custom.red || "#ff9580")
    readonly property color border: colorFor("border", custom.border || "#605975")
    readonly property color accent: ShellState.preferences.accent || purple
    // Material color roles retain the user's Dracula palette and glass opacity.
    readonly property color primaryContainer: colorFor("primaryContainer", mix(panel, accent, 0.30))
    readonly property color secondaryContainer: colorFor("secondaryContainer", mix(panel, pink, 0.22))
    readonly property color tertiaryContainer: colorFor("tertiaryContainer", mix(panel, cyan, 0.19))
    readonly property color surfaceContainer: colorFor("surfaceContainer", mix(background, surface, 0.66))
    readonly property color surfaceContainerHigh: colorFor("surfaceContainerHigh", mix(panel, surface, 0.74))
    readonly property color outlineVariant: alpha(border, 0.52)
    readonly property color onPrimary: colorFor("onPrimary", background)
    readonly property color buttonFill: colorFor("buttonFill", surfaceContainerHigh)
    readonly property color buttonHover: colorFor("buttonHover", mix(buttonFill, text, .08))
    readonly property color buttonPressed: colorFor("buttonPressed", mix(buttonFill, text, .14))
    readonly property color buttonSelected: colorFor("buttonSelected", primaryContainer)
    readonly property color buttonText: colorFor("buttonText", text)
    readonly property color iconColor: colorFor("iconColor", text)
    readonly property color iconHover: colorFor("iconHover", alpha(text, .09))
    readonly property color fieldFill: colorFor("fieldFill", surfaceContainer)
    readonly property color fieldText: colorFor("fieldText", text)
    readonly property color switchTrack: colorFor("switchTrack", accent)
    readonly property color switchThumb: colorFor("switchThumb", onPrimary)
    readonly property color sliderTrack: colorFor("sliderTrack", surfaceContainerHigh)
    readonly property color sliderFill: colorFor("sliderFill", accent)
    readonly property color barFill: colorFor("barFill", surfaceContainer)
    readonly property color barText: colorFor("barText", text)
    readonly property color barMuted: colorFor("barMuted", muted)
    readonly property color barHover: colorFor("barHover", primaryContainer)
    readonly property color workspaceActive: colorFor("workspaceActive", accent)
    readonly property color workspaceText: colorFor("workspaceText", onPrimary)
    readonly property color panelFill: colorFor("panelFill", surfaceContainer)
    readonly property color cardFill: colorFor("cardFill", surfaceContainerHigh)
    readonly property color controlFill: colorFor("controlFill", panelFill)
    readonly property color launcherFill: colorFor("launcherFill", panelFill)
    readonly property color notificationFill: colorFor("notificationFill", panelFill)
    readonly property color islandFill: colorFor("islandFill", panelFill)
    readonly property color settingsFill: colorFor("settingsFill", panelFill)
    readonly property real panelOpacity: ShellState.preferences.opacity === undefined ? 0.90 : ShellState.preferences.opacity
    readonly property int radius: 28
    readonly property int smallRadius: 16
    readonly property int barHeight: ShellState.preferences.barHeight || 42
    readonly property int barFontSize: ShellState.preferences.barFontSize || 13
    readonly property int barFontWeight: Font.Medium
    readonly property bool barBottom: ShellState.preferences.barEdge === "bottom"
    readonly property int barTopMargin: ShellState.preferences.barEdgeMargin === undefined ? 8 : ShellState.preferences.barEdgeMargin
    readonly property int barSideMargin: ShellState.preferences.barSideMargin === undefined ? 12 : ShellState.preferences.barSideMargin
    readonly property int panelTopMargin: barTopMargin + barHeight + 8
    readonly property string fontFamily: fonts.body || "Roboto"
    readonly property string headingFamily: fontFor("heading")
    readonly property string buttonFamily: fontFor("button")
    readonly property string barFamily: fontFor("bar")
    readonly property int bodySize: ShellState.preferences.fontSize || 14
    readonly property int labelSize: bodySize - 2
    readonly property int headingWeight: Font.Bold
    readonly property bool compact: ShellState.preferences.density === "compact"
    readonly property int cardPadding: compact ? 14 : 20
    readonly property int cardSpacing: compact ? 10 : 16
    readonly property string monoFamily: fontFor("mono")
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
    // Material expressive spatial/effects curves ported from DMS Anims.qml (MIT).
    // Copyright (c) 2025 Avenge Media LLC; notice: third_party/DankMaterialShell-LICENSE.
    readonly property var fastSpatialCurve: motionPreset === "smooth" ? spatialCurve : [.42, 1 + .67 * motionBounce, .21, .9, 1, 1]
    readonly property var effectsCurve: [.34, .8, .34, 1, 1, 1]
    readonly property var exitCurve: [.3, 0, .8, .15, 1, 1]
    readonly property real deformation: animations && motionPreset === "jelly" ? .09 * motionBounce : 0
    function alpha(color, opacity) { return Qt.rgba(color.r, color.g, color.b, opacity * color.a); }
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
