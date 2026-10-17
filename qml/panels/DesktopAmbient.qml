// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../components"
import "../services"

Variants {
    model: ShellState.preferences.desktopShapes === true ? Quickshell.screens : []
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
            playing: true
            shapesEnabled: true
            shapeScale: Math.max(1, Math.min(4, Math.min(width, height) / 360)) * (ShellState.preferences.desktopShapeScale ?? 1)
            shapeOpacity: ShellState.preferences.desktopShapeOpacity ?? .14
            shapeCount: ShellState.preferences.desktopShapeCount ?? 4
            shapeStyle: ShellState.preferences.desktopShapeStyle || "mixed"
            motionSpeed: ShellState.preferences.desktopShapeSpeed ?? 1
            rotateShapes: ShellState.preferences.desktopShapeRotation !== false
        }
    }
}
