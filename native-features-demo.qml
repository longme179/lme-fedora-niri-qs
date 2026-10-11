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
    Component.onCompleted: {
        if (Quickshell.env("LME_TEST_FEATURES") !== "1") { Qt.quit(); return; }
        if (Quickshell.env("LME_TEST_CLIPBOARD_UI") === "1") { ClipboardState.start(); ShellState.clipboardOpen = true; }
        else ShellState.activityOpen = true;
    }
    IpcHandler {
        target: "featuresFixture"
        function clipboardStatus(): string { return JSON.stringify({ready: ClipboardState.ready, capturing: ClipboardState.capturing, visible: ShellState.clipboardOpen, count: ClipboardState.entries.length, query: ClipboardState.query, kind: ClipboardState.filter, preview: clipboardLoader.item ? clipboardLoader.item.previewOpen : false, focused: clipboardLoader.item ? clipboardLoader.item.searchFocused : false, pinned: ClipboardState.entries.filter(i => i.pinned).length, images: ClipboardState.entries.filter(i => i.kind === "image").length, error: ClipboardState.state.error || ClipboardState.messageError}); }
        function openClipboard(): void { ShellState.togglePanel("clipboard"); }
        function openActivity(): void { ShellState.togglePanel("activity"); }
        function activityStatus(): string { return JSON.stringify({visible: ShellState.activityOpen, expansion: island.expansion, transitioning: island.transitioning, width: island.width, height: island.height, kind: ActivityState.kind, players: ActivityState.players.length, playing: ActivityState.playing, title: ActivityState.track, timerRunning: FocusTimer.running, remaining: FocusTimer.remaining, stopwatchRunning: FocusTimer.stopwatchRunning, elapsed: FocusTimer.stopwatchElapsed}); }
        function timerNearCompletion(): void { FocusTimer.remaining = 1; FocusTimer.start(); }
        function disableMotion(): void { ShellState.snapshot = Object.assign({}, ShellState.snapshot, {preferences: Object.assign({}, ShellState.preferences, {animations: false})}); }
        function buttonPosition(name: string): string {
            function find(item) { if (item.objectName === name) return item; for (const child of item.children || []) { const match = find(child); if (match) return match; } return null; }
            const button = find(surface); if (!button) return "";
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
        Loader { id: clipboardLoader; anchors.centerIn: parent; active: ShellState.clipboardOpen; sourceComponent: Component { ClipboardPanel {} }
            width: 620; height: 710 }
        }
    }
}
