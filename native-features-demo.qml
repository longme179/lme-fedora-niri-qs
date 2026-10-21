//@ pragma UseQApplication
//@ pragma Env LME_SHELL_BACKEND_DEMO=1
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/services"
import "qml/panels"

ShellRoot {
    property bool clipboardInitialPending: Quickshell.env("LME_TEST_CLIPBOARD_UI") === "1"
    function initializeClipboard() {
        if (!clipboardInitialPending || Quickshell.env("LME_TEST_FEATURES") !== "1" || !FeatureCatalog.ready) return;
        clipboardInitialPending = false;
        ClipboardState.start(); ShellState.togglePanel("clipboard");
    }
    Connections { target: FeatureCatalog; function onReadyChanged() { Qt.callLater(initializeClipboard); } }
    function find(item, name) { if (!item) return null; if (item.objectName === name) return item; for (const child of item.children || []) { const match = find(child, name); if (match) return match; } return null; }
    function mediaStatus(name) {
        const timeline = find(surface,name), wave = find(timeline,"mediaProgressWave");
        return {position:timeline?.position ?? 0,duration:timeline?.duration ?? 0,progressAvailable:timeline?.progressAvailable ?? false,elapsedText:find(timeline,"mediaElapsed")?.text,
            playerName:timeline?.player?.dbusName,playing:timeline?.playing,timingUnavailable:find(timeline,"mediaTimingUnavailable")?.visible,
            wave:{present:!!wave,running:wave?.animating,phase:wave?.phase,amplitude:wave?.currentAmp,value:wave?.ratio,indeterminate:wave?.indeterminate,software:wave?.software}};
    }
    Component.onCompleted: {
        if (Quickshell.env("LME_TEST_FEATURES") !== "1") { Qt.quit(); return; }
        if (clipboardInitialPending) initializeClipboard();
        else ShellState.activityOpen = true;
    }
    IpcHandler {
        target: "featuresFixture"
        function clipboardStatus(): string { return JSON.stringify({ready: ClipboardState.ready, capturing: ClipboardState.capturing, visible: ShellState.isPanelOpen("clipboard"), count: ClipboardState.entries.length, query: ClipboardState.query, kind: ClipboardState.filter, preview: clipboardLoader.item ? clipboardLoader.item.previewOpen : false, focused: clipboardLoader.item ? clipboardLoader.item.searchFocused : false, pinned: ClipboardState.entries.filter(i => i.pinned).length, images: ClipboardState.entries.filter(i => i.kind === "image").length, lastResult: ShellState.lastResult, error: ClipboardState.state.error || ClipboardState.messageError}); }
        function openClipboard(): void { ShellState.togglePanel("clipboard"); }
        function openNotifications(): void { ShellState.togglePanel("notifications"); }
        function annotationStatus(): string { return JSON.stringify({ready: ShellState.backendReady, notifications: Notifications.history, visible: ShellState.notificationsOpen, lastResult: ShellState.lastResult}); }
        function openActivity(): void { ShellState.togglePanel("activity"); }
        function openControl(): void {
            ShellState.run("setting", {key:"controlLayout",value:ShellState.preferences.controlLayout.map(item => Object.assign({},item,{enabled:item.id==="media"}))});
            ShellState.togglePanel("control");
        }
        function controlStatus(): string { return JSON.stringify(mediaStatus("controlMediaProgress")); }
        function selectPlayer(name: string, control: bool): void {
            const picker=find(surface,control ? "controlPlayerSelector" : "activityPlayerSelector");
            const index=ActivityState.players.findIndex(p => p.dbusName===name);
            if (picker && index>=0) { picker.currentIndex=index; picker.activated(index); }
        }
        function activityStatus(): string {
            const card = find(surface, "activityTimerCard"), timer = find(surface, "activityTimer");
            return JSON.stringify(Object.assign({visible: ShellState.activityOpen, expansion: island.expansion, transitioning: island.transitioning, width: island.width, height: island.height, kind: ActivityState.kind, players: ActivityState.players.length, title: ActivityState.track, timerRunning: FocusTimer.running, remaining: FocusTimer.remaining, stopwatchRunning: FocusTimer.stopwatchRunning, elapsed: FocusTimer.stopwatchElapsed,
                caption: find(surface,"activityPanelTitle")?.text, idleTitle: ActivityState.title, mode: FocusTimer.mode,
                cardColor: card?.color.toString(), startColor: timer?.plate?.color.toString(),
                modes: [0,1,2].map(i => { const button=find(surface,"activityMode-"+i); return {selected:button?.selected,color:button?.plate?.color.toString()}; })},mediaStatus("activityMediaProgress")));
        }
        function focusedWindow(title: string): string {
            ShellState.snapshot = Object.assign({}, ShellState.snapshot, {niri: Object.assign({}, ShellState.niri, {windows: title ? [{title, is_focused:true}] : []})});
            return JSON.stringify({title:ActivityState.title,caption:find(surface,"activityPanelTitle")?.text});
        }
        function timerNearCompletion(): void { FocusTimer.remaining = 1; FocusTimer.start(); }
        function disableMotion(): void { ShellState.run("setting", {key:"animations",value:false}); }
        function mediaWave(value: bool): void { ShellState.run("setting", {key:"mediaWave",value}); }
        function seek(position: real): void { if (ActivityState.player && ActivityState.player.canSeek) ActivityState.player.position=position; }
        function activityScreenshot(path: string): void { surface.grabToImage(result => result.saveToFile(path)); }
        function buttonPosition(name: string): string {
            const button = find(surface, name); if (!button) return "";
            const point = button.mapToGlobal(button.width / 2, button.height / 2);
            return JSON.stringify({x: Math.round(point.x), y: Math.round(point.y)});
        }
    }
    FloatingWindow {
        title: "LME Native Feature Test"
        implicitWidth: 800; implicitHeight: 820
        fullscreen: true
        color: "#22212c"
        Item { id: surface; anchors.fill: parent
        ActivityIsland { id: island }
        Loader { id: clipboardLoader; anchors.centerIn: parent; active: ShellState.isPanelOpen("clipboard"); sourceComponent: Component { ClipboardPanel {} }
            width: 620; height: 710 }
        Loader { id: controlLoader; anchors.centerIn: parent; active: ShellState.controlOpen; sourceComponent: Component { ControlDashboard {} }
            width: 620; height: 760 }
        Loader {
            anchors.centerIn: parent; active: ShellState.notificationsOpen
            sourceComponent: Component { NotificationCenter {} }
            width: 620; height: 760
        }
        }
    }
}
