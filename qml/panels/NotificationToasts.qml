// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "../components"
import "../services"
import "../theme"

PanelWindow {
    id: root
    property bool preview: false
    property var entries: ({})
    readonly property bool accepting: !preview && !ShellState.notificationsOpen && !ShellState.authenticationActive
    screen: ShellState.panelScreen || Quickshell.screens[0]
    visible: toastModel.count > 0 && !preview
    anchors { top: !Theme.barBottom; bottom: Theme.barBottom; right: true }
    margins { top: Theme.barBottom ? 0 : Theme.panelTopMargin; bottom: Theme.barBottom ? Theme.panelTopMargin : 0; right: 14 }
    implicitWidth: 360; implicitHeight: toastColumn.implicitHeight
    color: "transparent"; exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay; WlrLayershell.namespace: "lme-notifications"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region { item: root.accepting && Notifications.popups.length ? root.contentItem : null }
    ListModel { id: toastModel }
    function remove(id) {
        for (let i = 0; i < toastModel.count; i++) if (toastModel.get(i).identifier === id && !toastModel.get(i).present) {
            toastModel.remove(i);
            const next = Object.assign({}, entries); delete next[id]; entries = next;
            return;
        }
    }
    function synchronize() {
        const popups = Notifications.popups;
        const next = Object.assign({}, entries);
        for (const entry of popups) next[String(entry.id)] = entry;
        entries = next;
        for (let i = toastModel.count - 1; i >= 0; i--) {
            const id = toastModel.get(i).identifier;
            const present = popups.some(entry => String(entry.id) === id);
            if (!present && !toastRepeater.itemAt(i)?.mounted) { toastModel.remove(i); delete next[id]; }
            else toastModel.setProperty(i, "present", present);
        }
        for (const entry of [...popups].reverse()) {
            const id = String(entry.id);
            let found = false;
            for (let i = 0; i < toastModel.count; i++) if (toastModel.get(i).identifier === id) { found = true; break; }
            if (!found) toastModel.insert(0, {identifier: id, present: true});
        }
        // Bound retained exits during notification bursts to the three live cards plus three closing cards.
        while (toastModel.count > 6) { delete next[toastModel.get(6).identifier]; toastModel.remove(6); }
        entries = next;
    }
    Component.onCompleted: synchronize()
    Connections { target: Notifications; function onPopupsChanged() { root.synchronize(); } }
    Column {
        id: toastColumn
        width: root.implicitWidth; spacing: 10
        move: Transition { NumberAnimation { properties: "x,y"; duration: Theme.animationDuration; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.effectsCurve } }
        Repeater {
            id: toastRepeater
            model: toastModel
            delegate: SlideLoader {
                id: toast
                objectName: "notificationToast-" + identifier
                required property string identifier
                required property bool present
                readonly property var entry: root.entries[identifier] || ({appName: "", summary: "", body: "", actions: []})
                readonly property Item panel: item as Item
                width: toastColumn.width
                height: panel ? panel.implicitHeight : 0
                shown: present && root.accepting
                exitToEdge: true; exitEdge: "right"
                onMountedChanged: if (!mounted && !present) { const id = identifier; Qt.callLater(() => root.remove(id)); }
                content: GlassPanel {
                    role: "notificationFill"
                    implicitHeight: toastContent.implicitHeight + 32
                    MouseArea { anchors.fill: parent; enabled: !!toast.entry.imagePath; onClicked: Notifications.openImage(toast.entry.id) }
                    ColumnLayout {
                        id: toastContent
                        z: 1
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
                        spacing: 8
                        RowLayout {
                            LabelText { text: toast.entry.appName; color: Theme.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                            IconButton { glyph: "×"; tooltip: "Dismiss notification"; implicitWidth: 24; implicitHeight: 24; onClicked: Notifications.dismiss(toast.entry.id) }
                        }
                        LabelText { text: toast.entry.summary; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        LabelText { text: toast.entry.body; visible: text.length > 0; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight }
                        RowLayout {
                            LiquidButton { visible: !!toast.entry.imagePath; text: "Annotate"; onClicked: Notifications.openImage(toast.entry.id) }
                            Repeater {
                                model: toast.entry.actions || []
                                delegate: IconButton { required property var modelData; text: modelData.text; implicitWidth: Math.min(145, Math.max(80, text.length * 8)); onClicked: Notifications.invokeAction(toast.entry.id, modelData.identifier) }
                            }
                        }
                    }
                }
            }
        }
    }
}
