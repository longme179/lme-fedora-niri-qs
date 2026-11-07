// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import "../components"
import "../theme"

// Hosts one settings page at a time. The next page incubates asynchronously
// in a second loader while the current one stays mounted, so page switches
// never block the UI thread and never blank the content area.
Item {
    id: root
    property Component content: null
    readonly property var item: current.item
    property Loader current: loaderA
    property Loader incoming: loaderB
    property real enter: 1

    function activate(loader) {
        if (current === loader) return;
        const previous = current;
        current = loader;
        incoming = loader === loaderA ? loaderB : loaderA;
        // Deletion of the retired page is queued; hide it now so the two pages
        // can never render on top of each other.
        previous.visible = false;
        previous.active = false;
        previous.sourceComponent = null;
        loader.visible = true;
        if (Theme.animations) { enter = 0; enterMotion.restart(); }
        else enter = 1;
    }

    function dispatch() {
        if (!content) return;
        if (current.sourceComponent === content && current.status === Loader.Ready) {
            // The visible page already matches; cancel any incubation still in
            // flight so a late onLoaded cannot swap the wrong page in.
            if (incoming.active) { incoming.active = false; incoming.sourceComponent = null; }
            return;
        }
        if (incoming.sourceComponent === content && incoming.status === Loader.Ready) { activate(incoming); return; }
        if (incoming.sourceComponent !== content) incoming.sourceComponent = content;
        incoming.active = true;
    }

    onContentChanged: dispatch()
    Component.onCompleted: dispatch()

    Loader {
        id: loaderA
        anchors.fill: parent
        asynchronous: true
        active: false
        visible: false
        onLoaded: if (root.incoming === loaderA && root.content === loaderA.sourceComponent) root.activate(loaderA)
    }
    Loader {
        id: loaderB
        anchors.fill: parent
        asynchronous: true
        active: false
        visible: false
        onLoaded: if (root.incoming === loaderB && root.content === loaderB.sourceComponent) root.activate(loaderB)
    }

    transform: Translate { y: (1 - root.enter) * 28 }
    opacity: .35 + .65 * root.enter
    MotionAnimation { id: enterMotion; target: root; property: "enter"; to: 1; easing.bezierCurve: Theme.effectsCurve }
}
