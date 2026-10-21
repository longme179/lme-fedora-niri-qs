pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
    id: root
    property bool settled: false
    property string error: ""
    readonly property bool ready: settled && !error
    property var data: ({bar: [], settingsPage: [], controlTab: [], all: {}, ids: {}, preferences: {}})
    function fail(message) {
        if (error) return;
        error = "Feature catalog: " + message;
        console.warn(error);
        ShellState.statusMessage = error;
        ShellState.statusError = true;
    }
    function project(kind, legacy, key, includeDisabled = false) {
        const all = data.all[kind] || [];
        const duplicate = all.find(entry => legacy.some(item => item[key] === entry[key]));
        if (duplicate) { fail("Duplicate " + kind + " ID in legacy: " + duplicate[key]); return legacy; }
        const entries = includeDisabled ? all : data[kind] || [];
        if (!entries.length || error) return legacy;
        const max = kind === "controlTab" ? Math.max(-1, ...legacy.map(item => item.legacyIndex)) : -1;
        return legacy.concat(entries.map(entry => kind === "controlTab"
            ? Object.assign({}, entry, {legacyIndex: max + 1 + all.findIndex(item => item[key] === entry[key])}) : entry));
    }
    function url(entry) { return entry ? Qt.resolvedUrl(Quickshell.shellPath(entry)) : ""; }
    property Process reader: Process {
        command: ["python3", Quickshell.shellPath("scripts/feature_catalog.py")]
        running: true
        property bool received: false
        stdout: SplitParser {
            onRead: line => {
                try {
                    const value = JSON.parse(line);
                    if (value.version !== 1 || !value.all || !value.ids) throw new Error("Invalid reader result");
                    root.data = value; root.reader.received = true;
                } catch (exception) { root.fail(String(exception)); }
            }
        }
        stderr: SplitParser { onRead: line => root.fail(line.replace(/^Feature catalog: /, "")) }
        onExited: exitCode => {
            if (exitCode || !received) root.fail("Reader failed (" + exitCode + ")");
            root.settled = true;
        }
    }
}
