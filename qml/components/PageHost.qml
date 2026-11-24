// SPDX-License-Identifier: AGPL-3.0-or-later
// Hosts settings/control pages and the overlay panels with one retained Loader per key.
// REL: qml/settings/SettingsView.qml, qml/panels/ControlCenter.qml, shell.qml – keys/resolve.
pragma ComponentBehavior: Bound
import QtQuick
import "../theme"

// A page the user asks for builds synchronously: Quickshell incubates asynchronous work for
// ~1/3 frame per frame while anything animates, several times slower than the raw build.
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
    // Let the first page of a fresh host incubate so the host's window can paint its
    // shell first; every page the user asks for after that builds synchronously.
    property bool firstAsync: false
    // false hides the shown page as well (a closed window keeps no page timers alive).
    property bool active: true
    readonly property var item: shown ? shown.item : null
    property Loader shown: null
    property var entries: ({})
    // Least recently shown first. 0 keeps every page (owner lifted the RAM cap 2026-11-24).
    property int maxPages: 0
    property var order: []
    property real enter: 1
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
            if (!page || page === shown || victim === key) { i++; continue; }
            order.splice(i, 1);
            delete entries[victim];
            page.destroy();
        }
    }
    function entry(pageKey) {
        let page = entries[pageKey];
        if (page) { touch(pageKey); return page; }
        const content = pageKey && resolve ? resolve(pageKey) : null;
        if (!content) return null;
        page = pageLoader.createObject(root, {pageKey: pageKey, asynchronous: firstAsync && order.length === 0});
        entries[pageKey] = page;
        touch(pageKey);
        page.sourceComponent = content;
        trim();
        return page;
    }
    // Start a first visit before the click; it builds synchronously here, so callers
    // stagger calls (see ControlCenter's warm-up timer).
    function preload(keys) {
        for (const pageKey of keys) {
            if (pageKey === key || entries[pageKey]) continue;
            entry(pageKey);
        }
    }
    function present(page) {
        if (shown === page) return;
        touch(page.pageKey);
        const hadFocus = !!shown && shown.activeFocus;
        shown = page;
        page.focus = true;
        if (hadFocus) page.forceActiveFocus();
        if (animate && Theme.animations) { enter = 0; enterMotion.restart(); }
        else enter = 1;
    }
    function show() {
        if (shown && shown.pageKey === key) return;
        const page = entry(key);
        if (page && page.status === Loader.Ready) present(page);
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
            onLoaded: {
                root.pageLoaded(item);
                if (pageKey === root.key) root.present(page);
            }
        }
    }

    transform: Translate { y: (1 - root.enter) * 28 }
    opacity: .35 + .65 * root.enter
    MotionAnimation { id: enterMotion; target: root; property: "enter"; to: 1; easing.bezierCurve: Theme.effectsCurve }
}
