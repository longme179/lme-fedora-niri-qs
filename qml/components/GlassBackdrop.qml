// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import "../services"
import "GlassSampling.js" as GlassSampling

Image {
    id: root
    required property var hostWindow
    property int consumers: 0
    property bool disposed: false
    readonly property var proxyWindow: QsWindow.window
    readonly property var output: disposed ? null : proxyWindow ? proxyWindow.screen : null
    readonly property real outputWidth: Math.max(1, output ? output.width : hostWindow ? hostWindow.width : 1)
    readonly property real outputHeight: Math.max(1, output ? output.height : hostWindow ? hostWindow.height : 1)
    // LG2.0 A2: scaled outputs sample at up to a 1440p equivalent (never beyond
    // their physical resolution) so frosted interiors stay smooth at 2x; 1x
    // outputs keep the <=720p/0.5x cap. Glass is off entirely under battery
    // saver (Theme.liquidGlass), so the tier needs no gate of its own.
    readonly property real outputScale: output && output.scale ? output.scale : 1
    readonly property real resolution: GlassSampling.resolution(outputWidth, outputHeight, outputScale)
    // Shader samplers see the original image, not Image's PreserveAspectCrop geometry.
    readonly property rect cropRect: {
        const imageAspect = Math.max(1, implicitWidth) / Math.max(1, implicitHeight);
        const screenAspect = outputWidth / outputHeight;
        const w = Math.min(1, screenAspect / imageAspect), h = Math.min(1, imageAspect / screenAspect);
        return Qt.rect((1 - w) / 2, (1 - h) / 2, w, h);
    }
    // Wayland does not expose a floating QWindow's screen position; niri does.
    readonly property point windowOrigin: {
        if (disposed || !hostWindow) return Qt.point(0, 0);
        const w = proxyWindow;
        const a = w ? w.anchors : null;
        const m = w ? w.margins : null;
        const width = hostWindow ? hostWindow.width : 0, height = hostWindow ? hostWindow.height : 0;
        if (!a && hostWindow.title) {
            const matches = (ShellState.niri.windows || []).filter(item => item.title === hostWindow.title);
            const window = matches.length === 1 ? matches[0] : null;
            const workspace = window ? (ShellState.niri.workspaces || []).find(item => item.id === window.workspace_id) : null;
            const layout = window ? window.layout || {} : {};
            const pos = layout.tile_pos_in_workspace_view, offset = layout.window_offset_in_tile;
            if (workspace && output && workspace.output === output.name && pos && offset && pos.length === 2 && offset.length === 2 && [...pos, ...offset].every(Number.isFinite))
                return Qt.point(pos[0] + offset[0], pos[1] + offset[1]);
        }
        // shortcut: unknown or ambiguous toplevels remain centered until niri identifies them.
        return Qt.point(a ? a.left ? m.left : a.right ? outputWidth - w.width - m.right : (outputWidth - w.width) / 2 : (outputWidth - width) / 2,
            a ? a.top ? m.top : a.bottom ? outputHeight - w.height - m.bottom : (outputHeight - w.height) / 2 : (outputHeight - height) / 2);
    }
    objectName: "glassBackdrop"
    visible: false
    width: outputWidth; height: outputHeight
    readonly property string wallpaperPath: (ShellState.preferences.wallpaperOutputs || {})[output ? output.name : ""] || ShellState.preferences.wallpaper || ""
    // Color wallpapers have no image path; a flat fill tile (awww's default fill
    // is black) keeps the lens refracting a flat field, so sourceAvailable stays
    // 1 and rim/grain render instead of the dead flat rim. Part 2 of LG2.0 A2
    // (snapshot cache from awww's live state) will replace this with the exact
    // per-output color snapshot.
    readonly property string flatTile: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
    source: wallpaperPath ? "file://" + wallpaperPath.split("/").map(part => encodeURIComponent(part)).join("/")
        : ShellState.demo ? Qt.resolvedUrl("../../assets/wallpapers/liquid-dracula.png") : flatTile
    sourceSize: Qt.size(Math.max(1, Math.round(outputWidth * resolution)), Math.max(1, Math.round(outputHeight * resolution)))
    fillMode: Image.PreserveAspectCrop
    // cache: true shares one decode per output (identical URL + sourceSize is
    // one pixmap cache key) across every window's backdrop, instead of
    // re-decoding the wallpaper for each popup window that opens.
    asynchronous: true; cache: true; mipmap: true
    Component.onDestruction: GlassState.backdrops = GlassState.backdrops.filter(item => item !== root)
}
