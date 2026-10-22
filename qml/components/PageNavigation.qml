pragma ComponentBehavior: Bound
import QtQuick
import "../services"

// A local page-to-host connection; standalone and inline Settings share IDs.
QtObject {
    id: navigation
    property var target: null
    signal requested(string pageId)
    property Connections connection: Connections {
        target: navigation.target
        ignoreUnknownSignals: true
        function onNavigateRequested(pageId) {
            if (ShellState.settingsPageAvailable(pageId)) navigation.requested(pageId);
        }
    }
}
