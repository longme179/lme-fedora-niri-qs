import QtQuick

Canvas {
    id: root
    required property string source
    property string tool: "pen"
    property color ink: "#ff9580"
    property int lineWidth: 4
    property var strokes: []
    property var redoStack: []
    property var draft: null
    property string exportPath: ""
    property bool ready: false
    signal exported(string path)
    signal exportFailed()
    renderTarget: Canvas.Image
    renderStrategy: Canvas.Immediate
    onSourceChanged: { ready = false; strokes = []; redoStack = []; draft = null; if (source) { loadImage(source); ready = isImageLoaded(source); } }
    Component.onCompleted: if (source) { loadImage(source); ready = isImageLoaded(source); }
    onImageLoaded: { ready = isImageLoaded(source); requestPaint(); }
    onStrokesChanged: requestPaint()
    function point(x, y) { return {x: Math.max(0, Math.min(width, x)), y: Math.max(0, Math.min(height, y))}; }
    // shortcut: 200 strokes / 4000 points each, increase when long-form drawing is needed.
    function begin(x, y) { if (!ready || strokes.length >= 200) return; draft = {tool: tool, color: ink.toString(), width: lineWidth, points: [point(x, y)]}; requestPaint(); }
    function move(x, y) {
        if (!draft) return;
        const p = point(x, y);
        if (draft.tool === "pen") { if (draft.points.length < 4000) draft.points.push(p); }
        else draft.points[1] = p;
        requestPaint();
    }
    function finish() { if (!draft) return; strokes = strokes.concat([draft]); redoStack = []; draft = null; requestPaint(); }
    function cancel() { draft = null; requestPaint(); }
    function undo() { if (strokes.length) { redoStack = redoStack.concat([strokes[strokes.length - 1]]); strokes = strokes.slice(0, -1); } }
    function redo() { if (redoStack.length) { strokes = strokes.concat([redoStack[redoStack.length - 1]]); redoStack = redoStack.slice(0, -1); } }
    function exportTo(path) { if (!ready || exportPath) return; exportPath = path; requestPaint(); }
    function paintStroke(ctx, stroke) {
        const a = stroke.points[0], b = stroke.points[stroke.points.length - 1];
        ctx.save(); ctx.globalAlpha = 1; ctx.lineWidth = stroke.width; ctx.lineCap = "round"; ctx.lineJoin = "round";
        ctx.strokeStyle = stroke.color; ctx.fillStyle = stroke.color;
        if (stroke.tool === "redact" || stroke.tool === "highlight") {
            ctx.fillStyle = stroke.tool === "redact" ? "#000000" : stroke.color;
            ctx.globalAlpha = stroke.tool === "redact" ? 1 : .30;
            ctx.fillRect(Math.floor(Math.min(a.x, b.x)), Math.floor(Math.min(a.y, b.y)), Math.ceil(Math.abs(b.x - a.x)), Math.ceil(Math.abs(b.y - a.y)));
        } else if (stroke.tool === "rectangle") {
            ctx.strokeRect(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.abs(b.x - a.x), Math.abs(b.y - a.y));
        } else {
            ctx.beginPath(); ctx.moveTo(a.x, a.y);
            if (stroke.points.length === 1) ctx.lineTo(a.x + .01, a.y);
            for (const p of stroke.points.slice(1)) ctx.lineTo(p.x, p.y);
            ctx.stroke();
            if (stroke.tool === "arrow" && stroke.points.length > 1) {
                const angle = Math.atan2(b.y - a.y, b.x - a.x), head = Math.max(12, stroke.width * 3);
                ctx.beginPath(); ctx.moveTo(b.x - head * Math.cos(angle - .5), b.y - head * Math.sin(angle - .5));
                ctx.lineTo(b.x, b.y); ctx.lineTo(b.x - head * Math.cos(angle + .5), b.y - head * Math.sin(angle + .5)); ctx.stroke();
            }
        }
        ctx.restore();
    }
    onPaint: {
        if (!ready) return;
        const ctx = getContext("2d"); ctx.reset(); ctx.clearRect(0, 0, width, height); ctx.drawImage(source, 0, 0, width, height);
        for (const stroke of strokes) paintStroke(ctx, stroke);
        if (draft) paintStroke(ctx, draft);
        if (exportPath) {
            const path = exportPath; exportPath = "";
            if (save(path)) exported(path); else exportFailed();
        }
    }
}
