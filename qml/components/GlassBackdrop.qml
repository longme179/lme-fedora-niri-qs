// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import "../services"
import "GlassSampling.js" as GlassSampling
import "GlassGeometry.js" as GlassGeometry

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
        const p = GlassGeometry.resolve(w ? w.anchors : null, w ? w.margins : null,
            w ? {width: w.width, height: w.height} : {width: 0, height: 0},
            {width: hostWindow.width, height: hostWindow.height},
            {width: outputWidth, height: outputHeight},
            ShellState.niri.windows, ShellState.niri.workspaces, output ? output.name : "",
            [hostWindow.niriWindowId, hostWindow.windowId, hostWindow.niriId, w ? w.niriWindowId : null, w ? w.windowId : null], hostWindow.title);
        return Qt.point(p.x, p.y);
    }
    objectName: "glassBackdrop"
    visible: false
    width: outputWidth; height: outputHeight
    readonly property string wallpaperPath: (ShellState.preferences.wallpaperOutputs || {})[output ? output.name : ""] || ShellState.preferences.wallpaper || ""
    // LG2.0 A2 part 2: the backend snapshots awww's live per-output state to
    // $XDG_CACHE_HOME/lme-shell/glass/<output>.png with a revision counter.
    // Every window on the output binds the same URL plus ?rev=, so one decode
    // is shared and a revision bump reloads all backdrops within a frame.
    // Missing snapshots (awww surface changed, daemon down, glass off) fall
    // back to the direct-file path below.
    readonly property var glassEntry: ((ShellState.snapshot.glass || {}).outputs || {})[output ? output.name : ""] || null
    readonly property string snapshotSource: glassEntry && glassEntry.rev && glassEntry.url ? String(glassEntry.url) + (String(glassEntry.url).includes("?") ? "&rev=" : "?rev=") + glassEntry.rev : ""
    // Color wallpapers have no image path; a flat fill tile (awww's default fill
    // is black) keeps the lens refracting a flat field, so sourceAvailable stays
    // 1 and rim/grain render instead of the dead flat rim. Snapshots carry the
    // exact per-output awww color when available.
    readonly property string flatTile: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
    source: snapshotSource ? snapshotSource : wallpaperPath ? "file://" + wallpaperPath.split("/").map(part => encodeURIComponent(part)).join("/")
        : ShellState.demo ? Qt.resolvedUrl("../../assets/wallpapers/liquid-dracula.png") : flatTile
    sourceSize: Qt.size(Math.max(1, Math.round(outputWidth * resolution)), Math.max(1, Math.round(outputHeight * resolution)))
    fillMode: Image.PreserveAspectCrop
    // cache: true shares one decode per output (identical URL + sourceSize is
    // one pixmap cache key) across every window's backdrop, instead of
    // re-decoding the wallpaper for each popup window that opens.
    asynchronous: true; cache: true; mipmap: true
    Component.onDestruction: GlassState.backdrops = GlassState.backdrops.filter(item => item !== root)
}
