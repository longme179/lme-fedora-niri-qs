pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../services"
import "../theme"

ColumnLayout {
    id: root
    spacing: 12
    readonly property var state: ShellState.snapshot.mirror || ({})
    readonly property var outputs: ((ShellState.snapshot.displays || {}).outputs || []).filter(o => o.enabled)
    readonly property var targets: outputs.filter(o => o.name !== sourceName)
    readonly property bool busy: !!ShellState.pendingActions.mirrorStart || !!ShellState.pendingActions.mirrorStop
    property string sourceName: ""
    property string targetName: ""
    function refresh() {
        if (!ShellState.backendReady) return;
        if (!ShellState.pendingActions.displayRefresh) ShellState.run("displayRefresh");
        if (!ShellState.pendingActions.mirrorRefresh) ShellState.run("mirrorRefresh");
    }
    function selectAvailable() {
        const available = outputs || [];
        if (!available.some(o => o.name === sourceName)) sourceName = (available.find(o => o.name.startsWith("eDP")) || available[0] || {}).name || "";
        const destinations = available.filter(o => o.name !== sourceName);
        if (!destinations.some(o => o.name === targetName)) targetName = (destinations[0] || {}).name || "";
    }
    onOutputsChanged: selectAvailable()
    onSourceNameChanged: selectAvailable()
    onVisibleChanged: if (visible) refresh()
    Component.onCompleted: refresh()
    Connections { target: ShellState; function onBackendReadyChanged() { if (root.visible) root.refresh(); } }
    Timer { interval: 3000; repeat: true; running: root.visible; onTriggered: root.refresh() }
    LabelText { text: "Display mirroring"; font.pixelSize: 18; font.weight: Font.Bold; Layout.fillWidth: true }
    LabelText {
        text: "Mirror one active display onto another monitor or projector. The image fits without cropping; Stop restores the destination workspace."
        Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted
    }
    RowLayout {
        Layout.fillWidth: true
        LabelText { text: "Enable mirroring"; Layout.fillWidth: true }
        ExpressiveSwitch {
            checked: ShellState.preferences.mirroringEnabled !== false
            enabled: ShellState.backendReady
            Accessible.name: "Enable display mirroring"
            onToggled: ShellState.run("setting", {key: "mirroringEnabled", value: checked})
        }
    }
    LabelText { text: "Source"; font.weight: Font.Bold }
    LiquidComboBox {
        objectName: "mirrorSource"; Layout.fillWidth: true
        model: root.outputs.map(o => o.name + (o.description ? " · " + o.description : ""))
        currentIndex: root.outputs.findIndex(o => o.name === root.sourceName)
        enabled: !root.state.active && !root.busy
        Accessible.name: "Mirror source display"
        onActivated: root.sourceName = root.outputs[currentIndex].name
    }
    LabelText { text: "Destination"; font.weight: Font.Bold }
    LiquidComboBox {
        objectName: "mirrorTarget"; Layout.fillWidth: true
        model: root.targets.map(o => o.name + (o.description ? " · " + o.description : ""))
        currentIndex: root.targets.findIndex(o => o.name === root.targetName)
        enabled: !root.state.active && !root.busy
        Accessible.name: "Mirror destination display"
        onActivated: root.targetName = root.targets[currentIndex].name
    }
    LabelText {
        Layout.fillWidth: true; wrapMode: Text.Wrap
        color: root.state.error ? Theme.red : Theme.muted
        text: root.state.error || (root.state.active ? "Mirroring " + root.state.source + " → " + root.state.target
            : !root.state.available ? "Requires wl-mirror. Install it with: sudo dnf install wl-mirror"
            : root.outputs.length < 2 ? "Connect and enable a second display to start." : "Ready to present. Keep private windows off the source display.")
    }
    RowLayout {
        Layout.fillWidth: true
        LiquidButton {
            objectName: "mirrorStart"; text: root.busy ? "Please wait…" : "Start mirror"
            enabled: ShellState.backendReady && ShellState.preferences.mirroringEnabled !== false && !!root.state.available && !root.state.active && !root.busy && !!root.sourceName && !!root.targetName
            onClicked: { ShellState.run("mirrorStart", {source: root.sourceName, target: root.targetName}); root.refresh(); }
        }
        LiquidButton {
            objectName: "mirrorStop"; text: "Stop mirror"
            enabled: !!root.state.active && !root.busy
            onClicked: { ShellState.run("mirrorStop"); root.refresh(); }
        }
    }
    LabelText {
        text: "Notification popups follow your existing ‘Do not disturb while sharing’ preference. This shares the entire source display, including shell panels."
        Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.muted; font.pixelSize: 12
    }
}
