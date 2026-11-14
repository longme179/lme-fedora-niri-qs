// Role: UndoToast.qml (shared layer) — the bottom-center toast window hosting UndoCard
// while an undo offer is pending. One offer at a time (a newer act settles the last).
// REL: qml/services/UndoState.qml; qml/components/UndoCard.qml. Mounted by shell.qml.
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import "../components"
import "../services"
import "../theme"

PanelWindow {
    id: root
    screen: ShellState.panelScreen || Quickshell.screens[0]
    visible: transition.mounted && !ShellState.authenticationActive
    anchors { bottom: true }
    margins { bottom: Theme.panelTopMargin + 16 }
    implicitWidth: transition.item ? transition.item.implicitWidth : 0
    implicitHeight: transition.item ? transition.item.implicitHeight : 0
    color: "transparent"; exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay; WlrLayershell.namespace: "lme-undo"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region { item: transition.mounted && UndoState.pending ? transition.item : null }
    SlideLoader {
        id: transition
        anchors.centerIn: parent
        shown: UndoState.pending
        direction: "up"
        exitToEdge: true
        exitEdge: "bottom"
        content: UndoCard {}
    }
}
