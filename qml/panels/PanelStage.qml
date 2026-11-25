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

    // Startup prewarm: after the first real panel settles (shell.qml's stage timer
    // mounts `control` shortly after login), build every other openable panel in the
    // background — one per 350 ms tick, paused whenever a panel or the island is
    // open — so the first click on any panel is a warm switch, not a cold build.
    // The queue is snapshotted late (gate settles before the walk starts) so a
    // catalog feature that publishes after startup is still included.
    Timer {
        interval: 6000; repeat: false
        // Binding on the entries object never re-evaluated (var-object assignment
        // emits no change signal), so this prewarm never fired after login: every
        // panel built synchronously on first open (wifi 282 ms, control 199 ms...).
        // pageCount is a plain int property and notifies normally.
        running: root.pageCount > 0
        onTriggered: root.prewarm(() => {
            const kinds = ["launchpad", "launcher", "power", "overview", "tray", "wifi"]
                .concat((FeatureCatalog.data.panel || []).map(entry => entry.id));
            return kinds.filter((kind, index) => kinds.indexOf(kind) === index);
        }, () => !ShellState.panelOpen && !ShellState.activityOpen)
    }

    Component { id: launchpadComponent; LaunchpadPanel {} }
    Component { id: launcherComponent; Launcher {} }
    Component { id: controlComponent; ControlCenter {} }
    Component { id: settingsComponent; SettingsPanel {} }
    Component { id: powerComponent; PowerMenu {} }
    Component { id: trayComponent; TrayMenu { windowInfo: root.windowInfo } }
    Component { id: overviewComponent; Overview {} }
    Component { id: wifiComponent; WifiPanel {} }
}
