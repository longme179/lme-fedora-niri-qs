pragma ComponentBehavior: Bound
import QtQuick
import QtQml.Models
import "../services"

Instantiator {
    active: !ShellState.demo && !ShellState.settingsApp && FeatureCatalog.ready && !FeatureCatalog.error
    model: FeatureCatalog.data.bootstrap || []
    delegate: Loader {
        required property var modelData
        source: FeatureCatalog.url(modelData.entry)
    }
}
