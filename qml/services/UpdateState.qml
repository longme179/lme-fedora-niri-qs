// SPDX-License-Identifier: GPL-3.0-or-later
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    property var state: ({stage:"idle", message:"Open this page to inspect the Git checkout."})
    property string statePath: ""
    property bool ready: false
    readonly property bool busy: request.running || ["checking", "updating"].includes(state.stage)
    function accept(line) {
        try {
            const value = JSON.parse(line);
            if (!value.stage || !value.message) return;
            state = value; ready = true;
            if (value.statePath) statePath = value.statePath;
        } catch (error) { console.warn("Invalid updater status"); }
    }
    function run(action) {
        if (ShellState.demo || request.running || !["inspect", "check", "update"].includes(action)) return;
        if (action !== "inspect" && busy) return;
        request.command = ["python3", Quickshell.shellPath("scripts/shell_update.py"), action];
        request.running = true;
    }
    Component.onCompleted: {
        if (ShellState.demo) { state = {stage:"demo", message:"Updates are disabled in demo mode."}; ready = true; }
        else run("inspect");
    }
    Process {
        id: request
        stdout: SplitParser { onRead: line => root.accept(line) }
        onExited: code => {
            if (code !== 0) { root.state = {stage:"error", message:"The updater could not start. Check the shell log."}; root.ready = true; }
        }
    }
    FileView {
        id: status; path: root.statePath
        watchChanges: true; printErrors: false
        onFileChanged: reload()
        onLoaded: root.accept(text())
    }
    // No idle polling; recover interrupted workers while an operation is active.
    Timer { interval:1000; running:root.busy && !ShellState.demo; repeat:true; onTriggered:root.run("inspect") }
}
