pragma ComponentBehavior: Bound
import QtQuick
import "../services"
import "../theme"
Row {
    id: root
    spacing: 2; height: 30
    function primaryAction() { return false; }
    visible: ShellState.preferences.privacyIndicators !== false && PrivacyState.indicators.length > 0
    Repeater {
        model: parent.visible ? PrivacyState.indicators : []
        delegate: IconButton {
            required property var modelData
            implicitWidth: 30; implicitHeight: 30; iconName: modelData.icon; active: true; accentColor: Theme.green
            tooltip: modelData.title + (PrivacyState.captures.filter(c => c.kind===modelData.kind).length ? " · " + PrivacyState.captures.filter(c => c.kind===modelData.kind).map(c => c.name).join(", ") : "")
            onClicked: if (!root.primaryAction()) ShellState.togglePanel("control")
        }
    }
}
