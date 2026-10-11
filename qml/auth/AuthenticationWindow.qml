pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../components"
import "../theme"
import "../services"

PanelWindow {
    id: root
    required property var flow
    visible: !!flow && !flow.isCompleted
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "lme-authentication"
    BackgroundEffect.blurRegion: visible && ShellState.popupBlurEnabled ? authBlurRegion : null
    Region { id: authBlurRegion; item: root.contentItem }
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    onVisibleChanged: {
        if (visible) Qt.callLater(() => { if (dialog.contentDialog) dialog.contentDialog.focusInput(); });
    }
    Rectangle { anchors.fill: parent; color: Theme.alpha(Theme.background, 0.48) }
    // Outside clicks stay on this modal surface; only Cancel/Escape cancels.
    MouseArea { anchors.fill: parent }
    SlideLoader {
        id: dialog
        readonly property AuthenticationDialog contentDialog: item as AuthenticationDialog
        shown: root.visible
        direction: "up"
        width: Math.min(480, root.width - 32)
        height: contentDialog ? contentDialog.implicitHeight : 0
        x: (root.width - width) / 2
        y: Math.max(16, (root.height - height) / 2)
        content: AuthenticationDialog { flow: root.flow }
    }
}
