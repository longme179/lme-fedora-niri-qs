pragma Singleton
import QtQuick
import QtQml.Models
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    property bool settled: false
    property string error: ""
    readonly property bool ready: settled
    property var records: []
    onRecordsChanged: if (records.length) validate(ShellState.snapshot.catalogValidation)
    property var descriptors: ({})
    property bool verified: false
    property var data: ({bar: [], settingsPage: [], controlTab: [], all: {}, ids: {}, preferences: {}})
    function fail(message) {
        if (error) return;
        error = "Feature catalog: " + message;
        data = {bar: [], settingsPage: [], controlTab: [], all: {}, ids: {}, preferences: {}};
        settled = true;
        console.warn(error);
        ShellState.statusMessage = error;
        ShellState.statusError = true;
    }
    function validate(verdict) {
        if (!verdict || settled && error) return;
        if (verdict.error) fail(verdict.error);
        else verified = true;
    }
    function acceptDescriptor(index, value) {
        if (settled || error) return;
        try {
            if (!value || value.id !== records[index].id) throw new Error("Invalid descriptor identity");
            descriptors[index] = value;
            if (Object.keys(descriptors).length !== records.length) return;
            const result = {bar: [], settingsPage: [], controlTab: [], all: {bar: [], settingsPage: [], controlTab: []}, ids: {features: [], bar: [], settingsPage: [], controlTab: []}, preferences: {}};
            records.forEach((record, position) => {
                const descriptor = descriptors[position];
                result.ids.features.push(record.id);
                Object.assign(result.preferences, descriptor.preferences || {});
                for (const kind of ["bar", "settingsPage", "controlTab"]) {
                    const item = descriptor[kind];
                    if (!item) continue;
                    const key = kind === "settingsPage" ? "key" : "id";
                    if (typeof item[key] !== "string" || typeof item.entry !== "string") throw new Error("Invalid presentation entry");
                    result.ids[kind].push(item[key]);
                    result.all[kind].push(Object.assign({}, item, {enabled: record.enabled}));
                    if (record.enabled) result[kind].push(item);
                }
            });
            data = result; settled = true;
        } catch (exception) { fail(String(exception)); }
    }
    function project(kind, legacy, key, includeDisabled = false) {
        const all = data.all[kind] || [];
        const duplicate = all.find(entry => legacy.some(item => item[key] === entry[key]));
        if (duplicate) {
            // Defer publication so a registry binding never mutates its own input.
            Qt.callLater(() => root.fail("Duplicate " + kind + " ID in legacy: " + duplicate[key]));
            return legacy;
        }
        const entries = includeDisabled ? all : data[kind] || [];
        if (!entries.length || error) return legacy;
        const max = kind === "controlTab" ? Math.max(-1, ...legacy.map(item => item.legacyIndex)) : -1;
        return legacy.concat(entries.map(entry => kind === "controlTab"
            ? Object.assign({}, entry, {legacyIndex: max + 1 + all.findIndex(item => item[key] === entry[key])}) : entry));
    }
    function url(entry) { return entry ? Qt.resolvedUrl(Quickshell.shellPath(entry)) : ""; }
    property FileView indexFile: FileView {
        path: Quickshell.shellPath("config/features.json")
        onLoaded: {
            if (root.settled) return;
            try {
                const value = JSON.parse(text());
                if (value.version !== 1 || !Array.isArray(value.features)) throw new Error("Unsupported version or index");
                for (const item of value.features)
                    if (!item || typeof item.id !== "string" || typeof item.descriptor !== "string" || typeof item.enabled !== "boolean") throw new Error("Invalid index record");
                root.records = value.features;
                if (!root.records.length) root.settled = true;
            } catch (exception) { root.fail(String(exception)); }
        }
        onLoadFailed: root.fail("Index could not be read")
    }
    property Instantiator files: Instantiator {
        model: root.verified && !root.error ? root.records : []
        delegate: FileView {
            required property int index
            required property var modelData
            path: Quickshell.shellPath(modelData.descriptor)
            onLoaded: {
                try { root.acceptDescriptor(index, JSON.parse(text())); }
                catch (exception) { root.fail(String(exception)); }
            }
            onLoadFailed: root.fail("Descriptor could not be read")
        }
    }
    property Timer deadline: Timer {
        interval: 3000; running: !root.settled
        onTriggered: root.fail("Read or validation timed out; using legacy entries")
    }
}
