// SPDX-License-Identifier: GPL-3.0-or-later
pragma ComponentBehavior: Bound
import QtQuick
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
    readonly property string position: ShellState.preferences.notificationPosition === "bar" || !ShellState.preferences.notificationPosition
        ? (Theme.barBottom ? "bottom-right" : "top-right") : ShellState.preferences.notificationPosition
    readonly property real edgeMargin: Theme.notificationMargin
    readonly property real barMargin: Theme.panelTopMargin + Math.max(0, edgeMargin - 14)
    readonly property real availableHeight: Math.max(160, (screen?.height || 1080) - barMargin - edgeMargin)
    screen: ShellState.panelScreen || Quickshell.screens[0]
    visible: toastModel.count > 0 && !preview
    anchors { top: position.startsWith("top"); bottom: position.startsWith("bottom"); left: position.endsWith("left"); right: position.endsWith("right") }
    margins { top: Theme.barBottom ? edgeMargin : barMargin; bottom: Theme.barBottom ? barMargin : edgeMargin; left: edgeMargin; right: edgeMargin }
    implicitWidth: Math.min(Theme.notificationWidth, Math.max(160, (screen?.width || 1920) - edgeMargin * 2))
    implicitHeight: Math.min(availableHeight, toastColumn.implicitHeight)
    color: "transparent"; exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay; WlrLayershell.namespace: "lme-notifications"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    BackgroundEffect.blurRegion: visible && ShellState.liquidBlurEnabled ? glassBlur : null
    Region { id: glassBlur; regions: GlassState.popupsFor(root) }
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
                readonly property Region glassBlurRegion: SurfaceBlurRegion { surface: toast.panel; popup: true }
                width: toastColumn.width
                height: panel ? panel.implicitHeight : 0
                // Shared height limits must take effect together when another card arrives.
                animateResize: toastModel.count === 1
                shown: present && root.accepting
                exitToEdge: true
                exitEdge: root.position.endsWith("left") ? "left" : root.position.endsWith("right") ? "right" : root.position.startsWith("top") ? "top" : "bottom"
                onMountedChanged: if (!mounted && !present) { const id = identifier; Qt.callLater(() => root.remove(id)); }
                content: NotificationCard {
                    entry: toast.entry
                    maximumHeight: Math.max(1, (root.availableHeight - (toastModel.count - 1) * toastColumn.spacing) / Math.max(1, toastModel.count))
                    animateIdle: toast.shown
                    onDismissRequested: Notifications.dismiss(toast.entry.id)
                    onAnnotateRequested: Notifications.openImage(toast.entry.id)
                    onActionRequested: identifier => Notifications.invokeAction(toast.entry.id, identifier)
                }
            }
        }
    }
}
