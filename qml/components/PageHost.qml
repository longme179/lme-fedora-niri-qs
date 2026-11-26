// SPDX-License-Identifier: AGPL-3.0-or-later
// Hosts settings/control pages and the overlay panels with one retained Loader per key.
// REL: qml/settings/SettingsView.qml, qml/panels/ControlCenter.qml, shell.qml – keys/resolve; qml/services/Heartbeat.qml – build marks.
pragma ComponentBehavior: Bound
import QtQuick
import "../services"
import "../theme"

// By default a page the user asks for builds synchronously: Quickshell incubates asynchronous
// work for ~1/3 frame per frame while anything animates, several times slower than the raw
// build. asyncPages trades that latency for a surface that never blocks.
// Every built page stays built (hidden pages park past the right edge, and root.active stops
// their visible-bound timers), so a revisit is the next frame. maxPages bounds the retained
// set; the least recently shown page is destroyed first.
Item {
    id: root
    clip: true
    property string key: ""
    // key => Component; a null result leaves the shown page in place.
    property var resolve: null
    property bool animate: true
    // false hides the shown page as well (a closed window keeps no page timers alive).
    property bool active: true
    readonly property var item: shown ? shown.item : null
    property Loader shown: null
    property var entries: ({})
    // Number of built pages. `entries` is a var object: element assignment emits no
    // change signal, so bindings cannot watch it (PanelStage's prewarm timer used to
    // bind on `entries["control"] !== undefined` and never re-evaluated -> dead timer).
    property int pageCount: 0
    // Least recently shown first. 0 keeps every page (owner lifted the RAM cap 2026-11-24).
    property int maxPages: 0
    property var order: []
    property real enter: 1
    // True while the shown page slides in (prewarm() gates use it to stay out of the way).
    readonly property bool entering: enterMotion.running
    signal pageLoaded(var item)

    function touch(pageKey) {
        const i = order.indexOf(pageKey);
        if (i >= 0) order.splice(i, 1);
        order.push(pageKey);
    }
    function trim() {
        if (maxPages <= 0) return;
        for (let i = 0; order.length > maxPages && i < order.length;) {
            const victim = order[i];
            const page = entries[victim];
            if (!page || page === shown || page === prewarming || page === pending || victim === key) { i++; continue; }
            order.splice(i, 1);
            delete entries[victim];
            pageCount--;
            page.destroy();
        }
    }
    // `incubate` hands the build to Quickshell's incubator instead of running it here.
    function entry(pageKey, incubate) {
        let page = entries[pageKey];
        if (page) { touch(pageKey); return page; }
        const content = pageKey && resolve ? resolve(pageKey) : null;
        if (!content) return null;
        page = pageLoader.createObject(root, {pageKey: pageKey, asynchronous: incubate === true});
        entries[pageKey] = page;
        pageCount++;
        touch(pageKey);
        const started = Heartbeat.enabled ? Heartbeat.now() : 0;
        page.sourceComponent = content;
        // A synchronous build completes inside the assignment above; an incubated one has only started.
        if (Heartbeat.enabled) Heartbeat.mark("build " + pageKey + (incubate === true ? " start" : " " + (Heartbeat.now() - started).toFixed(1) + "ms"));
        trim();
        return page;
    }
    // Start a first visit before the click; it builds synchronously here, so callers
    // stagger calls (see ControlCenter's warm-up timer). With asyncPages on, preload
    // incubates instead (the walk may only START builds, never block a frame for one).
    function preload(keys) {
        for (const pageKey of keys) {
            if (pageKey === key || entries[pageKey]) continue;
            const page = entry(pageKey, root.asyncPages);
            if (root.asyncPages && page && page.status === Loader.Loading) prewarming = page;
        }
    }
    // Background walk over every page this host can resolve, one page at a time.
    // asyncPages off (default): one synchronous build per tick; `gate` (false while the
    // surface is in use) is checked on every tick so a live panel never shares its frame
    // budget with a build.
    // asyncPages on: a page is only STARTED while `gate` reports the surface quiet, because
    // an incubation in flight cannot be paused; the next one waits for it (or for a requested
    // page) to finish. The walk also stops while the host is hidden (root.active false).
    property bool asyncPages: false
    property var prewarmQueue: []
    property var prewarmSource: null // () => array of keys
    property var prewarmGate: null // () => bool, true = quiet enough to build
    property Loader prewarming: null // page of the background walk still incubating
    property Loader pending: null // requested page still incubating
    Timer {
        id: prewarmTimer
        interval: root.asyncPages ? 100 : 350; repeat: true
        running: root.prewarmQueue.length > 0 && !root.prewarming && !root.pending
        onTriggered: {
            if (!root.active) return; // a hidden window shows nothing new by building
            if (root.prewarmGate && !root.prewarmGate()) return;
            while (root.prewarmQueue.length) {
                const next = root.prewarmQueue.shift();
                if (next === root.key || root.entries[next]) continue;
                if (!root.entry(next, root.asyncPages)) continue; // unresolvable keys drop silently
                const page = root.entries[next];
                root.prewarming = root.asyncPages && page.status === Loader.Loading ? page : null;
                break; // one build at a time
            }
        }
    }
    function prewarm(source, gate) {
        prewarmSource = source; prewarmGate = gate;
        prewarmQueue = source ? source() : [];
    }
    function present(page) {
        leaving = 0;
        if (shown === page) return;
        touch(page.pageKey);
        const hadFocus = !!shown && shown.activeFocus;
        shown = page;
        page.focus = true;
        if (hadFocus) page.forceActiveFocus();
        if (animate && Theme.animations) { enter = 0; enterMotion.restart(); }
        else enter = 1;
    }
    // Cancels an incubating page and forgets it; a background page goes back to the queue.
    function drop(page) {
        if (!page || page.status !== Loader.Loading) return;
        if (prewarming === page) { prewarming = null; prewarmQueue.unshift(page.pageKey); }
        if (pending === page) pending = null;
        delete entries[page.pageKey];
        pageCount--;
        const i = order.indexOf(page.pageKey);
        if (i >= 0) order.splice(i, 1);
        page.destroy();
    }
    function show() {
        if (shown && shown.pageKey === key) return;
        // A request gets the incubator to itself: a superseded request is dropped and a
        // background build steps aside (back to the front of the queue). The FIRST page is
        // synchronous on purpose: it builds while the host window is still hidden, and the
        // incubator would pace it to a fraction of a frame per frame, showing an empty
        // window for seconds instead.
        drop(pending);
        if (asyncPages && !entries[key]) drop(prewarming);
        const page = entry(key, asyncPages && order.length > 0);
        if (page && page.status === Loader.Ready) present(page);
        else if (asyncPages && page && page.status === Loader.Loading) { pending = page; recede(); }
    }
    function recede() {
        if (animate && Theme.animations) { leaving = 0; leaveMotion.restart(); }
        else leaving = 1;
    }
    onKeyChanged: show()
    onActiveFocusChanged: if (activeFocus && shown) shown.forceActiveFocus()
    Component.onCompleted: show()

    Component {
        id: pageLoader
        Loader {
            id: page
            required property string pageKey
            // Explicit geometry, not anchors.fill: anchors override the parking x binding.
            y: 0
            width: root.width
            height: root.height
            asynchronous: false
            // Park out of view instead of toggling Item.visible: visibility propagation through a
            // large built tree costs ~0.5 s in LME, while an offset change is free.
            visible: root.active
            x: root.shown === page ? 0 : root.width + 8
            onStatusChanged: {
                if (status === Loader.Loading) return;
                // The walk resumes / the request settles once an incubated page is ready or has failed.
                if (root.prewarming === page) root.prewarming = null;
                if (root.pending === page) { root.pending = null; if (status === Loader.Error) root.leaving = 0; }
            }
            onLoaded: {
                root.pageLoaded(item);
                if (pageKey === root.key) root.present(page);
            }
        }
    }

    transform: Translate { y: (1 - root.enter) * 28 }
    // leaving runs to 1 while a requested page is still incubating, so the outgoing page
    // recedes under the new title instead of sitting there as if the click had missed.
    property real leaving: 0
    opacity: (.35 + .65 * root.enter) * (1 - .55 * root.leaving)
    MotionAnimation { id: enterMotion; target: root; property: "enter"; to: 1; easing.bezierCurve: Theme.effectsCurve }
    MotionAnimation { id: leaveMotion; target: root; property: "leaving"; to: 1; easing.bezierCurve: Theme.effectsCurve }
}
