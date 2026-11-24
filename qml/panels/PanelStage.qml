// SPDX-License-Identifier: AGPL-3.0-or-later
// Role: PanelStage.qml (host layer) — the retained overlay-panel stack and legacy panel map.
// REL: shell.qml – panelLoader content; qml/components/PageHost.qml – retention/LRU.
pragma ComponentBehavior: Bound
import QtQuick
import "../components"
import "../services"
import "../theme"

PageHost {
    id: root
    property var windowInfo: null
    animate: false
    // Keep every visited panel built; switching back is the next frame (RAM cap lifted 2026-11-24).
    maxPages: 0
    implicitWidth: item ? (item as Item).implicitWidth : 0
    implicitHeight: item ? (item as Item).implicitHeight : 0
    key: ShellState.panelKind
    readonly property var legacy: ({launchpad: launchpadComponent, launcher: launcherComponent, control: controlComponent, wifi: wifiComponent,
        settings: settingsComponent, tray: trayComponent, overview: overviewComponent, power: powerComponent})
    resolve: kind => FeatureCatalog.panel(kind) ? FeatureCatalog.component(FeatureCatalog.panel(kind).entry) : legacy[kind] || powerComponent

    Component { id: launchpadComponent; LaunchpadPanel {} }
    Component { id: launcherComponent; Launcher {} }
    Component { id: controlComponent; ControlCenter {} }
    Component { id: settingsComponent; SettingsPanel {} }
    Component { id: powerComponent; PowerMenu {} }
    Component { id: trayComponent; TrayMenu { windowInfo: root.windowInfo } }
    Component { id: overviewComponent; Overview {} }
    Component { id: wifiComponent; WifiPanel {} }
}
