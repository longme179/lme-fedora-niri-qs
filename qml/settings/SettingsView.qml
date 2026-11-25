// Role: SettingsView.qml (host layer) — Settings page host/navigation; handles page IDs and routing.
// REL: qml/settings/SettingsRegistry.qml – page resolution; qml/components/PageNavigation.qml – local routing.
// INVARIANT: page IDs/legacyIndex routes remain compatible with CLI/catalog (implicit coupling #3/#5).
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

Item {
    id: root
    property string page: "appearance"
    // false parks the shown page (a hidden Settings window keeps no page timers running).
    property bool active: true
    signal closeRequested()
    property var history: []
    readonly property var currentPage: SettingsRegistry.page(page)
    readonly property var displayPreview: (ShellState.displays || {}).preview || {}
    property real now: Date.now()
    onDisplayPreviewChanged: now = Date.now()
    Timer { interval: 1000; repeat: true; running: ["applying", "pending", "reverting"].includes(root.displayPreview.status); onTriggered: { root.now = Date.now(); if (ShellState.backendReady) ShellState.run("displayRefresh"); } }
    // One filter pass per keystroke, shared by the list, the indicator and the empty label.
    // The navigation Repeater keeps a constant model and hides the non-matches (layouts skip
    // invisible items): replacing the model tore every delegate down and up again, which cost
    // up to ~200 ms on a single keystroke.
    // FeatureCatalog.ready is read DIRECTLY so the binding re-runs when the catalog settles:
    // SettingsRegistry.pages is a plain function call whose result a binding latches at
    // creation, and the model and this list could latch on different sides of the settle
    // (deployed regression: catalog entries in results, legacy entries in the model, every
    // comparison by reference failed and the sidebar went blank). Before the catalog settles
    // both fall back to the SAME legacy list, and delegates match by key, never by reference.
    readonly property var results: FeatureCatalog.ready ? SettingsRegistry.search(search.text) : SettingsRegistry.legacyPages
    // Background builds (pageLoader.prewarm) start only while the window is quiet and
    // visible: the pointer still, nothing typed or clicked, neither list moving and the last
    // page change finished entering, for quietMs. A function, not a binding: it reads the clock.
    readonly property int quietMs: 600
    property real lastActivity: 0
    property point pointerSample: Qt.point(-1, -1)
    property bool pointerInside: false
    property int framesRendered: 0
    onFramesRenderedChanged: if (framesRendered) activity()
    function activity() { lastActivity = Date.now(); }
    function quiet() {
        const p = pointerWatch.point.position;
        if (p.x !== pointerSample.x || p.y !== pointerSample.y || pointerWatch.hovered !== pointerInside) {
            pointerSample = p; pointerInside = pointerWatch.hovered;
            activity();
        }
        return active && !pageScroll.moving && !navigationScroll.moving && !pageLoader.entering
               && Date.now() - lastActivity >= quietMs;
    }
    function navigate(key) {
        if (key === page) return;
        history = history.concat(page); page = SettingsRegistry.page(key).key;
        search.clear(); pageScroll.contentY = 0;
        activity();
    }
    PageNavigation { target: pageLoader.item; onRequested: pageId => root.navigate(pageId) }
    function goBack() {
        if (!history.length) return;
        page = history[history.length - 1]; history = history.slice(0, -1); pageScroll.contentY = 0;
        activity();
    }
    Shortcut { sequence: "Ctrl+F"; onActivated: search.forceActiveFocus() }
    Shortcut { sequence: "Alt+Left"; onActivated: root.goBack() }
    Shortcut { sequence: "Escape"; onActivated: { if (search.text) search.clear(); else root.closeRequested(); } }
    // Pointer motion anywhere in the window counts as activity. Qt delivers hover to the
    // topmost hover-accepting item only, so a MouseArea under the controls would miss the
    // pointer over every button and field; a non-blocking HoverHandler on this item keeps
    // following it. Its point has no change signals, hence the sampling in quiet().
    HoverHandler { id: pointerWatch }
    // Rendered-frame counter for the host surfaces: the Quickshell window type carries no
    // frame signal, but the attached Window.window resolves to the QQuickWindow, which has
    // frameSwapped. Counting here (not in the panel) keeps production free of probe code.
    readonly property var hostWindow: Window.window
    Connections {
        target: hostWindow
        function onFrameSwapped() { root.framesRendered++ }
    }
    GlassPanel { anchors.fill: parent; radius: 28; role: "settingsFill" }
    RowLayout {
        anchors.fill: parent; anchors.margins: 20; spacing: 24
        Rectangle {
            Layout.preferredWidth: root.width < 850 ? 192 : 226
            Layout.fillHeight: true
            radius: 24; color: Theme.alpha(Theme.surfaceContainer, 0.80)
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 14; spacing: 18
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 4
                    LabelText { objectName: "shellNameHeading"; text: ShellState.shellName + " Settings"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 22; font.weight: Font.Bold }
                    LabelText { text: "Make room for you."; color: Theme.muted; font.pixelSize: 13 }
                }
                ExpressiveField {
                    id: search
                    Layout.fillWidth: true
                    placeholderText: "Search settings"
                    Accessible.name: "Search settings"
                    onAccepted: { if (root.results.length) root.navigate(root.results[0].key); }
                    onTextChanged: root.activity()
                }
                Flickable {
                    id: navigationScroll
                    Layout.fillWidth: true; Layout.fillHeight: true
                    contentWidth: width; contentHeight: navigationColumn.implicitHeight + 8
                    clip: true; boundsBehavior: Flickable.StopAtBounds
                    onContentYChanged: root.activity()
                    ScrollBar.vertical: ScrollBar {}
                    StretchIndicator {
                        parent: navigationScroll.contentItem; vertical: true
                        // itemAt() is not notifiable: async incubation can leave the
                        // count stable before delegates exist, latching the indicator
                        // to null. Re-evaluate on every population change; the index is a
                        // place in the filtered results, which is what the Repeater shows.
                        targetItem: {
                            navRepeater.population;
                            const idx = root.results.findIndex(p => p.key === root.page);
                            const target = idx >= 0 ? navRepeater.itemAt(idx) : null;
                            return target && target.visible ? target : null;
                        }
                    }
                    ColumnLayout {
                        id: navigationColumn; z: 1; x: 4; y: 4
                        width: navigationScroll.width - 16; spacing: 6
                        Repeater {
                            // Gated like `results` (see there): both sides of the catalog
                            // settle must swap in the same re-evaluation, or the delegates
                            // and the filter compare different objects for the same page.
                            id: navRepeater; model: FeatureCatalog.ready ? SettingsRegistry.pages : SettingsRegistry.legacyPages
                            // Notifiable revision: itemAt() bindings latch null when count
                            // settles before async delegates are instantiated.
                            property int population: 0
                            onItemAdded: population++
                            onItemRemoved: population--
                            delegate: LiquidButton {
                                id: nav
                                required property var modelData
                                // Hidden delegates drop out of the layout. Match by key:
                                // around a catalog settle, results and the model can hold
                                // different objects for the same page.
                                visible: root.results.some(p => p.key === modelData.key)
                                Layout.fillWidth: true; Layout.preferredHeight: Math.max(48, contentItem.implicitHeight + 14)
                                selectionFill: !Theme.animatedTabs
                                selectionColor: Theme.primaryContainer
                                text: modelData.title; selected: root.page === modelData.key
                                checkable: false
                                Accessible.name: modelData.title + " settings"
                                onClicked: root.navigate(modelData.key)
                                onActiveFocusChanged: if (activeFocus) {
                                    const top = mapToItem(navigationScroll.contentItem, 0, 0).y - 4;
                                    if (top < navigationScroll.contentY) navigationScroll.contentY = top;
                                    else if (top + height + 8 > navigationScroll.contentY + navigationScroll.height)
                                        navigationScroll.contentY = Math.max(0, top + height + 8 - navigationScroll.height);
                                }
                                contentItem: RowLayout {
                                    spacing: 12
                                    ShellIcon { name: nav.modelData.icon; color: nav.selected ? Theme.accent : Theme.muted; width: 20; height: 20 }
                                    LabelText { text: nav.text; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.WordWrap; font.pixelSize: Math.min(Theme.bodySize, 16); font.weight: nav.selected ? Font.Bold : Font.Medium }
                                }
                            }
                        }
                        LabelText { visible: FeatureCatalog.ready && root.results.length === 0; text: "No matching settings"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 13 }
                    }
                }
                LabelText { text: ShellState.demo ? "Demo · changes stay in memory" : !ShellState.backendReady ? "Connecting…" : ShellState.pendingActions.setting ? "Saving changes…" : "Changes save automatically"; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 18
            RowLayout {
                Layout.fillWidth: true; spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 6
                    LabelText { text: root.currentPage.title; font.pixelSize: 32; font.weight: Font.Bold }
                    LabelText { text: root.currentPage.description; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap }
                }
                IconButton { glyph: "×"; tooltip: "Close settings"; onClicked: root.closeRequested() }
            }
            Rectangle {
                visible: ShellState.statusMessage.length > 0
                Layout.fillWidth: true; implicitHeight: status.implicitHeight + 24; radius: 16
                color: ShellState.statusError ? Theme.liquidGlass ? Theme.alpha(Theme.red, .12) : Theme.mix(Theme.panel, Theme.red, 0.2) : Theme.primaryContainer
                LabelText { id: status; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; text: ShellState.statusMessage; textFormat: Text.PlainText; wrapMode: Text.Wrap }
            }
            Rectangle {
                visible: root.displayPreview.status === "pending"
                Layout.fillWidth: true; implicitHeight: confirmRow.implicitHeight + 24; radius: 16; color: Theme.primaryContainer
                RowLayout {
                    id: confirmRow; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; spacing: 8
                    LabelText { text: "Keep this display layout? Reverts in " + Math.max(0, Math.ceil(root.displayPreview.deadline - root.now / 1000)) + "s"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.weight: Font.Bold }
                    LiquidButton { text: "Keep changes"; onClicked: ShellState.run("displayConfirm", {token: root.displayPreview.token}) }
                    LiquidButton { text: "Revert"; onClicked: ShellState.run("displayRevert", {token: root.displayPreview.token}) }
                }
            }
            Flickable {
                id: pageScroll
                Layout.fillWidth: true; Layout.fillHeight: true
                contentWidth: width; contentHeight: pageLoader.item ? (pageLoader.item as Item).implicitHeight + 12 : 0
                clip: true; boundsBehavior: Flickable.StopAtBounds
                onContentYChanged: root.activity()
                ScrollBar.vertical: ScrollBar {}
                PageHost {
                    id: pageLoader
                    x: 6; y: 6
                    width: pageScroll.width - 12
                    // The host clips, so it must be as tall as the page content (or the
                    // viewport while the page is still loading), never zero.
                    height: item ? (item as Item).implicitHeight : pageScroll.height
                    active: root.active
                    key: root.currentPage.key
                    readonly property var legacy: ({topbar: barPage, display: displayPage, controlLayout: controlPage, elements: elementsPage, behavior: behaviorPage, appearance: appearancePage})
                    resolve: key => { const entry = SettingsRegistry.page(key).entry; return entry ? FeatureCatalog.component(entry) : legacy[key] || appearancePage; }
                    // Keep every visited page built (RAM cap lifted 2026-11-24).
                    maxPages: 0
                    // No page build may freeze this window: a cold page the user asks for and
                    // every page of the background walk are incubated. The walk only runs while
                    // the window is shown, and starts once the
                    // first page is up and only starts a page while the window is quiet (see
                    // quiet()), so no build lands on a scroll, a keystroke or a page change,
                    // and every later navigation is a warm switch.
                    asyncPages: true
                    property bool pagesWarmupArmed: true
                    onPageLoaded: {
                        if (!pagesWarmupArmed) return;
                        pagesWarmupArmed = false;
                        prewarm(() => SettingsRegistry.pages.map(p => p.key).filter(k => k !== root.currentPage.key),
                                () => root.quiet());
                    }
                }
            }
        }
    }
    Component { id: appearancePage; AppearancePage {} }
    Component { id: barPage; TopBarPage {} }
    Component { id: displayPage; DisplayPage {} }
    Component { id: controlPage; ControlLayoutPage {} }
    Component { id: elementsPage; ElementsPage {} }
    Component { id: behaviorPage; BehaviorPage {} }
}
