// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import "../services"

Image {
    id: root
    required property var hostWindow
    property int consumers: 0
    property bool disposed: false
    readonly property var proxyWindow: QsWindow.window
    readonly property var output: disposed ? null : proxyWindow ? proxyWindow.screen : null
    readonly property real outputWidth: Math.max(1, output ? output.width : hostWindow ? hostWindow.width : 1)
    readonly property real outputHeight: Math.max(1, output ? output.height : hostWindow ? hostWindow.height : 1)
    readonly property real resolution: Math.min(.5, 1280 / outputWidth, 720 / outputHeight)
    // Shader samplers see the original image, not Image's PreserveAspectCrop geometry.
    readonly property rect cropRect: {
        const imageAspect = Math.max(1, implicitWidth) / Math.max(1, implicitHeight);
        const screenAspect = outputWidth / outputHeight;
        const w = Math.min(1, screenAspect / imageAspect), h = Math.min(1, imageAspect / screenAspect);
        return Qt.rect((1 - w) / 2, (1 - h) / 2, w, h);
    }
    // shortcut: floating windows sample as centered; use native coordinates when available on Wayland.
    readonly property point windowOrigin: {
        if (disposed || !hostWindow) return Qt.point(0, 0);
        const w = proxyWindow;
        const a = w ? w.anchors : null;
        const m = w ? w.margins : null;
        const width = hostWindow ? hostWindow.width : 0, height = hostWindow ? hostWindow.height : 0;
        return Qt.point(a ? a.left ? m.left : a.right ? outputWidth - w.width - m.right : (outputWidth - w.width) / 2 : (outputWidth - width) / 2,
            a ? a.top ? m.top : a.bottom ? outputHeight - w.height - m.bottom : (outputHeight - w.height) / 2 : (outputHeight - height) / 2);
    }
    objectName: "glassBackdrop"
    visible: false
    width: outputWidth; height: outputHeight
    source: ShellState.preferences.wallpaper ? "file://" + ShellState.preferences.wallpaper.split("/").map(part => encodeURIComponent(part)).join("/")
        : ShellState.demo ? Qt.resolvedUrl("../../assets/wallpapers/liquid-dracula.png") : ""
    sourceSize: Qt.size(Math.max(1, Math.round(outputWidth * resolution)), Math.max(1, Math.round(outputHeight * resolution)))
    fillMode: Image.PreserveAspectCrop
    asynchronous: true; cache: false; mipmap: true
    Component.onDestruction: GlassState.backdrops = GlassState.backdrops.filter(item => item !== root)
}
