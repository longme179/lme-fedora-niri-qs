//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env LME_SHELL_DEMO=1
//@ pragma Env QS_NO_RELOAD_POPUP=1
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/services"
import "qml/panels"
import "qml/settings"
import "qml/theme"
import "qml/services/LauncherSearch.js" as Search
ShellRoot {
    id: root
    property string mode: "control"
    property string page: "appearance"
    Component.onCompleted: if (Quickshell.env("LME_TEST_UPGRADES") !== "1") Qt.quit()
    FloatingWindow {
        id: window
        implicitWidth: 1280; implicitHeight: 900; fullscreen: true; title: "LME Upgrades Fixture"; color: Theme.background
        Loader {
            id: view
            anchors.centerIn: parent
            width: root.mode === "desktop" ? window.width : root.mode === "settings" ? Math.min(1160, window.width - 32) : root.mode === "control" ? Math.min(ShellState.preferences.controlWidth || 600, window.width - 32) : root.mode === "wifi" ? 560 : 700
            height: root.mode === "desktop" ? window.height : Math.min(window.height - 32, root.mode === "settings" ? 900 : 800)
            sourceComponent: root.mode === "desktop" ? desktop : root.mode === "settings" ? settingsView : root.mode === "launcher" ? launcher : root.mode === "wifi" ? wifi : root.mode === "notifications" ? notifications : control
        }
    }
    Component { id: settingsView; SettingsView { page: root.page; onCloseRequested: Qt.quit() } }
    Component { id: launcher; Launcher {} }
    Component { id: control; ControlCenter {} }
    Component { id: wifi; WifiPanel {} }
    Component { id: notifications; NotificationCenter {} }
    Component { id: desktop; DesktopPreview {} }
    function find(item, name) {
        if (!item) return null;
        if (item.objectName === name || item.text === name) return item;
        for (const child of item.children || []) { const result = find(child, name); if (result) return result; }
        if (item.contentItem && item.contentItem !== item) return find(item.contentItem, name);
        return null;
    }
    IpcHandler {
        target: "upgradesFixture"
        function navigate(mode: string, page: string): void { root.page = page; root.mode = mode; }
        function run(request: string): void { const data = JSON.parse(request); ShellState.run(data.action, data); }
        function panel(name: string): void { if (name) ShellState.togglePanel(name); else ShellState.closePanels(); }
        function confirmPower(): void {
            const loader = root.find(window.contentItem, "desktopPanel");
            const menu = loader ? loader.item as PowerMenu : null;
            if (menu) { menu.pendingAction = "shutdown"; menu.pendingLabel = "Shut down"; }
        }
        function state(): string {
            return JSON.stringify({ready: ShellState.backendReady, preferences: ShellState.preferences, lastResult: ShellState.lastResult,
                mode: root.mode, query: root.mode === "launcher" && view.item ? view.item.query : "", results: root.mode === "launcher" && view.item ? view.item.results : [],
                calculationError: root.mode === "launcher" && view.item ? view.item.calculationError : "", displays: ShellState.snapshot.displays || {},
                groups: root.mode === "notifications" && view.item ? view.item.grouped.length : 0, dnd: Notifications.dnd, popups: Notifications.popups.length,
                history: Notifications.history.length, library: ShellState.snapshot.wallpaperLibrary || {},
                monitor: ShellState.snapshot.monitor || {}, idle: ShellState.snapshot.idle || {}, nightLight: ShellState.snapshot.nightLight || {},
                motionProgress: root.find(window.contentItem, "motionPreview") ? root.find(window.contentItem, "motionPreview").progress : -1,
                deformation: Theme.deformation,
                processMatches: root.find(window.contentItem, "systemMonitor") ? root.find(window.contentItem, "systemMonitor").processes.length : -1,
                keybindMatches: root.find(window.contentItem, "keybindPage") ? root.find(window.contentItem, "keybindPage").matches.length : -1,
                wifiPopup: root.mode === "wifi" && view.item ? view.item.connectionPopup.visible : false});
        }
        function themeState(): string {
            const button = root.find(window.contentItem, "elementPreviewButton"), feedback = button ? root.find(button, "liquidFeedback") : null;
            const bar = root.find(window.contentItem, "desktopBar");
            const barViewport = bar ? root.find(bar, "barModuleViewport") : null;
            const panel = root.find(window.contentItem, "desktopPanel");
            const field = root.find(window.contentItem, "element-buttonFill"), group = root.find(window.contentItem, "elementGroup");
            const confirm = root.find(window.contentItem, "Confirm shut down");
            return JSON.stringify({ready: ShellState.backendReady, colors: Theme.catalog.colors.length,
                buttonFill: Theme.buttonFill.toString(), barFill: Theme.barFill.toString(), bodyFont: Theme.fontFamily, barFont: Theme.barFamily,
                bodySize: Theme.bodySize, animations: Theme.animations, status: ShellState.statusMessage, hover: button ? button.hovered : false, scale: button ? button.scale : 1, radius: button ? button.background.radius : 0,
                ripple: feedback ? feedback.rippleProgress : 0, rippleOpacity: feedback ? feedback.rippleOpacity : 0,
                feedbackRunning: feedback ? feedback.animating : false,
                field: field ? {text:field.text,focus:field.activeFocus,width:field.width,height:field.height} : {}, colorGroup: group ? group.currentIndex : -1,
                panel: panel ? {active:panel.active,shown:panel.shown,progress:panel.progress,x:panel.x,y:panel.y,kind:ShellState.panelKind} : {},
                power: confirm ? {hover:confirm.hovered,color:confirm.background.color.toString()} : {},
                bar: bar ? {x:bar.x,y:bar.y,width:bar.width,height:bar.height,viewportHeight:barViewport ? barViewport.height : 0,screenHeight:view.height} : {}});
        }
        function position(name: string): string {
            const popup = root.mode === "wifi" && view.item ? view.item.connectionPopup : null;
            const item = popup && popup.visible ? root.find(popup.contentItem, name) : root.find(window.contentItem, name);
            if (!item) return "{}";
            for (let p = item.parent; p; p = p.parent) if (typeof p.contentY === "number" && p.contentItem) {
                const position = item.mapToItem(p.contentItem, 0, 0);
                if (position.y < p.contentY || position.y + item.height > p.contentY + p.height)
                    p.contentY = Math.max(0, Math.min(p.contentHeight - p.height, position.y - 20));
            }
            const point = item.mapToGlobal(item.width / 2, item.height / 2); return JSON.stringify({x: Math.round(point.x), y: Math.round(point.y)});
        }
        function screenshot(path: string): void { view.grabToImage(result => result.saveToFile(path)); }
        function seedNotifications(): void { Notifications.local("Timer complete", "Take a short break."); Notifications.history = [{id: "example-mail", appName: "Mail", summary: "Project update", body: "The review is ready.", timestamp: Date.now(), urgency: 1, active: false, popup: false, actions: [], transient: false}, ...Notifications.history]; }
        function dndNearExpiry(): void { ShellState.run("setting", {key: "dndUntil", value: Date.now() + 1500}); }
        function fuzzy(): string { return JSON.stringify({subsequence: Search.apps("frfox", ShellState.apps, [], false).map(a => a.name), typo: Search.apps("fierfox", ShellState.apps, [], false).map(a => a.name)}); }
    }
}
