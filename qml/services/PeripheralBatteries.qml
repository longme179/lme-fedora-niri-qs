pragma Singleton
import QtQuick

QtObject {
    // Keep low-battery latches across disconnects and backend reconnects, within this shell session.
    property var alerts: ({})

    function check(devices, enabled, threshold) {
        const next = Object.assign({}, alerts);
        const low = [];
        const limit = Math.max(5, Math.min(50, Number(threshold) || 20));
        for (const device of devices) {
            if (!device.id || device.connected === false) continue;
            const previous = next[device.id] || {warned: false};
            if (device.charging === true) previous.warned = false;
            const percent = device.percentage;
            if (typeof percent === "number" && Number.isFinite(percent) && percent >= 0 && percent <= 100) {
                if (percent > limit + 5) previous.warned = false;
                if (enabled && device.charging !== true && percent <= limit && !previous.warned) {
                    previous.warned = true;
                    low.push(device);
                }
            }
            // Refresh insertion order, so old disconnected identities cannot grow the ledger indefinitely.
            delete next[device.id];
            next[device.id] = previous;
        }
        const keys = Object.keys(next);
        for (const key of keys.slice(0, Math.max(0, keys.length - 128))) delete next[key];
        alerts = next;
        return low;
    }
}
