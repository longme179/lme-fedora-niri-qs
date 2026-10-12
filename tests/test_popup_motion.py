"""Native popup lifecycle, backdrop and morph stroke regressions."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


@unittest.skipUnless(os.environ.get("LME_TEST_MOTION_UI") == "1", "opt-in private Wayland popup checks")
class PopupMotionCase(unittest.TestCase):
    def test_nearest_edge_close_reverse_backdrop_and_stroke(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("qml", "scripts", "config"):
                (root / name).symlink_to(repo / name, target_is_directory=True)
            entry = root / "shell.qml"
            entry.write_text("""//@ pragma UseQApplication
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "qml/components"
import "qml/panels"
import "qml/services"
import "qml/theme"
ShellRoot {
    id: fixture
    property var lastExit: ({})
    Component.onCompleted: Quickshell.watchFiles = false
    OSDWindow { id: osd; screenInfo: Quickshell.screens[0] }
    FloatingWindow {
        id: window; fullscreen: true; color: Theme.background
        PopupBackdrop { id: backdrop; anchors.fill: parent; shown: popup.shown || island.expanded }
        SlideLoader { id: popup; x: 20; y: 300; width: 200; height: 180; shown: false; exitToEdge: true
            onActiveChanged: if (!active && !shown) fixture.lastExit = mapToItem(window.contentItem, 0, 0, width, height)
            content: GlassPanel {} }
        ActivityIsland { id: island }
        MorphShape { id: shape; x: 500; y: 20; width: 50; height: 50; shape: "flower"; color: "transparent"; strokeColor: "red"; strokeWidth: 2 }
    }
    IpcHandler {
        target: "popupTest"
        function state(): string {
            return JSON.stringify({ready: ShellState.backendReady, active: popup.active, shown: popup.shown, progress: popup.progress,
                dx: popup.offsetX, dy: popup.offsetY, outside: popup.outsideViewport, dim: backdrop.amount,
                lastExit: fixture.lastExit, viewportWidth: window.width, viewportHeight: window.height, deformation: Theme.deformation,
                spring: Theme.springMotion, animations: Theme.animations,
                osdVisible: osd.visible,
                islandVisible: island.visible, islandMounted: island.mounted, islandProgress: island.progress,
                islandDy: island.offsetY, bottom: Theme.barBottom});
        }
        function setOpen(open: bool): void { popup.shown = open; }
        function place(edge: string): void {
            popup.direction = edge === "top" ? "up" : edge === "bottom" ? "down" : "right";
            popup.x = edge === "left" ? 16 : edge === "right" ? window.width - popup.width - 16 : (window.width - popup.width) / 2;
            popup.y = edge === "top" ? 16 : edge === "bottom" ? window.height - popup.height - 16 : (window.height - popup.height) / 2;
        }
        function setting(key: string, value: string): void { ShellState.run("setting", {key, value: JSON.parse(value)}); }
        function activity(open: bool): void { ShellState.activityOpen = open; }
        function setOsd(open: bool): void { if (open) OSDManager.show("Volume", 42); else osd.open = false; }
        function stroke(): string {
            const data = shape.getContext("2d").getImageData(0, 0, 50, 50).data;
            let edge = 0, ink = 0;
            for (let y = 0; y < 50; y++) for (let x = 0; x < 50; x++) {
                const alpha = data[(y * 50 + x) * 4 + 3]; ink += alpha;
                if (x === 0 || y === 0 || x === 49 || y === 49) edge += alpha;
            }
            return JSON.stringify({edge, ink});
        }
    }
}""")
            env = dict(os.environ, LME_SHELL_DEMO="1", XDG_CONFIG_HOME=str(root / "user-config"),
                       XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"))
            with (root / "shell.log").open("w+") as log:
                process = subprocess.Popen(["quickshell", "-p", str(entry)], env=env, stdout=log, stderr=log)
                def ipc(method, *args):
                    reply = subprocess.run(["quickshell", "-p", str(entry), "ipc", "call", "popupTest", method, *args],
                                           env=env, capture_output=True, text=True, timeout=5)
                    if method != "state": self.assertEqual(reply.returncode, 0, reply.stderr + reply.stdout)
                    return reply.stdout.strip()
                def wait(predicate, timeout=5):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        try: state = json.loads(ipc("state"))
                        except ValueError: state = {}
                        if predicate(state): return state
                        time.sleep(.025)
                    log.seek(0)
                    self.fail("Popup did not reach the expected state: " + str(state) + "\n" + log.read())
                def setting(key, value):
                    ipc("setting", key, json.dumps(value))
                try:
                    wait(lambda s: s.get("ready"))
                    setting("motionPreset", "jelly"); setting("motionBounce", 1)
                    wait(lambda s: s["deformation"] == .09)
                    for spring in (True, False):
                        setting("springMotion", spring); wait(lambda s: s["spring"] == spring)
                        for edge in ("left", "right", "top", "bottom"):
                            with self.subTest(spring=spring, edge=edge):
                                ipc("place", edge); ipc("setOpen", "true")
                                wait(lambda s: 0 < s["dim"] < .13)
                                wait(lambda s: s["active"] and s["progress"] == 1 and s["dim"] > .12)
                                started = time.monotonic(); ipc("setOpen", "false")
                                moving = wait(lambda s: s["active"] and not s["shown"])
                                self.assertLess(moving["dx"] if edge == "left" else moving["dy"] if edge == "top" else -moving["dx"] if edge == "right" else -moving["dy"], 0)
                                self.assertGreater(moving["dim"], 0)
                                self.assertLess(moving["dim"], .13)
                                hidden = wait(lambda s: not s["active"], timeout=.7)
                                bounds = hidden["lastExit"]
                                if edge == "left": self.assertLess(bounds["right"], 0)
                                elif edge == "right": self.assertGreater(bounds["left"], hidden["viewportWidth"])
                                elif edge == "top": self.assertLess(bounds["bottom"], 0)
                                else: self.assertGreater(bounds["top"], hidden["viewportHeight"])
                                self.assertLess(time.monotonic() - started, .7, "No spring settling tail may retain the modal surface")
                                wait(lambda s: s["dim"] == 0)
                    setting("springMotion", True); wait(lambda s: s["spring"])
                    ipc("place", "right"); ipc("setOpen", "true"); wait(lambda s: s["progress"] == 1)
                    ipc("setOpen", "false"); time.sleep(.04); before = json.loads(ipc("state"))
                    ipc("setOpen", "true"); after = json.loads(ipc("state"))
                    self.assertTrue(after["active"]); self.assertGreater(after["dx"], 0, "Reopening must preserve the moving position")
                    self.assertLess(abs(after["dx"] - before["dx"]), 100)
                    wait(lambda s: s["progress"] == 1 and abs(s["dx"]) < .01)
                    # Disabling motion during an exit must release it immediately too.
                    ipc("setOpen", "false"); time.sleep(.03); setting("animations", False)
                    wait(lambda s: not s["animations"] and not s["active"] and s["dim"] == 0)
                    setting("animations", True); wait(lambda s: s["animations"])
                    ipc("setOpen", "false"); wait(lambda s: not s["active"])
                    for bottom in (False, True):
                        setting("barEdge", "bottom" if bottom else "top"); wait(lambda s: s["bottom"] == bottom)
                        ipc("activity", "true"); wait(lambda s: s["islandProgress"] == 1)
                        ipc("activity", "false")
                        moving = wait(lambda s: s["islandMounted"] and not s["shown"] and abs(s["islandDy"]) > 1)
                        self.assertGreater(moving["islandDy"] if bottom else -moving["islandDy"], 0)
                        wait(lambda s: not s["islandVisible"] and not s["islandMounted"], timeout=.7)
                    setting("osdOutput", "all")  # Demo eDP-1 differs from the private compositor's output name.
                    for position in ("top-left", "top-center", "bottom-right", "bottom-center"):
                        setting("osdPosition", position); ipc("setOsd", "true")
                        wait(lambda s: s["osdVisible"]); time.sleep(.4)
                        ipc("setOsd", "false"); wait(lambda s: not s["osdVisible"], timeout=.7)
                    ipc("setOpen", "true"); wait(lambda s: s["active"])
                    setting("animations", False); wait(lambda s: not s["animations"] and s["dim"] == .13)
                    ipc("setOpen", "false"); state = wait(lambda s: not s["active"])
                    self.assertEqual(state["dim"], 0)
                    stroke = json.loads(ipc("stroke"))
                    self.assertEqual(stroke["edge"], 0, "Canvas stroke must fit inside every edge")
                    self.assertGreater(stroke["ink"], 0, "A missing stroke must not pass the clipping check")
                    log.seek(0); output = log.read()
                    for problem in ("TypeError", "ReferenceError", "Binding loop", "Unable to assign", "Failed to load configuration", "setRunning()"):
                        self.assertNotIn(problem, output)
                finally:
                    process.terminate(); process.wait(timeout=5)
