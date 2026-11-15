// Role: capture-demo.qml (host layer, fan-in 1).
// Shared component/helper; keep API stable for wide QML reuse.
//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env LME_SHELL_DEMO=1
//@ pragma Env QS_NO_RELOAD_POPUP=1
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/panels"
import "qml/services"
import "qml/theme"

ShellRoot {
    id: root
    readonly property var session: JSON.parse(Quickshell.env("LME_TEST_CAPTURE_SESSION") || "{}")
    property bool sourceReady: false
    property string ocr: ""
    readonly property ScreenshotEditor editor: view.item as ScreenshotEditor
    Timer { id: sourceRetry; interval: 250; repeat: false; onTriggered: root.saveSource() }
    function saveSource() {
        if (root.sourceReady || !root.session.path) return;
        original.grabToImage(result => { if (result.saveToFile(root.session.path)) root.sourceReady = true; });
    }
    Component.onCompleted: {
        if (Quickshell.env("LME_TEST_CAPTURE") !== "1") Qt.quit();
        else if (root.session.path) { Qt.callLater(root.saveSource); sourceRetry.start(); }
    }
    FloatingWindow {
        id: window
        title: "LME Screenshot Fixture"; implicitWidth: 1280; implicitHeight: 900; fullscreen: true; color: Theme.background
        Item {
            id: original; width: root.session.width || 960; height: root.session.height || 540
            Rectangle { anchors.fill: parent; color: "#ffffff" }
            Text { x: 48; y: 74; text: "LME SCREENSHOT"; font.pixelSize: 42; font.bold: true; color: "#111111" }
            Text { x: 48; y: 116; text: "Local OCR and flattened annotations"; font.pixelSize: 24; color: "#111111" }
            Rectangle { x: 48; y: 160; width: 400; height: 280; color: "#9580ff" }
            Rectangle { x: 480; y: 160; width: 430; height: 280; color: "#80ffea" }
        }
        Loader {
            id: view; anchors.centerIn: parent; width: 1180; height: 860; active: root.sourceReady
            sourceComponent: ScreenshotEditor {
                id: editor
                session: Object.assign({}, root.session, {ocrText: root.ocr})
                onCloseRequested: Qt.quit()
            }
        }
    }
    function find(item, name) {
        if (!item) return null;
        if (item.objectName === name || item.text === name) return item;
        for (const child of item.children || []) { const found = find(child, name); if (found) return found; }
        if (item.contentItem && item.contentItem !== item) return find(item.contentItem, name);
        return null;
    }
    IpcHandler {
        target: "captureFixture"
        function state(): string {
            const folder = root.find(window.contentItem, "screenshotFolder");
            return JSON.stringify({ready: !!root.editor && root.editor.canvas.ready, strokes: root.editor ? root.editor.canvas.strokes.length : -1, redo: root.editor ? root.editor.canvas.redoStack.length : -1, busy: root.editor ? root.editor.busy : false, error: root.editor ? root.editor.error : "", ocr: root.ocr, folderFocused: !!folder && folder.activeFocus, lastResult: ShellState.lastResult});
        }
        function position(name: string): string {
            const item = root.find(window.contentItem, name); if (!item) return "{}";
            const p = item.mapToGlobal(item.width / 2, item.height / 2); return JSON.stringify({x: Math.round(p.x), y: Math.round(p.y)});
        }
        function imagePoint(x: real, y: real): string {
            const item = root.find(window.contentItem, "annotationCanvas"); if (!item) return "{}";
            const p = item.mapToGlobal(x, y); return JSON.stringify({x: Math.round(p.x), y: Math.round(p.y)});
        }
        function recognized(text: string): void { root.ocr = text; }
        function resizeEditor(width: real, height: real): void { view.width = width; view.height = height; }
        function screenshot(path: string): void { view.grabToImage(result => result.saveToFile(path)); }
    }
}
