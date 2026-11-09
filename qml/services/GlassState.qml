// SPDX-License-Identifier: GPL-3.0-or-later
// Role: GlassState.qml (shared layer, fan-in 4).
// Shared component/helper; keep API stable for wide QML reuse.
pragma Singleton
import QtQuick

QtObject {
    id: root
    property var popupRegions: []
    function watchPopup(region, enabled) {
        if (enabled && !popupRegions.includes(region)) popupRegions = [...popupRegions, region];
        else if (!enabled && popupRegions.includes(region)) popupRegions = popupRegions.filter(item => item !== region);
    }
    function popupsFor(window) { return popupRegions.filter(region => region.hostWindow === window); }
}
