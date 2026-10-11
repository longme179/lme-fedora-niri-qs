pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

Item {
    id: root
    property string page: "appearance"
    signal closeRequested()
    property var history: []
    readonly property var currentPage: SettingsRegistry.page(page)
    readonly property var displayPreview: (ShellState.snapshot.displays || {}).preview || {}
    property real now: Date.now()
    onDisplayPreviewChanged: now = Date.now()
    Timer { interval: 1000; repeat: true; running: ["applying", "pending", "reverting"].includes(root.displayPreview.status); onTriggered: { root.now = Date.now(); if (ShellState.backendReady) ShellState.run("displayRefresh"); } }
    function navigate(key) {
        if (key === page) return;
        history = history.concat(page); page = SettingsRegistry.page(key).key;
        search.clear(); pageScroll.contentY = 0;
    }
    function goBack() { if (history.length) { page = history[history.length - 1]; history = history.slice(0, -1); pageScroll.contentY = 0; } }
    Shortcut { sequence: "Ctrl+F"; onActivated: search.forceActiveFocus() }
    Shortcut { sequence: "Alt+Left"; onActivated: root.goBack() }
    Shortcut { sequence: "Escape"; onActivated: { if (search.text) search.clear(); else root.closeRequested(); } }
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
                    LabelText { text: "LME Settings"; font.pixelSize: 22; font.weight: Font.Bold }
                    LabelText { text: "Make room for you."; color: Theme.muted; font.pixelSize: 13 }
                }
                ExpressiveField {
                    id: search
                    Layout.fillWidth: true
                    placeholderText: "Search settings"
                    Accessible.name: "Search settings"
                    onAccepted: { const results = SettingsRegistry.search(text); if (results.length) root.navigate(results[0].key); }
                }
                Flickable {
                    id: navigationScroll
                    Layout.fillWidth: true; Layout.fillHeight: true
                    contentWidth: width; contentHeight: navigationColumn.implicitHeight
                    clip: true; boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}
                    ColumnLayout {
                        id: navigationColumn
                        width: navigationScroll.width - 8; spacing: 6
                        Repeater {
                            model: SettingsRegistry.search(search.text)
                            delegate: LiquidButton {
                                id: nav
                                required property var modelData
                                Layout.fillWidth: true; Layout.preferredHeight: Math.max(48, contentItem.implicitHeight + 14)
                                text: modelData.title; selected: root.page === modelData.key
                                checkable: false
                                Accessible.name: modelData.title + " settings"
                                onClicked: root.navigate(modelData.key)
                                onActiveFocusChanged: if (activeFocus) {
                                    if (y < navigationScroll.contentY) navigationScroll.contentY = y;
                                    else if (y + height > navigationScroll.contentY + navigationScroll.height)
                                        navigationScroll.contentY = Math.max(0, y + height - navigationScroll.height);
                                }
                                contentItem: RowLayout {
                                    spacing: 12
                                    ShellIcon { name: nav.modelData.icon; color: nav.selected ? Theme.accent : Theme.muted; width: 20; height: 20 }
                                    LabelText { text: nav.text; Layout.fillWidth: true; Layout.minimumWidth: 0; wrapMode: Text.WordWrap; font.pixelSize: Math.min(Theme.bodySize, 16); font.weight: nav.selected ? Font.Bold : Font.Medium }
                                }
                            }
                        }
                        LabelText { visible: SettingsRegistry.search(search.text).length === 0; text: "No matching settings"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 13 }
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
                color: ShellState.statusError ? Theme.mix(Theme.panel, Theme.red, 0.2) : Theme.primaryContainer
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
                ScrollBar.vertical: ScrollBar {}
                SlideLoader {
                    id: pageLoader
                    direction: "up"
                    width: pageScroll.width - 12
                    content: root.page === "topbar" ? barPage : root.page === "wallpaper" ? wallpaperPage
                                   : root.page === "display" ? displayPage : root.page === "controlLayout" ? controlPage
                                   : root.page === "idle" ? idlePage : root.page === "keybinds" ? keybindsPage : root.page === "nightLight" ? nightPage : root.page === "elements" ? elementsPage
                                   : root.page === "weather" ? weatherPage : root.page === "clipboard" ? clipboardPage : root.page === "behavior" ? behaviorPage : root.page === "about" ? aboutPage : appearancePage
                }
            }
        }
    }
    Component { id: appearancePage; AppearancePage {} }
    Component { id: barPage; TopBarPage {} }
    Component { id: wallpaperPage; WallpaperPage {} }
    Component { id: displayPage; DisplayPage {} }
    Component { id: controlPage; ControlLayoutPage {} }
    Component { id: weatherPage; WeatherPage {} }
    Component { id: clipboardPage; ClipboardPage {} }
    Component { id: idlePage; IdlePage {} }
    Component { id: keybindsPage; KeybindsPage {} }
    Component { id: nightPage; NightLightPage {} }
    Component { id: elementsPage; ElementsPage {} }
    Component { id: behaviorPage; BehaviorPage {} }
    Component { id: aboutPage; AboutPage {} }
}
