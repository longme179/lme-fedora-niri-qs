import QtQuick
import "../theme"

Loader {
    id: root
    property string direction: "right"
    property real slideOffset: 0
    transform: Translate {
        x: root.direction === "right" ? root.slideOffset : 0
        y: root.direction === "right" ? 0 : root.slideOffset
    }
    onLoaded: {
        const panel = item as Item;
        if (panel) panel.forceActiveFocus();
        enter.stop();
        if (!Theme.animations) { slideOffset = 0; return; }
        slideOffset = direction === "right" ? width + 20 : direction === "down" ? -28 : 64;
        enter.start();
    }
    NumberAnimation {
        id: enter
        target: root; property: "slideOffset"; to: 0
        duration: Theme.slideDuration
        easing.type: Easing.OutExpo
    }
}
