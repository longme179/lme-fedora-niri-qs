pragma ComponentBehavior: Bound
import QtQuick
import "../services"

// Local page-to-host navigation bridge; connects navigateRequested(pageId) without a global bus.
// REL: qml/settings/SettingsView.qml, qml/settings/SettingsApplication.qml – host handles page IDs.
// INVARIANT: Settings page IDs are shared across standalone/inline hosts; keep IDs/catalog in sync.
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
