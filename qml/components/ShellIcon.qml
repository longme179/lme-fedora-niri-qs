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
            if (root.name === "record") {
                ctx.beginPath(); ctx.arc(12, 12, 8, 0, Math.PI * 2); ctx.stroke();
                ctx.beginPath(); ctx.arc(12, 12, 4, 0, Math.PI * 2); ctx.fill();
            } else if (root.name === "clipboard") {
                ctx.beginPath(); ctx.roundedRect(5, 4, 14, 18, 2, 2); ctx.stroke();
                ctx.beginPath(); ctx.roundedRect(9, 2, 6, 5, 1, 1); ctx.fill();
                for (const y of [11, 15, 18]) { ctx.beginPath(); ctx.moveTo(9, y); ctx.lineTo(15, y); ctx.stroke(); }
            } else if (root.name === "lock") {
                ctx.beginPath(); ctx.roundedRect(5, 10, 14, 11, 2, 2); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(8, 10); ctx.lineTo(8, 7); ctx.arc(12, 7, 4, Math.PI, 0); ctx.lineTo(16, 10); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(12, 14); ctx.lineTo(12, 17); ctx.stroke();
            } else if (root.name === "applications") {
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
            } else if (root.name === "settings") {
                ctx.beginPath();
                for (let i = 0; i < 24; i++) {
                    const angle = i * Math.PI / 12;
                    const radius = i % 4 === 0 || i % 4 === 3 ? 9 : 7;
                    const x = 12 + Math.cos(angle) * radius, y = 12 + Math.sin(angle) * radius;
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                }
                ctx.closePath(); ctx.stroke();
                ctx.beginPath(); ctx.arc(12, 12, 3, 0, Math.PI * 2); ctx.stroke();
            } else if (root.name === "refresh") {
                ctx.beginPath(); ctx.arc(12, 12, 8, 0.6, Math.PI * 1.8); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(15, 3); ctx.lineTo(20, 6); ctx.lineTo(15, 8); ctx.stroke();
            } else if (root.name === "clock") {
                ctx.beginPath(); ctx.arc(12, 12, 9, 0, Math.PI * 2); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(12, 6); ctx.lineTo(12, 12); ctx.lineTo(16, 14); ctx.stroke();
            } else if (root.name === "wifi") {
                for (const r of [5, 9, 13]) {
                    ctx.beginPath(); ctx.arc(12, 19, r, Math.PI * 1.25, Math.PI * 1.75); ctx.stroke();
                }
                ctx.beginPath(); ctx.arc(12, 19, 1, 0, Math.PI * 2); ctx.fill();
            } else if (root.name === "audio") {
                ctx.beginPath(); ctx.moveTo(3, 9); ctx.lineTo(7, 9); ctx.lineTo(12, 5); ctx.lineTo(12, 19); ctx.lineTo(7, 15); ctx.lineTo(3, 15); ctx.closePath(); ctx.stroke();
                for (const r of [5, 9]) { ctx.beginPath(); ctx.arc(12, 12, r, -0.8, 0.8); ctx.stroke(); }
            } else if (root.name === "battery") {
                ctx.beginPath(); ctx.roundedRect(3, 7, 17, 10, 2, 2); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(22, 10); ctx.lineTo(22, 14); ctx.stroke();
                ctx.fillRect(6, 10, 10, 4);
            } else if (root.name === "media") {
                ctx.beginPath(); ctx.moveTo(9, 17); ctx.lineTo(9, 5); ctx.lineTo(20, 3); ctx.lineTo(20, 15); ctx.stroke();
                ctx.beginPath(); ctx.ellipse(2, 14, 7, 5); ctx.fill();
                ctx.beginPath(); ctx.ellipse(13, 12, 7, 5); ctx.fill();
            } else if (root.name === "weather-sun") {
                ctx.beginPath(); ctx.arc(12, 12, 4, 0, Math.PI * 2); ctx.stroke();
                for (let i = 0; i < 8; i++) {
                    const a = i * Math.PI / 4;
                    ctx.beginPath(); ctx.moveTo(12 + 7 * Math.cos(a), 12 + 7 * Math.sin(a));
                    ctx.lineTo(12 + 10 * Math.cos(a), 12 + 10 * Math.sin(a)); ctx.stroke();
                }
            } else if (root.name.startsWith("weather-")) {
                ctx.beginPath(); ctx.moveTo(6, 16);
                ctx.bezierCurveTo(-1, 16, 0, 8, 6, 8);
                ctx.bezierCurveTo(8, 1, 17, 2, 18, 9);
                ctx.bezierCurveTo(25, 9, 24, 16, 18, 16);
                ctx.closePath(); ctx.stroke();
                if (root.name === "weather-rain") {
                    for (const x of [6, 12, 18]) { ctx.beginPath(); ctx.moveTo(x, 19); ctx.lineTo(x - 1, 22); ctx.stroke(); }
                } else if (root.name === "weather-snow") {
                    for (const x of [6, 12, 18]) { ctx.beginPath(); ctx.arc(x, 21, 0.8, 0, Math.PI * 2); ctx.fill(); }
                } else if (root.name === "weather-storm") {
                    ctx.beginPath(); ctx.moveTo(13, 17); ctx.lineTo(10, 20); ctx.lineTo(14, 20); ctx.lineTo(11, 23); ctx.stroke();
                }
            } else if (root.name === "resources") {
                ctx.beginPath(); ctx.roundedRect(6, 6, 12, 12, 2, 2); ctx.stroke();
                for (const n of [8, 12, 16]) { ctx.beginPath(); ctx.moveTo(n, 3); ctx.lineTo(n, 6); ctx.moveTo(n, 18); ctx.lineTo(n, 21); ctx.moveTo(3, n); ctx.lineTo(6, n); ctx.moveTo(18, n); ctx.lineTo(21, n); ctx.stroke(); }
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
