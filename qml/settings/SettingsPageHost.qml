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
        previous.active = false;
        previous.sourceComponent = null;
        if (Theme.animations) { enter = 0; enterMotion.restart(); }
        else enter = 1;
    }

    function dispatch() {
        if (!content) return;
        if (current.sourceComponent === content && current.status === Loader.Ready) return;
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
        onLoaded: if (root.incoming === loaderA) root.activate(loaderA)
    }
    Loader {
        id: loaderB
        anchors.fill: parent
        asynchronous: true
        active: false
        onLoaded: if (root.incoming === loaderB) root.activate(loaderB)
    }

    transform: Translate { y: (1 - root.enter) * 28 }
    opacity: .35 + .65 * root.enter
    MotionAnimation { id: enterMotion; target: root; property: "enter"; to: 1; easing.bezierCurve: Theme.effectsCurve }
}
