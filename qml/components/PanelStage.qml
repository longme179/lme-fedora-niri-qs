// SPDX-License-Identifier: AGPL-3.0-or-later
// Bounded retained panel pool. The active panel is shown; closed panels stay
// parked off-screen so reopening is a visibility/geometry change, not a rebuild.
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import "../services"
import "../theme"

Item {
    id: root
    property string activeId: ""
    property bool open: false
    property var componentFor: id => null
    property int retainLimit: Math.max(1, Number(Quickshell.env("LME_PANEL_CACHE_LIMIT") || 6))
    readonly property Item activeItem: activeLoader ? activeLoader.item : null
    property var activeLoader: null
    property var warmupLoader: null
    property bool surfaceLive: false
    property var loaders: ({})
    property var order: []
    property var doomed: []

    Item { id: stage; anchors.fill: parent }

    Component {
        id: loaderComponent
        SlideLoader {
            id: panel
            required property string panelId
            readonly property bool centered: FeatureCatalog.panel(panelId)?.centered === true || ["launchpad", "launcher", "power", "overview"].includes(panelId)
            direction: centered ? "up" : panelId === "tray" ? Theme.barBottom ? "up" : "down" : "right"
            exitToEdge: true
            keepAlive: true
            shown: root.open && root.activeId === panelId
            content: root.componentFor(panelId)
            width: item ? Math.min(item.implicitWidth, parent.width - 32) : rememberedWidth || 400
            height: item ? Math.min(item.implicitHeight, parent.height - Theme.panelTopMargin - 16) : rememberedHeight || 500
            x: centered ? (parent.width - width) / 2
               : panelId === "tray" && ShellState.trayAnchorX >= 0 ? Math.max(14, Math.min(parent.width - width - 14, ShellState.trayAnchorX - width))
               : parent.width - width - 14
            y: centered ? (parent.height - height) / 2 : Theme.barBottom ? parent.height - height - Theme.panelTopMargin : Theme.panelTopMargin
            MouseArea { anchors.fill: parent; z: -1; onClicked: mouse => mouse.accepted = true }
            Connections {
                target: panel
                function onLoaded() { Qt.callLater(() => panel.startControlWarmup(ShellState.panelOpen, ShellState.activityOpen)); root.refresh(); }
                function onDormantChanged() { if (panel.dormant) Qt.callLater(() => panel.startControlWarmup(ShellState.panelOpen, ShellState.activityOpen)); root.refresh(); }
                function onMountedChanged() { root.refresh(); }
                function onWarmupActiveChanged() { root.refresh(); }
                function onShownChanged() { root.refresh(); }
            }
        }
    }

    function refresh() {
        activeLoader = loaders[activeId] || null;
        let live = false;
        let warm = null;
        for (const id in loaders) {
            const loader = loaders[id];
            if (loader.mounted && !loader.dormant) live = true;
            if (loader.item && "panelActive" in loader.item) loader.item.panelActive = root.open && root.activeId === id;
            if (loader.warmupActive) { live = true; warm = loader; }
        }
        surfaceLive = live;
        warmupLoader = warm;
    }

    function touch(id) { order = order.filter(k => k !== id).concat(id); }

    function ensure(id) {
        if (!id) return null;
        if (loaders[id]) { touch(id); return loaders[id]; }
        if (!root.componentFor(id)) return null;
        const loader = loaderComponent.createObject(stage, { panelId: id });
        if (!loader) return null;
        loaders[id] = loader;
        order = order.concat(id);
        touch(id);
        evictIfNeeded();
        return loader;
    }

    function warm(id) {
        const loader = ensure(id);
        if (!loader || loader.controlWarmupDone) return;
        loader.controlWarmupPending = true;
        if (loader.mounted && !loader.dormant) return;
        if (!loader.mounted) {
            loader.dormant = true;
            loader.retainedContent = loader.content;
            loader.mounted = true;
        }
        loader.startControlWarmup(ShellState.panelOpen, ShellState.activityOpen);
    }

    function snapOut() { for (const id in loaders) loaders[id].snapOut(); }
    function finishWarmups() { for (const id in loaders) if (loaders[id].warmupActive) loaders[id].finishControlWarmup(); }
    function retryWarmups() { for (const id in loaders) loaders[id].startControlWarmup(ShellState.panelOpen, ShellState.activityOpen); }

    function evictIfNeeded() {
        while (order.length > retainLimit) {
            const id = order.find(k => k !== activeId && k !== "control" && loaders[k] && loaders[k].dormant && !loaders[k].warmupActive);
            if (!id) break;
            const loader = loaders[id];
            delete loaders[id];
            order = order.filter(k => k !== id);
            loader.shown = false;
            loader.keepAlive = false;
            loader.mounted = false;
            doomed = doomed.concat([loader]);
        }
        if (doomed.length) teardownTimer.restart();
    }

    Timer {
        id: teardownTimer
        interval: 50
        repeat: true
        running: root.doomed.length > 0
        onTriggered: {
            const loader = root.doomed.shift();
            if (loader) loader.destroy();
            if (!root.doomed.length) stop();
        }
    }

    onActiveIdChanged: { ensure(activeId); refresh(); }
    onOpenChanged: { if (open) ensure(activeId); refresh(); }
    Component.onCompleted: { ensure(activeId); refresh(); }
}
