// SPDX-License-Identifier: GPL-3.0-or-later
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
