import QtQuick

Item {
    id: root
    property string name: "bell"
    property color color: "white"
    implicitWidth: 18
    implicitHeight: 18

    // Draw small shell icons with a shared 24px grid, independent of icon fonts.
    Canvas {
        id: canvas
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections {
            target: root
            function onNameChanged() { canvas.requestPaint(); }
            function onColorChanged() { canvas.requestPaint(); }
        }
        onPaint: {
            const ctx = getContext("2d");
            ctx.reset();
            ctx.clearRect(0, 0, width, height);
            ctx.scale(width / 24, height / 24);
            ctx.strokeStyle = root.color;
            ctx.fillStyle = root.color;
            ctx.lineWidth = 1.8;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            if (root.name === "applications") {
                for (const x of [4, 14]) {
                    for (const y of [4, 14]) {
                        ctx.beginPath();
                        ctx.roundedRect(x, y, 6, 6, 1.4, 1.4);
                        ctx.stroke();
                    }
                }
            } else if (root.name === "overview") {
                for (const x of [3, 13]) {
                    ctx.beginPath(); ctx.roundedRect(x, 4, 8, 16, 2, 2); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(x + 2, 9); ctx.lineTo(x + 6, 9); ctx.stroke();
                }
            } else if (root.name === "tray") {
                for (const x of [5, 11, 17]) {
                    for (const y of [5, 11]) {
                        ctx.beginPath();
                        ctx.arc(x, y, 1.1, 0, Math.PI * 2);
                        ctx.fill();
                    }
                }
                ctx.beginPath();
                ctx.moveTo(8, 17); ctx.lineTo(12, 21); ctx.lineTo(16, 17);
                ctx.stroke();
            } else {
                ctx.beginPath();
                ctx.moveTo(5, 17);
                ctx.lineTo(7, 14);
                ctx.lineTo(7, 9);
                ctx.bezierCurveTo(7, 2.5, 17, 2.5, 17, 9);
                ctx.lineTo(17, 14);
                ctx.lineTo(19, 17);
                ctx.closePath();
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(10, 20);
                ctx.bezierCurveTo(10.8, 21.4, 13.2, 21.4, 14, 20);
                ctx.stroke();
                if (root.name === "bell-off") {
                    ctx.beginPath();
                    ctx.moveTo(3, 3); ctx.lineTo(21, 21);
                    ctx.stroke();
                }
            }
        }
    }
}
