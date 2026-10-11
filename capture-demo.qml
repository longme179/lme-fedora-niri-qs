//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma Env LME_SHELL_DEMO=1
//@ pragma Env QS_NO_RELOAD_POPUP=1
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/panels"
import "qml/theme"

ShellRoot {
    id: root
    readonly property var session: JSON.parse(Quickshell.env("LME_TEST_CAPTURE_SESSION") || "{}")
    property bool sourceReady: false
    property string ocr: ""
    readonly property ScreenshotEditor editor: view.item as ScreenshotEditor
    Component.onCompleted: if (Quickshell.env("LME_TEST_CAPTURE") !== "1") Qt.quit()
    FloatingWindow {
        id: window
        title: "LME Screenshot Fixture"; implicitWidth: 1280; implicitHeight: 900; fullscreen: true; color: Theme.background
        Canvas {
            id: original; width: root.session.width || 960; height: root.session.height || 540
            renderTarget: Canvas.Image; renderStrategy: Canvas.Immediate
            onPaint: {
                const ctx = getContext("2d"); ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, width, height);
                ctx.fillStyle = "#111111"; ctx.font = "bold 42px Roboto"; ctx.fillText("LME SCREENSHOT", 48, 74);
                ctx.font = "24px Roboto"; ctx.fillText("Local OCR and flattened annotations", 48, 116);
                ctx.fillStyle = "#9580ff"; ctx.fillRect(48, 160, 400, 280);
                ctx.fillStyle = "#80ffea"; ctx.fillRect(480, 160, 430, 280);
                if (!root.sourceReady && root.session.path && save(root.session.path)) root.sourceReady = true;
            }
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
            return JSON.stringify({ready: !!root.editor && root.editor.canvas.ready, strokes: root.editor ? root.editor.canvas.strokes.length : -1, redo: root.editor ? root.editor.canvas.redoStack.length : -1, busy: root.editor ? root.editor.busy : false, error: root.editor ? root.editor.error : "", ocr: root.ocr, folderFocused: !!folder && folder.activeFocus});
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
