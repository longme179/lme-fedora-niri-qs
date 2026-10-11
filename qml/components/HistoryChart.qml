import QtQuick
import QtQuick.Layouts
import "../theme"
ColumnLayout {
    id: root
    property var samples: []
    property string series: "cpu"
    property color lineColor: Theme.cyan
    property real maximum: 100
    Layout.fillWidth: true
    spacing: 6
    Canvas {
        id: canvas
        Layout.fillWidth: true; Layout.preferredHeight: 76
        onWidthChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d"); ctx.reset();
            ctx.strokeStyle = Theme.alpha(Theme.text, 0.1); ctx.lineWidth = 1;
            for (let n = 1; n < 4; n++) { ctx.beginPath(); ctx.moveTo(0, height*n/4); ctx.lineTo(width, height*n/4); ctx.stroke(); }
            ctx.strokeStyle = root.lineColor; ctx.lineWidth = 2; ctx.beginPath();
            let connected = false;
            for (let i = 0; i < root.samples.length; i++) {
                const value = root.samples[i][root.series];
                if (value === null || value === undefined) { connected = false; continue; }
                const x = width * (60-root.samples.length+i)/59;
                const y = height - 2 - Math.max(0, Math.min(1, Number(value)/Math.max(1,root.maximum)))*(height-4);
                if (connected) ctx.lineTo(x,y); else ctx.moveTo(x,y);
                connected = true;
            }
            ctx.stroke();
        }
        Connections { target: root; function onSamplesChanged() { canvas.requestPaint(); } function onMaximumChanged() { canvas.requestPaint(); } function onLineColorChanged() { canvas.requestPaint(); } }
    }
    RowLayout {
        Layout.fillWidth: true
        LabelText { text: "2 min ago"; color: Theme.muted; font.pixelSize: 10 }
        Item { Layout.fillWidth: true }
        LabelText { text: "Now"; color: Theme.muted; font.pixelSize: 10 }
    }
}
