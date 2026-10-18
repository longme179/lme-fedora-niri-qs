pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../components"
import "../services"

PanelWindow {
    id: root
    required property var flow
    readonly property bool pending: !!flow && !flow.isCompleted
    visible: dialog.mounted
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "lme-authentication"
    BackgroundEffect.blurRegion: !visible ? null : ShellState.liquidBlurEnabled ? glassBlur : ShellState.popupBlurEnabled ? authBlurRegion : null
    Region { id: authBlurRegion; item: root.contentItem }
    SurfaceBlurRegion { id: glassBlur; surface: dialog.contentDialog }
    mask: Region { item: root.pending ? root.contentItem : null }
    WlrLayershell.keyboardFocus: pending ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    onPendingChanged: {
        if (pending) Qt.callLater(() => { if (dialog.contentDialog) dialog.contentDialog.focusInput(); });
    }
    PopupBackdrop { anchors.fill: parent; shown: root.pending; strength: .48 }
    // Outside clicks stay on this modal surface; only Cancel/Escape cancels.
    MouseArea { anchors.fill: parent }
    Item {
        width: (root.screen || Quickshell.screens[0]).width
        height: (root.screen || Quickshell.screens[0]).height
        SlideLoader {
                id: dialog
                readonly property AuthenticationDialog contentDialog: item as AuthenticationDialog
                shown: root.pending
                exitToEdge: true
                direction: "up"
                width: Math.min(480, parent.width - 32)
                height: contentDialog ? contentDialog.implicitHeight : 0
                x: (parent.width - width) / 2
                y: Math.max(16, (parent.height - height) / 2)
                content: AuthenticationDialog { flow: root.flow }
        }
    }
}
