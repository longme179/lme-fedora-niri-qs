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
    def test_real_shell_has_no_idle_ghost_and_seeds_every_fresh_surface(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('qml', 'scripts', 'config', 'assets'):
                (root / name).symlink_to(repo / name, target_is_directory=True)
            source = (repo / 'shell.qml').read_text()
            source = source.replace('id: root\n', 'id: root\n    property bool idleGhost: true\n', 1)
            source = source.replace('Component.onCompleted: ClipboardState.start()',
                'Component.onCompleted: { ClipboardState.start(); root.idleGhost = overlay.visible || activityIsland.mounted || panelLoader.mounted; }')
            source = source.replace('target: "shell"', '''target: "shell"
        function fixtureState(): string { return JSON.stringify({ready: ShellState.backendReady, ghost: root.idleGhost, visible: overlay.visible, active: panelLoader.active, progress: panelLoader.progress}); }
        function fixtureOpen(): string {
            ShellState.togglePanel("control");
            return JSON.stringify({width: overlay.screen.width, height: overlay.screen.height,
                bounds: panelLoader.mapToItem(overlay.contentItem, 0, 0, panelLoader.width, panelLoader.height)});
        }''', 1)
            entry = root / 'shell.qml'; entry.write_text(source)
            env = dict(os.environ, LME_SHELL_DEMO='1', XDG_CONFIG_HOME=str(root / 'home'),
                       XDG_STATE_HOME=str(root / 'state'), XDG_DATA_HOME=str(root / 'data'))
            with (root / 'gui.log').open('w+') as log:
                process = subprocess.Popen(['quickshell', '-p', str(entry)], env=env, stdout=log, stderr=log)
                def ipc(method):
                    return subprocess.check_output(['quickshell', '-p', str(entry), 'ipc', 'call', 'shell', method], env=env, text=True, timeout=5).strip()
                def wait(predicate):
                    deadline = time.monotonic() + 6
                    while time.monotonic() < deadline:
                        try: state = json.loads(ipc('fixtureState'))
                        except (ValueError, subprocess.CalledProcessError): state = {}
                        if predicate(state): return state
                        time.sleep(.03)
                    log.seek(0); self.fail(str(state) + '\n' + log.read())
                try:
                    state = wait(lambda s: s.get('ready'))
                    self.assertFalse(state['ghost'], 'Hidden panels must never mount during construction')
                    self.assertFalse(state['visible'])
                    media = json.loads(ipc('mediaStatus'))
                    self.assertTrue(media['demo'])
                    self.assertTrue(media['mediaWave'] and media['animations'])
                    self.assertEqual(media['player'], '')
                    self.assertFalse(media['positionSupported'] or media['lengthSupported'])
                    for _ in range(2):
                        opened = json.loads(ipc('fixtureOpen'))
                        self.assertGreater(opened['bounds']['left'], opened['width'], 'A fresh layer surface must start beyond the real output, not the unconfigured 100 px window')
                        wait(lambda s: s['progress'] == 1)
                        ipc('close'); wait(lambda s: not s['active'] and not s['visible'])
                    log.seek(0); output = log.read()
                    for problem in ('TypeError', 'ReferenceError', 'Unable to assign', 'Binding loop', 'Failed to load configuration'):
                        self.assertNotIn(problem, output)
                finally:
                    process.terminate(); process.wait(timeout=5)

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
    property var lastRetarget: ({})
    property var lastContentChange: ({})
    property var lastMenuChange: ({})
    property var lastMenuEntry: ({})
    property real islandCloseDy: 0
    property bool dimIntermediate: false
    property var rememberedToast: null
    property var lastToastClose: ({})
    property var lastCloseSample: null
    property bool reverseAtFrame: false
    property bool alternate: false
    Component.onCompleted: Quickshell.watchFiles = false
    OSDWindow { id: osd; screenInfo: Quickshell.screens[0] }
    NotificationToasts { id: toasts }
    StatusWindow { id: status }
    function toastItems(item) {
        if (!item) return [];
        let found = item.objectName.startsWith("notificationToast-") ? [item] : [];
        for (const child of item.children || []) found = found.concat(toastItems(child));
        return found;
    }
    function sampleClose() {
        if (!popup.shown && popup.mounted && !lastCloseSample && (Math.abs(popup.offsetX) > 1 || Math.abs(popup.offsetY) > 1)) {
            lastCloseSample = {dx: popup.offsetX, dy: popup.offsetY, dim: backdrop.amount, active: popup.active};
            if (reverseAtFrame) {
                reverseAtFrame = false;
                const before = popup.offsetX;
                popup.shown = true;
                lastRetarget = {before, after: popup.offsetX, active: popup.active};
            }
        }
    }
    FloatingWindow {
        id: window; fullscreen: true; color: Theme.background
        PopupBackdrop { id: backdrop; anchors.fill: parent; shown: popup.shown || island.expanded
            onAmountChanged: if (amount > 0 && amount < .13) fixture.dimIntermediate = true }
        SlideLoader { id: popup; x: 20; y: 300; width: 200; height: 180; shown: false; exitToEdge: true
            onActiveChanged: if (!active && !shown) fixture.lastExit = mapToItem(window.contentItem, 0, 0, width, height)
            onOffsetXChanged: fixture.sampleClose()
            onOffsetYChanged: fixture.sampleClose()
            content: fixture.alternate ? alternateContent : mainContent }
        ActivityIsland { id: island
            onOffsetYChanged: if (!expanded && mounted && fixture.islandCloseDy === 0 && Math.abs(offsetY) > 1) fixture.islandCloseDy = offsetY }
        MotionPopup { id: menu; x: 400; y: 320; width: 260; height: 200
            onPositionedChanged: if (positioned) fixture.lastMenuEntry = background.mapToItem(window.contentItem, 0, 0, background.width, background.height)
            background: GlassPanel {}
            contentItem: LabelText { text: "Motion menu" } }
        MorphShape { id: shape; x: 500; y: 20; width: 50; height: 50; shape: "flower"; color: "transparent"; strokeColor: "red"; strokeWidth: 2 }
    }
    Component { id: mainContent; GlassPanel {} }
    Component { id: alternateContent; GlassPanel {} }
    IpcHandler {
        target: "popupTest"
        function state(): string {
            return JSON.stringify({ready: ShellState.backendReady, active: popup.active, shown: popup.shown, progress: popup.progress,
                dx: popup.offsetX, dy: popup.offsetY, outside: popup.outsideViewport, dim: backdrop.amount,
                lastExit: fixture.lastExit, viewportWidth: window.width, viewportHeight: window.height, deformation: Theme.deformation,
                lastRetarget: fixture.lastRetarget,
                lastContentChange: fixture.lastContentChange,
                lastMenuChange: fixture.lastMenuChange, menuVisible: menu.visible, menuMounted: menu.mounted, menuProgress: menu.progress,
                lastMenuEntry: fixture.lastMenuEntry, islandCloseDy: fixture.islandCloseDy,
                dimIntermediate: fixture.dimIntermediate,
                lastCloseSample: fixture.lastCloseSample,
                toasts: fixture.toastItems(toasts.contentItem).map(t => ({id: t.identifier, mounted: t.mounted, shown: t.shown, progress: t.progress})),
                toastStable: fixture.rememberedToast && fixture.toastItems(toasts.contentItem).includes(fixture.rememberedToast),
                toastVisible: toasts.visible, toastCache: Object.keys(toasts.entries).length, lastToastClose: fixture.lastToastClose,
                statusVisible: status.visible, statusText: status.message, statusMaskEmpty: !status.mask.item,
                spring: Theme.springMotion, animations: Theme.animations,
                osdVisible: osd.visible,
                islandVisible: island.visible, islandMounted: island.mounted, islandProgress: island.progress,
                islandDy: island.offsetY, bottom: Theme.barBottom});
        }
        function setOpen(open: bool): void {
            const before = popup.offsetX, active = popup.active;
            if (open) fixture.dimIntermediate = false;
            else fixture.lastCloseSample = null;
            popup.shown = open;
            fixture.lastRetarget = {before, after: popup.offsetX, active, edge: popup.travelEdge,
                bounds: popup.mapToItem(window.contentItem, 0, 0, popup.width, popup.height)};
        }
        function place(edge: string): void {
            popup.direction = edge === "top" ? "up" : edge === "bottom" ? "down" : "right";
            popup.x = edge === "left" ? 16 : edge === "right" ? window.width - popup.width - 16 : (window.width - popup.width) / 2;
            popup.y = edge === "top" ? 16 : edge === "bottom" ? window.height - popup.height - 16 : (window.height - popup.height) / 2;
        }
        function reverse(): void { fixture.reverseAtFrame = true; fixture.lastCloseSample = null; popup.shown = false; }
        function swapContent(): void {
            const before = popup.progress;
            fixture.alternate = !fixture.alternate;
            fixture.lastContentChange = {before, after: popup.progress};
        }
        function setting(key: string, value: string): void { ShellState.run("setting", {key, value: JSON.parse(value)}); }
        function activity(open: bool): void { if (!open) fixture.islandCloseDy = 0; ShellState.activityOpen = open; }
        function setOsd(open: bool): void { if (open) OSDManager.show("Volume", 42); else osd.open = false; }
        function menuOpen(open: bool): void {
            const before = menu.progress, mounted = menu.mounted;
            if (open) menu.open(); else menu.close();
            fixture.lastMenuChange = {before, after: menu.progress, mounted,
                bounds: menu.background.mapToItem(window.contentItem, 0, 0, menu.background.width, menu.background.height)};
        }
        function toast(count: int): void {
            Notifications.history = Array.from({length: count}, (_, i) => ({id: "toast-" + i, appName: "Motion test", summary: "Toast " + i,
                body: "Notification body", actions: [{identifier: "default", text: "Open"}], active: true, popup: true, timestamp: Date.now()}));
        }
        function rememberToast(): void { fixture.rememberedToast = fixture.toastItems(toasts.contentItem)[0]; }
        function retireToasts(): void {
            Notifications.history = [];
            fixture.lastToastClose = {mounted: fixture.toastItems(toasts.contentItem).filter(t => t.mounted).length, maskEmpty: !toasts.mask.item};
        }
        function toastStorm(): void {
            for (let i = 0; i < 20; i++) Notifications.history = [{id: "burst-" + i, appName: "Motion test", summary: "Burst " + i,
                body: "", actions: [], active: true, popup: true, timestamp: Date.now()}];
        }
        function message(text: string): void { ShellState.statusMessage = text; }
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
                    ipc("setOpen", "true")
                    wait(lambda s: 0 < s["progress"] < 1)
                    ipc("swapContent")
                    changed = json.loads(ipc("state"))["lastContentChange"]
                    self.assertAlmostEqual(changed["before"], changed["after"], delta=.001, msg="Changing popup content must not restart its entrance")
                    wait(lambda s: s["progress"] == 1)
                    ipc("swapContent")
                    changed = json.loads(ipc("state"))["lastContentChange"]
                    self.assertEqual(changed, {"before": 1, "after": 1})
                    ipc("setOpen", "false"); wait(lambda s: not s["active"])
                    for spring in (True, False):
                        setting("springMotion", spring); wait(lambda s: s["spring"] == spring)
                        for edge in ("left", "right", "top", "bottom"):
                            with self.subTest(spring=spring, edge=edge):
                                ipc("place", edge); ipc("setOpen", "true")
                                entry_state = json.loads(ipc("state"))
                                bounds = entry_state["lastRetarget"]["bounds"]
                                self.assertEqual(entry_state["lastRetarget"]["edge"], ("left", "right", "top", "bottom").index(edge))
                                if edge == "left": self.assertLess(bounds["right"], 0)
                                elif edge == "right": self.assertGreater(bounds["left"], entry_state["viewportWidth"])
                                elif edge == "top": self.assertLess(bounds["bottom"], 0)
                                else: self.assertGreater(bounds["top"], entry_state["viewportHeight"])
                                wait(lambda s: s["dimIntermediate"])
                                wait(lambda s: s["active"] and s["progress"] == 1 and s["dim"] > .12)
                                started = time.monotonic(); ipc("setOpen", "false")
                                sample = wait(lambda s: s["lastCloseSample"])
                                moving = sample["lastCloseSample"]
                                self.assertTrue(moving["active"])
                                self.assertEqual(sample["lastRetarget"]["edge"], entry_state["lastRetarget"]["edge"])
                                self.assertLess(moving["dx"] if edge == "left" else moving["dy"] if edge == "top" else -moving["dx"] if edge == "right" else -moving["dy"], 0)
                                self.assertGreater(moving["dim"], 0)
                                self.assertLessEqual(moving["dim"], .13)
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
                    ipc("reverse"); after = wait(lambda s: s["lastCloseSample"] and s["shown"])
                    self.assertTrue(after["active"]); self.assertGreater(after["lastRetarget"]["before"], 0, "Reopening must preserve the moving position")
                    self.assertTrue(after["lastRetarget"]["active"])
                    self.assertAlmostEqual(after["lastRetarget"]["before"], after["lastRetarget"]["after"], delta=.001,
                                           msg="Retarget must preserve position within the same event, independent of IPC latency")
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
                        moving = wait(lambda s: abs(s["islandCloseDy"]) > 1)
                        self.assertGreater(moving["islandCloseDy"] if bottom else -moving["islandCloseDy"], 0)
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
                    setting("animations", True)
                    for spring in (True, False):
                        setting("springMotion", spring); wait(lambda s: s["spring"] == spring)
                        ipc("menuOpen", "true")
                        menu_state = wait(lambda s: bool(s["lastMenuEntry"]))
                        self.assertLess(menu_state["lastMenuEntry"]["bottom"], 0, "A menu must start above the screen, not fade in at its destination")
                        wait(lambda s: s["menuProgress"] == 1)
                        ipc("menuOpen", "false"); time.sleep(.04); ipc("menuOpen", "true")
                        changed = json.loads(ipc("state"))["lastMenuChange"]
                        self.assertTrue(changed["mounted"])
                        self.assertAlmostEqual(changed["before"], changed["after"], delta=.001)
                        wait(lambda s: s["menuProgress"] == 1)
                        ipc("menuOpen", "false"); wait(lambda s: not s["menuVisible"] and not s["menuMounted"])
                    setting("animations", False)
                    ipc("menuOpen", "true"); wait(lambda s: s["menuProgress"] == 1)
                    ipc("menuOpen", "false"); wait(lambda s: not s["menuVisible"] and not s["menuMounted"])
                    setting("animations", True); setting("springMotion", True)
                    ipc("toast", "1"); wait(lambda s: len(s["toasts"]) == 1 and s["toasts"][0]["progress"] == 1)
                    ipc("rememberToast"); ipc("toast", "2")
                    wait(lambda s: len(s["toasts"]) == 2 and all(t["progress"] == 1 for t in s["toasts"]))
                    self.assertTrue(json.loads(ipc("state"))["toastStable"], "A new toast must not recreate a card already on screen")
                    ipc("retireToasts")
                    closed = json.loads(ipc("state"))["lastToastClose"]
                    self.assertEqual(closed, {"mounted": 2, "maskEmpty": True})
                    wait(lambda s: not s["toastVisible"] and not s["toasts"] and s["toastCache"] == 0)
                    ipc("toastStorm")
                    storm = json.loads(ipc("state"))
                    self.assertLessEqual(len(storm["toasts"]), 6)
                    self.assertLessEqual(storm["toastCache"], 6)
                    ipc("retireToasts"); wait(lambda s: not s["toastVisible"] and not s["toasts"] and s["toastCache"] == 0)
                    ipc("message", "Motion status"); wait(lambda s: s["statusVisible"] and s["statusText"] == "Motion status")
                    ipc("message", ""); wait(lambda s: not s["statusVisible"])
                    self.assertEqual(json.loads(ipc("state"))["statusText"], "Motion status")
                    self.assertTrue(json.loads(ipc("state"))["statusMaskEmpty"])
                    stroke = json.loads(ipc("stroke"))
                    self.assertEqual(stroke["edge"], 0, "Canvas stroke must fit inside every edge")
                    self.assertGreater(stroke["ink"], 0, "A missing stroke must not pass the clipping check")
                    log.seek(0); output = log.read()
                    for problem in ("TypeError", "ReferenceError", "Binding loop", "Unable to assign", "Failed to load configuration", "setRunning()"):
                        self.assertNotIn(problem, output)
                finally:
                    process.terminate(); process.wait(timeout=5)
