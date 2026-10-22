pragma ComponentBehavior: Bound
import QtQuick
import "../services"
import "../theme"
import "ControlGridLogic.js" as GridLogic

Item {
    id: root
    objectName: "controlGrid"
    property bool editing: false
    property Item dragLayer: root
    property Flickable viewport: null
    property var components: ({})
    readonly property var tiles: ControlRegistry.tiles
    property var draft: null
    property string movingId: ""
    property bool dragging: false
    property var proposed: null
    readonly property var saved: ShellState.preferences.controlGrid || ({columns: 4, rows: Math.max(8, ...tiles.map(tile => tile.row + 1)), tiles: []})
    readonly property var configuration: draft || saved
    readonly property int columns: configuration.columns || 4
    readonly property int rows: configuration.rows || 4
    readonly property var layout: configuration.tiles.length ? configuration.tiles : defaults
    readonly property var defaults: tiles.map(t => ({id: t.id, col: t.col, row: t.row}))
    readonly property real gap: 10
    readonly property real unitWidth: (width - gap * (columns - 1)) / columns
    readonly property real unitHeight: Theme.compact ? 82 : 90
    readonly property bool ready: ShellState.backendReady && !ShellState.pendingActions.setting
    readonly property int shownRows: editing ? rows : Math.max(0, ...layout.filter(t => shown(t.id)).map(t => t.row + 1))
    implicitHeight: shownRows * unitHeight + gap * Math.max(0, shownRows - 1)
    onSavedChanged: draft = null
    onEditingChanged: if (!editing) cancelDrag()
    Connections {
        target: ShellState
        function onLastResultChanged() {
            if (ShellState.lastResult && ShellState.lastResult.action === "setting" && !ShellState.lastResult.ok) root.draft = null;
        }
    }
    function shown(id) {
        const tile = tiles.find(t => t.id === id);
        return tile && root.components[id] !== null && (ShellState.preferences.controlLayout || []).some(m => m.id === tile.id && m.enabled);
    }
    function cancelDrag() { ghost.visible = false; movingId = ""; proposed = null; dragging = false; }
    function updateTarget() {
        const point = ghost.mapToItem(root, 0, 0);
        proposed = GridLogic.move(layout, tiles, movingId,
            Math.round(point.x / (unitWidth + gap)), Math.round(point.y / (unitHeight + gap)), columns, rows);
    }
    function reveal(item) {
        if (!viewport || !item.activeFocus || dragging) return;
        const point = item.mapToItem(viewport.contentItem, 0, 0);
        if (point.y < viewport.contentY || point.y + item.height > viewport.contentY + viewport.height)
            viewport.contentY = Math.max(0, Math.min(viewport.contentHeight - viewport.height, point.y - 8));
    }
    Timer {
        interval: 30; running: root.dragging && root.viewport !== null; repeat: true
        onTriggered: {
            const point = ghost.mapToItem(root.viewport, ghost.width / 2, ghost.height / 2);
            const delta = point.y < 40 ? -12 : point.y > root.viewport.height - 40 ? 12 : 0;
            root.viewport.contentY = Math.max(0, Math.min(root.viewport.contentHeight - root.viewport.height, root.viewport.contentY + delta));
            if (delta) root.updateTarget();
        }
    }
    function save(next, columns = root.columns, rows = root.rows) {
        if (!ready || !next) return;
        draft = {columns: columns, rows: rows, tiles: next};
        ShellState.run("setting", {key: "controlGrid", value: draft});
    }
    function reset() { save(GridLogic.pack(tiles, columns)); }
    function resize(columns, rows) {
        const next = columns === root.columns && layout.every(t => t.row < rows) ? layout : GridLogic.pack(tiles, columns);
        const needed = Math.max(4, ...next.map(t => t.row + 1));
        save(next, columns, Math.max(rows, needed));
    }
    function nudge(id, dx, dy) {
        const start = layout.find(t => t.id === id);
        for (let col = start.col + dx, row = start.row + dy; col >= 0 && col < columns && row >= 0 && row < rows; col += dx, row += dy) {
            const next = GridLogic.move(layout, tiles, id, col, row, columns, rows);
            if (next) { save(next); return; }
        }
    }
    Repeater {
        model: root.editing ? root.columns * root.rows : 0
        delegate: Rectangle {
            required property int index
            x: (index % root.columns) * (root.unitWidth + root.gap); y: Math.floor(index / root.columns) * (root.unitHeight + root.gap)
            width: root.unitWidth; height: root.unitHeight; radius: 18
            color: Theme.alpha(Theme.surface, .4)
            border.width: 1; border.color: Theme.alpha(Theme.muted, .3)
        }
    }
    Repeater {
        id: slots
        model: root.tiles.length
        delegate: Item {
            id: slot
            required property int index
            readonly property var tile: root.tiles[index]
            readonly property var position: root.layout.find(t => t.id === tile.id) || tile
            objectName: "controlTile-" + tile.id
            visible: root.shown(tile.id)
            x: position.col * (root.unitWidth + root.gap); y: position.row * (root.unitHeight + root.gap)
            width: root.unitWidth * tile.cols + root.gap * (tile.cols - 1); height: root.unitHeight
            z: activeFocus ? 2 : 0
            opacity: root.movingId === tile.id ? .25 : 1
            Behavior on x { MotionAnimation {} }
            Behavior on y { MotionAnimation {} }
            onYChanged: root.reveal(slot)
            Rectangle {
                anchors.fill: parent; anchors.margins: -2; radius: 22; color: "transparent"
                border.width: root.editing ? 1 : 0; border.color: slot.activeFocus ? Theme.accent : Theme.alpha(Theme.accent, .45)
            }
            Loader {
                anchors.fill: parent
                active: slot.visible
                sourceComponent: root.components[slot.tile.id] || null
                enabled: !root.editing
            }
            MouseArea {
                anchors.fill: parent; visible: root.editing; enabled: root.ready
                cursorShape: drag.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                preventStealing: true; drag.target: ghost; drag.threshold: 6
                onPressed: {
                    slot.forceActiveFocus(); root.movingId = slot.tile.id;
                    const point = slot.mapToItem(root.dragLayer, 0, 0);
                    ghost.x = point.x; ghost.y = point.y; ghost.width = slot.width; ghost.title = slot.tile.title;
                    ghost.visible = true; root.proposed = null;
                }
                onPositionChanged: {
                    if (!drag.active) return;
                    root.dragging = true; root.updateTarget();
                }
                onReleased: { const next = root.proposed; root.cancelDrag(); if (next) root.save(next); }
                onCanceled: root.cancelDrag()
            }
            Keys.onPressed: event => {
                if (!root.editing) return;
                const delta = ({[Qt.Key_Left]: [-1, 0], [Qt.Key_Right]: [1, 0], [Qt.Key_Up]: [0, -1], [Qt.Key_Down]: [0, 1]})[event.key];
                if (delta) { root.nudge(tile.id, delta[0], delta[1]); event.accepted = true; }
            }
            activeFocusOnTab: root.editing
            Accessible.role: root.editing ? Accessible.Button : Accessible.NoRole
            Accessible.name: root.editing ? "Move " + tile.title + ", " + tile.cols + " by 1" : ""
            Accessible.onPressAction: if (root.editing) slot.forceActiveFocus()
        }
    }
    Rectangle {
        visible: root.proposed !== null && root.movingId !== ""
        readonly property var cell: root.proposed ? root.proposed.find(t => t.id === root.movingId) : null
        readonly property var tile: root.tiles.find(t => t.id === root.movingId)
        x: cell ? cell.col * (root.unitWidth + root.gap) : 0; y: cell ? cell.row * (root.unitHeight + root.gap) : 0
        width: tile ? root.unitWidth * tile.cols + root.gap * (tile.cols - 1) : 0; height: root.unitHeight
        radius: 20; color: Theme.alpha(Theme.accent, .12); border.width: 2; border.color: Theme.accent
        z: 3
    }
    Rectangle {
        id: ghost
        parent: root.dragLayer
        visible: false; z: 100; height: root.unitHeight; radius: 20
        property string title: ""
        color: Theme.primaryContainer; border.width: 2; border.color: root.proposed ? Theme.accent : Theme.muted
        LabelText { anchors.fill: parent; anchors.margins: 10; text: ghost.title; font.weight: Font.Bold; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
    }
}
