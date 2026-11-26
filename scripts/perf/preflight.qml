// SPDX-License-Identifier: AGPL-3.0-or-later
// PERF HARNESS — parse check of a probe tree before it is allowed to replace the session's shell.
// Started by scripts/perf/run.py as
//   LME_PERF_TREE=<tree> quickshell -p scripts/perf/preflight.qml
// Creates no window and instantiates nothing: every .qml file of the tree is handed to
// Qt.createComponent (parse and compile only). One `PREFLIGHT ERROR <file>: <reason>` line per
// broken file, then `PREFLIGHT OK <n> files` or `PREFLIGHT ERROR <n> files`. A parse check: a
// property that only fails at run time is not caught here, the probe log of the first swap is.
//@ pragma Env QS_NO_RELOAD_POPUP=1
import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root

    readonly property string tree: Quickshell.env("LME_PERF_TREE")
    property int total: 0
    property var failures: []
    property var components: []

    // The exit signal can come before the last lines were parsed: finish a moment later.
    property Timer settle: Timer {
        interval: 400
        onTriggered: root.finish()
    }

    Process {
        running: true
        command: ["find", root.tree, "-name", "*.qml", "-not", "-path", "*/.git/*"]
        stdout: SplitParser { onRead: data => root.check(data) }
        onExited: root.settle.restart()
    }

    function check(path) {
        if (!path)
            return
        total++
        const component = Qt.createComponent("file://" + path)
        // Kept for the life of this process: nothing of a probe tree is ever created here,
        // but a component that is released at once would not prove anything.
        components.push(path)
        if (component.status === Component.Error)
            failures.push(path.slice(root.tree.length + 1) + ": " + component.errorString())
    }

    function finish() {
        for (let i = 0; i < failures.length; i++)
            console.log("PREFLIGHT ERROR " + failures[i])
        console.log((failures.length ? "PREFLIGHT ERROR " : "PREFLIGHT OK ") + total + " files")
        Qt.quit()
    }
}
