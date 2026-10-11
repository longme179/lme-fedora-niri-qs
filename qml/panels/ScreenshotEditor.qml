pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

Item {
    id: root
    required property var session
    signal closeRequested()
    property string tool: "pen"
    property color ink: Theme.red
    property int strokeWidth: 4
    property real zoom: 1
    property string exportAction: ""
    property string error: ""
    readonly property bool busy: !!exportAction || !!ShellState.pendingActions.captureExport || !!ShellState.pendingActions.captureOcr
    readonly property var canvas: drawing
    function render(action) {
        if (busy || !drawing.ready) return;
        error = ""; exportAction = action; drawing.exportTo(session.renderPath);
    }
    Shortcut { sequence: "Ctrl+Z"; enabled: !root.busy && !saveFolder.activeFocus; onActivated: drawing.undo() }
    Shortcut { sequence: "Ctrl+Shift+Z"; enabled: !root.busy && !saveFolder.activeFocus; onActivated: drawing.redo() }
    Shortcut { sequence: "Ctrl+S"; onActivated: root.render("save") }
    Shortcut { sequence: "Ctrl+C"; enabled: !ocrText.activeFocus && !saveFolder.activeFocus; onActivated: root.render("copy") }
    Shortcut { sequence: "Escape"; onActivated: root.closeRequested() }
    Component.onCompleted: if (ShellState.backendReady && !ShellState.demo) ShellState.run("captureLanguages")
    GlassPanel { anchors.fill: parent }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 20; spacing: 12
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Screenshot studio"; font.pixelSize: 24; font.weight: Font.Bold; Layout.fillWidth: true }
            LabelText { text: root.session.width + " × " + root.session.height; color: Theme.muted }
            IconButton { glyph: "×"; tooltip: "Close screenshot editor"; onClicked: root.closeRequested() }
        }
        Flow {
            Layout.fillWidth: true; spacing: 6
            Repeater {
                model: [{id: "pan", title: "Pan"}, {id: "pen", title: "Pen"}, {id: "highlight", title: "Highlight"}, {id: "rectangle", title: "Rectangle"}, {id: "arrow", title: "Arrow"}, {id: "redact", title: "Redact"}]
                delegate: LiquidButton {
                    required property var modelData; text: modelData.title; selected: root.tool === modelData.id; enabled: !root.busy
                    onClicked: root.tool = modelData.id
                }
            }
            LiquidButton { text: "Undo"; enabled: drawing.strokes.length > 0 && !root.busy; onClicked: drawing.undo() }
            LiquidButton { text: "Redo"; enabled: drawing.redoStack.length > 0 && !root.busy; onClicked: drawing.redo() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            Repeater {
                model: [Theme.red, Theme.yellow, Theme.cyan, Theme.green, Theme.purple, Theme.text]
                delegate: LiquidButton {
                    id: colorButton; required property var modelData
                    Layout.preferredWidth: 28; Layout.preferredHeight: 28; padding: 0; enabled: !root.busy
                    Accessible.name: "Ink color " + modelData
                    background: Rectangle { radius: 10; color: colorButton.modelData; border.width: root.ink.toString() === color.toString() ? 2 : 0; border.color: Theme.background }
                    onClicked: root.ink = modelData
                }
            }
            LiquidComboBox { model: ["4 px", "8 px", "12 px", "20 px"]; Accessible.name: "Stroke width"; enabled: !root.busy; onActivated: root.strokeWidth = [4, 8, 12, 20][currentIndex] }
            Item { Layout.fillWidth: true }
            LabelText { text: "Zoom" }
            LiquidSlider { Layout.preferredWidth: 120; from: 1; to: 3; stepSize: .1; value: 1; Accessible.name: "Screenshot zoom"; onValueChanged: root.zoom = value }
        }
        LabelText {
            Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12
            text: drawing.strokes.length >= 200 ? "Annotation limit reached (200). Undo a stroke to continue."
                : root.tool === "redact" ? "Drag to cover pixels with solid black. Copy or save the edited image to share the redacted version. Niri also puts the original capture in the clipboard." : "Drag to annotate. Pan to move around a zoomed image. Ctrl+Z undo · Ctrl+Shift+Z redo · Ctrl+S save · Ctrl+C copy."
        }
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 160
            radius: 18; color: Theme.background; clip: true
            Flickable {
                id: viewport; anchors.fill: parent; anchors.margins: 8
                readonly property real fitScale: Math.min(width / root.session.width, height / root.session.height)
                readonly property real imageScale: fitScale * root.zoom
                contentWidth: Math.max(width, imageContainer.width); contentHeight: Math.max(height, imageContainer.height)
                interactive: root.tool === "pan"; boundsBehavior: Flickable.StopAtBounds; clip: true
                ScrollBar.vertical: ScrollBar {} ScrollBar.horizontal: ScrollBar {}
                Item {
                    id: imageContainer; objectName: "annotationImage"
                    width: root.session.width * viewport.imageScale; height: root.session.height * viewport.imageScale
                    x: Math.max(0, (viewport.width - width) / 2); y: Math.max(0, (viewport.height - height) / 2)
                    AnnotationCanvas {
                        id: drawing; objectName: "annotationCanvas"; width: root.session.width; height: root.session.height
                        source: root.session.url || ""; scale: viewport.imageScale; transformOrigin: Item.TopLeft
                        tool: root.tool; ink: root.ink; lineWidth: root.strokeWidth
                        onExportFailed: { root.error = "Could not render the screenshot. Try again."; root.exportAction = ""; }
                        onExported: {
                            const action = root.exportAction; root.exportAction = "";
                            if (action === "ocr") ShellState.run("captureOcr", {token: root.session.token, language: languages.currentText});
                            else ShellState.run("captureExport", {token: root.session.token, operation: action, folder: saveFolder.text});
                        }
                    }
                    MouseArea {
                        anchors.fill: parent; enabled: root.tool !== "pan" && !root.busy && drawing.ready
                        cursorShape: Qt.CrossCursor
                        onPressed: mouse => { root.forceActiveFocus(); drawing.begin(mouse.x / viewport.imageScale, mouse.y / viewport.imageScale); }
                        onPositionChanged: mouse => { if (pressed) drawing.move(mouse.x / viewport.imageScale, mouse.y / viewport.imageScale); }
                        onReleased: drawing.finish(); onCanceled: drawing.cancel()
                    }
                }
            }
        }
        LabelText { visible: !!root.error || !!ShellState.statusMessage; text: root.error || ShellState.statusMessage; Layout.fillWidth: true; wrapMode: Text.Wrap; color: root.error || ShellState.statusError ? Theme.red : Theme.accent }
        RowLayout {
            Layout.fillWidth: true
            ExpressiveField { id: saveFolder; objectName: "screenshotFolder"; Layout.fillWidth: true; text: root.session.saveFolder || ""; placeholderText: "Save folder"; maximumLength: 4096; Accessible.name: "Screenshot save folder" }
            LiquidButton { text: "Save PNG"; enabled: drawing.ready && !root.busy; onClicked: root.render("save") }
            LiquidButton { text: "Copy image"; enabled: drawing.ready && !root.busy; onClicked: root.render("copy") }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Local OCR"; font.weight: Font.Bold }
            LiquidComboBox { id: languages; model: (root.session.languages || []).includes("eng") && (root.session.languages || []).includes("vie") ? ["eng+vie", ...root.session.languages] : root.session.languages || []; Accessible.name: "OCR language"; enabled: !root.busy; currentIndex: 0 }
            LiquidButton { text: ShellState.pendingActions.captureOcr ? "Recognizing…" : "Extract text"; enabled: drawing.ready && !root.busy && languages.model.length > 0; onClicked: root.render("ocr") }
            Item { Layout.fillWidth: true }
            LiquidButton { text: "Copy text"; enabled: ocrText.text.length > 0; onClicked: { ocrText.selectAll(); ocrText.copy(); ocrText.deselect(); } }
        }
        ScrollView {
            Layout.fillWidth: true; Layout.preferredHeight: root.session.ocrText ? 105 : 48; clip: true
            TextArea {
                id: ocrText; objectName: "ocrText"; text: root.session.ocrText || ""; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                placeholderText: languages.model.length ? "Choose Extract text to recognize the edited image. Processing stays on this machine." : "Install tesseract and language packs to extract selectable text. Processing stays on this machine."
                placeholderTextColor: Theme.muted
                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Theme.bodySize
                background: Rectangle { radius: 14; color: Theme.surfaceContainer }
            }
        }
    }
}
