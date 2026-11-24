// SPDX-License-Identifier: AGPL-3.0-or-later
// Hosts settings/catalog pages with a bounded instance cache.
// REL: qml/settings/SettingsView.qml, qml/services/FeatureCatalog.qml – page IDs/entries/navigation.
pragma ComponentBehavior: Bound
import QtQuick
import "../theme"

Item {
    id: root
    property Component content: null
    property string contentKey: ""
    property string contentUrl: ""
    property bool embedded: false
    property bool panelActive: true
    property int cacheLimit: 6
    property int anticipationDelay: 90
    property int teardownInterval: 50
    readonly property var item: currentHost ? currentHost.pageItem : null
    readonly property string currentKey: currentHost ? currentHost.pageKey : ""
    signal navigateRequested(string pageId)
    property var hosts: ({})
    property var order: []
    property var doomed: []
    property var currentHost: null
    property var warmHost: null
    property var pending: null
    property real enter: 1

    Item { id: stage; anchors.fill: parent; clip: true }
    Item {
        id: activeStage
        anchors.fill: parent; z: 1
        transform: Translate { y: (1 - root.enter) * 28 }
        opacity: .35 + .65 * root.enter
    }
    Item { id: cacheStage; width: stage.width; height: stage.height; x: stage.width; z: 0 }
    Item { id: warmStage; anchors.fill: parent; z: -1 }

    Component {
        id: hostComponent
        Item {
            id: host
            required property string pageKey
            property Component pageComponent
            property string pageUrl
            property bool embedded: false
            readonly property var pageItem: loader.item
            readonly property int status: loader.status
            property bool warmDone: false
            property bool warming: false
            property bool warmPending: false
            anchors.fill: parent
            Loader {
                id: loader
                anchors.fill: parent
                asynchronous: true
                source: host.pageComponent ? "" : host.pageUrl
                sourceComponent: host.pageComponent
                onLoaded: {
                    if (host.embedded && item && "embedded" in item) item.embedded = true;
                    root.hostLoaded(host);
                }
            }
            PageNavigation { target: loader.item; onRequested: pageId => root.navigateRequested(pageId) }
            FrameAnimation {
                id: warmFrame
                running: host.warming
                property int frames: 0
                onTriggered: {
                    frames++;
                    if (frames >= 3) root.finishWarm(host);
                }
            }
        }
    }

    function touch(key) { order = order.filter(k => k !== key).concat(key); }
    function isDescendant(parentItem, item) {
        for (let p = item; p; p = p.parent) if (p === parentItem) return true;
        return false;
    }
    function releaseFocus(host) {
        const page = host.pageItem;
        if (!page) return;
        const focused = page.Window ? page.Window.activeFocusItem : null;
        if (focused && isDescendant(page, focused)) focused.focus = false;
        page.focus = false;
    }
    function setPageActive(host, active) {
        if (host && host.pageItem && "pageActive" in host.pageItem) host.pageItem.pageActive = active && root.panelActive;
    }
    function ensure(key, component, url, embedded, direct) {
        if (hosts[key]) { touch(key); return hosts[key]; }
        const host = hostComponent.createObject(direct ? activeStage : cacheStage, {
            pageKey: key, pageComponent: component || null,
            pageUrl: url || "", embedded: !!embedded
        });
        if (!host) return null;
        hosts[key] = host;
        order = order.concat(key);
        touch(key);
        evictIfNeeded();
        return host;
    }
    function activate(host) {
        if (!host || host === currentHost) return;
        if (host.warming) cancelWarm(host);
        const previous = currentHost;
        currentHost = host;
        host.parent = activeStage;
        host.visible = true; host.opacity = 1; host.layer.enabled = false;
        setPageActive(host, true);
        if (previous) {
            setPageActive(previous, false);
            releaseFocus(previous);
            previous.parent = cacheStage;
            previous.z = 0;
        }
        touch(host.pageKey);
        if (Theme.animations) { enter = 0; enterMotion.restart(); } else enter = 1;
        evictIfNeeded();
    }
    function dispatch() {
        if (!contentKey || (!content && !contentUrl)) return;
        const host = ensure(contentKey, content, contentUrl, embedded, !currentHost && order.length === 0);
        if (host && host.status === Loader.Ready) activate(host);
    }
    function hostLoaded(host) {
        if (host.embedded && host.pageItem && "embedded" in host.pageItem) host.pageItem.embedded = true;
        if (host.pageKey === contentKey) { activate(host); return; }
        setPageActive(host, false);
        if (host.warmPending) warm(host);
    }
    function warm(host) {
        if (!host || host === currentHost || host.warming || host.warmDone) return;
        if (host.status !== Loader.Ready) { host.warmPending = true; return; }
        host.warmPending = false;
        setPageActive(host, false);
        host.parent = warmStage;
        host.layer.enabled = true;
        host.opacity = 0;
        host.warming = true;
        warmHost = host;
    }
    function cancelWarm(host) {
        if (!host || !host.warming) return;
        host.warming = false;
        host.layer.enabled = false;
        host.opacity = 1;
        if (warmHost === host) warmHost = null;
    }
    function finishWarm(host) {
        if (!host) return;
        host.warming = false;
        host.warmDone = true;
        host.layer.enabled = false;
        host.opacity = 1;
        if (host !== currentHost) { host.parent = cacheStage; setPageActive(host, false); }
        if (warmHost === host) warmHost = null;
    }
    function anticipate(key, component, url, embedded) {
        if (!key || key === contentKey) return;
        pending = {key: key, component: component || null, url: url || "", embedded: !!embedded};
        anticipation.restart();
    }
    function startAnticipation() {
        const p = pending;
        pending = null;
        if (p) warm(ensure(p.key, p.component, p.url, p.embedded, false));
    }
    function evictIfNeeded() {
        while (order.length > cacheLimit) {
            const key = order.find(k => k !== contentKey && k !== "control" && k !== (warmHost ? warmHost.pageKey : "") && hosts[k]);
            if (!key) break;
            const host = hosts[key];
            delete hosts[key];
            order = order.filter(k => k !== key);
            doomed = doomed.concat([host]);
        }
        if (doomed.length) teardownTimer.restart();
    }
    Timer { id: anticipation; interval: root.anticipationDelay; onTriggered: root.startAnticipation() }
    Timer {
        id: teardownTimer
        interval: root.teardownInterval
        repeat: true
        running: root.doomed.length > 0
        onTriggered: {
            const host = root.doomed.shift();
            if (host) { host.parent = null; host.destroy(); }
            if (!root.doomed.length) stop();
        }
    }
    onPanelActiveChanged: setPageActive(currentHost, true)
    onContentKeyChanged: Qt.callLater(root.dispatch)
    onContentChanged: Qt.callLater(root.dispatch)
    onContentUrlChanged: Qt.callLater(root.dispatch)
    onEmbeddedChanged: Qt.callLater(root.dispatch)
    Component.onCompleted: dispatch()
    MotionAnimation { id: enterMotion; target: root; property: "enter"; to: 1; easing.bezierCurve: Theme.effectsCurve }
}
