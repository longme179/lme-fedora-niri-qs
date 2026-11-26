// SPDX-License-Identifier: AGPL-3.0-or-later
// PERF HARNESS — reference client (started by scripts/perf/run.py; never installed).
// A second, independent Wayland client that animates all the time and logs every frame it
// gets. For each stall of the shell it answers one question: did the WHOLE screen stop
// (compositor or GPU: this client loses frames too) or only the shell's GUI thread (this
// client keeps its cadence)? One small layer surface at the bottom right, no layout
// footprint, click-through; it goes away with the run.
//
// Output, one line per frame on stdout:  F <epoch ms> <performance.now()>
//@ pragma Env QS_NO_RELOAD_POPUP=1
import QtQuick
import QtQuick.Window
import Quickshell

ShellRoot {
    id: root

    // run.py ends this client with the run. Should run.py die, it leaves by itself.
    readonly property int lifeSeconds: Math.max(120, parseInt(Quickshell.env("LME_PERF_REF_SECONDS") || "1200"))

    Timer {
        interval: root.lifeSeconds * 1000
        running: true
        onTriggered: Qt.quit()
    }

    PanelWindow {
        id: win
        screen: Quickshell.screens[0]
        anchors { bottom: true; right: true }
        implicitWidth: 132
        implicitHeight: 40
        exclusiveZone: ExclusionMode.Ignore
        color: "transparent"
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.namespace: "lme-perf-ref"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        mask: Region {} // empty input region: every click falls through to what is below
        Rectangle {
            id: plate
            anchors.fill: parent
            radius: 10
            color: "#d0141622"
            Text {
                id: label
                anchors.centerIn: parent
                color: "#7fd0ff"
                font.pixelSize: 13
                text: "perf ref 0"
            }
            RotationAnimation on rotation { from: 0; to: 360; duration: 6000; loops: Animation.Infinite; running: true }
        }
        Item {
            // Quickshell's window type carries no frame signal (see SettingsView.qml): the
            // attached Window.window is the QQuickWindow, which has frameSwapped.
            readonly property var frameWindow: Window.window
            property int frames: 0
            Connections {
                target: frameWindow
                function onFrameSwapped() {
                    frames++
                    label.text = "perf ref " + frames
                    const hires = typeof performance !== "undefined" && typeof performance.now === "function"
                    console.log("F " + Date.now() + " " + (hires ? performance.now() : 0))
                }
            }
        }
    }
}
