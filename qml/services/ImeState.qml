// Role: ImeState.qml (ime layer, fan-in 3).
// Shared component/helper; keep API stable for wide QML reuse.
pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Services.SystemTray
import "../services"

Singleton {
    id: root

    property int consumers: 0
    property string currentIM: ""
    property string lastIMLabel: ""
    property bool imInitialized: false

    readonly property bool active: consumers > 0 || ShellState.preferences.imeIndicator !== false
    readonly property var fcitxItem: findItem(SystemTray.items.values)
    readonly property bool available: fcitxItem !== null
    readonly property string trayIdentity: trayIdentityOf(fcitxItem)
    readonly property string currentIMLabel: displayName(fcitxItem ? (fcitxItem.tooltipTitle || "") : "", currentIM)

    Timer {
        id: resolveTimer
        interval: 100
        repeat: false
        onTriggered: root.resolve()
    }

    onTrayIdentityChanged: {
        if (active && available) resolveTimer.restart();
    }

    onActiveChanged: {
        if (active && available) resolveTimer.restart();
    }

    onCurrentIMLabelChanged: root.observeIM()

    Connections {
        target: ShellState
        function onLastResultChanged() {
            if (ShellState.lastResult && ShellState.lastResult.action === "inputMethod" && ShellState.lastResult.ok) {
                const name = String(ShellState.lastResult.message || "").trim();
                if (name !== "") root.currentIM = name;
            }
        }
    }

    function findItem(items) {
        return items ? items.find(item => item && item.id === "Fcitx") : null;
    }

    function trayIdentityOf(item) {
        return item ? (item.icon || "") + "\u0000" + (item.tooltipTitle || "") : "";
    }

    function displayName(tooltipTitle, rawName) {
        const title = String(tooltipTitle ?? "").trim();
        if (title === "" || title === "Input Method")
            return String(rawName ?? "");
        const separator = title.lastIndexOf(" - ");
        return separator > 0 ? title.slice(separator + 3) : title;
    }

    function observeIM() {
        const label = currentIMLabel;
        if (label === "") {
            imInitialized = false;
            lastIMLabel = "";
            return;
        }
        if (!imInitialized) {
            lastIMLabel = label;
            imInitialized = true;
            return;
        }
        if (lastIMLabel === label)
            return;
        lastIMLabel = label;
        if (ShellState.preferences.imeIndicator !== false) {
            OSDManager.show(label, 0, label);
        }
    }

    function resolve() {
        if (!active || !available)
            return;
        ShellState.run("inputMethod");
    }

    Component.onCompleted: {
        if (active && available) resolveTimer.restart();
        observeIM();
    }
}