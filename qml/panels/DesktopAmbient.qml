// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../components"
import "../services"

Variants {
    model: ShellState.preferences.desktopShapes === true && ActivityState.hasMedia ? Quickshell.screens : []
    delegate: PanelWindow {
        required property var modelData
        screen: modelData
        objectName: "desktopAmbient"
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        exclusiveZone: 0
        mask: Region {}
        WlrLayershell.namespace: "lme-desktop-ambient"
        WlrLayershell.layer: WlrLayer.Bottom
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        MediaAmbient {
            anchors.fill: parent
            playing: ActivityState.playing
            shapesEnabled: true
            shapeScale: Math.max(1, Math.min(4, Math.min(width, height) / 360))
            shapeOpacity: .14
        }
    }
}
