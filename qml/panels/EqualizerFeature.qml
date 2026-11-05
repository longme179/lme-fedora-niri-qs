pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import "../components"
import "../services"
import "../theme"

Scope {
    id: root
    EqualizerPopup { id: popup }
    property bool open: false

    Connections {
        target: ShellState
        function onEqualizerPopupOpenChanged() {
            if (ShellState.equalizerPopupOpen)
                popup.open();
            else
                popup.close();
        }
    }

    Component.onCompleted: {
        if (ShellState.equalizerPopupOpen)
            popup.open();
    }
}