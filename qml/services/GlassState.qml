// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick
import "../components"

QtObject {
    id: root
    property var backdrops: []
    property Component factory: Component { GlassBackdrop {} }
    function acquire(window) {
        if (!window || !window.contentItem) return null;
        let backdrop = backdrops.find(item => item.hostWindow === window);
        if (!backdrop) {
            backdrop = factory.createObject(window.contentItem, {hostWindow:window});
            if (!backdrop) return null;
            backdrops = backdrops.concat(backdrop);
        }
        backdrop.consumers++;
        return backdrop;
    }
    function release(backdrop) {
        if (!backdrop || !backdrops.includes(backdrop)) return;
        if (--backdrop.consumers > 0) return;
        backdrops = backdrops.filter(item => item !== backdrop);
        backdrop.disposed = true;
        backdrop.hostWindow = null;
        backdrop.destroy();
    }
}
