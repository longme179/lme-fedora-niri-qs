pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../components"
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 20
    readonly property var displays: ShellState.snapshot.displays || {outputs: [], preview: {}}
    readonly property var outputs: displays.outputs || []
    readonly property var preview: displays.preview || {}
    property var drafts: []
    property bool dirty: false
    property string selectedName: ""
    property real now: Date.now()
    readonly property bool testing: ["applying", "pending", "reverting"].includes(preview.status)
    readonly property var selected: drafts.find(d => d.name === selectedName) || drafts[0] || null
    readonly property var output: outputs.find(o => selected && o.name === selected.name) || null
    readonly property real minX: Math.min(0, ...drafts.map(d => d.x))
    readonly property real minY: Math.min(0, ...drafts.map(d => d.y))
    readonly property real spanX: Math.max(1, ...drafts.map(d => d.x + d.width / d.scale)) - minX
    readonly property real spanY: Math.max(1, ...drafts.map(d => d.y + d.height / d.scale)) - minY
    function resetDrafts() {
        drafts = outputs.filter(o => o.enabled && o.current).map(o => ({name: o.name, width: o.current.width, height: o.current.height, refresh: o.current.refresh, scale: o.scale, x: o.x, y: o.y}));
        dirty = false;
        if (!drafts.some(d => d.name === selectedName)) selectedName = drafts.length ? drafts[0].name : "";
    }
    function patch(values) {
        if (!selected || testing) return;
        drafts = drafts.map(d => d.name === selected.name ? Object.assign({}, d, values) : d);
        dirty = true;
    }
    Component.onCompleted: if (ShellState.backendReady) ShellState.run("displayRefresh")
    Connections {
        target: ShellState
        function onBackendReadyChanged() { if (ShellState.backendReady) ShellState.run("displayRefresh"); }
        function onSnapshotChanged() { if (!root.dirty && root.outputs.length) root.resetDrafts(); }
        function onLastResultChanged() {
            if (ShellState.lastResult && ShellState.lastResult.ok && ShellState.lastResult.action === "displayConfirm") root.dirty = false;
        }
    }
    Timer { interval: 3000; repeat: true; running: root.visible; onTriggered: { root.now = Date.now(); if (ShellState.backendReady && !ShellState.pendingActions.displayRefresh) ShellState.run("displayRefresh"); } }
    SettingsCard {
        title: "Arrange displays"
        description: "Select a display, drag it into place, or enter exact coordinates. Changes are tested before they are saved."
        Rectangle {
            id: arrangement
            Layout.fillWidth: true; Layout.preferredHeight: 210; radius: 20; color: Theme.background; clip: true
            readonly property real factor: Math.min((width - 32) / root.spanX, (height - 32) / root.spanY)
            Repeater {
                model: root.drafts
                delegate: Rectangle {
                    id: monitor
                    required property var modelData
                    objectName: "displayMonitor-" + modelData.name
                    x: 16 + (modelData.x - root.minX) * arrangement.factor
                    y: 16 + (modelData.y - root.minY) * arrangement.factor
                    width: modelData.width / modelData.scale * arrangement.factor
                    height: modelData.height / modelData.scale * arrangement.factor
                    radius: 10; color: root.selectedName === modelData.name ? Theme.primaryContainer : Theme.surface
                    border.width: 2; border.color: root.selectedName === modelData.name ? Theme.accent : Theme.border
                    LabelText { anchors.centerIn: parent; width: parent.width - 12; text: monitor.modelData.name; font.weight: Font.Bold; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter }
                    MouseArea {
                        anchors.fill: parent; enabled: !root.testing; drag.target: monitor
                        onPressed: root.selectedName = monitor.modelData.name
                        onReleased: {
                            root.patch({x: Math.round((monitor.x - 16) / arrangement.factor + root.minX), y: Math.round((monitor.y - 16) / arrangement.factor + root.minY)});
                            monitor.x = Qt.binding(() => 16 + (monitor.modelData.x - root.minX) * arrangement.factor);
                            monitor.y = Qt.binding(() => 16 + (monitor.modelData.y - root.minY) * arrangement.factor);
                        }
                    }
                }
            }
            LabelText { anchors.centerIn: parent; visible: !root.drafts.length; text: ShellState.demo ? "Loading demo displays…" : "No active niri displays"; color: Theme.muted }
        }
        LiquidComboBox { Layout.fillWidth: true; model: root.drafts.map(d => d.name); currentIndex: Math.max(0, root.drafts.findIndex(d => d.name === root.selectedName)); Accessible.name: "Display"; onActivated: root.selectedName = root.drafts[currentIndex].name }
        LabelText { text: root.output ? root.output.description : "Open Settings inside a niri session."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted }
    }
    SettingsCard {
        visible: !!root.selected
        title: "Resolution and scale"
        LiquidComboBox {
            objectName: "displayMode"
            Layout.fillWidth: true; model: root.output ? root.output.modes.map(m => m.label) : []
            currentIndex: root.output && root.selected ? root.output.modes.findIndex(m => m.width === root.selected.width && m.height === root.selected.height && m.refresh === root.selected.refresh) : -1
            enabled: !root.testing; Accessible.name: "Resolution and refresh rate"
            onActivated: { const mode = root.output.modes[currentIndex]; root.patch({width: mode.width, height: mode.height, refresh: mode.refresh}); }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "Scale"; Layout.fillWidth: true }
            LiquidComboBox { property var scales: [.5, .75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3]; model: scales.map(v => Math.round(v * 100) + "%"); currentIndex: root.selected ? scales.indexOf(root.selected.scale) : -1; enabled: !root.testing; Accessible.name: "Display scale"; onActivated: root.patch({scale: scales[currentIndex]}) }
        }
        RowLayout {
            Layout.fillWidth: true
            LabelText { text: "X" }
            ExpressiveField { Layout.fillWidth: true; text: root.selected ? String(root.selected.x) : "0"; validator: IntValidator { bottom: -32768; top: 32768 } enabled: !root.testing; Accessible.name: "Display X position"; onEditingFinished: if (acceptableInput) root.patch({x: Number(text)}) }
            LabelText { text: "Y" }
            ExpressiveField { Layout.fillWidth: true; text: root.selected ? String(root.selected.y) : "0"; validator: IntValidator { bottom: -32768; top: 32768 } enabled: !root.testing; Accessible.name: "Display Y position"; onEditingFinished: if (acceptableInput) root.patch({y: Number(text)}) }
        }
        RowLayout {
            LiquidButton { text: "Apply & test"; enabled: root.dirty && !root.testing && ShellState.backendReady; onClicked: ShellState.run("displayApply", {layout: root.drafts}) }
            LiquidButton { text: "Discard edits"; enabled: root.dirty && !root.testing; onClicked: root.resetDrafts() }
        }
    }
    SettingsCard {
        visible: root.testing || !!root.preview.error || root.preview.status === "reverted"
        title: root.preview.status === "pending" ? "Keep this layout?" : root.preview.status === "reverted" ? "Previous layout restored" : "Display preview"
        LabelText { Layout.fillWidth: true; wrapMode: Text.Wrap; color: root.preview.error ? Theme.red : Theme.muted; text: root.preview.error || (root.preview.status === "pending" ? "Automatically reverts in " + Math.max(0, Math.ceil(root.preview.deadline - root.now / 1000)) + " seconds, even if Settings closes." : "The independent preview timer protects your previous configuration.") }
        RowLayout {
            visible: root.preview.status === "pending"
            LiquidButton { text: "Keep changes"; onClicked: ShellState.run("displayConfirm", {token: root.preview.token}) }
            LiquidButton { text: "Revert now"; onClicked: { ShellState.run("displayRevert", {token: root.preview.token}); root.dirty = false; } }
        }
    }
}
