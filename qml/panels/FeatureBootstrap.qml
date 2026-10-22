pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import QtQml.Models
import "../services"

Instantiator {
    readonly property string context: ShellState.settingsApp ? "settings"
        : Quickshell.env("LME_SHELL_PREVIEW") === "1" ? "preview" : ShellState.demo ? "demo" : "live-main"
    active: FeatureCatalog.ready && !FeatureCatalog.error
    model: (FeatureCatalog.data.bootstrap || []).filter(entry => (entry.contexts || ["live-main"]).includes(context))
    delegate: Loader {
        required property var modelData
        source: FeatureCatalog.url(modelData.entry)
    }
}
