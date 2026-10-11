import QtQuick
import "../theme"

Loader {
    id: root
    property string direction: "right"
    property real progress: 1
    readonly property real slideOffset: (1 - progress) * (direction === "right" ? 92 : direction === "down" ? -32 : 64)
    transform: [
        Translate { x: root.direction === "right" ? root.slideOffset : 0; y: root.direction === "right" ? 0 : root.slideOffset },
        Scale {
            origin.x: root.direction === "right" ? root.width : root.width / 2
            origin.y: root.direction === "down" ? 0 : root.height / 2
            xScale: 1 - (1 - root.progress) * Theme.deformation
            yScale: 1 + (1 - root.progress) * Theme.deformation
        }
    ]
    onLoaded: {
        const panel = item as Item;
        if (panel) panel.forceActiveFocus();
        enter.stop();
        if (!Theme.animations) { progress = 1; return; }
        progress = 0;
        enter.start();
    }
    MotionAnimation {
        id: enter
        target: root; property: "progress"; to: 1; large: true
    }
    Connections { target: Theme; function onAnimationsChanged() { if (!Theme.animations) { enter.stop(); root.progress = 1; } } }
}
