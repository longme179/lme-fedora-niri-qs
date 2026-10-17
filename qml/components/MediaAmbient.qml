// SPDX-License-Identifier: GPL-3.0-only
// Adapted from Caelestia BackgroundShapes (a3a8fe59); modified for LME's existing polygons and motion settings.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import "../services"
import "../theme"

Item {
    id: root
    property bool playing: false
    property bool shapesEnabled: ShellState.preferences.mediaShapes !== false
    property real shapeScale: 1
    property real shapeOpacity: .09
    readonly property bool animating: playing && visible && width > 0 && height > 0 && Theme.animations && shapesEnabled && (Window.window?.visible ?? false)
    objectName: "mediaAmbient"
    clip: true
    Loader {
        id: layer
        anchors.fill: parent
        active: root.visible && root.shapesEnabled
        sourceComponent: Item {
            component DriftingShape: MorphShape {
                    required property int index
                    property real progressX: (index * .29 + .15) % 1
                    property real progressY: (index * .37 + .2) % 1
                    readonly property real vx: (index % 2 ? -1 : 1) * (5 + index * 2)
                    readonly property real vy: (index % 2 ? 1 : -1) * (4 + index)
                    width: (48 + index * 14) * root.shapeScale; height: width
                    x: progressX * (root.width + width) - width
                    y: progressY * (root.height + height) - height
                    rotation: index * 57
                    shape: ["flower", "circle", "square"][index % 3]
                    color: [Theme.accent, Theme.pink, Theme.cyan, Theme.yellow][index]
                    opacity: root.shapeOpacity
            }
            Repeater { id: shapes; model: 4; delegate: DriftingShape {} }
            FrameAnimation {
                running: root.animating
                onTriggered: {
                    const dt = Math.min(frameTime, .05);
                    for (let i = 0; i < shapes.count; i++) {
                        const shape = shapes.itemAt(i) as DriftingShape;
                        if (!shape) continue;
                        shape.progressX = (shape.progressX + shape.vx * dt / (root.width + shape.width) + 1) % 1;
                        shape.progressY = (shape.progressY + shape.vy * dt / (root.height + shape.height) + 1) % 1;
                        shape.rotation = (shape.rotation + (i % 2 ? -7 : 9) * dt) % 360;
                    }
                }
            }
        }
    }
}
